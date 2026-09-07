from app.core.exceptions import AppError
from app.models.semantic import DataProduct
from app.repositories.base import TenantRepository


class SemanticRepository(TenantRepository):
    async def product(self, code, user):
        obj = await self.session.scalar(
            self.query(DataProduct).where(DataProduct.code == code, DataProduct.status == "ACTIVE")
        )
        if obj is None or user.role not in obj.allowed_roles:
            raise AppError("DATA_PRODUCT_NOT_FOUND", "Data product tidak tersedia untuk akses Anda.", 404)
        return obj
