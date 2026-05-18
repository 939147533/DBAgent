from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .database_agent import AgentConfigurationError, get_database_agent_assistant, reset_database_agent_assistant
from .cache import result_cache
from .database import DatabaseConfigurationError, create_database_client
from .exporters import export_csv, export_insert_sql, export_xlsx
from .models import (
    DatabaseProfile,
    DatabaseProfilesPayload,
    DatabaseSettings,
    ExportFormat,
    LLMProfile,
    LLMProfilesPayload,
    LLMSettings,
    PublicDatabaseProfilesPayload,
    PublicLLMProfilesPayload,
    QueryRequest,
    QueryResponse,
    ResultCacheEntry,
    SchemaResponse,
    TestConnectionResponse,
)
from .settings_store import (
    load_settings,
    public_database_profiles,
    public_database_settings,
    public_llm_profiles,
    public_llm_settings,
    save_database_profiles,
    save_database_settings,
    save_llm_profiles,
    save_llm_settings,
)
from .sql_safety import UnsafeSqlError, apply_row_limit, infer_export_table_name

app = FastAPI(title="Dataset Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/settings/database")
def get_database_settings() -> DatabaseSettings:
    return public_database_settings(load_settings().database)


@app.put("/api/settings/database")
def put_database_settings(settings: DatabaseSettings) -> DatabaseSettings:
    current = load_settings().database
    if settings.password == "********":
        settings.password = current.password
    saved = save_database_settings(settings)
    reset_database_agent_assistant()
    return public_database_settings(saved.database)


@app.get("/api/settings/database/profiles")
def get_database_setting_profiles() -> PublicDatabaseProfilesPayload:
    return public_database_profiles(load_settings())


@app.put("/api/settings/database/profiles")
def put_database_setting_profiles(payload: DatabaseProfilesPayload) -> PublicDatabaseProfilesPayload:
    saved = save_database_profiles(payload)
    reset_database_agent_assistant()
    return public_database_profiles(saved)


@app.post("/api/settings/database/test")
def test_database_settings(settings: DatabaseProfile | None = None) -> TestConnectionResponse:
    try:
        stored = load_settings()
        db_settings = settings or DatabaseProfile(**stored.database.model_dump())
        if db_settings.password == "********":
            matched = next((profile for profile in stored.database_profiles if profile.id == db_settings.id), None)
            if matched is None:
                matched = next((profile for profile in stored.database_profiles if profile.id == stored.active_database_id), None)
            if matched is not None:
                db_settings.password = matched.password
        client = create_database_client(db_settings)
        message = client.test()
        return TestConnectionResponse(ok=True, message=message)
    except Exception as exc:
        return TestConnectionResponse(ok=False, message=str(exc))


@app.get("/api/settings/llm")
def get_llm_settings() -> LLMSettings:
    return public_llm_settings(load_settings().llm)


@app.put("/api/settings/llm")
def put_llm_settings(settings: LLMSettings) -> LLMSettings:
    current = load_settings().llm
    if settings.api_key == "********":
        settings.api_key = current.api_key
    saved = save_llm_settings(settings)
    reset_database_agent_assistant()
    return public_llm_settings(saved.llm)


@app.get("/api/settings/llm/profiles")
def get_llm_setting_profiles() -> PublicLLMProfilesPayload:
    return public_llm_profiles(load_settings())


@app.put("/api/settings/llm/profiles")
def put_llm_setting_profiles(payload: LLMProfilesPayload) -> PublicLLMProfilesPayload:
    saved = save_llm_profiles(payload)
    reset_database_agent_assistant()
    return public_llm_profiles(saved)


@app.post("/api/settings/llm/test")
def test_llm_settings(settings: LLMProfile | None = None) -> TestConnectionResponse:
    try:
        stored = load_settings()
        llm_settings = settings or LLMProfile(**stored.llm.model_dump())
        if llm_settings.api_key == "********":
            matched = next((profile for profile in stored.llm_profiles if profile.id == llm_settings.id), None)
            if matched is None:
                matched = next((profile for profile in stored.llm_profiles if profile.id == stored.active_llm_id), None)
            if matched is not None:
                llm_settings.api_key = matched.api_key
        if not llm_settings.api_key or not llm_settings.model:
            raise AgentConfigurationError("大模型 API Key 或模型名称未配置")
        return TestConnectionResponse(ok=True, message="配置格式有效")
    except Exception as exc:
        return TestConnectionResponse(ok=False, message=str(exc))


@app.get("/api/schema")
def get_schema() -> SchemaResponse:
    try:
        client = create_database_client(load_settings().database)
        return SchemaResponse(columns=client.list_schema())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/query", response_model=QueryResponse)
def query_database(request: QueryRequest) -> QueryResponse:
    settings = load_settings()
    try:
        print("🔄 获取数据库智能体实例...")
        # 使用 DatabaseAgent（ReActAgent）执行查询
        client = create_database_client(settings.database)
        agent = get_database_agent_assistant()
        generated_sql = agent.run(request.question, max_rows=request.max_rows)
        limited_sql = apply_row_limit(generated_sql, request.max_rows)
        started = time.perf_counter()
        result = client.execute(limited_sql, max_rows=request.max_rows)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        # sql = result.get("sql", "")
        # columns = result.get("columns", [])
        # rows = result.get("rows", [])
        # elapsed_ms = result.get("elapsed_ms", 0)
        # warnings = result.get("warnings", [])
        entry = ResultCacheEntry(
            sql=generated_sql,
            columns=result["columns"],
            rows=result["rows"],
            inferred_table_name=infer_export_table_name(generated_sql),
        )
        query_id = result_cache.set(entry)
        return QueryResponse(
            query_id=query_id,
            sql=generated_sql,
            columns=result["columns"],
            rows=result["rows"],
            row_count=len(result["rows"]),
            elapsed_ms=elapsed_ms,
            warnings=[] if limited_sql == generated_sql else ["已自动限制最大返回行数"],
        )
    except (UnsafeSqlError, AgentConfigurationError, DatabaseConfigurationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/query/{query_id}/export")
def export_query(
    query_id: str,
    format: ExportFormat = Query(...),
    table_name: str = Query(default="QUERY_RESULT_EXPORT"),
) -> Response:
    entry = result_cache.get(query_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="查询结果不存在或已过期")
    try:
        if format == ExportFormat.csv:
            return Response(
                content=export_csv(entry),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="query-result.csv"'},
            )
        if format == ExportFormat.xlsx:
            return Response(
                content=export_xlsx(entry),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": 'attachment; filename="query-result.xlsx"'},
            )
        content = export_insert_sql(entry, table_name or entry.inferred_table_name)
        return Response(
            content=content,
            media_type="application/sql; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="query-result.sql"'},
        )
    except UnsafeSqlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
