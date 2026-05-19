from __future__ import annotations

import json
import re
import time
from typing import Any
import ast
import httpx

from .database import DatabaseConfigurationError, create_database_client
from .models import DatabaseSettings, LLMSettings, SchemaColumn
from .sql_safety import UnsafeSqlError, apply_row_limit, validate_readonly_sql
from .settings_store import load_settings
from hello_agents import HelloAgentsLLM, ReActAgent
from hello_agents.tools import ToolRegistry
from hello_agents.core.config import Config


class AgentConfigurationError(RuntimeError):
    pass


SYSTEM_PROMPT = """你是数据库 SQL 生成 Agent。
目标数据库使用 Oracle SQL 方言，OceanBase Oracle 模式也按 Oracle 方言处理。
只能生成一条只读 SQL：SELECT 或 WITH ... SELECT。
禁止 INSERT、UPDATE、DELETE、MERGE、DROP、ALTER、TRUNCATE、CREATE、PL/SQL、过程调用、多语句。
只返回 SQL 文本，不要 Markdown，不要解释。
优先使用提供的 schema，不要猜测不存在的表和列。
生成的sql要先通过ExecuteQuery工具执行，如果执行错误或者没有数据，要重新生成sql，直到满足用户需求或达到最大步骤限制。
最终返回一条只读SQL语句。
"""


# class SafeHelloAgentsLLM(HelloAgentsLLM):
#     """
#     修复 hello_agents httpx 连接泄漏问题：
#     每次 invoke() 使用新的 httpx.Client，避免连接复用导致 "I/O operation on closed file"。
#     """
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self._client: httpx.Client | None = None
#
#     def invoke(self, messages, **kwargs):
#         """每次调用时创建新的 httpx.Client，禁用连接池复用"""
#         # 关闭旧连接（如果存在）
#         if self._client is not None:
#             try:
#                 self._client.close()
#             except Exception:
#                 pass
#
#         # 创建新客户端，禁用 keepalive 避免连接复用问题
#         self._client = httpx.Client(
#             timeout=httpx.Timeout(60.0),
#             limits=httpx.Limits(max_keepalive_connections=0, max_connections=1),
#         )
#
#         # 临时替换父类的 _client 属性
#         original_client = getattr(self, '_client', None)
#         try:
#             return super().invoke(messages, **kwargs)
#         finally:
#             # 调用完成后立即关闭连接
#             if self._client is not None:
#                 try:
#                     self._client.close()
#                 except Exception:
#                     pass
#                 self._client = None


class DatabaseAgent:
    """基于 ReActAgent 的数据库 Agent"""

    def __init__(self, max_steps: int = 10):
        print("🔄 开始初始化数据库助手...")
        try:
            settings = load_settings()
            self.db_settings = settings.database
            self.llm_settings = settings.llm
            self.max_steps = max_steps
            self._client = None

            registry = ToolRegistry()
            registry.register_function(self._tool_get_table, name="GetTableName",
                                       description="获取数据库表名、表注释）")
            registry.register_function(self._tool_get_schema_with_table_names, name="GetSchema",
                                       description="根据表名获取数据库 Schema（表名、列名、数据类型、注释）。入参为表名列表，例子:['table1', 'table2']")
            registry.register_function(self._tool_execute_query, name="ExecuteQuery",
                                       description="执行 SQL 并返回结果")

            self.llm = HelloAgentsLLM(
                model=self.llm_settings.model,
                api_key=self.llm_settings.api_key,
                base_url=self.llm_settings.base_url,
                temperature=self.llm_settings.temperature,
            )

            # 禁用 trace_enabled，避免 TraceLogger 的文件关闭问题，后去如果使用trace需要解决文件关闭问题：I/O operation on closed file.
            config = Config(
                trace_enabled=False,  # 禁用 TraceLogger，避免 "I/O operation on closed file"
                max_steps=max_steps,
            )

            self.agent = ReActAgent(
                name="数据库查询Agent",
                llm=self.llm,
                tool_registry=registry,
                system_prompt=SYSTEM_PROMPT,
                config=config,  # 传入禁用 trace 的配置
                max_steps=self.max_steps,
            )
        except Exception as e:
            print(f"❌ 多智能体系统初始化失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise AgentConfigurationError(f"多智能体系统初始化失败: {str(e)}")

    def _get_db_client(self):
        if self._client is None:
            self._client = create_database_client(self.db_settings)
        return self._client

    def run(self, question: str, max_rows: int = 100) -> dict[str, Any]:
        result_text = self.agent.run(question)
        sql = _extract_sql(result_text)
        print("🔍 生成的 SQL:", sql)
        return sql

    def _tool_get_table(self, _input: str) -> str:
        try:
            client = self._get_db_client()
            columns = client.list_table_name()
            lines = []
            for col in columns:
                comments = f" -- {col.table_comments}" if col.table_comments else ""
                lines.append(f"{col.table_name} {comments}")
            return "\n".join(lines) if lines else "未找到表名。"
        except DatabaseConfigurationError as exc:
            return f"获取表名失败: {exc}"
        except Exception as exc:
            return f"获取表名异常: {exc}"

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

    def _tool_get_schema_with_table_names(self, table_names : list[str]) -> str:
        try:
            client = self._get_db_client()
            if isinstance(table_names, str) and table_names.startswith("[") and table_names.endswith("]"):
                table_names = ast.literal_eval(table_names)
            columns = client.list_schema(table_names)
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


# 全局多智能体系统实例（单例模式，Agent 内部已修复 TraceLogger 问题）
_database_agent: DatabaseAgent | None = None


def get_database_agent_assistant() -> DatabaseAgent:
    """获取 DatabaseAgent 实例（单例）"""
    global _database_agent
    if _database_agent is None:
        _database_agent = DatabaseAgent()
    return _database_agent


def reset_database_agent_assistant() -> None:
    global _database_agent
    _database_agent = None
