import argparse
import praw
import sys
import json
import os
import time
from datetime import datetime

import dotenv

import config as aural_config

def format_filename(author, created_utc, post_id):
    # Convert UTC timestamp to datetime
    date_str = datetime.fromtimestamp(created_utc).strftime('%Y-%m-%d')
    # Create safe filename
    author = ''.join(c for c in author if c.isalnum() or c in ('-', '_'))
    return f"{author}_{date_str}_{post_id}.json"

def save_post_data(post):
    # Extract relevant post data
    post_data = {
        'title': post.title,
        'author': post.author.name if post.author else '[deleted]',
        'url': post.url,
        'created_utc': post.created_utc,
        'id': post.id,
        'permalink': f"https://reddit.com{post.permalink}",
        'score': post.score,
        'subreddit': post.subreddit.display_name,
        'selftext': post.selftext,
        'selftext_html': post.selftext_html
    }

    # Create filename using post metadata
    filename = format_filename(post_data['author'], post_data['created_utc'], post_data['id'])

    # Create saved posts directory if it doesn't exist
    save_dir = aural_config.REDDIT_SAVED_PENDING_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    # Save to JSON file
    filepath = save_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(post_data, f, indent=2)

    return filepath

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unsave', action='store_true', help='Unsave parsed posts')
    args = parser.parse_args()

    try:
        dotenv.load_dotenv()
    except Exception as e:
        print(f"Error loading .env file: {str(e)}", file=sys.stderr)
        sys.exit(1)

    env_client_id = os.getenv("REDDIT_CLIENT_ID")
    env_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    env_username = os.getenv("REDDIT_USERNAME")
    env_password = os.getenv("REDDIT_PASSWORD")

    if not env_client_id:
        print("REDDIT_CLIENT_ID is not set", file=sys.stderr)
        sys.exit(1)
    if not env_client_secret:
        print("REDDIT_CLIENT_SECRET is not set", file=sys.stderr)
        sys.exit(1)
    if not env_password:
        print("REDDIT_PASSWORD is not set", file=sys.stderr)
        sys.exit(1)
    if not env_username:
        print("REDDIT_USERNAME is not set", file=sys.stderr)
        sys.exit(1)

    try:
        reddit = praw.Reddit(
            client_id=env_client_id,
            client_secret=env_client_secret,
            password=env_password,
            username=env_username,
            user_agent=f'script:gwa_saved:v1.0 (by /u/{env_username})'
        )

        me = reddit.user.me()
        items = me.saved(limit=None)

        saved_count = 0
        failed_count = 0
        skipped_count = 0

        for item in items:
            if isinstance(item, praw.models.Submission):
                try:
                    filepath = save_post_data(item)
                    print(f"Saved: {filepath}")
                    saved_count += 1
                    if args.unsave:
                        item.unsave()
                    time.sleep(0.5)  # Rate limit delay
                except Exception as e:
                    print(f"Failed to save {item.id}: {e}", file=sys.stderr)
                    failed_count += 1
            else:
                skipped_count += 1

        # Get remaining saved count
        remaining_saved = sum(1 for _ in me.saved(limit=None))

        print(f"\n--- Summary ---")
        print(f"Saved: {saved_count}")
        print(f"Failed: {failed_count}")
        print(f"Skipped (non-submissions): {skipped_count}")
        print(f"Remaining saved on Reddit: {remaining_saved}")

    except Exception as e:
        print(f"Authentication error: {str(e)}", file=sys.stderr)
        print(f"Error type: {type(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
