import time
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import func, select, text

from app.core.config import ROOT, get_settings
from app.core.database import SessionFactory
from app.core.exceptions import AppError
from app.models.audit import AIUsage


class OpenAIService:
    async def generate(self, user, purpose, context, schema):
        s = get_settings()
        model = s.openai_model_etl_config if purpose == "ETL_CONFIG" else s.openai_model_nl2sql
        if not s.openai_api_key.get_secret_value() or not model:
            raise AppError("OPENAI_NOT_CONFIGURED", "Isi OPENAI_API_KEY dan OPENAI_MODEL_* pada .env.", 503)
        template = "etl_configuration_v1.md" if purpose == "ETL_CONFIG" else "nl2sql_v1.md"
        prompt = (ROOT / "app/prompts" / template).read_text(encoding="utf-8")
        start = time.monotonic()
        # A separate committed ledger persists usage even if downstream validation fails.
        async with SessionFactory() as usage_session, usage_session.begin():
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
            if s.ai_daily_tenant_budget_usd:
                if not s.openai_input_usd_per_million or not s.openai_output_usd_per_million:
                    raise AppError(
                        "AI_PRICING_REQUIRED", "Isi harga model sebelum mengaktifkan budget USD.", 503
                    )
                spent = (
                    await usage_session.scalar(
                        select(func.sum(AIUsage.estimated_cost_usd)).where(
                            AIUsage.tenant_id == user.tenant_id, AIUsage.created_at >= midnight
                        )
                    )
                    or 0
                )
                reserve = (
                    len(context.encode()) * s.openai_input_usd_per_million
                    + s.openai_max_output_tokens * s.openai_output_usd_per_million
                ) / 1_000_000
                if spent + reserve > s.ai_daily_tenant_budget_usd:
                    raise AppError("AI_BUDGET_EXCEEDED", "Budget AI tenant tercapai.", 429)
            error, response = None, None
            try:
                async with AsyncOpenAI(
                    api_key=s.openai_api_key.get_secret_value(),
                    timeout=s.openai_timeout_seconds,
                    max_retries=0,
                ) as client:
                    response = await client.responses.parse(
                        model=model,
                        store=s.openai_store_responses,
                        input=[
                            {"role": "developer", "content": prompt},
                            {"role": "user", "content": context},
                        ],
                        text_format=schema,
                        max_output_tokens=s.openai_max_output_tokens,
                    )
                if response.output_parsed is None:
                    error = AppError(
                        "AI_CONFIGURATION_INVALID", "AI tidak menghasilkan output terstruktur yang valid."
                    )
            except Exception:
                error = AppError(
                    "AI_UPSTREAM_FAILED", "Layanan AI gagal; periksa konfigurasi atau coba kembali.", 503
                )
            usage = response.usage if response else None
            input_tokens = usage.input_tokens if usage else 0
            output_tokens = usage.output_tokens if usage else 0
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
                    purpose=purpose,
                    model=model,
                    response_id=response.id if response else None,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0)
                    or 0,
                    estimated_cost_usd=cost,
                    latency_ms=int((time.monotonic() - start) * 1000),
                    status="FAILED" if error else "SUCCEEDED",
                )
            )
        if error:
            raise error
        return response.output_parsed, {
            "ai_response_id": response.id,
            "ai_model": model,
            "prompt_version": template,
        }
