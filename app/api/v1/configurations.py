from uuid import UUID

from fastapi import Depends
from fastapi.responses import Response

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.domain.enums import EDIT_ROLES, REVIEW_ROLES
from app.models.configuration import Artifact, Configuration
from app.repositories.base import record
from app.schemas.configuration import ConfigurationCreate, ConfigurationPatch, Decision, ExportRequest
from app.services.configuration_service import ConfigurationService

router = APIRouter(
    prefix="/configurations",
    tags=["Configurations"],
    dependencies=[Depends(require_roles(*EDIT_ROLES, *REVIEW_ROLES))],
)
edit = [Depends(require_roles(*EDIT_ROLES))]
review = [Depends(require_roles(*REVIEW_ROLES))]


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
async def submit_review(config_id: UUID, session: Session, user: CurrentUser):
    return success(record(await ConfigurationService(session, user).submit_review(config_id)))


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
