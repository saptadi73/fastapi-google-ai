from app.core.exceptions import AppError
from app.schemas.semantic import QueryFilter, QueryPlan
from app.services.query_execution_service import QueryExecutionService


class ReportService:
    def __init__(self, session, user):
        self.executor = QueryExecutionService(session, user)

    async def sales(self, start_date, end_date, dimensions=None, grain="none"):
        if end_date < start_date:
            raise AppError("INVALID_PERIOD", "end_date harus setelah start_date.")
        plan = QueryPlan(
            metrics=["net_sales", "transaction_count"],
            dimensions=dimensions or [],
            time_grain=grain,
            filters=[
                QueryFilter(
                    field="transaction_date",
                    operator="between",
                    value=[start_date.isoformat(), end_date.isoformat()],
                )
            ],
        )
        return await self.executor.execute("SALES", plan)

    async def stock(self):
        return await self.executor.execute(
            "INVENTORY", QueryPlan(dimensions=["product_code", "warehouse_code"], metrics=["stock_quantity"])
        )
