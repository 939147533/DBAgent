# Dataset Agent By GPT

Natural-language database querying workbench for Oracle and OceanBase Oracle mode.

## Structure

- `backend/`: FastAPI API, database adapters, Agent SQL generation, SQL safety, result exports.
- `frontend/`: Vue 3 + TypeScript workbench UI.

## Run

Backend:

```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

OceanBase Oracle mode additionally requires a local JDK and:

```bash
cd backend
pip install -r requirements-oceanbase.txt
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.
