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
Batch Steps (batch/steps.py)
    │
    ├── CentralWelfareStep ──► WelfareCollector (batch/services/welfare.py)
    ├── RegionalWelfareStep ──► WelfareCollector (batch/services/welfare.py)
    └── ChromaConversionStep ──► ChromaConverter (batch/services/chroma_converter.py)
    │
    └── APIClient (shared/clients/client.py) ──► Public Data API (data.go.kr)
    └── D1Client (shared/db/d1.py) ──► Cloudflare D1 Cloud Storage

app/main.py (FastAPI Server Entry Point)
    │
    ▼
API Endpoints (/welfare/policies, /health, etc.)
    │
    └── D1Client (shared/db/d1.py) ──► Cloudflare D1 Cloud Storage

Settings (shared/config/settings.py) - Centralized env-based configuration
```

**Batch Data Flow:**
1. **Collection**: WelfareCollector fetches welfare service IDs from public API (XML)
2. **Details**: Fetches detailed policy data for each ID (rate-limited sequential processing)
3. **Storage**: Saves raw XML data to D1 (batch upserts)
4. **Conversion**: ChromaConverter transforms D1 data to ChromaDB JSON format for vector search

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
├── app/              # Application code (FastAPI server)
│   ├── main.py       # FastAPI server entry point
│   └── services/     # API-specific business logic
├── batch/            # Batch job code (GitHub Actions, scheduled data collection)
│   ├── main.py       # Batch job entry point
│   ├── core.py       # Job framework
│   ├── steps.py      # Job step definitions
│   └── services/     # Batch-specific services
│       ├── welfare.py          # WelfareCollector - data collection
│       ├── chroma_converter.py # ChromaConverter - vector DB conversion
│       └── processor.py        # WelfareProcessor - data normalization
├── shared/           # Common code shared by app and batch
│   ├── clients/      # External service clients (Public Data Portal, LLM)
│   ├── config/       # Settings and environment configuration
│   └── db/           # Database clients (D1Client, SQLAlchemy)
├── tests/            # pytest tests
└── scripts/          # Development utilities
```

## Code Notes

- **Separated concerns**:
  - `app/` - FastAPI server and API-specific logic
  - `batch/` - Scheduled data collection jobs (self-contained, no app dependencies)
  - `shared/` - Common utilities (DB clients, API clients, config)
- **Import paths**:
  - Batch services: `from batch.services.welfare import WelfareCollector`
  - Shared utilities: `from shared.config.settings import settings`
  - **Never import from app/ in batch/** - batch is independent
- **Data Processing**:
  - XML parsing with ElementTree
  - Sequential processing with rate limiting (10 req/sec)
  - Batch inserts to D1 (50 items per batch)
  - ChromaConverter transforms D1 data to vector DB format
- **Database**:
  - Primary storage: Cloudflare D1 (cloud)
  - D1Client gracefully handles missing credentials
  - SQLAlchemy models exist but local DB is disabled
- **Deployment**:
  - Batch jobs run via GitHub Actions (schedule.yaml)
  - FastAPI server provides REST API endpoints
