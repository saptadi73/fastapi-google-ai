from sqlalchemy import or_

from app.core.exceptions import AppError
from app.models.semantic import DataProduct, JoinRelationship, SavedQuery
from app.models.source import DataSource, SourceSheet
from app.repositories.base import TenantRepository, record
from app.schemas.access import AccessEvaluationRequest
from app.services.access_service import AccessService
from app.services.profiling_service import digest


class SemanticRepository(TenantRepository):
    def __init__(self, session, tenant_id):
        super().__init__(session, tenant_id)
        self.authorization_revisions = set()
        self.product_access_decisions = {}

    def _remember_decision(self, resource_type, resource_id, action, decision):
        controls = {
            "allowed": decision.get("allowed", False),
            "reason": decision.get("reason"),
            "row_scope": decision.get("row_scope", {}),
            "columns": decision.get("columns", {}),
            "export_allowed": decision.get("export_allowed", False),
        }
        self.authorization_revisions.add(
            (f"decision:{resource_type}:{resource_id}:{action}:{digest(controls)}", 1)
        )

    async def source_allowed(self, source, user, action):
        self.authorization_revisions.add((f"source:{source.id}", source.access_revision))
        if source.access_metadata is None:
            return True
        if source.access_status != "POLICY_APPROVED":
            return False
        decision = await AccessService(self.session, user).evaluate(
            AccessEvaluationRequest(
                action=action, resource_type="SOURCE", resource_id=source.source_code
            )
        )
        self.authorization_revisions.update(
            (item["id"], item["revision"]) for item in decision.get("policy_revisions", [])
        )
        self._remember_decision("SOURCE", source.source_code, action, decision)
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
        obj, _ = await self._product_access(code, user, action)
        return obj

    async def _product_access(self, code, user, action):
        decision = None
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
        if source.access_metadata is not None:
            decision = await AccessService(self.session, user).evaluate(
                AccessEvaluationRequest(
                    action=action, resource_type="DATA_PRODUCT", resource_id=obj.code
                )
            )
            self.authorization_revisions.update(
                (item["id"], item["revision"]) for item in decision.get("policy_revisions", [])
            )
            self._remember_decision("DATA_PRODUCT", obj.code, action, decision)
            if not decision["allowed"]:
                raise AppError("DATA_PRODUCT_NOT_FOUND", "Data product tidak tersedia untuk akses Anda.", 404)
            self.product_access_decisions[obj.code] = decision
        return obj, decision

    @staticmethod
    def _sanitize_product(obj, decision):
        if hasattr(obj, "__table__"):
            payload = record(obj, exclude=("view_name",))
        else:
            payload = {key: value for key, value in vars(obj).items() if key != "view_name"}
        if not decision:
            return payload
        visibility = dict(decision.get("columns", {}))
        columns = []
        hidden_columns = set()
        for column in payload.get("columns", []):
            field = column["target_column"]
            rule = visibility.get(field)
            if column.get("pii_classification") in ("MEDIUM", "HIGH") and rule is None:
                rule = "HIDDEN"
            if rule == "HIDDEN":
                hidden_columns.add(field)
                continue
            item = dict(column)
            if rule == "MASKED":
                item["access_visibility"] = "MASKED"
            columns.append(item)
        payload["columns"] = columns
        payload["dimensions"] = [field for field in payload.get("dimensions", []) if field not in hidden_columns]
        payload["metrics"] = [
            metric for metric in payload.get("metrics", [])
            if metric.get("column") not in hidden_columns
        ]
        return payload

    async def product_record(self, code, user, *, action="DISCOVER"):
        obj, decision = await self._product_access(code, user, action)
        return self._sanitize_product(obj, decision)

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
