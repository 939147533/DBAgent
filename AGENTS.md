# 项目说明 (AGENTS.md)

## 项目概述

**Dataset Agent** 是一个自然语言数据库查询工作台，支持 Oracle 和 OceanBase Oracle 模式。用户输入自然语言问题，系统通过大语言模型生成 SQL 查询数据库，返回结果并支持导出 CSV/XLSX/INSERT SQL。

## 技术栈

- **后端**: Python 3.10 + FastAPI + Pydantic + oracledb
- **前端**: Vue 3 + TypeScript + Vite + lucide-vue-next (图标)
- **数据存储**: 本地 `.data/settings.json` (密码使用 Fernet/base64 加密)
- **LLM 集成**: `hello-agents` 库 或 OpenAI 兼容 API

## 目录结构

```
backend/
  app/
    main.py          # FastAPI 应用入口，定义所有路由
    models.py        # Pydantic 模型 (DatabaseSettings, LLMSettings, QueryResponse 等)
    agent.py         # SQL 生成 Agent (Prompt 构建、LLM 调用、安全校验)
    database.py      # 数据库客户端 (OracleClient, OceanBaseOracleClient)
    sql_safety.py    # SQL 安全校验、行数限制、表名推断
    exporters.py     # 结果导出 (CSV/XLSX/INSERT SQL)
    cache.py         # 查询结果内存缓存
    settings_store.py# 配置加载/保存/加解密
requirements.txt     # 基础依赖
requirements-oceanbase.txt # OceanBase JDBC 依赖
requirements-test.txt  # 测试依赖
tests/               # Pytest 测试
frontend/
  src/
    App.vue          # 主组件 (侧边栏 + 工作区)
    main.ts          # Vue 应用入口
    api.ts           # API 请求封装
    types.ts         # TypeScript 接口定义
    style.css        # 全局样式
  vite.config.ts     # Vite 代理配置 (指向 8000 端口后端)
  package.json       # 前端依赖
```

## 核心功能流程

1. **配置管理**: 用户在侧边栏配置数据库连接或大模型 API 信息，保存至本地 JSON。
2. **Schema 同步**: 前端通过 `/api/schema` 获取当前数据库表结构，辅助 LLM 生成准确 SQL。
3. **SQL 生成**: 用户输入问题后，后端调用 LLM，传入系统提示词 (强制只读)、当前 Schema 上下文和用户问题。
4. **安全校验**: 使用 `sql_safety.py` 拦截所有 DDL/DML、多语句、PL/SQL 等非只读 SQL。自动包裹 `ROWNUM` 限制行数。
5. **查询执行**: 通过 `oracledb` 或 `jaydebeapi` 执行 SQL，结果缓存 30 分钟。
6. **结果展示**: 前端表格渲染数据，支持查看生成的 SQL、导出 CSV/XLSX/INSERT SQL。

## 环境变量与配置

无需 `.env`，所有配置通过 UI 保存至 `.data/settings.json`。

## 开发环境搭建

### 后端

```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### OceanBase Oracle 模式支持 (可选)

需要本地 JDK 环境，并额外安装：

```bash
pip install -r requirements-oceanbase.txt
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://127.0.0.1:5173`，通过 Vite 代理将 `/api` 请求转发至后端 `http://127.0.0.1:8000`。

## API 接口说明

| 方法   | 路径                               | 说明                     |
| ------ | ---------------------------------- | ------------------------ |
| GET    | `/health`                          | 健康检查                 |
| GET    | `/api/settings/database`           | 获取数据库配置           |
| PUT    | `/api/settings/database`           | 保存数据库配置           |
| POST   | `/api/settings/database/test`      | 测试数据库连接           |
| GET    | `/api/settings/llm`                | 获取大模型配置           |
| PUT    | `/api/settings/llm`                | 保存大模型配置           |
| POST   | `/api/settings/llm/test`           | 测试大模型连接           |
| GET    | `/api/schema`                      | 获取当前数据库 Schema    |
| POST   | `/api/query`                       | 执行自然语言查询         |
| GET    | `/api/query/{query_id}/export`     | 导出查询结果 (csv/xlsx/sql) |

## 安全机制

- **SQL 安全**: 严格限制为单条 `SELECT` 或 `WITH` 查询，自动包裹 `ROWNUM` 防超时。
- **导出表名校验**: 导出 INSERT SQL 时校验表名，防止注入。
- **密码加密**: 配置文件的 `password` 和 `api_key` 字段使用 Fernet 对称加密存储。

## 测试

运行后端测试：

```bash
cd backend
pytest
```

测试覆盖 SQL 安全校验逻辑和导出格式处理。

## 依赖关系图

```
前端 (Vue) -> Vite -> FastAPI (后端) -> oracledb/JDBC -> Oracle/OceanBase
                                    -> HelloAgents/OpenAI-Compatible -> LLM -> SQL 生成
                                    -> SQL Safety -> Oracle SQL -> 查询执行 -> 结果缓存 -> 导出
```
