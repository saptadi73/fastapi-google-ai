from uuid import UUID

from fastapi import Depends
from fastapi.responses import Response

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.configuration import Artifact, Configuration
from app.repositories.base import record
from app.schemas.configuration import (
    ConfigurationCreate,
    ConfigurationPatch,
    CurrencyConversion,
    Decision,
    ExportRequest,
    ReviewSubmission,
    UnitConversion,
    WorkbookApplyRequest,
    WorkbookPreviewRequest,
)
from app.services.configuration_review_service import CAPABILITIES, ConfigurationReviewService
from app.services.configuration_service import ConfigurationService

router = APIRouter(
    prefix="/configurations",
    tags=["Configurations"],
    dependencies=[Depends(require_roles(*EDIT_ROLES, *REVIEW_ROLES))],
)
edit = [Depends(require_roles(*EDIT_ROLES))]
review = [Depends(require_roles(*REVIEW_ROLES))]


@router.get("/parameter-catalog")
async def parameter_catalog(session: Session, user: CurrentUser):
    return success({
        "schema_version": "1.0",
        "parameters": [
            {"name": "dataset_business_name", "type": "string", "default": "", "supported": True},
            {"name": "target_table", "type": "identifier", "default": "", "supported": True},
            {"name": "load_strategy", "type": "enum", "default": "UPSERT", "supported": True},
            {"name": "columns", "type": "array", "default": [], "supported": True},
            {"name": "data_quality_rules", "type": "array", "default": [], "supported": True},
            {"name": "locale", "type": "string", "default": "id-ID", "supported": False, "reason": "BE-12 runtime locale"},
            {"name": "source_timezone", "type": "string", "default": None, "supported": True, "scope": "columns.source_timezone; IANA source zone for naive timestamptz; output UTC; DST ambiguity/gaps rejected"},
            {"name": "date_format", "type": "string", "default": "ISO-8601", "supported": True, "scope": "parse_date_id columns"},
            {"name": "number_format", "type": "enum", "default": "ID", "supported": True, "allowed": ["ID", "US"], "scope": "parse_decimal_id columns"},
            {"name": "currency_conversion", "type": "object", "default": None, "supported": True, "scope": "columns.currency_conversion; explicit fixed rate per configuration revision", "parameter_schema": CurrencyConversion.model_json_schema()},
            {"name": "uom", "type": "string", "default": "", "supported": False, "reason": "BE-12 unit conversion"},
            {"name": "numeric_precision_scale", "type": "object", "default": {}, "supported": True, "scope": "numeric columns"},
            {"name": "varchar_length", "type": "integer", "default": None, "supported": True, "scope": "text/varchar columns"},
            {"name": "transformation_codes", "type": "enum[]", "default": [], "supported": True, "allowed": ["trim", "normalize_whitespace", "parse_date_id", "parse_decimal_id", "uppercase", "lowercase", "null_if_empty"]},
            {"name": "transform_parameters", "type": "object[]", "default": [], "supported": False, "reason": "BE-12 parameterized transform registry"},
            {"name": "dq_threshold_percent", "type": "number", "default": None, "supported": True, "scope": "data_quality_rules.threshold_percent; per-rule failure rate"},
            {"name": "dq_format", "type": "enum", "supported": True, "allowed": ["UUID", "ISO_DATE", "ISO_DATETIME"]},
            {"name": "dq_domain", "type": "array", "supported": True, "scope": "allowed_values"},
            {"name": "dq_max_age_days", "type": "integer", "supported": True, "scope": "temporal columns; UTC"},
            {"name": "dq_default_value", "type": "scalar", "supported": True, "scope": "cast before nullability and DQ checks"},
            {"name": "dq_severity_owner", "type": "object", "supported": True, "scope": "finding metadata; action_on_fail controls routing"},
            {"name": "effective_dating", "type": "object", "default": None, "supported": True, "scope": "MASTER policy"},
            {"name": "unit_conversion", "type": "object", "default": None, "supported": True, "scope": "columns.unit_conversion; non-key numeric", "parameter_schema": UnitConversion.model_json_schema()},
            {"name": "multi_target", "type": "object[]", "default": [], "supported": False, "reason": "BE-12 split grain compiler"},
            {"name": "schema_evolution", "type": "object", "default": {}, "supported": False, "reason": "BE-12 migration compiler"},
            {"name": "taxonomy_mapping", "type": "array", "default": [], "supported": False, "reason": "BE-13"},
            {"name": "join_relationships", "type": "array", "default": [], "supported": False, "reason": "BE-14"},
        ],
        "operations": [
            {"code": "convert_currency", "parameters": CurrencyConversion.model_json_schema(), "on_error": "REJECT_ROW", "supported": True, "scope": "columns.currency_conversion; after cast before DQ; no live provider"},
            {"code": "trim", "parameters": {}, "on_error": "REJECT_ROW", "supported": True},
            {"code": "normalize_whitespace", "parameters": {}, "on_error": "REJECT_ROW", "supported": True},
            {"code": "parse_date_id", "parameters": {}, "on_error": "REJECT_ROW", "supported": True},
            {"code": "parse_decimal_id", "parameters": {}, "on_error": "REJECT_ROW", "supported": True},
            {"code": "convert_unit", "parameters": UnitConversion.model_json_schema(), "on_error": "REJECT_ROW", "supported": True, "scope": "columns.unit_conversion; after cast and before DQ"},
        ],
        "capabilities": CAPABILITIES,
    })


