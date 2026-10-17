"""Default semantic metric detection for NON_MASTER data products."""

from app.schemas.configuration import MetricDefinition

NUMERIC_TYPES = {
    "smallint",
    "int",
    "integer",
    "bigint",
    "numeric",
    "decimal",
    "real",
    "double precision",
}


def _value(item, name, default=None):
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def default_numeric_metric_definitions(columns, existing_metrics, dataset_kind):
    """Return missing public numeric metrics, without changing existing definitions."""
    if dataset_kind != "NON_MASTER":
        return []

    metrics = [
        metric.model_dump(mode="json") if hasattr(metric, "model_dump") else dict(metric)
        for metric in existing_metrics
    ]
    metric_columns = {metric["column"] for metric in metrics}
    used_codes = {metric["code"] for metric in metrics}
    used_terms = {
        " ".join(str(term).casefold().split())
        for metric in metrics
        for term in (metric.get("code", ""), metric.get("label", ""), *metric.get("synonyms", []))
        if str(term).strip()
    }
    column_names = {_value(column, "target_column", "") for column in columns}
    generated = []

    for column in columns:
        target = _value(column, "target_column", "")
        target_type = str(_value(column, "target_type", "")).casefold()
        pii = _value(column, "pii_classification")
        visibility = _value(column, "access_visibility", "VISIBLE")
        if (
            target_type not in NUMERIC_TYPES
            or pii not in ("NONE", "LOW")
            or visibility in ("HIDDEN", "MASKED")
            or target in metric_columns
        ):
            continue

        code_base = f"metric_{target}"[:63]
        code = code_base
        suffix = 2
        while code in used_codes or code in column_names:
            tail = f"_{suffix}"
            code = f"{code_base[:63 - len(tail)]}{tail}"
            suffix += 1

        business_name = str(_value(column, "business_name", "") or "").strip()
        label_base = business_name or target
        label = label_base[:200]
        term = " ".join(label.casefold().split())
        if term in used_terms:
            label = f"{label_base[: max(1, 190 - len(target))]} ({target})"
            term = " ".join(label.casefold().split())
        while term in used_terms:
            label = f"{target} ({suffix})"[:200]
            term = " ".join(label.casefold().split())
            suffix += 1

        is_key = bool(_value(column, "is_business_key")) or bool(_value(column, "is_primary_key"))
        if is_key:
            aggregation = "count_distinct"
        elif any(
            token in f"{target} {business_name}".casefold()
            for token in ("percent", "percentage", "persen", "ratio", "rasio", "rate", "margin")
        ):
            aggregation = "avg"
        else:
            aggregation = "sum"

        generated.append(
            MetricDefinition(
                code=code,
                column=target,
                aggregation=aggregation,
                label=label,
                description=(
                    f"Metrik otomatis dari kolom {business_name or target} bertipe {target_type}; "
                    "periksa agregasi dan satuannya."
                )[:1000],
            )
        )
        used_codes.add(code)
        used_terms.update((term, code.casefold()))
        metric_columns.add(target)

    return generated


def add_default_numeric_metrics(configuration, dataset_kind):
    generated = default_numeric_metric_definitions(
        configuration.columns, configuration.semantic.metrics, dataset_kind
    )
    configuration.semantic.metrics.extend(generated)
    return [metric.column for metric in generated]


def backfill_data_product_numeric_metrics(product, dataset_kind):
    """Apply defaults to one active catalog product; return added target columns."""
    if product.status != "ACTIVE" or dataset_kind != "NON_MASTER":
        return []
    generated = default_numeric_metric_definitions(product.columns or [], product.metrics or [], dataset_kind)
    if not generated:
        return []
    product.metrics = [*(product.metrics or []), *(metric.model_dump(mode="json") for metric in generated)]
    product.version += 1
    return [metric.column for metric in generated]
