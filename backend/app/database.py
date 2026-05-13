from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from .models import DatabaseSettings, DatabaseType, SchemaColumn, TableColumn


class DatabaseConfigurationError(RuntimeError):
    pass


class BaseDatabaseClient:
    def __init__(self, settings: DatabaseSettings) -> None:
        self.settings = settings

    @contextmanager
    def connect(self) -> Iterator[Any]:
        raise NotImplementedError

    def test(self) -> str:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.fetchone()
        return "连接成功"

    def list_table_name(self, limit: int=4000) -> list[TableColumn]:
        sql = """
                SELECT ut.table_name, utc.comments 
                from user_tables ut 
                left join user_tab_comments utc
                  on ut.table_name = utc.table_name 
                order by ut.table_name
                """
        rows = self.execute(sql, max_rows=limit)["rows"]
        return [
            TableColumn(table_name=str(row[0]), table_comments=str(row[1] or ""))
            for row in rows
        ]

    # def list_schema(self, limit: int = 300) -> list[SchemaColumn]:
    #     sql = """
    #     SELECT utc.table_name, utc.column_name, utc.data_type, NVL(ucc.comments, '') AS comments
    #     FROM user_tab_columns utc
    #     LEFT JOIN user_col_comments ucc
    #       ON utc.table_name = ucc.table_name AND utc.column_name = ucc.column_name
    #     ORDER BY utc.table_name, utc.column_id
    #     """
    #     rows = self.execute(sql, max_rows=limit)["rows"]
    #     return [
    #         SchemaColumn(table_name=str(row[0]), column_name=str(row[1]), data_type=str(row[2]), comments=str(row[3] or ""))
    #         for row in rows
    #     ]

    def list_schema(self, table_names: list[str], limit: int = 300) -> list[SchemaColumn]:
        placeholders = ', '.join(['?'] * len(table_names))
        sql = f"""
        SELECT utc.table_name, utc.column_name, utc.data_type, NVL(ucc.comments, '') AS comments
        FROM user_tab_columns utc
        LEFT JOIN user_col_comments ucc
          ON utc.table_name = ucc.table_name AND utc.column_name = ucc.column_name
        WHERE utc.table_name IN ({placeholders})
        ORDER BY utc.table_name, utc.column_id
        """
        rows = self.execute(sql, max_rows=limit)["rows"]
        return [
            SchemaColumn(table_name=str(row[0]), column_name=str(row[1]), data_type=str(row[2]), comments=str(row[3] or ""))
            for row in rows
        ]

    def execute(self, sql: str, max_rows: int = 100) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(sql)
            rows = cursor.fetchmany(max_rows)
            columns = [description[0] for description in cursor.description or []]
            return {"columns": columns, "rows": [list(row) for row in rows]}


class OracleClient(BaseDatabaseClient):
    @contextmanager
    def connect(self) -> Iterator[Any]:
        try:
            import oracledb
        except Exception as exc:
            raise DatabaseConfigurationError("缺少 oracledb 依赖，请安装 backend/requirements.txt") from exc
        if not all([self.settings.host, self.settings.port, self.settings.service_name, self.settings.user]):
            raise DatabaseConfigurationError("Oracle 连接配置不完整")
        dsn = oracledb.makedsn(self.settings.host, self.settings.port, service_name=self.settings.service_name)
        connection = oracledb.connect(user=self.settings.user, password=self.settings.password, dsn=dsn)
        try:
            yield connection
        finally:
            connection.close()


class OceanBaseOracleClient(BaseDatabaseClient):
    @contextmanager
    def connect(self) -> Iterator[Any]:
        try:
            import jaydebeapi
        except Exception as exc:
            raise DatabaseConfigurationError("缺少 jaydebeapi/JPype1 依赖，请安装 backend/requirements.txt") from exc
        if not all([self.settings.host, self.settings.port, self.settings.service_name, self.settings.tenant, self.settings.user, self.settings.jdbc_jar_path]):
            raise DatabaseConfigurationError("OceanBase Oracle 模式连接配置不完整")
        jdbc_url = f"jdbc:oceanbase://{self.settings.host}:{self.settings.port}/{self.settings.service_name}"
        user = f"{self.settings.user}@{self.settings.tenant}"
        if self.settings.cluster:
            user = f"{user}#{self.settings.cluster}"
        connection = jaydebeapi.connect(
            "com.oceanbase.jdbc.Driver",
            jdbc_url,
            [user, self.settings.password],
            self.settings.jdbc_jar_path,
        )
        try:
            yield connection
        finally:
            connection.close()


def create_database_client(settings: DatabaseSettings) -> BaseDatabaseClient:
    if settings.db_type == DatabaseType.oracle:
        return OracleClient(settings)
    if settings.db_type == DatabaseType.oceanbase_oracle:
        return OceanBaseOracleClient(settings)
    raise DatabaseConfigurationError(f"不支持的数据库类型: {settings.db_type}")
