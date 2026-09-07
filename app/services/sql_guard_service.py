from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.core.exceptions import AppError

SAFE_FUNCTIONS = {
    "SUM",
    "COUNT",
    "AVG",
    "MIN",
    "MAX",
    "COALESCE",
    "CAST",
    "DATE_TRUNC",
    "TIMESTAMP_TRUNC",
    "AND",
}


def validate_readonly_sql(sql, allowed_objects, allowed_columns):
    def reject():
        raise AppError("NL2SQL_UNSAFE_QUERY", "Query tidak memenuhi kebijakan SELECT semantic.")

    try:
        statements = parse(sql, read="postgres")
    except ParseError:
        reject()
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        reject()
    tree = statements[0]
    if any(node.comments for node in tree.walk()):
        reject()
    if tree.args.get("into") or tree.args.get("locks") or tree.args.get("with_"):
        reject()
    # The supported plan compiler emits a single select over one semantic view, without subqueries or joins.
    if len(list(tree.find_all(exp.Select))) != 1 or list(tree.find_all(exp.Join)):
        reject()
    tables = list(tree.find_all(exp.Table))
    if len(tables) != 1 or any(t.catalog or f"{t.db}.{t.name}" not in allowed_objects for t in tables):
        reject()
    aliases = {a.alias for a in tree.find_all(exp.Alias)}
    for column in tree.find_all(exp.Column):
        if column.name not in allowed_columns | aliases:
            reject()
    if list(tree.find_all(exp.Star)):
        reject()
    for func in tree.find_all(exp.Func):
        name = func.name.upper() if isinstance(func, exp.Anonymous) else func.sql_name().upper()
        if name not in SAFE_FUNCTIONS:
            reject()
    if not tree.args.get("limit"):
        reject()
    return tree.sql(dialect="postgres")
