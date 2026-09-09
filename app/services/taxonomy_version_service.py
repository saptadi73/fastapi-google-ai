"""Draft complete term sets and atomically publish immutable taxonomy snapshots."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.taxonomy import Taxonomy, TaxonomyTerm, TaxonomyVersion
from app.repositories.base import TenantRepository
from app.schemas.taxonomy import TaxonomyVersionUpdate
from app.services.audit_service import audit
from app.services.profiling_service import digest


def term_payload(term):
    return {name: getattr(term, name) for name in ("id", "code", "label", "parent_id", "aliases", "is_active")}


async def archive_current(session, taxonomy):
    existing = await session.scalar(select(TaxonomyVersion).where(
        TaxonomyVersion.tenant_id == taxonomy.tenant_id, TaxonomyVersion.taxonomy_id == taxonomy.id,
        TaxonomyVersion.version == taxonomy.version))
    if existing:
        return existing
    terms = (await session.scalars(select(TaxonomyTerm).where(
        TaxonomyTerm.tenant_id == taxonomy.tenant_id, TaxonomyTerm.taxonomy_id == taxonomy.id)
        .order_by(TaxonomyTerm.id))).all()
    version = TaxonomyVersion(tenant_id=taxonomy.tenant_id, taxonomy_id=taxonomy.id, version=taxonomy.version,
                              base_version=None, status="APPROVED", definition_json={"terms": [term_payload(t) for t in terms]},
                              created_by=taxonomy.created_by, approved_by=taxonomy.approved_by,
                              approved_at=taxonomy.approved_at)
    session.add(version)
    await session.flush()
    return version


class TaxonomyVersionService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = TenantRepository(session, user.tenant_id)

    async def create(self, taxonomy_id, data):
        taxonomy = await self.repo.get(Taxonomy, taxonomy_id, lock=True)
        if taxonomy.status != "APPROVED" or not taxonomy.is_active or taxonomy.version != data.base_version:
            raise AppError("TAXONOMY_VERSION_STALE", "Pilih versi taxonomy aktif/approved terbaru.", 409)
        current = await archive_current(self.session, taxonomy)
        existing = await self.session.scalar(self.repo.query(TaxonomyVersion).where(
            TaxonomyVersion.taxonomy_id == taxonomy.id, TaxonomyVersion.version == taxonomy.version + 1))
        if existing:
            return existing
        version = await self.repo.add(TaxonomyVersion, taxonomy_id=taxonomy.id, version=taxonomy.version + 1,
                                       base_version=taxonomy.version, created_by=self.user.id,
                                       definition_json={"terms": current.definition_json["terms"], "edited_by": self.user.id})
        audit(self.session, self.user, "taxonomy.version_drafted", version.id, base_version=taxonomy.version)
        return version

    async def locked(self, version_id, revision_no):
        initial = await self.repo.get(TaxonomyVersion, version_id)
        taxonomy = await self.repo.get(Taxonomy, initial.taxonomy_id, lock=True)
        version = await self.repo.get(TaxonomyVersion, version_id, lock=True)
        await self.session.refresh(version)
        if version.revision_no != revision_no:
            raise AppError("REVISION_CONFLICT", "Revision draft taxonomy berubah; muat ulang.", 409)
        if version.status != "DRAFT":
            raise AppError("TAXONOMY_VERSION_IMMUTABLE", "Versi terbit tidak dapat diubah.", 409)
        if (not taxonomy.is_active or taxonomy.status != "APPROVED"
                or taxonomy.version != version.base_version or version.version != taxonomy.version + 1):
            raise AppError("TAXONOMY_VERSION_STALE", "Versi dasar draft sudah tidak berlaku.", 409)
        return taxonomy, version

    async def validate_identity(self, taxonomy, terms):
        ids = [str(term.id) for term in terms]
        existing = (await self.session.scalars(select(TaxonomyTerm).where(TaxonomyTerm.id.in_(ids)))).all()
        by_id = {str(term.id): term for term in terms}
        for old in existing:
            if old.tenant_id != taxonomy.tenant_id or old.taxonomy_id != taxonomy.id:
                raise AppError("TAXONOMY_TERM_ID_CONFLICT", "UUID term telah digunakan di luar taxonomy ini.", 409)
            if old.code != by_id[old.id].code:
                raise AppError("TAXONOMY_TERM_CODE_IMMUTABLE", "Kode identitas term lama tidak boleh diubah.", 409)
        current = (await self.session.scalars(self.repo.query(TaxonomyTerm).where(
            TaxonomyTerm.taxonomy_id == taxonomy.id))).all()
        by_code = {term.code: term.id for term in current}
        if any(term.code in by_code and by_code[term.code] != str(term.id) for term in terms):
            raise AppError("TAXONOMY_TERM_CODE_CONFLICT", "Kode term lama harus memakai UUID yang sama.", 409)

    async def update(self, version_id, data):
        taxonomy, version = await self.locked(version_id, data.revision_no)
        await self.validate_identity(taxonomy, data.terms)
        version.definition_json = {"terms": data.model_dump(mode="json")["terms"], "edited_by": self.user.id}
        version.revision_no += 1
        # The latest editor must not approve their own changes.
        audit(self.session, self.user, "taxonomy.version_edited", version.id, revision_no=version.revision_no)
        return version

    async def approve(self, version_id, data):
        taxonomy, version = await self.locked(version_id, data.revision_no)
        editor_id = version.definition_json.get("edited_by", version.created_by)
        if get_settings().require_separate_approver and editor_id == self.user.id:
            raise AppError("SEPARATE_APPROVER_REQUIRED", "Editor terakhir tidak boleh menyetujui draft sendiri.", 403)
        parsed = TaxonomyVersionUpdate(revision_no=version.revision_no, terms=version.definition_json["terms"])
        await self.validate_identity(taxonomy, parsed.terms)
        old = {term.id: term for term in (await self.session.scalars(self.repo.query(TaxonomyTerm).where(
            TaxonomyTerm.taxonomy_id == taxonomy.id))).all()}
        timestamp = datetime.now(timezone.utc)
        incoming = {str(term.id): term for term in parsed.terms}
        for term_id, term in old.items():
            if term_id not in incoming:
                term.is_active = False
        # New parents may occur after their children in the submitted list.
        for item in parsed.terms:
            term_id = str(item.id)
            values = item.model_dump(mode="json")
            if term_id not in old:
                old[term_id] = TaxonomyTerm(id=term_id, tenant_id=taxonomy.tenant_id, taxonomy_id=taxonomy.id,
                                           created_by=editor_id, code=item.code, parent_id=None)
                self.session.add(old[term_id])
            term = old[term_id]
            term.label, term.aliases, term.is_active = item.label, item.aliases, item.is_active
            term.fingerprint = digest({"taxonomy_id": taxonomy.id, "code": item.code})
            term.snapshot_hash = digest(values)
            term.approved_by, term.approved_at = self.user.id, timestamp
        await self.session.flush()
        for item in parsed.terms:
            old[str(item.id)].parent_id = str(item.parent_id) if item.parent_id else None
        version.status, version.approved_by, version.approved_at = "APPROVED", self.user.id, timestamp
        version.revision_no += 1
        taxonomy.version = version.version
        taxonomy.approved_by, taxonomy.approved_at = self.user.id, timestamp
        taxonomy.snapshot_hash = digest(version.definition_json)
        audit(self.session, self.user, "taxonomy.version_published", version.id, taxonomy_id=taxonomy.id,
              version=version.version, term_count=len(incoming))
        await self.session.flush()
        return version
