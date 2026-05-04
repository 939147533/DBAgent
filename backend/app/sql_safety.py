from __future__ import annotations

import re

import sqlparse

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|truncate|create|grant|revoke|commit|rollback|call|exec|execute)\b",
    re.IGNORECASE,
)
VALID_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*(\.[A-Za-z_][A-Za-z0-9_$#]*)?$")


class UnsafeSqlError(ValueError):
    pass


def clean_sql(sql: str) -> str:
    stripped = sqlparse.format(sql, strip_comments=True).strip()
    while stripped.endswith(";"):
        stripped = stripped[:-1].strip()
    return stripped


def validate_readonly_sql(sql: str) -> str:
    cleaned = clean_sql(sql)
    if not cleaned:
        raise UnsafeSqlError("SQL 为空")
    statements = [statement for statement in sqlparse.parse(cleaned) if str(statement).strip()]
    if len(statements) != 1:
        raise UnsafeSqlError("只允许执行单条 SQL")
    if ";" in cleaned:
        raise UnsafeSqlError("只允许执行单条 SQL，不能包含分号分隔的多语句")
    lowered = cleaned.lstrip().lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise UnsafeSqlError("只允许 SELECT 或 WITH 查询")
    if FORBIDDEN.search(cleaned):
        raise UnsafeSqlError("检测到写入、DDL 或过程调用关键字，已拒绝执行")
    if re.search(r"\bbegin\b|\bend\b|--|/\*", cleaned, re.IGNORECASE):
        raise UnsafeSqlError("不允许执行 PL/SQL 块或包含注释的 SQL")
    return cleaned


def apply_row_limit(sql: str, max_rows: int) -> str:
    safe_limit = max(1, min(int(max_rows), 500))
    cleaned = validate_readonly_sql(sql)
    if re.search(r"\b(rownum|fetch\s+first|limit)\b", cleaned, re.IGNORECASE):
        return cleaned
    return f"SELECT * FROM ({cleaned}) WHERE ROWNUM <= {safe_limit}"


def infer_export_table_name(sql: str) -> str:
    match = re.search(r"\bfrom\s+([A-Za-z_][\w$#]*(?:\.[A-Za-z_][\w$#]*)?)", sql, re.IGNORECASE)
    return match.group(1).upper() if match else "QUERY_RESULT_EXPORT"


def validate_export_table_name(table_name: str) -> str:
    normalized = table_name.strip().upper()
    if not VALID_TABLE_NAME.match(normalized):
        raise UnsafeSqlError("导出表名非法，只允许常规标识符或 schema.table")
    return normalized
