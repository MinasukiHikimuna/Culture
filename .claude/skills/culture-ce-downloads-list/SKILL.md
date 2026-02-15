---
name: culture-ce-downloads-list
description: Check download status of releases for a site. Use when the user asks about which releases have been downloaded, what file types are present, or which releases are missing videos or other download types.
---

# Culture CE Downloads List

Check per-release download status for a site, showing what file types and content types have been downloaded for each release.

## Instructions

Use the `culture ce downloads list` CLI command to check download status.

When the user asks about downloads:
1. Determine what site they're asking about
2. Determine if they want to filter by download status (e.g., missing videos, no downloads)
3. Run the appropriate command from the examples below
4. Present the results clearly to the user

The API server must be running for this command to work. If you get a connection error, tell the user to start it with: `cd api && uv run uvicorn api.main:app --port 8000`

## Usage Examples

```bash
# List all releases with download status for a site
uv run culture ce downloads list --site xart

# Newest releases first
uv run culture ce downloads list --site xart --desc

# Releases with no downloads at all
uv run culture ce downloads list --site xart --downloads none

# Releases missing video downloads (may have covers/galleries)
uv run culture ce downloads list --site xart --missing-file video

# Releases that have video downloads
uv run culture ce downloads list --site xart --has-file video

# Releases missing scene content type
uv run culture ce downloads list --site xart --missing-content scene

# Releases that have cover content type
uv run culture ce downloads list --site xart --has-content cover

# Combine filters: newest releases missing video, limit to 20
uv run culture ce downloads list --site xart --missing-file video --desc --limit 20

# JSON output for parsing
uv run culture ce downloads list --site xart --json
```

## Options

- `--site` / `-s` - Site identifier (short name or UUID) — **required**
- `--downloads` - Basic filter: `all` (default) or `none` (no downloads)
- `--has-file TYPE` - Show releases with this file_type downloaded (e.g. `video`, `image`, `gallery`)
- `--missing-file TYPE` - Show releases missing this file_type
- `--has-content TYPE` - Show releases with this content_type downloaded (e.g. `scene`, `cover`, `gallery`)
- `--missing-content TYPE` - Show releases missing this content_type
- `--limit` / `-l` - Limit number of results
- `--desc` / `-d` - Sort by release date descending (newest first)
- `--json` / `-j` - Output results as JSON

## Download Types

File types and content types vary between sites. The command shows a summary of available types at the bottom of the output. Common values:

**File types:** `video`, `image`, `gallery`, `audio`, `zip`
**Content types:** `scene`, `cover`, `gallery`, `preview`, `poster`

## Output Format

Table output:
```
Date        | Name             | Short Name  | Downloads
2024-01-01  | Scene Title      | scene-title | 5 (video/scene, image/cover)
2024-01-02  | Another Scene    | another     | 2 (image/cover)
2024-01-03  | No Downloads     | no-dl       | —
```

After the table, a summary line shows all file types and content types found:
```
File types: gallery, image, video
Content types: cover, gallery, scene
```
