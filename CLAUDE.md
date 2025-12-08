# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TQ Data Platform is a Python data collection service that aggregates Korean government welfare information from the Public Data Portal (data.go.kr). It collects both central and regional government welfare service data and stores it in Cloudflare D1.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with actual API keys and credentials

# Run the application
python main.py
```

## Architecture

```
main.py (Entry Point)
    │
    ▼
WelfareService (services/welfare.py)
    │
    ├── APIClient (api/client.py) ──► Public Data API (data.go.kr)
    │
    └── D1Client (db/d1.py) ──► Cloudflare D1 Cloud Storage

Settings (config/settings.py) - Centralized env-based configuration
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

## Code Notes

- SQLAlchemy models exist in `db/models.py` but local DB persistence is currently disabled
- D1Client gracefully handles missing credentials (logs warning, continues without cloud storage)
- XML parsing is done manually with ElementTree
- Concurrent processing uses `ThreadPoolExecutor` with configurable worker count
