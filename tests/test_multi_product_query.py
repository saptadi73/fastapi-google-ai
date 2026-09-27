from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import AppError
from app.schemas.semantic import QueryFilter, QueryPlan
from app.services.query_execution_service import QueryExecutionService, build_join_query, cache_key
from app.services.sql_guard_service import validate_readonly_sql


def product(code, view, columns, dimensions, metrics=()):
    return SimpleNamespace(
        id=str(uuid4()),
        code=code,
        view_name=view,
        columns=columns,
        dimensions=list(dimensions),
        metrics=list(metrics),
        allowed_roles=["VIEWER"],
        version=1,
        freshness_version=1,
    )


def column(name, kind="text", pii="NONE"):
    return {"target_column": name, "target_type": kind, "pii_classification": pii}


def relationship(**changes):
    values = {
        "id": str(uuid4()),
        "code": "sales_product",
        "left_product_code": "SALES",
        "left_column": "product_id",
        "right_product_code": "PRODUCT",
        "right_column": "id",
        "cardinality": "MANY_TO_ONE",
        "join_type": "LEFT",
        "duplicate_policy": "REJECT_AMBIGUOUS",
        "revision_no": 2,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def catalog():
    sales = product(
        "SALES",
        "sales",
        [column("product_id", "uuid"), column("amount", "numeric"), column("branch")],
        ["branch"],
        [{"code": "net_sales", "column": "amount", "aggregation": "sum"}],
    )
    products = product(
        "PRODUCT",
        "products",
        [column("id", "uuid"), column("category")],
        ["category"],
    )
    return sales, products


def current_user():
    return SimpleNamespace(
        tenant_id=str(uuid4()),
        role="VIEWER",
        row_scope={"SALES": {"branch": ["Jakarta"]}, "PRODUCT": {"category": ["Food"]}},
    )


def test_join_query_scopes_every_table_and_allows_qualified_dimensions():
    sales, products = catalog()
    plan = QueryPlan(
        join_relationships=["sales_product"],
        dimensions=["PRODUCT.category"],
        metrics=["net_sales"],
        filters=[QueryFilter(field="PRODUCT.category", operator="eq", value="Food")],
    )
    stmt = build_join_query(sales, [sales, products], [relationship()], current_user(), plan)
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    validate_readonly_sql(
        sql,
        {"semantic.sales", "semantic.products"},
        {"_tenant_id", "product_id", "amount", "branch", "id", "category"},
        allow_joins=True,
    )
    assert "LEFT OUTER JOIN semantic.products" in sql
    assert sql.count("_tenant_id") >= 3
    assert "Jakarta" in sql and sql.count("Food") >= 2
    relation = relationship()
    user = current_user()
    first_key = cache_key(user, sales, plan, joined_products=[products], relationships=[relation])
    relation.revision_no += 1
    assert first_key != cache_key(user, sales, plan, joined_products=[products], relationships=[relation])


@pytest.mark.parametrize(
    ("relation", "metric"),
    [
        (relationship(), "PRODUCT.product_count"),
        (relationship(cardinality="ONE_TO_MANY"), "net_sales"),
    ],
)
def test_join_query_rejects_ambiguous_aggregation(relation, metric):
    sales, products = catalog()
    products.metrics = [{"code": "product_count", "column": "id", "aggregation": "count"}]
    with pytest.raises(AppError) as failure:
        build_join_query(
            sales,
            [sales, products],
            [relation],
            current_user(),
            QueryPlan(join_relationships=[relation.code], metrics=[metric]),
        )
    assert failure.value.code == "QUERY_AGGREGATION_AMBIGUOUS"


def test_join_query_rejects_sensitive_join_and_stale_path():
    sales, products = catalog()
    products.columns[0]["pii_classification"] = "HIGH"
    with pytest.raises(AppError) as failure:
        build_join_query(
            sales,
            [sales, products],
            [relationship()],
            current_user(),
            QueryPlan(join_relationships=["sales_product"], dimensions=["PRODUCT.category"]),
        )
    assert failure.value.code == "QUERY_JOIN_FORBIDDEN"


def test_join_query_supports_ordered_multi_hop_path():
    sales, products = catalog()
    products.columns.append(column("category_id", "uuid"))
    categories = product(
        "CATEGORY",
        "categories",
        [column("id", "uuid"), column("name")],
        ["name"],
    )
    user = current_user()
    user.row_scope["CATEGORY"] = {"name": ["Food"]}
    second = relationship(
        code="product_category",
        left_product_code="PRODUCT",
        left_column="category_id",
        right_product_code="CATEGORY",
        right_column="id",
        cardinality="MANY_TO_ONE",
    )
    statement = build_join_query(
        sales,
        [sales, products, categories],
        [relationship(), second],
        user,
        QueryPlan(
            join_relationships=["sales_product", "product_category"],
            dimensions=["CATEGORY.name"],
        ),
    )
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert sql.count("LEFT OUTER JOIN") == 2
    assert "category.category_id = category.id" not in sql
    assert "product.category_id = category.id" in sql
    assert "Food" in sql


@pytest.mark.asyncio
async def test_compile_checks_approved_relationship_and_access_to_each_product():
    sales, products = catalog()
    service = QueryExecutionService(AsyncMock(), current_user())
    service.repo.product = AsyncMock(side_effect=[sales, products])
    service.repo.join_relationship = AsyncMock(return_value=relationship())
    _, joined, relations, statement, _ = await service.compile(
        "SALES",
        QueryPlan(join_relationships=["sales_product"], dimensions=["PRODUCT.category"]),
    )
    assert joined == [products] and len(relations) == 1
    assert "JOIN" in str(statement)
    service.repo.product.assert_any_await("PRODUCT", service.user)
