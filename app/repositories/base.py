from sqlalchemy import select

from app.core.exceptions import AppError


class TenantRepository:
    def __init__(self, session, tenant_id: str):
        self.session, self.tenant_id = session, tenant_id

    def query(self, model):
        return select(model).where(model.tenant_id == self.tenant_id)

    async def get(self, model, object_id, *, lock=False):
        query = self.query(model).where(model.id == str(object_id))
        if lock:
            query = query.with_for_update()
        obj = await self.session.scalar(query)
        if obj is None:
            raise AppError("RESOURCE_NOT_FOUND", "Data tidak ditemukan.", 404)
        return obj

    async def list(self, model, *, offset=0, limit=100, conditions=()):
        return list(
            (
                await self.session.scalars(
                    self.query(model)
                    .where(*conditions)
                    .order_by(model.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )

    async def add(self, model, **values):
        obj = model(tenant_id=self.tenant_id, **values)
        self.session.add(obj)
        await self.session.flush()
        return obj


def record(obj, exclude=()):
    return {col.key: getattr(obj, col.key) for col in obj.__table__.columns if col.key not in exclude}
