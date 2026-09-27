from sqlalchemy import or_

from app.core.exceptions import AppError
from app.models.semantic import DataProduct, JoinRelationship, SavedQuery
from app.models.source import DataSource, SourceSheet
from app.repositories.base import TenantRepository
from app.schemas.access import AccessEvaluationRequest
from app.services.access_service import AccessService


class SemanticRepository(TenantRepository):
    async def source_allowed(self, source, user, action):
        if source.access_metadata is None:
            return True
        if source.access_status != "POLICY_APPROVED":
            return False
        decision = await AccessService(self.session, user).evaluate(
            AccessEvaluationRequest(
                action=action, resource_type="SOURCE", resource_id=source.source_code
            )
        )
        return (
            decision["allowed"]
            and not decision["row_scope"]
            and not decision["columns"]
            and (action != "EXPORT" or decision["export_allowed"])
        )

    def visible_products(self):
        return (
            self.query(DataProduct)
            .join(SourceSheet, (SourceSheet.id == DataProduct.source_sheet_id)
                  & (SourceSheet.tenant_id == self.tenant_id))
            .join(DataSource, (DataSource.id == SourceSheet.source_id)
                  & (DataSource.tenant_id == self.tenant_id))
            .where(
                DataProduct.status == "ACTIVE",
                or_(DataSource.access_metadata.is_(None), DataSource.access_status == "POLICY_APPROVED"),
            )
        )

    async def matching_templates(self, intent, user, product_code=None):
        query = self.query(SavedQuery).join(DataProduct,
            (DataProduct.tenant_id == SavedQuery.tenant_id) & (DataProduct.code == SavedQuery.data_product_code)
        ).join(SourceSheet, (SourceSheet.id == DataProduct.source_sheet_id)
               & (SourceSheet.tenant_id == self.tenant_id)
        ).join(DataSource, (DataSource.id == SourceSheet.source_id)
               & (DataSource.tenant_id == self.tenant_id)
        ).where(SavedQuery.status == "ACTIVE", DataProduct.status == "ACTIVE",
                or_(DataSource.access_metadata.is_(None), DataSource.access_status == "POLICY_APPROVED"),
                SavedQuery.examples.contains([intent]), SavedQuery.allowed_roles.contains([user.role]),
                DataProduct.allowed_roles.contains([user.role]))
        if product_code:
            query = query.where(SavedQuery.data_product_code == product_code)
        return list((await self.session.scalars(query.order_by(SavedQuery.code).limit(21))).all())

    async def product(self, code, user, *, action="DISCOVER"):
        obj = await self.session.scalar(
            self.visible_products().where(DataProduct.code == code)
        )
        if obj is None or user.role not in obj.allowed_roles:
            raise AppError("DATA_PRODUCT_NOT_FOUND", "Data product tidak tersedia untuk akses Anda.", 404)
        source = await self.session.scalar(
            self.query(DataSource).join(
                SourceSheet, (SourceSheet.source_id == DataSource.id)
                & (SourceSheet.tenant_id == self.tenant_id)
            ).where(SourceSheet.id == obj.source_sheet_id)
        )
        if source is None or not await self.source_allowed(source, user, action):
            raise AppError("DATA_PRODUCT_NOT_FOUND", "Data product tidak tersedia untuk akses Anda.", 404)
        return obj

    async def join_relationship(self, code):
        obj = await self.session.scalar(
            self.query(JoinRelationship).where(
                JoinRelationship.code == code, JoinRelationship.status == "APPROVED"
            )
        )
        if obj is None:
            raise AppError("QUERY_JOIN_NOT_FOUND", "Join relationship approved tidak tersedia.", 404)
        return obj

    async def approved_join_relationships(self):
        return list(
            (
                await self.session.scalars(
                    self.query(JoinRelationship)
                    .where(JoinRelationship.status == "APPROVED")
                    .order_by(JoinRelationship.code)
                    .limit(100)
                )
            ).all()
        )
