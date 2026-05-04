import datetime as dt
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from app.exporters import export_csv, export_insert_sql, export_xlsx
from app.models import ResultCacheEntry


def sample_entry():
    return ResultCacheEntry(
        sql="select id, name, created_at, amount from orders",
        columns=["ID", "NAME", "CREATED_AT", "AMOUNT"],
        rows=[[1, "张三's order", dt.datetime(2026, 5, 3, 10, 30, 0), Decimal("12.50")], [2, None, None, None]],
        inferred_table_name="ORDERS",
    )


def test_export_csv_has_bom_and_header():
    content = export_csv(sample_entry())
    assert content.startswith("\ufeffID,NAME".encode("utf-8"))
    assert "张三".encode("utf-8") in content


def test_export_xlsx_can_be_read_back():
    content = export_xlsx(sample_entry())
    workbook = load_workbook(BytesIO(content))
    sheet = workbook.active
    assert sheet["A1"].value == "ID"
    assert sheet["B2"].value == "张三's order"


def test_export_insert_sql_escapes_values():
    text = export_insert_sql(sample_entry(), "orders_export").decode("utf-8")
    assert 'INSERT INTO ORDERS_EXPORT ("ID", "NAME", "CREATED_AT", "AMOUNT")' in text
    assert "'张三''s order'" in text
    assert "TO_TIMESTAMP" in text
    assert "NULL" in text