@router.get("/{config_id}/review")
async def review_details(config_id: UUID, session: Session, user: CurrentUser):
    return success(await ConfigurationReviewService(session, user).review(config_id))


@router.post("/{config_id}/workbook-preview", dependencies=edit)
async def workbook_preview(
    config_id: UUID, data: WorkbookPreviewRequest, session: Session, user: CurrentUser
):
    return success(await ConfigurationReviewService(session, user).preview(config_id, data))


@router.post("/{config_id}/workbook-apply", dependencies=edit)
async def workbook_apply(config_id: UUID, data: WorkbookApplyRequest, session: Session, user: CurrentUser):
    return success(record(await ConfigurationReviewService(session, user).apply(config_id, data)))


@router.post("", status_code=201, dependencies=edit)
async def create(data: ConfigurationCreate, session: Session, user: CurrentUser):
    return success(
        record(
            await ConfigurationService(session, user).create(str(data.source_sheet_id), data.configuration)
        )
    )


@router.get("/{config_id}")
async def get(config_id: UUID, session: Session, user: CurrentUser):
    return success(record(await ConfigurationService(session, user).repo.get(Configuration, config_id)))


@router.patch("/{config_id}", dependencies=edit)
async def patch(config_id: UUID, data: ConfigurationPatch, session: Session, user: CurrentUser):
    return success(record(await ConfigurationService(session, user).patch(config_id, data)))


@router.post("/{config_id}/validate")
async def validate(config_id: UUID, session: Session, user: CurrentUser):
    service = ConfigurationService(session, user)
    return success(await service.validate(await service.repo.get(Configuration, config_id)))


@router.post("/{config_id}/submit-review", dependencies=edit)
async def submit_review(config_id: UUID, data: ReviewSubmission, session: Session, user: CurrentUser):
    return success(record(await ConfigurationService(session, user).submit_review(config_id, data)))


@router.post("/{config_id}/approve", dependencies=review)
async def approve(config_id: UUID, data: Decision, session: Session, user: CurrentUser):
    return success(record(await ConfigurationService(session, user).decision(config_id, data, "APPROVED")))


@router.post("/{config_id}/reject", dependencies=review)
async def reject(config_id: UUID, data: Decision, session: Session, user: CurrentUser):
    return success(record(await ConfigurationService(session, user).decision(config_id, data, "REJECTED")))


@router.post("/{config_id}/clone", status_code=201, dependencies=edit)
async def clone(config_id: UUID, session: Session, user: CurrentUser):
    return success(record(await ConfigurationService(session, user).clone(config_id)))


@router.post("/{config_id}/deploy", status_code=202, dependencies=review)
@router.post("/{config_id}/activate", status_code=202, dependencies=review)
async def deploy(config_id: UUID, session: Session, user: CurrentUser):
    return success(await ConfigurationService(session, user).queue_deployment(config_id))


@router.post("/{config_id}/rollback", status_code=202, dependencies=review)
async def rollback(config_id: UUID, session: Session, user: CurrentUser):
    return success(await ConfigurationService(session, user).queue_deployment(config_id, rollback=True))


@router.get("/{config_id}/artifacts")
async def artifacts(config_id: UUID, session: Session, user: CurrentUser):
    service = ConfigurationService(session, user)
    await service.repo.get(Configuration, config_id)
    return success(
        [
            record(a, exclude=("storage_uri",))
            for a in await service.repo.list(
                Artifact, conditions=(Artifact.configuration_version_id == str(config_id),)
            )
        ]
    )


@router.post("/{config_id}/export", status_code=201)
async def export(config_id: UUID, data: ExportRequest, session: Session, user: CurrentUser):
    service = ConfigurationService(session, user)
    config = await service.repo.get(Configuration, config_id)
    artifact = await service.artifacts.create(config, "EXPORT_" + data.format, data.format)
    return success(record(artifact, exclude=("storage_uri",)))


@router.get("/{config_id}/artifacts/{artifact_id}/download", response_class=Response)
async def download(config_id: UUID, artifact_id: UUID, session: Session, user: CurrentUser):
    service = ConfigurationService(session, user)
    config = await service.repo.get(Configuration, config_id)
    artifact, content = await service.artifacts.read(config, artifact_id)
    return Response(
        content,
        media_type=artifact.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.file_name}"'},
    )


@router.get("/{config_id}/questions")
async def questions(config_id: UUID, session: Session, user: CurrentUser):
    config = await ConfigurationService(session, user).repo.get(Configuration, config_id)
    return success(config.configuration_json["unresolved_questions"])


@router.get("/{config_id}/diff")
async def diff(config_id: UUID, against: UUID, session: Session, user: CurrentUser):
    return success(await ConfigurationService(session, user).compare(config_id, against))
