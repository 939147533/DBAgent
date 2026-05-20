from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class DatabaseType(str, Enum):
    oracle = "oracle"
    oceanbase_oracle = "oceanbase_oracle"


class DatabaseSettings(BaseModel):
    db_type: DatabaseType = DatabaseType.oracle
    host: str = ""
    port: int = 1521
    service_name: str = ""
    tenant: str = ""
    cluster: str = ""
    user: str = ""
    password: str = ""
    jdbc_jar_path: str = ""
    table_name_sql: str = ""


class PublicDatabaseSettings(DatabaseSettings):
    password: str = ""


class DatabaseProfile(DatabaseSettings):
    id: str = ""
    name: str = "Default database"


class PublicDatabaseProfile(DatabaseProfile):
    password: str = ""


class LLMSettings(BaseModel):
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = ""
    temperature: float = Field(default=0, ge=0, le=2)


class PublicLLMSettings(LLMSettings):
    api_key: str = ""


class LLMProfile(LLMSettings):
    id: str = ""
    name: str = "Default model"


class PublicLLMProfile(LLMProfile):
    api_key: str = ""


class SettingsPayload(BaseModel):
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    database_profiles: list[DatabaseProfile] = Field(default_factory=list)
    active_database_id: str = ""
    llm_profiles: list[LLMProfile] = Field(default_factory=list)
    active_llm_id: str = ""


class DatabaseProfilesPayload(BaseModel):
    active_id: str = ""
    profiles: list[DatabaseProfile] = Field(default_factory=list)


class PublicDatabaseProfilesPayload(BaseModel):
    active_id: str = ""
    profiles: list[PublicDatabaseProfile] = Field(default_factory=list)


class LLMProfilesPayload(BaseModel):
    active_id: str = ""
    profiles: list[LLMProfile] = Field(default_factory=list)


class PublicLLMProfilesPayload(BaseModel):
    active_id: str = ""
    profiles: list[PublicLLMProfile] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    max_rows: int = Field(default=100, ge=1, le=500)


class QueryResponse(BaseModel):
    query_id: str
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    elapsed_ms: int
    warnings: list[str] = Field(default_factory=list)


class TestConnectionResponse(BaseModel):
    ok: bool
    message: str

class TableColumn(BaseModel):
    table_name: str
    table_comments: str

class SchemaColumn(BaseModel):
    table_name: str
    column_name: str
    data_type: str
    comments: str = ""


class SchemaResponse(BaseModel):
    columns: list[SchemaColumn]


class ExportFormat(str, Enum):
    csv = "csv"
    xlsx = "xlsx"
    sql = "sql"


class ExportQueryParams(BaseModel):
    format: ExportFormat
    table_name: str = "QUERY_RESULT_EXPORT"

    @field_validator("table_name")
    @classmethod
    def normalize_table_name(cls, value: str) -> str:
        return value.strip() or "QUERY_RESULT_EXPORT"


class ResultCacheEntry(BaseModel):
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    inferred_table_name: str = "QUERY_RESULT_EXPORT"


QuerySource = Literal["agent", "manual"]
