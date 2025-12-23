# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TQ Data Platform is a Python data collection service that aggregates Korean government welfare information from the Public Data Portal (data.go.kr). It collects both central and regional government welfare service data and stores it in Cloudflare D1.

## Development Commands

```bash
# Install dependencies (using uv)
uv pip install -e ".[dev]"

# Setup environment
cp .env.example .env
# Edit .env with actual API keys and credentials

# Run the batch job
python batch/main.py

# Run the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Architecture

```
batch/main.py (Batch Job Entry Point)
    │
    ▼
WelfareService (app/services/welfare.py)
    │
    ├── APIClient (shared/clients/client.py) ──► Public Data API (data.go.kr)
    │
    └── D1Client (shared/db/d1.py) ──► Cloudflare D1 Cloud Storage

app/main.py (FastAPI Server Entry Point)
    │
    ▼
API Endpoints (/welfare/policies, /health, etc.)
    │
    └── D1Client (shared/db/d1.py) ──► Cloudflare D1 Cloud Storage

Settings (shared/config/settings.py) - Centralized env-based configuration
```

**Data Flow:**
1. WelfareService fetches list of welfare service IDs from public API (XML)
2. Concurrently fetches details for each ID using ThreadPoolExecutor
3. Parses XML responses and extracts policy data
4. Saves records to Cloudflare D1 with upsert logic

## Key Configuration

Environment variables in `.env`:
- `API_KEY` - Public Data Portal API key (required)
- `CENTRAL_LIST_URL`, `CENTRAL_DETAILED_URL` - Central government API endpoints
- `REGIONAL_LIST_URL`, `REGIONAL_DETAILED_URL` - Regional government API endpoints
- `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_D1_DB_ID` - D1 credentials
- `MAX_WORKERS` (default: 10) - Thread pool size
- `REQUEST_TIMEOUT` (default: 30) - API request timeout in seconds

## Project Structure

```
tq-data-platform/
├── app/              # Application code (FastAPI server, business logic)
│   ├── main.py       # FastAPI server entry point
│   └── services/     # Business logic (WelfareService, Processor)
├── shared/           # Common code shared by app and batch
│   ├── clients/      # External service clients (Public Data Portal, LLM)
│   ├── config/       # Settings and environment configuration
│   └── db/           # Database clients (D1Client, SQLAlchemy)
├── batch/            # Batch job code (GitHub Actions only)
│   ├── main.py       # Batch job entry point
│   ├── core.py       # Job framework
│   └── steps.py      # Job steps
├── tests/            # pytest tests
└── scripts/          # Development utilities
```

## Code Notes

- **Separated concerns**: `app/` for API server, `batch/` for scheduled jobs, `shared/` for common code
- **Import paths**: Use `from shared.config.settings import settings` for common code
- SQLAlchemy models exist in `shared/db/models.py` but local DB persistence is currently disabled
- D1Client gracefully handles missing credentials (logs warning, continues without cloud storage)
- XML parsing is done manually with ElementTree
- Concurrent processing uses `ThreadPoolExecutor` with configurable worker count
- FastAPI server provides REST API endpoints for welfare policy data
- Batch jobs run via GitHub Actions (schedule.yaml)
