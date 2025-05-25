#!/usr/bin/env python3
"""
Test script to demonstrate the new membership API functionality.
This shows how to use the current_user endpoint to get all campaigns.
"""

import json
from scripts.cookie_scraper import (
    cookies_json_to_string,
    create_headers,
    get_user_memberships,
    extract_campaigns_from_memberships,
    list_user_campaigns,
)


def test_membership_api():
    """Test the membership API with sample cookies."""

    # You would replace this with your actual cookies file
    cookies_file = "cookies.json"

    try:
        with open(cookies_file, "r", encoding="utf-8") as f:
            cookies_json = f.read()
    except FileNotFoundError:
        print(
            f"Please create a {cookies_file} file with your cookies from Copy Cookies extension"
        )
        return

    print("Testing membership API...")

    # Test listing campaigns
    campaigns = list_user_campaigns(cookies_json)

    if campaigns:
        print(f"\n🎉 Successfully found {len(campaigns)} campaigns!")

        # Show some examples
        print("\nExamples of what you can do:")

        # Show paid vs free breakdown
        paid_campaigns = [c for c in campaigns if not c["is_free_member"]]
        free_campaigns = [c for c in campaigns if c["is_free_member"]]

        print(f"📊 Membership breakdown:")
        print(f"   Paid memberships: {len(paid_campaigns)}")
        print(f"   Free memberships: {len(free_campaigns)}")

        # Show NSFW breakdown
        nsfw_campaigns = [c for c in campaigns if c["is_nsfw"]]
        print(f"   NSFW campaigns: {len(nsfw_campaigns)}")

        # Show some campaign names
        print(f"\n📝 Sample campaign names:")
        for i, campaign in enumerate(campaigns[:5], 1):
            membership_type = "PAID" if not campaign["is_free_member"] else "FREE"
            nsfw_flag = " [NSFW]" if campaign["is_nsfw"] else ""
            print(f"   {i}. {campaign['name']}{nsfw_flag} ({membership_type})")

        if len(campaigns) > 5:
            print(f"   ... and {len(campaigns) - 5} more")

        print(f"\n💡 Usage examples:")
        print(f"   # List all campaigns:")
        print(f"   python cookie_scraper.py list --cookies-file cookies.json")
        print(f"   ")
        print(f"   # Scrape a single creator:")
        print(
            f"   python cookie_scraper.py single {campaigns[0]['vanity']} --cookies-file cookies.json"
        )
        print(f"   ")
        print(f"   # Scrape all paid memberships:")
        print(
            f"   python cookie_scraper.py multi --cookies-file cookies.json --paid-only"
        )
        print(f"   ")
        print(f"   # Scrape specific creators:")
        print(
            f"   python cookie_scraper.py multi --cookies-file cookies.json --creators {campaigns[0]['vanity']} {campaigns[1]['vanity'] if len(campaigns) > 1 else campaigns[0]['vanity']}"
        )

    else:
        print("❌ No campaigns found. Check your cookies file.")


if __name__ == "__main__":
    test_membership_api()
