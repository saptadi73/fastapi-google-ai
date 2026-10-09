from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.configuration import Configuration
from app.models.semantic import DataProduct, JoinRelationship, SavedQuery
from app.models.source import DataSource, SourceSheet
from app.repositories.base import record
from app.repositories.semantic_repository import SemanticRepository
from app.schemas.semantic import QueryPlan
from app.services.audit_service import audit
from app.services.query_execution_service import QueryExecutionService


def normalize_intent(question):
    return " ".join(question.casefold().strip().rstrip("?!.").split())


class SemanticCatalogService:
    def __init__(self, session, user):
        self.session, self.user = session, user
        self.repo = SemanticRepository(session, user.tenant_id)

    async def update_product(self, product_id, data):
        product = await self.repo.get(DataProduct, product_id, lock=True)
        if data.expected_version is not None and product.version != data.expected_version:
            raise AppError("PRODUCT_VERSION_CONFLICT", "Versi produk berubah; muat ulang katalog dan tinjau edit lokal.", 409)
        changes = data.model_dump(mode="json", exclude_none=True, exclude={"expected_version", "metric_metadata"})
        if data.metric_metadata is not None:
            metrics = [dict(metric) for metric in product.metrics]
            by_code = {metric["code"]: metric for metric in metrics}
            for update in data.metric_metadata:
                if update.code not in by_code:
                    raise AppError("METRIC_NOT_FOUND", "Kode metrik tidak tersedia pada produk ini.", 422)
                by_code[update.code].update(update.model_dump(exclude_unset=True, exclude={"code"}))
            # Aliases aid discovery; never resolve an ambiguous label to an arbitrary metric.
            for metric in metrics:
                for synonym in metric.get("synonyms", []):
                    normalized = " ".join(synonym.casefold().split())
                    for other in metrics:
                        if other["code"] == metric["code"]:
                            continue
                        labels = [other["code"], other.get("label", ""), *other.get("synonyms", [])]
                        if normalized in {" ".join(label.casefold().split()) for label in labels}:
                            raise AppError("METRIC_SYNONYM_CONFLICT", "Sinonim bertabrakan dengan metrik lain dalam produk.", 422)
            changes["metrics"] = metrics
        for key, value in changes.items():
            setattr(product, key, value)
        product.version += 1
        audit(self.session, self.user, "data_product.updated", product.id,
              changed_fields=sorted(changes), semantic_version=product.version)
        return record(product, exclude=("view_name",))

    async def create_join_relationship(self, data):
        left = await self.repo.product(data.left_product_code, self.user)
        right = await self.repo.product(data.right_product_code, self.user)
        if left.id == right.id:
            raise AppError("JOIN_PRODUCT_INVALID", "Relationship harus menghubungkan dua product berbeda.", 422)
        for product, column in ((left, data.left_column), (right, data.right_column)):
            view = await self.repo.product_record(product.code, self.user)
            columns = {item["target_column"]: item for item in view["columns"]}
            selected = columns.get(column)
            if selected is None:
                raise AppError("JOIN_COLUMN_INVALID", "Kolom relationship tidak tersedia pada product.", 422)
            if selected.get("access_visibility") == "MASKED" or selected.get("pii_classification") in ("MEDIUM", "HIGH"):
                raise AppError("QUERY_JOIN_FORBIDDEN", "Join pada kolom non-visible tidak diizinkan.", 403)
        obj = await self.repo.add(
            JoinRelationship, **data.model_dump(), created_by=self.user.id
        )
        audit(self.session, self.user, "join_relationship.created", obj.id)
        return record(obj)

    async def update_join_relationship(self, relationship_id, data):
        obj = await self.repo.get(JoinRelationship, relationship_id, lock=True)
        if obj.revision_no != data.revision_no or obj.status != "DRAFT":
            raise AppError("JOIN_RELATIONSHIP_REVISION_CONFLICT", "Relationship berubah atau bukan draft.", 409)
        left = await self.repo.product(data.left_product_code, self.user)
        right = await self.repo.product(data.right_product_code, self.user)
        if left.id == right.id:
            raise AppError("JOIN_PRODUCT_INVALID", "Relationship harus menghubungkan dua product berbeda.", 422)
        for product, column in ((left, data.left_column), (right, data.right_column)):
            view = await self.repo.product_record(product.code, self.user)
            selected = next((item for item in view["columns"] if item["target_column"] == column), None)
            if selected is None:
                raise AppError("JOIN_COLUMN_INVALID", "Kolom relationship tidak tersedia pada product.", 422)
            if selected.get("access_visibility") == "MASKED" or selected.get("pii_classification") in ("MEDIUM", "HIGH"):
                raise AppError("QUERY_JOIN_FORBIDDEN", "Join pada kolom non-visible tidak diizinkan.", 403)
        for key, value in data.model_dump(exclude={"revision_no"}).items():
            setattr(obj, key, value)
        obj.revision_no += 1
        obj.approved_by = None
        audit(self.session, self.user, "join_relationship.updated", obj.id, revision_no=obj.revision_no)
        return record(obj)

    async def approve_join_relationship(self, relationship_id, data):
        obj = await self.repo.get(JoinRelationship, relationship_id, lock=True)
        if obj.revision_no != data.revision_no or obj.status != "DRAFT":
            raise AppError("JOIN_RELATIONSHIP_REVISION_CONFLICT", "Relationship berubah atau bukan draft.", 409)
        for product_code, column in (
            (obj.left_product_code, obj.left_column),
            (obj.right_product_code, obj.right_column),
        ):
            view = await self.repo.product_record(product_code, self.user)
            selected = next((item for item in view["columns"] if item["target_column"] == column), None)
            if selected is None:
                raise AppError("QUERY_JOIN_STALE", "Kolom join tidak lagi tersedia atau tidak dapat diakses.", 409)
            if selected.get("access_visibility") == "MASKED" or selected.get("pii_classification") in ("MEDIUM", "HIGH"):
                raise AppError("QUERY_JOIN_FORBIDDEN", "Join pada kolom non-visible tidak diizinkan.", 403)
        obj.status, obj.approved_by = "APPROVED", self.user.id
        obj.revision_no += 1
        audit(self.session, self.user, "join_relationship.approved", obj.id, revision_no=obj.revision_no)
        return record(obj)

    async def reject_join_relationship(self, relationship_id, data):
        obj = await self.repo.get(JoinRelationship, relationship_id, lock=True)
        if obj.revision_no != data.revision_no or obj.status != "DRAFT":
            raise AppError("JOIN_RELATIONSHIP_REVISION_CONFLICT", "Relationship berubah atau bukan draft.", 409)
        obj.status, obj.revision_no = "REJECTED", obj.revision_no + 1
        audit(self.session, self.user, "join_relationship.rejected", obj.id, revision_no=obj.revision_no)
        return record(obj)

    async def validate_saved(self, template_id):
        obj = await self.repo.get(SavedQuery, template_id, lock=True)
        product = await self.repo.product(obj.data_product_code, self.user)
        plan = QueryPlan.model_validate(obj.plan)
        await QueryExecutionService(self.session, self.user).compile(product.code, plan)
        obj.status, obj.semantic_version = "VALIDATED", product.version
        audit(self.session, self.user, "query_template.validated", obj.id)
        return record(obj)

    async def activate_saved(self, template_id):
        obj = await self.repo.get(SavedQuery, template_id, lock=True)
        product = await self.repo.product(obj.data_product_code, self.user)
        if obj.status != "VALIDATED" or obj.semantic_version != product.version:
            raise AppError(
                "TEMPLATE_VALIDATION_REQUIRED", "Validasi template terhadap semantic version terkini.", 409
            )
        obj.status = "ACTIVE"
        audit(self.session, self.user, "query_template.activated", obj.id)
        return record(obj)

    async def products(self):
        products = list((await self.session.execute(
            self.repo.visible_products().add_columns(DataSource)
            .order_by(DataProduct.created_at.desc()).limit(1000)
        )).all())
        result = []
        for product, source in products:
            if self.user.role not in product.allowed_roles:
                continue
            if not await self.repo.source_allowed(source, self.user, "DISCOVER"):
                continue
            result.append(await self.repo.product_record(product.code, self.user))
        return result

    async def product_inventory(self):
        """List active ETL outputs with their source tab and database locations."""
        accessible = await self.products()
        product_ids = [item["id"] for item in accessible]
        if not product_ids:
            return []
        rows = (await self.session.execute(
            select(DataProduct, SourceSheet, DataSource, Configuration)
            .join(
                SourceSheet,
                (SourceSheet.id == DataProduct.source_sheet_id)
                & (SourceSheet.tenant_id == DataProduct.tenant_id),
            )
            .join(
                DataSource,
                (DataSource.id == SourceSheet.source_id)
                & (DataSource.tenant_id == SourceSheet.tenant_id),
            )
            .join(
                Configuration,
                (Configuration.id == SourceSheet.active_configuration_id)
                & (Configuration.tenant_id == SourceSheet.tenant_id),
            )
            .where(
                DataProduct.tenant_id == self.user.tenant_id,
                DataProduct.id.in_(product_ids),
                DataProduct.status == "ACTIVE",
                Configuration.status == "ACTIVE",
            )
            .order_by(DataProduct.name, DataSource.name, SourceSheet.sheet_name)
        )).all()
        products_by_id = {item["id"]: item for item in accessible}
        inventory = []
        for product, sheet, source, config in rows:
            product_data = products_by_id.get(str(product.id))
            if product_data is None:
                continue
            sheet_uuid = str(sheet.id).replace("-", "")
            target_table = config.configuration_json["target_table"]
            inventory.append({
                **product_data,
                "source_id": source.id,
                "source_name": source.name,
                "source_code": source.source_code,
                "spreadsheet_id": source.spreadsheet_id,
                "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{source.spreadsheet_id}/edit",
                "sheet_name": sheet.sheet_name,
                "sheet_id": sheet.sheet_id,
                "source_sheet_id": sheet.id,
                "source_enabled": sheet.enabled,
                "source_present": sheet.is_present,
                "database_schema": "trusted",
                "database_table": f"{target_table}_{sheet_uuid}",
                "semantic_view": product.view_name,
                "configuration_id": config.id,
                "configuration_version": config.version_no,
                "configuration_revision": config.revision_no,
                "configuration_status": config.status,
                "freshness_version": product.freshness_version,
            })
        return inventory

    async def join_relationships(self):
        product_codes = {product["code"] for product in await self.products()}
        relationships = await self.repo.list(JoinRelationship)
        return [
            record(item)
            for item in relationships
            if item.left_product_code in product_codes and item.right_product_code in product_codes
        ]

    async def create_saved(self, data):
        product = await self.repo.product(data.data_product_code, self.user)
        await QueryExecutionService(self.session, self.user).compile(product.code, data.plan)
        obj = await self.repo.add(
            SavedQuery,
            code=data.code,
            data_product_code=product.code,
            plan=data.plan.model_dump(mode="json"),
            examples=[normalize_intent(e) for e in data.examples],
            allowed_roles=[r.value for r in data.allowed_roles],
            semantic_version=product.version,
            created_by=self.user.id,
        )
        audit(self.session, self.user, "saved_query.created", obj.id)
        return record(obj)

    async def saved(self, code):
        obj = await self.session.scalar(
            self.repo.query(SavedQuery).where(SavedQuery.code == code, SavedQuery.status == "ACTIVE")
        )
        if obj is None or self.user.role not in obj.allowed_roles:
            raise AppError("SAVED_QUERY_NOT_FOUND", "Saved query tidak tersedia.", 404)
        product = await self.repo.product(obj.data_product_code, self.user)
        if product.version != obj.semantic_version:
            raise AppError("TEMPLATE_STALE", "Schema berubah; validasi ulang saved query.", 409)
        return obj
