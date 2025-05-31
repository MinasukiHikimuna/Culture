# CultureExtractor

A multi-engine content scraping and management system for adult media collection curation.

## Architecture Overview

**CultureExtractor** uses multiple ingestion engines to scrape both metadata and content from adult releases:

### Ingestion Engines

- **Scrapy Engine** (`/scrapy/`) - Python-based web scraping framework
- **Playwright Scraper** (`/dotnet/`) - .NET-based scraper using Playwright for dynamic content

### Web Application

- **NextJS Web Interface** (`/webapp/`) - Modern web application for browsing and managing scraped content
  - **Technology Stack**: NextJS 15 with App Router, TypeScript, Tailwind CSS
  - **Database**: Prisma ORM connecting to existing PostgreSQL
  - **Features**: Browse releases, search content, view media, manage collections

### Data Storage

- **Metadata** - Stored in PostgreSQL database (configured via `docker-compose.yml`)
- **Media Content** - Stored locally on disk

### Workflow

1. **Scraping** - Multiple engines scrape release metadata and download media content
2. **Storage** - Metadata goes to PostgreSQL, files stored locally
3. **Browsing** - Web interface provides modern UI for content discovery and management
4. **Curation** - User reviews and culls scraped content through web interface
5. **Integration** - Selected content moved to Stash app for final collection management

## Quick Start

1. Start the PostgreSQL database:

   ```bash
   docker-compose up -d
   ```

2. Run scrapers:

   - **Scrapy**: Navigate to `/scrapy/` and follow instructions
   - **.NET Scraper**: Navigate to `/dotnet/` and build the solution

3. Launch web interface:
   ```bash
   cd webapp
   npm install
   npm run dev
   ```

## Project Structure

```
├── scrapy/                 # Python Scrapy-based scraper
├── dotnet/                 # .NET Playwright-based scraper
├── webapp/                 # NextJS web application
│   ├── app/               # NextJS App Router pages and API routes
│   ├── components/        # Reusable UI components
│   ├── lib/              # Utility functions and database client
│   └── prisma/           # Database schema and migrations
├── docker-compose.yml      # PostgreSQL database setup
└── README.md              # This file
```

## Web Application Features

- **Browse Releases**: Paginated view of all scraped content with filtering
- **Release Details**: Detailed view with media gallery, performers, and tags
- **Search**: Full-text search across releases, performers, and tags
- **Media Viewer**: Built-in image and video preview capabilities
- **Statistics Dashboard**: Overview of collection stats and recent activity
- **Responsive Design**: Works on desktop, tablet, and mobile devices
