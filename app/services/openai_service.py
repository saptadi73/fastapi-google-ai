import json
import re
import time
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import and_, case, func, or_, select, text

from app.core.config import ROOT, get_settings
from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.models.ai_policy import AITaskPolicy
from app.models.audit import AIUsage

PROMPT_PATHS = {
    "ETL_CONFIG": "etl_configuration_v1.md",
    "TAXONOMY_RECOMMEND": "taxonomy_recommend_v1.md",
    "NL2SQL": "nl2sql_v1.md",
    "USER_HELP": "user_help_v1.md",
}


def _normalize_target(value: str, fallback: str = "data") -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", str(value)).strip("_").lower()
    if not value or not value[0].isalpha():
        value = "data_" + value
    return value[:29]


def _coerce_etl_draft(value: dict, schema, context: str):
    """Convert the compact AI draft shape into the runtime ETL contract."""
    if "dataset_business_name" in value and "target_table" in value:
        return schema.model_validate(value)
    source = value.get("source") if isinstance(value.get("source"), dict) else {}
    sheet_name = source.get("sheet_name") or "dataset"
    columns = value.get("columns") if isinstance(value.get("columns"), list) else []
    mapped, dimensions, keys = [], [], []
    type_map = {
        "int": "bigint", "integer": "bigint", "long": "bigint", "float": "numeric",
        "double": "numeric", "decimal": "numeric", "number": "numeric",
        "string": "text", "str": "text", "datetime": "timestamp", "date": "date",
        "boolean": "boolean", "bool": "boolean",
    }
    pii_map = {"none": "NONE", "low": "LOW", "medium": "MEDIUM", "high": "HIGH"}
    for item in columns:
        if not isinstance(item, dict):
            continue
        source_column = str(item.get("source_column") or item.get("name") or "").strip()
        target_column = _normalize_target(item.get("target_column") or item.get("name"), "column")
        if not source_column or any(c["source_column"] == source_column for c in mapped):
            continue
        target_type = type_map.get(str(item.get("target_type") or item.get("data_type") or "text").lower(), "text")
        pii = pii_map.get(str(item.get("pii_classification") or item.get("pii_level") or "none").lower(), "NONE")
        is_key = bool(item.get("is_business_key")) or target_column in {"id", "code", "no"} or str(item.get("semantic_type", "")).lower() == "key"
        mapped.append({
            "source_column": source_column, "target_column": target_column, "target_type": target_type,
            "business_name": source_column, "nullable": not is_key, "is_business_key": is_key,
            "is_primary_key": False, "transformation_codes": [], "transform_parameters": [],
            "pii_classification": pii, "confidence": 0.6,
            "reason": "Draft AI dinormalisasi dan divalidasi oleh backend.",
        })
        if str(item.get("semantic_type", "")).lower() == "dimension" and pii in ("NONE", "LOW"):
            dimensions.append(target_column)
        if is_key:
            keys.append(target_column)
    if not mapped:
        raise ValueError("Draft AI tidak memiliki kolom yang dapat dipetakan")
    if not keys:
        keys = [mapped[0]["target_column"]]
        mapped[0]["is_business_key"] = True
        mapped[0]["nullable"] = False
    grain = value.get("grain", "Satu baris sumber")
    if isinstance(grain, list):
        grain = "Satu record per " + ", ".join(str(item) for item in grain)
    return schema.model_validate({
        "dataset_business_name": sheet_name,
        "dataset_description": "",
        "grain": str(grain),
        "target_schema": "trusted",
        "target_table": _normalize_target(sheet_name),
        "load_strategy": "UPSERT" if keys else "APPEND",
        "append_duplicate_policy": None,
        "columns": mapped,
        "data_quality_rules": [],
        "semantic": {"code": _normalize_target(sheet_name, "dataset"), "dimensions": dimensions, "metrics": []},
        "unresolved_questions": value.get("unresolved_questions", []),
        "overall_confidence": 0.6,
    })


