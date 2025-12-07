# Culture Extractor CLI

A modern command-line interface for Culture Extractor database operations.

## Installation

```bash
uv sync
```

## Usage

```bash
# List all sites
ce sites list

# List sites in JSON format
ce sites list --json
```

## Development

The CLI is built with:
- **Typer**: Modern CLI framework
- **Rich**: Beautiful terminal formatting
- **Polars**: Fast data processing
- **psycopg**: PostgreSQL database access
