from uuid import UUID

from fastapi import Depends, Query

from app.api.dependencies import CurrentUser, Session, require_roles
from app.core.exceptions import success
from app.core.routing import APIRouter
from app.models.auth import User
from app.repositories.base import TenantRepository
from app.schemas.auth import LoginRequest, PasswordChange, RefreshRequest, UserCreate, UserUpdate
from app.services.auth_service import AuthService, public_user

router = APIRouter(prefix="/auth", tags=["Authentication"])
users_router = APIRouter(
    prefix="/users", tags=["User administration"], dependencies=[Depends(require_roles("PLATFORM_ADMIN"))]
)


@router.post("/login")
async def login(data: LoginRequest, session: Session):
    return success(await AuthService(session).login(data))


@router.post("/refresh")
async def refresh(data: RefreshRequest, session: Session):
    return success(await AuthService(session).refresh(data.refresh_token))


@router.get("/me")
async def me(user: CurrentUser):
    return success(public_user(user))


@router.post("/logout")
async def logout(user: CurrentUser):
    user.token_version += 1
    return success({"message": "Semua token akun ini dicabut."})


@router.post("/change-password")
async def change_password(data: PasswordChange, session: Session, user: CurrentUser):
    await AuthService(session).change_password(user, data)
    return success({"message": "Password diubah; silakan login kembali."})


@users_router.post("", status_code=201)
async def create_user(data: UserCreate, session: Session, user: CurrentUser):
    return success(await AuthService(session).create_user(user, data))


@users_router.get("")
async def list_users(
    session: Session, user: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)
):
    users = await TenantRepository(session, user.tenant_id).list(User, offset=offset, limit=limit)
    return success([public_user(u) for u in users], offset=offset, limit=limit)


@users_router.patch("/{user_id}")
async def update_user(user_id: UUID, data: UserUpdate, session: Session, user: CurrentUser):
    return success(await AuthService(session).update_user(user, user_id, data))
