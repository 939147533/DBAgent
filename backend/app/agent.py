from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .models import LLMSettings, SchemaColumn
from .sql_safety import validate_readonly_sql


class AgentConfigurationError(RuntimeError):
    pass


SYSTEM_PROMPT = """你是数据库 SQL 生成 Agent。
目标数据库使用 Oracle SQL 方言，OceanBase Oracle 模式也按 Oracle 方言处理。
只能生成一条只读 SQL：SELECT 或 WITH ... SELECT。
禁止 INSERT、UPDATE、DELETE、MERGE、DROP、ALTER、TRUNCATE、CREATE、PL/SQL、过程调用、多语句。
只返回 SQL 文本，不要 Markdown，不要解释。
优先使用提供的 schema，不要猜测不存在的表和列。
"""


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


def _generate_with_openai_compatible(prompt: str, settings: LLMSettings) -> str:
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
    with httpx.Client(timeout=60) as client:
        response = client.post(url, headers={"Authorization": f"Bearer {settings.api_key}"}, json=payload)
        response.raise_for_status()
        data = response.json()
    return str(data["choices"][0]["message"]["content"])


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
