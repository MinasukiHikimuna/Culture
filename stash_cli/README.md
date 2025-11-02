# Stashapp CLI

Command-line interface for interacting with your Stashapp database.

## Features

- **Performers Management**: List, search, and view detailed performer information
- **Multiple Search Options**: Filter by name, StashDB ID, TPDB ID, gender, and favorite status
- **Rich Output**: Beautiful table formatting with color-coded information
- **JSON Export**: Export results in JSON format for scripting
- **Environment Support**: Use different Stashapp instances with environment variable prefixes

## Installation

The CLI is installed automatically when you install the project:

```bash
uv sync
```

## Configuration

Set up your Stashapp connection in `.env`:

```env
STASHAPP_SCHEME=http
STASHAPP_HOST=localhost
STASHAPP_PORT=9999
STASHAPP_API_KEY=your_api_key_here
```

For multiple Stashapp instances, use prefixes:

```env
# Primary instance (no prefix)
STASHAPP_SCHEME=http
STASHAPP_HOST=localhost
STASHAPP_PORT=9999
STASHAPP_API_KEY=key1

# Secondary instance (with prefix)
BACKUP_STASHAPP_SCHEME=http
BACKUP_STASHAPP_HOST=192.168.1.100
BACKUP_STASHAPP_PORT=9999
BACKUP_STASHAPP_API_KEY=key2
```

## Usage

### Performers Commands

#### List All Performers

```bash
stash-cli performers list
```

#### Filter by Name

```bash
stash-cli performers list --name "Jane"
stash-cli performers list -n "Doe"
```

#### Filter by StashDB ID

```bash
stash-cli performers list --stashdb-id "abc123def456"
stash-cli performers list -s "abc123def456"
```

#### Filter by TPDB ID

```bash
stash-cli performers list --tpdb-id "xyz789"
stash-cli performers list -t "xyz789"
```

#### Filter by Gender

```bash
stash-cli performers list --gender FEMALE
stash-cli performers list -g MALE
```

Available genders: `MALE`, `FEMALE`, `TRANSGENDER_MALE`, `TRANSGENDER_FEMALE`, `NON_BINARY`

#### Filter Favorites Only

```bash
stash-cli performers list --favorite
stash-cli performers list -f
```

#### Combine Filters

```bash
stash-cli performers list --gender FEMALE --favorite
stash-cli performers list --name "Jane" --limit 10
```

#### Limit Results

```bash
stash-cli performers list --limit 50
stash-cli performers list -l 10
```

#### JSON Output

```bash
stash-cli performers list --json
stash-cli performers list --name "Jane" --json > results.json
```

#### Use Alternative Instance

```bash
stash-cli performers list --prefix BACKUP_
stash-cli performers list -p BACKUP_
```

### Show Performer Details

```bash
stash-cli performers show 123
stash-cli performers show 456 --prefix BACKUP_
```

### Create Performer

Create a new performer with optional external IDs:

```bash
# Create performer with name only
stash-cli performers create "Jane Doe"

# Create with StashDB ID
stash-cli performers create "Jane Doe" --stashdb-id "fb7a0e15-fa8c-4b3d-9cdf-69c75351d785"

# Create with both StashDB and Culture Extractor IDs
stash-cli performers create "Jane Doe" \
  --stashdb-id "fb7a0e15-fa8c-4b3d-9cdf-69c75351d785" \
  --ce-id "01993396-a5f5-70b0-9294-d9ce343a0829"

# Create in alternative instance
stash-cli performers create "Jane Doe" --stashdb-id "abc123..." --prefix BACKUP_
```

Short flags are also available:
- `-s` for `--stashdb-id`
- `-c` for `--ce-id`
- `-p` for `--prefix`

## Output Format

### Table Output (Default)

The default output is a beautiful table with:
- ID (cyan)
- Name (green)
- Gender (yellow)
- Favorite status (⭐)
- StashDB ID (blue)
- TPDB ID (blue)

### Detailed View

The `show` command displays:
- All basic performer information
- Aliases
- URLs
- Custom fields
- StashDB/TPDB IDs

### JSON Output

Use `--json` flag to get machine-readable output for scripting:

```json
[
  {
    "stashapp_id": 123,
    "stashapp_name": "Jane Doe",
    "stashapp_gender": "FEMALE",
    "stashapp_favorite": true,
    "stashapp_stashdb_id": "abc123",
    "stashapp_tpdb_id": null,
    ...
  }
]
```

## Examples

### Find a performer by partial name match

```bash
stash-cli performers list --name "Jane"
```

### Get all favorite female performers

```bash
stash-cli performers list --gender FEMALE --favorite
```

### Export all performers to JSON

```bash
stash-cli performers list --json > all_performers.json
```

### Find performer by StashDB ID

```bash
stash-cli performers list --stashdb-id "f8d35c12-3a4b-4e5d-9876-abc123def456"
```

### View detailed performer information

```bash
stash-cli performers show 123
```

### Search in backup Stashapp instance

```bash
stash-cli performers list --name "Jane" --prefix BACKUP_
```

### Create missing performers from StashDB

If you have performers that exist in StashDB but not in Stashapp:

```bash
# First, check if the StashDB ID exists in Stashapp
stash-cli performers list --stashdb-id "81c09da6-c015-4bda-8b60-215413f7a848"

# If not found, create the performer with the StashDB ID
stash-cli performers create "Bonni Gee" --stashdb-id "81c09da6-c015-4bda-8b60-215413f7a848"

# Verify the performer was created
stash-cli performers list --stashdb-id "81c09da6-c015-4bda-8b60-215413f7a848"
```

## Development

The stash-cli tool is built with:
- **Typer**: Modern CLI framework with automatic help generation
- **Rich**: Beautiful terminal output with tables and colors
- **Polars**: Fast dataframe operations
- **stashapp-tools**: Official Stashapp Python library

### Project Structure

```
stash_cli/
├── __init__.py          # Package initialization
├── __main__.py          # Entry point for python -m stash_cli
├── cli.py               # Main CLI application
└── commands/
    ├── __init__.py
    └── performers.py    # Performer commands
```

## Future Enhancements

Potential features to add:
- Scenes management commands
- Studios management commands
- Tags management commands
- Galleries management commands
- Bulk operations (tagging, updating)
- GraphQL introspection tools
- Export/import functionality

## Troubleshooting

### Connection Issues

If you get connection errors:
1. Check your `.env` file has correct Stashapp credentials
2. Ensure Stashapp is running
3. Verify API key has proper permissions
4. Test with `--prefix` if using multiple instances

### No Results

If searches return no results:
- Name searches are case-insensitive and use partial matching
- StashDB/TPDB ID searches must be exact matches
- Check your filters aren't too restrictive

## Related Tools

- [ce-cli](../ce_cli/README.md) - Culture Extractor CLI tool
- [libraries/client_stashapp.py](../libraries/client_stashapp.py) - Stashapp client library
