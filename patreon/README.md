# Patreon Content Scraper

A Python-based tool for scraping and analyzing Patreon content with intelligent data management and HAR format support.

## Features

- **HAR Format Support**: Automatic header extraction from captured HTTP requests
- **Multi-Account Support**: Scrape content from multiple Patreon accounts
- **Intelligent Data Management**: Automatic duplicate detection and incremental updates
- **High-Performance Analysis**: Polars-powered data manipulation
- **Media Download**: Automatic download and organization of media files
- **Multiple Export Formats**: JSON, Parquet, CSV, and HTML reports

## Technology Stack

- **Python 3.8+** with uv package manager
- **HAR Format** for complete HTTP request capture
- **Polars** for high-performance data analysis
- **Requests** for HTTP handling with rate limiting

## Quick Start

### 1. Install Dependencies

```bash
# Install uv if not already installed
brew install uv  # macOS
# or
scoop install main/uv  # Windows

# Install project dependencies
uv sync
```

### 2. Capture Data (Microsoft Edge Recommended)

```bash
# Open Edge → F12 → Network tab → Navigate to posts → Right-click → "Save all as HAR with content"
# Save as: captured/patreon_capture.har
```

### 3. Test Your Capture

```bash
uv run python scripts/validate_capture.py captured/patreon_capture.har
```

### 4. Run the Scraper

```bash
uv run python scripts/scraper.py captured/patreon_capture.har
```

## Project Structure

```
patreon-scraper/
├── scripts/
│   ├── scraper.py    # Main scraping workflow
│   └── validate_capture.py   # Validate captured data
├── captured/                 # HAR files from browser
├── data/                     # Processed data (JSON/Parquet)
├── media/                    # Downloaded media files
└── pyproject.toml           # Dependencies
```

## Key Commands

```bash
# Test captured data
uv run python scripts/validate_capture.py <har_file>

# Run scraper with HAR file
uv run python scripts/scraper.py <har_file>

# Run with default HAR location
uv run python scripts/scraper.py

# Skip media downloads
uv run python scripts/scraper.py <har_file> --no-media
```

## Data Output

The scraper generates:

- **JSON files**: Complete backup data
- **Parquet files**: Optimized for analysis
- **CSV exports**: Human-readable summaries
- **Media files**: Downloaded images/videos
- **HTML reports**: Analysis summaries

## Development

### Code Quality & Formatting

This project uses [Black](https://black.readthedocs.io/) for code formatting and [Ruff](https://docs.astral.sh/ruff/) for comprehensive linting.

#### Format Code

```bash
# Format all Python files
uv run black scripts/

# Check formatting without making changes
uv run black --check --diff scripts/

# Use the convenience script
python format.py          # Format code
python format.py --check  # Check formatting
```

#### Linting with Ruff

```bash
# Check for linting issues
uv run ruff check scripts/

# Auto-fix many issues
uv run ruff check --fix scripts/

# Check for specific error types (e.g., undefined names)
uv run ruff check scripts/ --select F821,F822,F823

# Format imports and fix style issues
uv run ruff check --fix --select I,UP scripts/
```

#### Pre-commit Hooks

Pre-commit hooks are set up to automatically format code before commits:

```bash
# Install pre-commit hooks (already done in setup)
uv run pre-commit install

# Run hooks manually on all files
uv run pre-commit run --all-files
```

#### Configuration

Both Black and Ruff are configured in `pyproject.toml`:

**Black Configuration:**

- Line length: 88 characters
- Target Python version: 3.8+
- Excludes: data/, captured/, media/ directories

**Ruff Configuration:**

- Comprehensive rule sets: pyflakes, pycodestyle, isort, pyupgrade, and more
- Auto-fixes for imports, code modernization, and style issues
- Catches undefined names, unused imports, and common bugs
- Same line length and exclusions as Black for consistency

## Best Practices

- Use Microsoft Edge for HAR capture (most reliable)
- Capture data while logged in for full access
- Test captures before running full scrapes
- Use rate limiting to respect server resources
- Keep HAR files secure (contain session data)
- Format code with Black and lint with Ruff before committing
- Run `uv run ruff check scripts/` to catch issues early
- Use `uv run ruff check --fix scripts/` to auto-fix common problems

## Contributing

This tool is for educational and research purposes. Users must comply with Patreon's terms of service and applicable laws.

## License

[Specify your license here]
