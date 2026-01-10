# Reddit API Setup Guide

This guide will help you set up Reddit API access to use the `reddit_extractor.py` script.

## Prerequisites

1. **uv**: Dependencies are managed via `uv` and will be installed automatically
2. **Reddit Account**: You need a Reddit account

## Step 1: Create a Reddit App

1. Go to https://www.reddit.com/prefs/apps
2. Scroll to the bottom and click **"Create App"** or **"Create Another App"**
3. Fill out the form:
   - **Name**: Choose any name (e.g., "gwasi-reddit-extractor")
   - **App type**: Select **"script"** 
   - **Description**: Optional description
   - **About URL**: Leave blank or add any URL
   - **Redirect URI**: Use `http://localhost:8080` (required but not used for scripts)
4. Click **"Create app"**

## Step 2: Get Your Credentials

After creating the app, you'll see something like this:

```
personal use script
[Your App Name]
[long string of characters] <- This is your CLIENT_ID
```

- **CLIENT_ID**: The string of characters under "personal use script"
- **CLIENT_SECRET**: Click "edit" to see the secret key

## Step 3: Set Environment Variables

### On Windows (Command Prompt):
```cmd
set REDDIT_CLIENT_ID=your_client_id_here
set REDDIT_CLIENT_SECRET=your_client_secret_here
set REDDIT_USER_AGENT=reddit_extractor/1.0 by your_reddit_username
```

### On Windows (PowerShell):
```powershell
$env:REDDIT_CLIENT_ID="your_client_id_here"
$env:REDDIT_CLIENT_SECRET="your_client_secret_here" 
$env:REDDIT_USER_AGENT="reddit_extractor/1.0 by your_reddit_username"
```

### Permanent Setup (Windows):
1. Right-click "This PC" → Properties → Advanced System Settings
2. Click "Environment Variables"
3. Under "User variables", click "New" and add:
   - `REDDIT_CLIENT_ID` = your client ID
   - `REDDIT_CLIENT_SECRET` = your client secret
   - `REDDIT_USER_AGENT` = reddit_extractor/1.0 by your_username

## Step 4: Test the Setup

Run a small test with limited posts:

```bash
uv run python reddit_extractor.py aural_data/index/gwasi/gwasi_data_*.json --max-posts 5
```

## Usage Examples

### Basic usage:
```bash
uv run python reddit_extractor.py aural_data/index/gwasi/gwasi_data_*.json
```

### With custom output directory:
```bash
uv run python reddit_extractor.py aural_data/index/gwasi/gwasi_data_*.json --output my_reddit_data
```

### Process only first 10 posts for testing:
```bash
uv run python reddit_extractor.py aural_data/index/gwasi/gwasi_data_*.json --max-posts 10
```

### Custom rate limiting (slower requests):
```bash
uv run python reddit_extractor.py aural_data/index/gwasi/gwasi_data_*.json --delay 2.0
```

### Pass credentials directly (not recommended for security):
```bash
uv run python reddit_extractor.py gwasi_data.json --client-id YOUR_ID --client-secret YOUR_SECRET
```

## Output Files

The script creates several output files:

- `reddit_enriched_TIMESTAMP.csv` - Flattened CSV with all data
- `reddit_enriched_TIMESTAMP.json` - Full JSON with nested structure  
- `failed_posts_TIMESTAMP.json` - Posts that couldn't be fetched (for debugging)

## Rate Limiting

The script includes built-in rate limiting (1 second between requests by default) to be respectful to Reddit's API. You can adjust this with the `--delay` parameter.

## Troubleshooting

### "Reddit API credentials not found" error:
- Make sure environment variables are set correctly
- Try restarting your command prompt/terminal after setting variables
- Use the `--client-id` and `--client-secret` parameters as a test

### "403 Forbidden" or "401 Unauthorized" errors:
- Double-check your client ID and secret
- Make sure you selected "script" as the app type
- Verify your user agent string

### Posts showing as "[deleted]" or not found:
- Some posts may have been deleted from Reddit
- Private subreddits won't be accessible
- Some posts may be quarantined or restricted

### Rate limiting / 429 errors:
- Increase the delay with `--delay 2.0` or higher
- Reddit API has limits, the script will handle most cases automatically

## Data Structure

The enriched data combines gwasi metadata with detailed Reddit information:

```json
{
  "post_id": "abc123",
  "subreddit": "gonewildaudio", 
  "username": "user123",
  "full_title": "[M4F] Example Title [tags]",
  "reddit_data": {
    "title": "Full Reddit title",
    "selftext": "Post content text",
    "score": 150,
    "upvote_ratio": 0.95,
    "num_comments": 23,
    "created_date": "2025-07-30T12:00:00",
    "over_18": true,
    "link_flair_text": "Audio",
    "total_awards_received": 2,
    "all_awardings": [...],
    // ... many more Reddit fields
  }
}
```

This gives you both the gwasi index data and full Reddit post details for comprehensive analysis.