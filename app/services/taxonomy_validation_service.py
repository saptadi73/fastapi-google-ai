"""Shared taxonomy identity, dependency fingerprint and final-write validation."""
from types import SimpleNamespace

from app.core.exceptions import AppError
from app.models.import_review import ImportQuestion
from app.models.taxonomy import Taxonomy, TaxonomyColumnBinding, TaxonomyTerm
from app.repositories.base import TenantRepository, record
from app.services.profiling_service import digest


def normalized(value):
    return str(value).strip().casefold()


def exact_terms(terms, value):
    key = normalized(value)
    codes = [term for term in terms if normalized(term.code) == key]
    if codes:
        return codes
    return [term for term in terms if key in {
        normalized(v) for v in (term.code, term.label, *(term.aliases or []))
    }]


async def taxonomy_context(session, tenant_id, sheet_id, config, *, lock=False):
    repo = TenantRepository(session, tenant_id)
    result = {}
    # Stable lock order across configurations that reference several taxonomies.
    columns = sorted((c for c in config.columns if c.taxonomy_id), key=lambda c: str(c.taxonomy_id))
    for column in columns:
        taxonomy = await repo.get(Taxonomy, column.taxonomy_id, lock=lock)
        if lock:
            await session.refresh(taxonomy)
        if not taxonomy.is_active or taxonomy.status != "APPROVED" or taxonomy.version != column.taxonomy_version:
            raise AppError("TAXONOMY_VERSION_STALE", "Taxonomy tidak aktif/approved atau versinya berubah.", 409)
        query = repo.query(TaxonomyColumnBinding).where(
            TaxonomyColumnBinding.source_sheet_id == str(sheet_id),
            TaxonomyColumnBinding.source_column == column.source_column)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        binding = await session.scalar(query)
        if (binding is None or binding.status != "APPROVED"
                or binding.taxonomy_id != str(column.taxonomy_id)
                or binding.taxonomy_version != column.taxonomy_version
                or binding.required != column.taxonomy_required or binding.normalization != "TRIM_CASEFOLD"):
            raise AppError("TAXONOMY_BINDING_REQUIRED", "Mapping taxonomy harus sesuai binding approved tab/kolom.", 409)
        terms = (await session.scalars(repo.query(TaxonomyTerm).where(
            TaxonomyTerm.taxonomy_id == taxonomy.id).order_by(TaxonomyTerm.id)
            .execution_options(populate_existing=True))).all()
        result[column.target_column] = (column, taxonomy, binding, terms)
    return result


def context_hash(context):
    return digest({name: {"taxonomy": record(taxonomy), "binding": record(binding),
                          "terms": [record(term) for term in terms]}
                   for name, (_, taxonomy, binding, terms) in context.items()})


def validate_rows(context, rows):
    for name, (column, _, _, terms) in context.items():
        active = [term for term in terms if term.is_active]
        for row in rows:
            value = {**row.transformed_data, **row.corrected_data}.get(name)
            if value is None or not normalized(value):
                if not column.taxonomy_required:
                    continue
                raise AppError("TAXONOMY_VALUE_INVALID", f"Kategori wajib pada kolom {column.source_column} kosong.", 422)
            matches = exact_terms(active, value) if value is not None else []
            if len(matches) != 1:
                code = "TAXONOMY_VALUE_AMBIGUOUS" if len(matches) > 1 else "TAXONOMY_VALUE_INVALID"
                raise AppError(code, f"Kategori kolom {column.source_column}, baris {row.source_row} tidak valid.", 422)


