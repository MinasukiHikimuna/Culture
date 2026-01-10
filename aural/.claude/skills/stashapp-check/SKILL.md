---
name: stashapp-check
description: Check Stashapp releases, scenes, and performers. Use when the user asks to look up a scene, find scenes by performer, check release status, or get Stashapp statistics.
---

# Stashapp Release Checker

Check on a Stashapp release by querying the Stashapp GraphQL API.

## Instructions

Use the Python script at `.claude/skills/stashapp-check/scripts/stashapp_check.py` to query Stashapp.

When the user asks about a Stashapp release:
1. Determine what they're looking for (scene by title, scene by ID, scenes by performer, or stats)
2. Run the appropriate command from the examples below
3. Present the results clearly to the user

If the basic information doesn't include what you were looking for, use --json.

## Usage Examples

```bash
# Search scenes by title
uv run python .claude/skills/stashapp-check/scripts/stashapp_check.py "shy ghost girl"

# Get a specific scene by ID
uv run python .claude/skills/stashapp-check/scripts/stashapp_check.py --id 123

# Find scenes by performer
uv run python .claude/skills/stashapp-check/scripts/stashapp_check.py --performer "SnakeySmut"

# Show Stashapp statistics
uv run python .claude/skills/stashapp-check/scripts/stashapp_check.py --stats

# Verbose output with details
uv run python .claude/skills/stashapp-check/scripts/stashapp_check.py --id 123 --verbose

# JSON output for parsing
uv run python .claude/skills/stashapp-check/scripts/stashapp_check.py "ghost" --json

# Limit results
uv run python .claude/skills/stashapp-check/scripts/stashapp_check.py "ghost" --limit 5
```

## Options

- `query` - Search scenes by title (positional argument)
- `--id ID` - Get scene by specific ID
- `--performer NAME` / `-p NAME` - Find scenes by performer name
- `--stats` - Show Stashapp statistics (scene count, performer count, etc.)
- `--verbose` / `-v` - Show verbose output including file paths and details
- `--limit N` / `-l N` - Limit number of results (default: 10)
- `--json` - Output results as JSON

## Configuration

The script uses environment variables for configuration:
- `STASHAPP_URL` - GraphQL endpoint (default: https://stash-aural.chiefsclub.com/graphql)
- `STASHAPP_API_KEY` - API key for authentication

## Output Format

For scene listings:
```
  [ ID] ✓/✗ DATE | Title
         Performers: Name1, Name2
```

For detailed view:
```
Scene: [Title]
ID: 123
Date: 2024-01-15
Organized: Yes
Play Count: 5

Performers:
  - PerformerName (ID: 45)

Studio: StudioName (ID: 12)

Tags: Tag1, Tag2, Tag3

Files:
  - filename.mp4 (duration: 15:30, size: 150MB)

URLs:
  - https://reddit.com/...
  - https://soundgasm.net/...
```
