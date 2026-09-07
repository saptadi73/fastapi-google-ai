from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "google-sheet-ai-platform"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: SecretStr
    database_ddl_url: SecretStr = SecretStr("")
    database_nl2sql_url: SecretStr = SecretStr("")
    jwt_secret: SecretStr
    jwt_issuer: str = "google-sheet-ai-platform"
    jwt_audience: str = "google-sheet-dashboard"
    jwt_access_minutes: int = Field(30, ge=1, le=1440)
    jwt_refresh_days: int = Field(7, ge=1, le=90)
    bootstrap_tenant: str = "default"
    bootstrap_username: str = "admin"
    bootstrap_password: SecretStr = SecretStr("")
    google_service_account_file: str = "secrets/google-service-account.json"
    google_credential_ref: str = "default"
    google_api_timeout_seconds: int = 30
    google_max_rows: int = Field(50000, ge=1, le=1000000)
    google_max_columns: int = Field(100, ge=1, le=1000)
    openai_api_key: SecretStr = SecretStr("")
    openai_model_etl_config: str = ""
    openai_model_nl2sql: str = ""
    openai_store_responses: bool = False
    openai_timeout_seconds: int = 60
    openai_max_output_tokens: int = 12000
    openai_input_usd_per_million: float = Field(0, ge=0)
    openai_output_usd_per_million: float = Field(0, ge=0)
    ai_daily_tenant_budget_usd: float = Field(0, ge=0)
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    celery_broker_url: SecretStr = SecretStr("redis://127.0.0.1:6379/1")
    celery_result_backend: SecretStr = SecretStr("redis://127.0.0.1:6379/2")
    redis_required: bool = False
    query_cache_ttl_seconds: int = 300
    nl2sql_statement_timeout_ms: int = Field(10000, ge=100, le=60000)
    nl2sql_max_rows: int = Field(1000, ge=1, le=10000)
    nl2sql_max_estimated_cost: float = 100000
    nl2sql_daily_user_limit: int = Field(25, ge=1)
    etl_sample_row_limit: int = Field(200, ge=1, le=1000)
    job_poll_seconds: int = 5
    job_stale_minutes: int = 30
    artifact_storage_path: Path = ROOT / "storage/configs"
    require_separate_approver: bool = True
    test_database_url: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def validate_secrets(self):
        if len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must have at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