def canonicalize_rows(context, rows, config):
    """Validate the whole set before correcting staging; raw input remains intact."""
    if not context:
        return
    validate_rows(context, rows)
    keys = [c.target_column for c in config.columns if c.is_business_key or c.is_primary_key]
    corrected, seen = [], {}
    for row in rows:
        original = {**row.transformed_data, **row.corrected_data}
        patch = dict(row.corrected_data)
        for name, (_, _, _, terms) in context.items():
            value = original.get(name)
            if value is not None and normalized(value):
                patch[name] = exact_terms([term for term in terms if term.is_active], value)[0].code
        output = {**row.transformed_data, **patch}
        if keys:
            before = digest([original.get(key) for key in keys])
            after = digest([output.get(key) for key in keys])
            if after in seen and seen[after] != before:
                raise AppError("TAXONOMY_KEY_COLLISION", "Normalisasi kategori menyatukan business key berbeda; perbaiki sumber.", 422)
            seen[after] = before
        corrected.append((row, patch))
    for row, patch in corrected:
        row.corrected_data = patch


async def canonicalize_outputs(session, tenant_id, sheet_id, config, good):
    context = await taxonomy_context(session, tenant_id, sheet_id, config, lock=True)
    rows = [SimpleNamespace(source_row=n, transformed_data=v, corrected_data={}) for n, v in good]
    canonicalize_rows(context, rows, config)
    return [(row.source_row, {**row.transformed_data, **row.corrected_data}) for row in rows]


async def review_taxonomy_rows(session, tenant_id, review, config, rows):
    """Resolve unambiguous values and persist mandatory questions for the rest."""
    context = await taxonomy_context(session, tenant_id, review.source_sheet_id, config, lock=True)
    repo = TenantRepository(session, tenant_id)
    findings, invalid_rows, count = [], set(), 0
    keys = [c.target_column for c in config.columns if c.is_business_key or c.is_primary_key]
    original_keys = {row.id: digest([{**row.transformed_data, **row.corrected_data}.get(k) for k in keys]) for row in rows}
    for name, (column, taxonomy, _, terms) in context.items():
        active = [term for term in terms if term.is_active]
        for row in rows:
            values = {**row.transformed_data, **row.corrected_data}
            if name not in values:
                continue  # A separate type/DQ question owns this missing output.
            value = values[name]
            empty = value is None or not normalized(value)
            if empty and not column.taxonomy_required:
                continue
            matches = [] if empty else exact_terms(active, value)
            if len(matches) == 1:
                row.corrected_data = {**row.corrected_data, name: matches[0].code}
                continue
            key = digest({"taxonomy_id": taxonomy.id, "version": taxonomy.version, "row_id": row.id,
                          "target": name, "value": normalized(value)})
            existing = await session.scalar(repo.query(ImportQuestion).where(
                ImportQuestion.import_review_id == review.id, ImportQuestion.question_key == key))
            if not existing:
                await repo.add(ImportQuestion, import_review_id=review.id, staging_row_id=row.id,
                               source_row=row.source_row, source_column=column.source_column, target_column=name,
                               question_key=key, category="TAXONOMY_AMBIGUOUS" if matches else "TAXONOMY_INVALID",
                               prompt="Pilih kategori baku atau perbaiki nilai kategori pada sumber.", mandatory=True,
                               allowed_actions=(["SELECT_RECORD"] if matches else ["APPLY_CORRECTION"]) + ["CORRECT_SOURCE"],
                               candidates=[{"id": term.id, "code": term.code, "label": term.label} for term in matches],
                               evidence={"taxonomy_id": taxonomy.id, "taxonomy_version": taxonomy.version})
            count += 1
            invalid_rows.add(row.source_row)
            findings.append({"source_row": row.source_row, "errors": [{"column": name,
                             "code": "TAXONOMY_VALUE_AMBIGUOUS" if matches else "TAXONOMY_VALUE_INVALID"}]})
    seen = {}
    for row in rows:
        if not keys or row.source_row in invalid_rows or not all(k in row.transformed_data for k in keys):
            continue
        key = digest([{**row.transformed_data, **row.corrected_data}.get(k) for k in keys])
        if key in seen and seen[key] != original_keys[row.id]:
            raise AppError("TAXONOMY_KEY_COLLISION", "Normalisasi menyatukan business key berbeda; perbaiki sumber dan buat batch baru.", 422)
        seen[key] = original_keys[row.id]
    return count, invalid_rows, findings
