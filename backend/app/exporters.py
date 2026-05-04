from __future__ import annotations

import csv
import datetime as dt
import io
from decimal import Decimal
from typing import Any

from openpyxl import Workbook

from .models import ResultCacheEntry
from .sql_safety import validate_export_table_name


def export_csv(entry: ResultCacheEntry) -> bytes:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(entry.columns)
    writer.writerows(entry.rows)
    return buffer.getvalue().encode("utf-8")


def export_xlsx(entry: ResultCacheEntry) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Query Result"
    sheet.append(entry.columns)
    for row in entry.rows:
        sheet.append([_excel_value(value) for value in row])
    for column_cells in sheet.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 10), 48)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def export_insert_sql(entry: ResultCacheEntry, table_name: str) -> bytes:
    target = validate_export_table_name(table_name or entry.inferred_table_name)
    columns = ", ".join(_quote_identifier(column) for column in entry.columns)
    lines = [f"-- Generated from natural-language query result", f"-- Source SQL: {entry.sql}", ""]
    for row in entry.rows:
        values = ", ".join(_sql_literal(value) for value in row)
        lines.append(f"INSERT INTO {target} ({columns}) VALUES ({values});")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _excel_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, dt.datetime):
        text = value.strftime("%Y-%m-%d %H:%M:%S.%f")
        return f"TO_TIMESTAMP('{text}', 'YYYY-MM-DD HH24:MI:SS.FF6')"
    if isinstance(value, dt.date):
        text = value.strftime("%Y-%m-%d")
        return f"TO_DATE('{text}', 'YYYY-MM-DD')"
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"
