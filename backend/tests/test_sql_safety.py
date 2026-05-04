import pytest

from app.sql_safety import UnsafeSqlError, apply_row_limit, infer_export_table_name, validate_export_table_name, validate_readonly_sql


def test_validate_readonly_allows_select():
    assert validate_readonly_sql("select * from users") == "select * from users"


def test_validate_readonly_allows_with():
    sql = "with t as (select * from users) select * from t"
    assert validate_readonly_sql(sql) == sql


@pytest.mark.parametrize(
    "sql",
    [
        "delete from users",
        "update users set name = 'x'",
        "drop table users",
        "select * from users; select * from orders",
        "begin null; end;",
    ],
)
def test_validate_readonly_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeSqlError):
        validate_readonly_sql(sql)


def test_apply_row_limit_wraps_query():
    assert apply_row_limit("select * from users", 10) == "SELECT * FROM (select * from users) WHERE ROWNUM <= 10"


def test_infer_export_table_name():
    assert infer_export_table_name("select * from hr.users") == "HR.USERS"
    assert infer_export_table_name("select 1 from dual") == "DUAL"


def test_validate_export_table_name():
    assert validate_export_table_name("hr.users") == "HR.USERS"
    with pytest.raises(UnsafeSqlError):
        validate_export_table_name("users;drop table x")
