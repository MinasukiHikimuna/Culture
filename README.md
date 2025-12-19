# Culture Monorepo

## Components

- `api/` - FastAPI backend
- `web/` - Next.js frontend
- `extractors/` - Scraping code (Scrapy + legacy .NET)
- `cli/` - Unified CLI tool for database operations
- `analysis/` - Data analysis notebooks and scripts
- `libraries/` - Shared client libraries

## Getting Started

### Prerequisites

- Python 3.14+
- Node.js
- Docker (for PostgreSQL)
- [uv](https://docs.astral.sh/uv/) package manager

### Database

Start PostgreSQL:

```bash
cd infrastructure && docker compose up -d
```

### API

```bash
cd api && uv sync && uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000

### Web

```bash
cd web && npm install && npm run dev
```

The web app will be available at http://localhost:3000
