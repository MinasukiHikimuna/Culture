---
name: stashapp-schema
description: Introspect Stashapp GraphQL API schema. Use when the user asks about GraphQL types, queries, mutations, fields, or API structure.
---

# Stashapp Schema Introspector

Query the Stashapp GraphQL API schema to explore available types, queries, mutations, and their fields/arguments.

## Instructions

Use the Python script at `.claude/skills/stashapp-schema/scripts/stash_schema.py` to introspect the schema.

When the user asks about the Stashapp API:
1. Determine what they're looking for (types, queries, mutations, or specific details)
2. Run the appropriate command from the examples below
3. Present the results clearly to the user

## Usage Examples

```bash
# List all GraphQL types (excludes internal __ types)
uv run python .claude/skills/stashapp-schema/scripts/stash_schema.py --types

# Show details of a specific type (fields, their types, and arguments)
uv run python .claude/skills/stashapp-schema/scripts/stash_schema.py --type Scene

# List all available queries
uv run python .claude/skills/stashapp-schema/scripts/stash_schema.py --queries

# List all available mutations
uv run python .claude/skills/stashapp-schema/scripts/stash_schema.py --mutations

# Show details of a specific query (arguments and return type)
uv run python .claude/skills/stashapp-schema/scripts/stash_schema.py --query findScenes

# Show details of a specific mutation
uv run python .claude/skills/stashapp-schema/scripts/stash_schema.py --mutation sceneUpdate

# Search types and operations by name
uv run python .claude/skills/stashapp-schema/scripts/stash_schema.py --search "performer"

# JSON output for parsing
uv run python .claude/skills/stashapp-schema/scripts/stash_schema.py --types --json

# Verbose output with descriptions
uv run python .claude/skills/stashapp-schema/scripts/stash_schema.py --type Scene --verbose
```

## Options

- `--types` - List all GraphQL types
- `--type NAME` - Show details of a specific type
- `--queries` - List all available query operations
- `--mutations` - List all available mutation operations
- `--query NAME` - Show details of a specific query
- `--mutation NAME` - Show details of a specific mutation
- `--search TERM` - Search types and operations by name
- `--verbose` / `-v` - Show verbose output including descriptions
- `--json` - Output results as JSON

## Configuration

The script uses environment variables for configuration:
- `STASHAPP_URL` - GraphQL endpoint (required)
- `STASHAPP_API_KEY` - API key for authentication (required)

## Output Format

For type listings:
```
Types (42):
  OBJECT      Scene
  OBJECT      Performer
  INPUT_OBJECT SceneFilterType
  ENUM        SortDirectionEnum
  ...
```

For type details:
```
Type: Scene (OBJECT)
Fields:
  id: ID!
  title: String
  date: String
  performers: [Performer!]!
  files(filter: FileFilter): [VideoFile!]!
  ...
```

For query/mutation details:
```
Query: findScenes
Arguments:
  scene_filter: SceneFilterType
  filter: FindFilterType
Returns: FindScenesResultType!
```
