#!/usr/bin/env python3
"""
Reddit Flair Fetcher - Get user flair from a subreddit

Usage:
    python reddit-flair-fetcher.py <username> [--subreddit gonewildaudio]

Returns JSON with flair information that can be used to determine gender.
"""

import argparse
import json
import os
import sys

import praw
from dotenv import load_dotenv


def get_reddit_client():
    """Initialize Reddit client using environment variables."""
    load_dotenv()

    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "Aural/1.0")

    if not client_id or not client_secret:
        print(json.dumps({
            "error": "Missing Reddit credentials",
            "message": "Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env"
        }))
        sys.exit(1)

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )


def get_user_flair(reddit, username: str, subreddit_name: str = "gonewildaudio") -> dict:
    """
    Get a user's flair in a specific subreddit.

    Since direct flair API requires moderator permissions, we fetch the user's
    recent posts in the subreddit and extract author_flair_text from there.

    Args:
        reddit: PRAW Reddit instance
        username: Reddit username (without u/)
        subreddit_name: Subreddit to check flair in

    Returns:
        Dictionary with flair information
    """
    try:
        # Get user's recent submissions in the subreddit
        redditor = reddit.redditor(username)

        flair_text = None
        flair_css_class = None

        # Search user's submissions in the target subreddit
        for submission in redditor.submissions.new(limit=50):
            if submission.subreddit.display_name.lower() == subreddit_name.lower():
                if submission.author_flair_text:
                    flair_text = submission.author_flair_text
                    flair_css_class = submission.author_flair_css_class
                    break

        # If no submissions found, try comments
        if not flair_text:
            for comment in redditor.comments.new(limit=50):
                if comment.subreddit.display_name.lower() == subreddit_name.lower():
                    if comment.author_flair_text:
                        flair_text = comment.author_flair_text
                        flair_css_class = comment.author_flair_css_class
                        break

        if flair_text:
            # Parse gender from flair
            gender = parse_gender_from_flair(flair_text, flair_css_class)

            return {
                "username": username,
                "subreddit": subreddit_name,
                "flair_text": flair_text,
                "flair_css_class": flair_css_class,
                "gender": gender,
                "stashapp_gender": map_to_stashapp_gender(gender)
            }
        return {
            "username": username,
            "subreddit": subreddit_name,
            "flair_text": None,
            "flair_css_class": None,
            "gender": None,
            "stashapp_gender": None,
            "note": "No flair found in recent posts/comments"
        }

    except Exception as e:
        return {
            "username": username,
            "subreddit": subreddit_name,
            "error": str(e)
        }


def parse_gender_from_flair(flair_text: str, flair_css_class: str) -> str | None:
    """
    Parse gender from flair text and CSS class.

    GoneWildAudio flairs typically include:
    - ":female: Verified!" or ":male: Verified!" with emoji placeholders
    - "Verified!" with CSS class indicating gender
    - Custom text that may include gender indicators
    - Pronouns like "(she/her)" or "(he/him)"
    - Bracketed markers like "[F]" or "[M]"

    CSS classes often used:
    - "f-flair" or similar for female
    - "m-flair" or similar for male
    - "nb-flair" for non-binary
    - "t-flair" for trans
    """
    import re

    if not flair_text and not flair_css_class:
        return None

    flair_lower = (flair_text or "").lower()
    css_lower = (flair_css_class or "").lower()

    # Check for Reddit emoji placeholders first (most common in GWA)
    # Format: :female:, :male:, :nonbinary:, :trans:, etc.
    if flair_text:
        if ":female:" in flair_text.lower():
            return "female"
        if ":male:" in flair_text.lower():
            return "male"
        if ":nonbinary:" in flair_text.lower() or ":non-binary:" in flair_text.lower() or ":nb:" in flair_text.lower():
            return "non_binary"
        if ":trans:" in flair_text.lower():
            if ":transm:" in flair_text.lower() or ":ftm:" in flair_text.lower():
                return "transgender_male"
            if ":transf:" in flair_text.lower() or ":mtf:" in flair_text.lower():
                return "transgender_female"
            return "transgender"

    # Check CSS class (backup)
    if css_lower:
        if "female" in css_lower or css_lower.startswith("f-") or css_lower == "f":
            return "female"
        if "male" in css_lower or css_lower.startswith("m-") or css_lower == "m":
            # Check it's not "female"
            if "female" not in css_lower:
                return "male"
        if "nb" in css_lower or "nonbinary" in css_lower or "non-binary" in css_lower:
            return "non_binary"
        if "trans" in css_lower:
            if "ftm" in css_lower or "transm" in css_lower:
                return "transgender_male"
            if "mtf" in css_lower or "transf" in css_lower:
                return "transgender_female"
            return "transgender"

    # Check flair text for other patterns
    if flair_lower:
        # Unicode symbols
        if "♀" in flair_text:
            return "female"
        if "♂" in flair_text:
            return "male"

        # Pronoun indicators
        if "she/her" in flair_lower or "(she)" in flair_lower:
            return "female"
        if "he/him" in flair_lower or "(he)" in flair_lower:
            return "male"
        if "they/them" in flair_lower:
            return "non_binary"

        # Bracketed gender markers [F], [M], [NB]
        if re.search(r"\[f\]", flair_lower):
            return "female"
        if re.search(r"\[m\]", flair_lower) and not re.search(r"\[fm\]|\[mf\]", flair_lower):
            return "male"
        if re.search(r"\[nb\]", flair_lower):
            return "non_binary"

        # Text patterns (be careful with "male" matching "female")
        if "female" in flair_lower:
            return "female"
        if "male" in flair_lower and "female" not in flair_lower:
            return "male"
        if "non-binary" in flair_lower or "nonbinary" in flair_lower:
            return "non_binary"
        if "trans" in flair_lower:
            return "transgender"

        # Check for F/M at start of flair (common pattern)
        if flair_lower.startswith("f ") or flair_lower.startswith("f/"):
            return "female"
        if flair_lower.startswith("m ") or flair_lower.startswith("m/"):
            return "male"

    return None


def map_to_stashapp_gender(gender: str | None) -> str | None:
    """
    Map parsed gender to Stashapp GenderEnum values.

    Stashapp values: MALE, FEMALE, TRANSGENDER_MALE, TRANSGENDER_FEMALE, INTERSEX, NON_BINARY
    """
    if not gender:
        return None

    mapping = {
        "male": "MALE",
        "female": "FEMALE",
        "transgender_male": "TRANSGENDER_MALE",
        "transgender_female": "TRANSGENDER_FEMALE",
        "transgender": None,  # Can't determine specific type
        "non_binary": "NON_BINARY",
        "intersex": "INTERSEX"
    }

    return mapping.get(gender)


def main():
    parser = argparse.ArgumentParser(
        description="Get Reddit user flair from a subreddit"
    )
    parser.add_argument("username", help="Reddit username to look up")
    parser.add_argument(
        "--subreddit", "-s",
        default="gonewildaudio",
        help="Subreddit to check flair in (default: gonewildaudio)"
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="Pretty print JSON output"
    )

    args = parser.parse_args()

    # Remove u/ prefix if present
    username = args.username.lstrip("u/").lstrip("/u/")

    reddit = get_reddit_client()
    result = get_user_flair(reddit, username, args.subreddit)

    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
