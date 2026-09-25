from app.core.exceptions import AppError
from app.models.semantic import DataProduct, SavedQuery
from app.repositories.base import TenantRepository


class SemanticRepository(TenantRepository):
    async def matching_templates(self, intent, user, product_code=None):
        query = self.query(SavedQuery).join(DataProduct,
            (DataProduct.tenant_id == SavedQuery.tenant_id) & (DataProduct.code == SavedQuery.data_product_code)
        ).where(SavedQuery.status == "ACTIVE", DataProduct.status == "ACTIVE",
                SavedQuery.examples.contains([intent]), SavedQuery.allowed_roles.contains([user.role]),
                DataProduct.allowed_roles.contains([user.role]))
        if product_code:
            query = query.where(SavedQuery.data_product_code == product_code)
        return list((await self.session.scalars(query.order_by(SavedQuery.code).limit(21))).all())

    async def product(self, code, user):
        obj = await self.session.scalar(
            self.query(DataProduct).where(DataProduct.code == code, DataProduct.status == "ACTIVE")
        )
        if obj is None or user.role not in obj.allowed_roles:
            raise AppError("DATA_PRODUCT_NOT_FOUND", "Data product tidak tersedia untuk akses Anda.", 404)
        return obj
