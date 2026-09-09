# CortexBI

AI-powered analytics platform that transforms CSV files into interactive dashboards with multi-agent AI analysis, ML models, and SHAP explanations.

## Architecture

```
User -> Next.js Frontend -> FastAPI Backend -> LangGraph Pipeline -> Dashboard
                                            |
                              Postgres + pgvector (single datastore)
                              Object Storage (local disk / S3)
```

## Quick Start

### 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Postgres)
- [Miniforge](https://github.com/conda-forge/miniforge) or conda
- Node.js 20+

### 2. Start Postgres

```bash
docker compose up -d postgres
```

### 3. Create conda environment

```bash
conda create -p ./.conda -f environment.yml -y
conda activate ./.conda
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env and set JWT_SECRET_KEY to a random string
```

### 5. Run database migrations

```bash
alembic upgrade head
```

### 6. Start the backend

```bash
uvicorn apps.api.main:app --reload --port 8000
```

### 7. Start the frontend

```bash
cd apps/web
npm install
npm run dev
```

### 8. Verify

```bash
curl http://localhost:8000/health
# Should return: {"status":"ok"}
```

## Project Structure

```
cortexbi/
├── apps/
│   ├── api/          # FastAPI backend
│   ├── web/          # Next.js frontend
│   └── worker/       # Background pipeline runner
├── packages/
│   ├── agents/       # LangGraph pipeline (state, graph, nodes, tools)
│   ├── security/     # CSV validation, PII detection
│   ├── storage/      # Object storage interface (local / S3)
│   └── db/           # SQLAlchemy models + Alembic migrations
├── tests/
│   ├── backend/      # pytest tests
│   └── fixtures/     # Small synthetic CSVs for testing
└── docs/
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend  | Next.js 14, TypeScript, Tailwind CSS, Recharts |
| Backend   | FastAPI, Python 3.12, LangGraph |
| ML        | XGBoost, scikit-learn, SHAP |
| Database  | Postgres 16 + pgvector |
| Storage   | Local disk (dev) / S3-compatible (prod) |
| Auth      | JWT via PyJWT |
