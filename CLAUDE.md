# Culture Monorepo

This is a monorepo containing three main components:
- `extractors/` - Scraping code (Scrapy + legacy .NET)
- `cli/` - Unified CLI tool for database operations
- `analysis/` - Data analysis notebooks and scripts
- `libraries/` - Shared client libraries

## General Guidelines

- Remember to focus on small steps at a time. Always commit when a single task has been finished.
- Remember to run ruff on all new code and fix errors. Fix them properly instead of suppressing:
  ```
  uv run ruff check <file>
  ```
- When refactoring larger functions into shorter ones, place helper functions under the public function in chronological order as if telling a story.
- Use uv to run Python code.

## Extractors (extractors/)

- Culture Extractor scrapes both metadata and actual files.
- It primarily uses Python-based Scrapy now.
- Historical scrapers were created with .NET-based Playwright (frozen, no new development).
- Prefer Scrapy unless Playwright is absolutely needed.
- The scraped metadata is stored into PostgreSQL database.
- The scraped files are stored on disk.
- During developing a new scraper, use MCP Playwright to interact with the site and inspect DOM.
- If a login page is encountered, let user handle the login.
- Prefer small commits i.e. first implementing just scraping a single list page and printing out the output, commit and then proceed.

## CLI (cli/)

- Unified CLI for both scraping operations and data analysis.
- Entry point: `culture` command.
- Modules: `ce` (Culture Extractor), `stash` (Stashapp integration).

## Libraries (libraries/)

- Shared client libraries used by both CLI and analysis tools.
- `client_culture_extractor.py` - PostgreSQL client for CE database
- `client_stashapp.py` - GraphQL client for Stashapp
- `StashDbClient.py` - StashDB client

## Agents

- playwright-site-inspector to inspect the target sites.
- scrapy-output-validator should be used whenever scraper code is changed to check if the output is right.
- code-reviewer needs to be used before committing anything.
