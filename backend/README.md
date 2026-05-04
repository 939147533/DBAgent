# Dataset Agent Backend

FastAPI service for natural-language database querying against Oracle and OceanBase Oracle mode.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API listens on `http://127.0.0.1:8000` by default.

OceanBase Oracle mode uses JDBC through `jaydebeapi`/`JPype1`, which requires a local JDK:

```bash
pip install -r requirements-oceanbase.txt
```
