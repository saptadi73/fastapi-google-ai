from app.core.exceptions import AppError
from app.models.semantic import DataProduct, SavedQuery
from app.repositories.base import record
from app.repositories.semantic_repository import SemanticRepository
from app.schemas.semantic import QueryPlan
from app.services.audit_service import audit
from app.services.query_execution_service import build_query


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

    async def validate_saved(self, template_id):
        obj = await self.repo.get(SavedQuery, template_id, lock=True)
        product = await self.repo.product(obj.data_product_code, self.user)
        build_query(product, self.user, QueryPlan.model_validate(obj.plan))
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
        products = await self.repo.list(DataProduct, limit=1000, conditions=(DataProduct.status == "ACTIVE",))
        return [record(p, exclude=("view_name",)) for p in products if self.user.role in p.allowed_roles]

    async def create_saved(self, data):
        product = await self.repo.product(data.data_product_code, self.user)
        build_query(product, self.user, data.plan)
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
