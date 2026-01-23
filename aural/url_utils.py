#!/usr/bin/env python3
"""
URL utilities for audio platform detection and validation.
"""

import re


def is_audio_content_url(url: str) -> bool:
    """
    Check if a URL points to actual audio content vs a user profile page.

    Content URLs have a specific audio identifier in the path.
    Profile URLs just point to a user's page without a specific audio.

    Returns:
        True if URL is a content URL, False if it's a profile URL.
    """
    url_lower = url.lower()

    # Soundgasm: /u/Username/AudioTitle (two segments after /u/)
    if "soundgasm.net" in url_lower:
        match = re.search(r"soundgasm\.net/u/[^/]+/[^/]+", url_lower)
        return match is not None

    # HotAudio: /u/Username/AudioSlug (two segments after /u/)
    if "hotaudio.net" in url_lower:
        match = re.search(r"hotaudio\.net/u/[^/]+/[^/]+", url_lower)
        return match is not None

    # Audiochan: /a/slug (content), /u/Username (profile)
    if "audiochan.com" in url_lower:
        # Content URLs use /a/, profile URLs use /u/
        return "/a/" in url_lower

    # Whyp.it: /track/id format
    if "whyp.it" in url_lower:
        return "/track/" in url_lower

    # Erocast: /track/slug format
    if "erocast.me" in url_lower:
        return "/track/" in url_lower

    # Unknown platform - assume it's content
    return True
