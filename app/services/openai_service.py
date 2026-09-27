import time
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import case, func, or_, select, text

from app.core.config import ROOT, get_settings
from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.models.ai_policy import AITaskPolicy
from app.models.audit import AIUsage

PROMPT_PATHS = {
    "ETL_CONFIG": "etl_configuration_v1.md",
    "TAXONOMY_RECOMMEND": "taxonomy_recommend_v1.md",
    "NL2SQL": "nl2sql_v1.md",
}


class OpenAIService:
    async def generate(self, user, purpose, context, schema, *, data_product_code=None):
        s = get_settings()
        model = s.openai_model_etl_config if purpose in ("ETL_CONFIG", "TAXONOMY_RECOMMEND") else s.openai_model_nl2sql
        if not s.openai_api_key.get_secret_value() or not model:
            raise AppError("OPENAI_NOT_CONFIGURED", "Isi OPENAI_API_KEY dan OPENAI_MODEL_* pada .env.", 503)
        template = PROMPT_PATHS.get(purpose, "nl2sql_v1.md")
        prompt = (ROOT / "app/prompts" / template).read_text(encoding="utf-8")
        start = time.monotonic()
        policy_id = None
        policy_budget = None
        fallback_model = None
        # A separate committed ledger persists usage even if downstream validation fails.
        async with SessionFactory() as usage_session, usage_session.begin():
            policy_scope = (
                or_(
                    AITaskPolicy.data_product_code == data_product_code,
                    AITaskPolicy.data_product_code.is_(None),
                )
                if data_product_code
                else AITaskPolicy.data_product_code.is_(None)
            )
            policy = await usage_session.scalar(
                select(AITaskPolicy).where(
                    AITaskPolicy.tenant_id == user.tenant_id,
                    AITaskPolicy.purpose == purpose,
                    AITaskPolicy.status == "APPROVED",
                    policy_scope,
                ).order_by(
                    case((AITaskPolicy.data_product_code == data_product_code, 1), else_=0).desc(),
                    AITaskPolicy.approved_at.desc(),
                    AITaskPolicy.created_at.desc(),
                ).limit(1)
            )
            if policy is not None and hasattr(policy, "model"):
                policy_id = getattr(policy, "id", None)
                policy_budget = getattr(policy, "daily_budget_usd", None)
                fallback_model = getattr(policy, "fallback_model", None)
                allowed_models = getattr(policy, "allowed_models", [])
                server_models = (
                    set(s.openai_allowed_models)
                    | {s.openai_model_etl_config, s.openai_model_nl2sql}
                ) - {""}
                if (
                    policy.model not in allowed_models
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
                    AIUsage.created_at >= midnight,
                )
            )
            if count >= s.nl2sql_daily_user_limit:
                raise AppError("NL2SQL_QUOTA_EXCEEDED", "Kuota AI harian pengguna tercapai.", 429)
            if s.ai_daily_tenant_budget_usd or policy_budget:
                if not s.openai_input_usd_per_million or not s.openai_output_usd_per_million:
                    raise AppError(
                        "AI_PRICING_REQUIRED", "Isi harga model sebelum mengaktifkan budget USD.", 503
                    )
                attempts = 2 if fallback_model else 1
                reserve = (
                    attempts
                    * (
                        len(context.encode()) * s.openai_input_usd_per_million
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
            responses = []
            models = [model] + ([fallback_model] if fallback_model else [])
            had_structured_failure = False
            try:
                async with AsyncOpenAI(
                    api_key=s.openai_api_key.get_secret_value(),
                    timeout=s.openai_timeout_seconds,
                    max_retries=0,
                ) as client:
                    for candidate_model in models:
                        actual_model = candidate_model
                        try:
                            candidate_response = await client.responses.parse(
                                model=candidate_model,
                                store=s.openai_store_responses,
                                input=[
                                    {"role": "developer", "content": prompt},
                                    {"role": "user", "content": context},
                                ],
                                text_format=schema,
                                max_output_tokens=s.openai_max_output_tokens,
                            )
                            responses.append(candidate_response)
                            response = candidate_response
                            if candidate_response.output_parsed is not None:
                                break
                            had_structured_failure = True
                        except Exception:
                            continue
                    else:
                        error = (
                            AppError(
                                "AI_CONFIGURATION_INVALID",
                                "AI tidak menghasilkan output terstruktur yang valid.",
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
        return response.output_parsed, {
            "ai_response_id": response.id,
            "ai_model": actual_model,
            "prompt_version": template,
            "fallback_used": actual_model != model,
        }
