# CultureExtractor

A multi-engine content scraping and management system for adult media collection curation.

## Architecture Overview

**CultureExtractor** uses multiple ingestion engines to scrape both metadata and content from adult releases:

### Ingestion Engines

- **Scrapy Engine** (`/scrapy/`) - Python-based web scraping framework
- **Playwright Scraper** (`/dotnet/`) - .NET-based scraper using Playwright for dynamic content

### Data Storage

- **Metadata** - Stored in PostgreSQL database (configured via `docker-compose.yml`)
- **Media Content** - Stored locally on disk

### Workflow

1. **Scraping** - Multiple engines scrape release metadata and download media content
2. **Storage** - Metadata goes to PostgreSQL, files stored locally
3. **Curation** - User reviews and culls scraped content
4. **Integration** - Selected content moved to Stash app for final collection management

## Quick Start

1. Start the PostgreSQL database:

   ```bash
   docker-compose up -d
   ```

2. Run scrapers:
   - **Scrapy**: Navigate to `/scrapy/` and follow instructions
   - **.NET Scraper**: Navigate to `/dotnet/` and build the solution

## Project Structure

```
├── scrapy/                 # Python Scrapy-based scraper
├── dotnet/                 # .NET Playwright-based scraper
├── docker-compose.yml      # PostgreSQL database setup
└── README.md              # This file
```
