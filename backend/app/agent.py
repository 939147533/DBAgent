from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from .database import DatabaseConfigurationError, create_database_client
from .models import DatabaseSettings, LLMSettings, SchemaColumn
from .sql_safety import UnsafeSqlError, apply_row_limit, validate_readonly_sql


class AgentConfigurationError(RuntimeError):
    pass


SYSTEM_PROMPT = """你是数据库 SQL 生成与执行 Agent。
目标数据库使用 Oracle SQL 方言，OceanBase Oracle 模式也按 Oracle 方言处理。

## 工作流程
1. 使用 `GetSchema` 工具获取数据库 Schema（表名、列名、数据类型、注释）
2. 根据 Schema 生成 Oracle 只读 SQL
3. 使用 `ExecuteQuery` 工具执行 SQL 并返回结果
4. 使用 `Finish` 工具返回最终结果

## Oracle SQL 要求
- 只允许单条只读 SQL：SELECT 或 WITH ... SELECT
- 禁止 INSERT、UPDATE、DELETE、MERGE、DROP、ALTER、TRUNCATE、CREATE、PL/SQL、过程调用、多语句
- 只使用提供的 Schema 中的表和列，不要猜测不存在的表和列
- 当 `ExecuteQuery` 返回结果后，必须立即使用 `Finish` 工具返回最终结果
"""


class DatabaseAgent:
    """基于 ReActAgent 的数据库 Agent"""

    def __init__(self, db_settings: DatabaseSettings, llm_settings: LLMSettings, max_steps: int = 10):
        self.db_settings = db_settings
        self.llm_settings = llm_settings
        self.max_steps = max_steps
        self._client = None

    def _get_db_client(self):
        if self._client is None:
            self._client = create_database_client(self.db_settings)
        return self._client

    def run(self, question: str, max_rows: int = 100) -> dict[str, Any]:
        from hello_agents import HelloAgentsLLM, ReActAgent
        from hello_agents.tools import ToolRegistry

        registry = ToolRegistry()
        registry.register_function(self._tool_get_schema, name="GetSchema", description="获取数据库 Schema（表名、列名、数据类型、注释）")
        registry.register_function(self._tool_execute_query, name="ExecuteQuery", description="执行 SQL 并返回结果")

        llm = HelloAgentsLLM(
            model=self.llm_settings.model,
            api_key=self.llm_settings.api_key,
            base_url=self.llm_settings.base_url,
            temperature=self.llm_settings.temperature,
        )

        agent = ReActAgent(
            name="database-query-agent",
            llm=llm,
            registry=registry,
            system_prompt=SYSTEM_PROMPT,
            max_steps=self.max_steps,
        )

        result_text = agent.run(question)
        return self._parse_agent_result(result_text, question)

    def _tool_get_schema(self, _input: str) -> str:
        try:
            client = self._get_db_client()
            columns = client.list_schema()
            lines = []
            for col in columns:
                comment = f" -- {col.comments}" if col.comments else ""
                lines.append(f"{col.table_name}.{col.column_name} {col.data_type}{comment}")
            return "\n".join(lines) if lines else "未找到 Schema 数据。"
        except DatabaseConfigurationError as exc:
            return f"获取 Schema 失败: {exc}"
        except Exception as exc:
            return f"获取 Schema 异常: {exc}"

    def _tool_execute_query(self, sql: str) -> str:
        try:
            client = self._get_db_client()
            sql = validate_readonly_sql(sql)
            result = client.execute(sql, max_rows=100)
            return json.dumps(
                {
                    "sql": sql,
                    "columns": result["columns"],
                    "rows": result["rows"],
                    "row_count": len(result["rows"]),
                },
                ensure_ascii=False,
            )
        except UnsafeSqlError as exc:
            return f"SQL 安全检查失败: {exc}"
        except Exception as exc:
            return f"执行查询失败: {exc}"

    def _parse_agent_result(self, result_text: str, question: str) -> dict[str, Any]:
        try:
            parsed = json.loads(result_text)
            if isinstance(parsed, dict) and "sql" in parsed and "rows" in parsed:
                return parsed
        except (json.JSONDecodeError, AttributeError):
            pass
        return {"sql": question, "columns": [], "rows": [], "row_count": 0, "elapsed_ms": 0, "warnings": []}


# ========================= 兼容旧接口的辅助函数 =========================

def build_schema_context(columns: list[SchemaColumn], max_lines: int = 220) -> str:
    if not columns:
        return "当前未能读取到 schema 元数据。"
    lines = []
    for column in columns[:max_lines]:
        comment = f" -- {column.comments}" if column.comments else ""
        lines.append(f"{column.table_name}.{column.column_name} {column.data_type}{comment}")
    if len(columns) > max_lines:
        lines.append(f"... 还有 {len(columns) - max_lines} 个列未展示")
    return "\n".join(lines)


def generate_sql(question: str, schema_columns: list[SchemaColumn], settings: LLMSettings) -> str:
    if not settings.api_key or not settings.model:
        raise AgentConfigurationError("大模型 API Key 或模型名称未配置")
    prompt = _user_prompt(question, schema_columns)
    sql = _generate_with_hello_agents(prompt, settings) or _generate_with_openai_compatible(prompt, settings)
    return validate_readonly_sql(_extract_sql(sql))


def _user_prompt(question: str, schema_columns: list[SchemaColumn]) -> str:
    return f"""Schema:
{build_schema_context(schema_columns)}

用户问题:
{question}

请生成一条 Oracle 只读 SQL。"""


def _generate_with_hello_agents(prompt: str, settings: LLMSettings) -> str | None:
    try:
        from hello_agents import HelloAgentsLLM, SimpleAgent
    except Exception:
        return None
    try:
        llm = HelloAgentsLLM(
            model=settings.model,
            api_key=settings.api_key,
            base_url=settings.base_url,
            temperature=settings.temperature,
        )
        agent = SimpleAgent(name="database-sql-agent", llm=llm, system_prompt=SYSTEM_PROMPT)
        result = agent.run(prompt)
        return str(result)
    except Exception:
        return None


def _generate_with_openai_compatible(prompt: str, settings: LLMSettings) -> str | None:
    base_url = settings.base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.model,
        "temperature": settings.temperature,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(url, headers={"Authorization": f"Bearer {settings.api_key}"}, json=payload)
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"]["content"])
    except Exception:
        return None


def _extract_sql(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except Exception:
        return stripped
    if isinstance(parsed, dict) and "sql" in parsed:
        return str(parsed["sql"])
    return stripped