class OpenAIService:
    async def generate(
        self,
        user,
        purpose,
        context,
        schema,
        *,
        data_product_code=None,
        data_source_id=None,
        taxonomy_id=None,
    ):
        s = get_settings()
        if sum(value is not None for value in (data_product_code, data_source_id, taxonomy_id)) > 1:
            raise AppError("AI_TASK_SCOPE_INVALID", "Satu task AI hanya menerima satu scope dataset.", 422)
        if data_product_code is not None and purpose != "NL2SQL":
            raise AppError("AI_TASK_SCOPE_INVALID", "Scope DataProduct hanya untuk NL2SQL.", 422)
        if data_source_id is not None and purpose != "ETL_CONFIG":
            raise AppError("AI_TASK_SCOPE_INVALID", "Scope source hanya untuk ETL_CONFIG.", 422)
        if taxonomy_id is not None and purpose != "TAXONOMY_RECOMMEND":
            raise AppError("AI_TASK_SCOPE_INVALID", "Scope taxonomy hanya untuk TAXONOMY_RECOMMEND.", 422)
        model = (
            s.openai_model_etl_config
            if purpose in ("ETL_CONFIG", "TAXONOMY_RECOMMEND")
            else (s.openai_model_help or s.openai_model_nl2sql)
        )
        if not s.openai_api_key.get_secret_value() or not model:
            raise AppError("OPENAI_NOT_CONFIGURED", "Isi OPENAI_API_KEY dan OPENAI_MODEL_* pada .env.", 503)
        template = PROMPT_PATHS.get(purpose, "nl2sql_v1.md")
        prompt = (ROOT / "app/prompts" / template).read_text(encoding="utf-8")
        start = time.monotonic()
        policy_id = None
        policy_budget = None
        fallback_model = None
        if purpose == "ETL_CONFIG":
            fallback_model = s.openai_model_etl_fallback or None
        # A separate committed ledger persists usage even if downstream validation fails.
        async with SessionFactory() as usage_session, usage_session.begin():
            requested_scope = []
            if data_product_code is not None:
                requested_scope.append(AITaskPolicy.data_product_code == data_product_code)
            if data_source_id is not None:
                requested_scope.append(AITaskPolicy.data_source_id == str(data_source_id))
            if taxonomy_id is not None:
                requested_scope.append(AITaskPolicy.taxonomy_id == str(taxonomy_id))
            global_scope = and_(
                AITaskPolicy.data_product_code.is_(None),
                AITaskPolicy.data_source_id.is_(None),
                AITaskPolicy.taxonomy_id.is_(None),
            )
            policy_scope = or_(*requested_scope, global_scope)
            scope_priority = case(*((condition, 1) for condition in requested_scope), else_=0)
            policy = await usage_session.scalar(
                select(AITaskPolicy).where(
                    AITaskPolicy.tenant_id == user.tenant_id,
                    AITaskPolicy.purpose == purpose,
                    AITaskPolicy.status == "APPROVED",
                    policy_scope,
                ).order_by(
                    scope_priority.desc(),
                    AITaskPolicy.approved_at.desc(),
                    AITaskPolicy.created_at.desc(),
                ).limit(1)
            )
            if policy is not None and hasattr(policy, "model"):
                policy_id = getattr(policy, "id", None)
                policy_budget = getattr(policy, "daily_budget_usd", None)
                fallback_model = getattr(policy, "fallback_model", None)
                stored_scopes = [
                    getattr(policy, "data_product_code", None),
                    getattr(policy, "data_source_id", None),
                    getattr(policy, "taxonomy_id", None),
                ]
                allowed_models = getattr(policy, "allowed_models", [])
                server_models = (
                    set(s.openai_allowed_models)
                    | {s.openai_model_etl_config, s.openai_model_nl2sql, s.openai_model_help}
                ) - {""}
                if (
                    sum(value is not None for value in stored_scopes) > 1
                    or (stored_scopes[0] is not None and purpose != "NL2SQL")
                    or (stored_scopes[1] is not None and purpose != "ETL_CONFIG")
                    or (stored_scopes[2] is not None and purpose != "TAXONOMY_RECOMMEND")
                    or policy.model not in allowed_models
                    or not set(allowed_models).issubset(server_models)
                    or policy.model not in server_models
                    or policy.prompt_version != PROMPT_PATHS.get(purpose)
                    or (fallback_model and fallback_model == policy.model)
                    or (fallback_model and fallback_model not in allowed_models)
                    or (fallback_model and fallback_model not in server_models)
                ):
                    raise AppError("AI_TASK_POLICY_INVALID", "Policy AI tersimpan tidak valid.", 503)
                max_context_chars = getattr(policy, "max_context_chars", 200_000)
                if len(context) > max_context_chars:
                    raise AppError(
                        "AI_CONTEXT_LIMIT_EXCEEDED",
                        f"Konteks AI melebihi batas policy ({max_context_chars} karakter).",
                        422,
                    )
                model, template = policy.model, policy.prompt_version
            await usage_session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "ai-quota:" + user.tenant_id}
            )
            midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            count = await usage_session.scalar(
                select(func.count())
                .select_from(AIUsage)
                .where(
                    AIUsage.tenant_id == user.tenant_id,
                    AIUsage.user_id == user.id,
                    AIUsage.purpose == purpose,
                    AIUsage.created_at >= midnight,
                )
            )
            daily_limit = (
                s.ai_help_daily_user_limit if purpose == "USER_HELP" else s.nl2sql_daily_user_limit
            )
            if count >= daily_limit:
                code = "AI_HELP_QUOTA_EXCEEDED" if purpose == "USER_HELP" else "NL2SQL_QUOTA_EXCEEDED"
                raise AppError(code, "Kuota AI harian pengguna tercapai.", 429)
            if s.ai_daily_tenant_budget_usd or policy_budget:
                if not s.openai_input_usd_per_million or not s.openai_output_usd_per_million:
                    raise AppError(
                        "AI_PRICING_REQUIRED", "Isi harga model sebelum mengaktifkan budget USD.", 503
                    )
                attempts = 2 if fallback_model else 1
                reserve = (
                    attempts
                    * (
                        (len(prompt.encode()) + len(context.encode()))
                        * s.openai_input_usd_per_million
                        + s.openai_max_output_tokens * s.openai_output_usd_per_million
                    )
                ) / 1_000_000
                if s.ai_daily_tenant_budget_usd:
                    tenant_spent = (
                        await usage_session.scalar(
                            select(func.sum(AIUsage.estimated_cost_usd)).where(
                                AIUsage.tenant_id == user.tenant_id,
                                AIUsage.created_at >= midnight,
                            )
                        )
                        or 0
                    )
                    if tenant_spent + reserve > s.ai_daily_tenant_budget_usd:
                        raise AppError("AI_BUDGET_EXCEEDED", "Budget AI tenant tercapai.", 429)
                if policy_budget and policy_id:
                    policy_spent = (
                        await usage_session.scalar(
                            select(func.sum(AIUsage.estimated_cost_usd)).where(
                                AIUsage.tenant_id == user.tenant_id,
                                AIUsage.policy_id == policy_id,
                                AIUsage.created_at >= midnight,
                            )
                        )
                        or 0
                    )
                    if policy_spent + reserve > policy_budget:
                        raise AppError(
                            "AI_TASK_BUDGET_EXCEEDED", "Budget harian policy AI tercapai.", 429
                        )
            error, response, actual_model = None, None, model
            parsed_output = None
            responses = []
            models = [model] + ([fallback_model] if fallback_model and fallback_model != model else [])
            had_structured_failure = False
            parse_diagnostics = []
            try:
                async with AsyncOpenAI(
                    api_key=s.openai_api_key.get_secret_value(),
                    timeout=s.openai_timeout_seconds,
                    max_retries=0,
                ) as client:
                    for candidate_model in models:
                        actual_model = candidate_model
                        try:
                            request = dict(
                                model=candidate_model,
                                store=s.openai_store_responses,
                                input=[
                                    {"role": "developer", "content": prompt},
                                    {"role": "user", "content": context},
                                ],
                                text_format=schema,
                                max_output_tokens=s.openai_max_output_tokens,
                            )
                            # Reasoning models can spend the entire budget reasoning and
                            # return no structured output. Keep ETL generation focused.
                            if candidate_model.startswith(("gpt-5", "o1", "o3", "o4")):
                                request["reasoning"] = {"effort": "low"}
                            candidate_response = await client.responses.parse(**request)
                            responses.append(candidate_response)
                            response = candidate_response
                            if candidate_response.output_parsed is not None:
                                parsed_output = candidate_response.output_parsed
                                break
                            # Some models cannot satisfy the full ETL schema in strict
                            # structured mode. Retry as JSON mode, then validate the
                            # returned object with the same Pydantic schema server-side.
                            json_response = await client.responses.create(
                                model=candidate_model,
                                store=s.openai_store_responses,
                                input=[
                                    {"role": "developer", "content": prompt + "\nReturn only one JSON object. Do not wrap it in markdown."},
                                    {"role": "user", "content": context},
                                ],
                                text={"format": {"type": "json_object"}},
                                max_output_tokens=s.openai_max_output_tokens,
                                **({"reasoning": {"effort": "low"}} if candidate_model.startswith(("gpt-5", "o1", "o3", "o4")) else {}),
                            )
                            raw_json = (getattr(json_response, "output_text", "") or "").strip()
                            if raw_json:
                                try:
                                    decoded = json.loads(raw_json)
                                    for wrapper in ("draft_configuration", "configuration", "etl_configuration"):
                                        if isinstance(decoded, dict) and isinstance(decoded.get(wrapper), dict):
                                            decoded = decoded[wrapper]
                                            break
                                    parsed = _coerce_etl_draft(decoded, schema, context) if purpose == "ETL_CONFIG" else schema.model_validate(decoded)
                                except Exception as exc:
                                    parse_diagnostics.append(f"{candidate_model}:json_mode={type(exc).__name__}:{' '.join(str(exc).split())[-250:]}")
                                else:
                                    response = json_response
                                    parsed_output = parsed
                                    responses.append(json_response)
                                    break
                            # SDK parsing can be empty even when the response contains
                            # valid JSON. Validate the raw text as a safe second path.
                            raw = (getattr(candidate_response, "output_text", "") or "").strip()
                            if raw:
                                try:
                                    parsed = schema.model_validate_json(raw)
                                except Exception as exc:
                                    parse_diagnostics.append(f"{candidate_model}:raw_parse={type(exc).__name__}")
                                else:
                                    response.output_parsed = parsed
                                    break
                            status = getattr(candidate_response, "status", None)
                            incomplete = getattr(candidate_response, "incomplete_details", None)
                            parse_diagnostics.append(f"{candidate_model}:status={status};incomplete={incomplete}")
                            had_structured_failure = True
                        except Exception as exc:
                            detail = " ".join(str(exc).split())[-400:]
                            parse_diagnostics.append(f"{candidate_model}:request={type(exc).__name__}:{detail}")
                            # A parser exception (for example an empty structured
                            # response) must still get the JSON-mode fallback.
                            try:
                                json_response = await client.responses.create(
                                    model=candidate_model,
                                    store=s.openai_store_responses,
                                    input=[
                                        {"role": "developer", "content": prompt + "\nReturn only one JSON object. Do not wrap it in markdown."},
                                        {"role": "user", "content": context},
                                    ],
                                    text={"format": {"type": "json_object"}},
                                    max_output_tokens=s.openai_max_output_tokens,
                                    **({"reasoning": {"effort": "low"}} if candidate_model.startswith(("gpt-5", "o1", "o3", "o4")) else {}),
                                )
                                raw_json = (getattr(json_response, "output_text", "") or "").strip()
                                decoded = json.loads(raw_json) if raw_json else None
                                if isinstance(decoded, dict):
                                    for wrapper in ("draft_configuration", "configuration", "etl_configuration"):
                                        if isinstance(decoded.get(wrapper), dict):
                                            decoded = decoded[wrapper]
                                            break
                                    parsed = _coerce_etl_draft(decoded, schema, context) if purpose == "ETL_CONFIG" else schema.model_validate(decoded)
                                    response, parsed_output = json_response, parsed
                                    responses.append(json_response)
                                    break
                            except Exception as fallback_exc:
                                parse_diagnostics.append(f"{candidate_model}:json_exception={type(fallback_exc).__name__}:{' '.join(str(fallback_exc).split())[-250:]}")
                            continue
                    else:
                        error = (
                            AppError(
                                "AI_CONFIGURATION_INVALID",
                                "AI tidak menghasilkan output terstruktur yang valid. "
                                + " ".join(parse_diagnostics)[-500:],
                            )
                            if had_structured_failure
                            else AppError(
                                "AI_UPSTREAM_FAILED",
                                "Layanan AI gagal; periksa konfigurasi atau coba kembali.",
                                503,
                            )
                        )
            except Exception:
                error = AppError(
                    "AI_UPSTREAM_FAILED",
                    "Layanan AI gagal; periksa konfigurasi atau coba kembali.",
                    503,
                )
            usages = [item.usage for item in responses if getattr(item, "usage", None)]
            input_tokens = sum(item.input_tokens for item in usages)
            output_tokens = sum(item.output_tokens for item in usages)
            cached_tokens = sum(
                getattr(getattr(item, "input_tokens_details", None), "cached_tokens", 0) or 0
                for item in usages
            )
            cost = (
                (
                    (
                        input_tokens * s.openai_input_usd_per_million
                        + output_tokens * s.openai_output_usd_per_million
                    )
                    / 1_000_000
                )
                if s.openai_input_usd_per_million and s.openai_output_usd_per_million
                else None
            )
            usage_session.add(
                AIUsage(
                    tenant_id=user.tenant_id,
                    user_id=user.id,
                    policy_id=policy_id,
                    purpose=purpose,
                    model=actual_model,
                    response_id=response.id if response else None,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                    estimated_cost_usd=cost,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    status="FAILED" if error else "SUCCEEDED",
                )
            )
        if error:
            raise error
        return parsed_output, {
            "ai_response_id": response.id,
            "ai_model": actual_model,
            "prompt_version": template,
            "fallback_used": actual_model != model,
        }
