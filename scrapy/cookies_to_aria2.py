#!/usr/bin/env python3
"""Convert JSON cookies to aria2c format"""
import json
import os
from dotenv import load_dotenv

load_dotenv()

def json_to_aria2_header(cookie_json_str):
    """Convert JSON cookie string to aria2c --header format"""
    if not cookie_json_str or cookie_json_str == '{}':
        return ""

    cookies = json.loads(cookie_json_str)
    cookie_pairs = [f"{c['name']}={c['value']}" for c in cookies]
    return "; ".join(cookie_pairs)

def json_to_netscape_format(cookie_json_str, domain):
    """Convert JSON cookies to Netscape cookies.txt format for aria2c --load-cookies"""
    if not cookie_json_str or cookie_json_str == '{}':
        return ""

    cookies = json.loads(cookie_json_str)
    lines = ["# Netscape HTTP Cookie File"]

    for cookie in cookies:
        # Netscape format: domain, flag, path, secure, expiration, name, value
        cookie_domain = cookie.get('domain', domain)
        include_subdomains = "TRUE" if cookie_domain.startswith('.') else "FALSE"
        path = cookie.get('path', '/')
        secure = "TRUE" if cookie.get('secure', False) else "FALSE"

        # Handle expiration
        if 'expirationDate' in cookie:
            expiration = str(int(cookie['expirationDate']))
        else:
            expiration = "0"  # Session cookie

        name = cookie['name']
        value = cookie['value']

        line = f"{cookie_domain}\t{include_subdomains}\t{path}\t{secure}\t{expiration}\t{name}\t{value}"
        lines.append(line)

    return "\n".join(lines)

# Get ANGELSLOVE_COOKIES from environment
angelslove_cookies = os.getenv('ANGELSLOVE_COOKIES', '[]')

print("=" * 80)
print("ANGELSLOVE COOKIES - aria2c --header format:")
print("=" * 80)
header_format = json_to_aria2_header(angelslove_cookies)
print(f'--header="Cookie: {header_format}"')

print("\n" + "=" * 80)
print("ANGELSLOVE COOKIES - Netscape cookies.txt format:")
print("=" * 80)
netscape_format = json_to_netscape_format(angelslove_cookies, 'angels.love')
print(netscape_format)

print("\n" + "=" * 80)
print("Example aria2c command with header:")
print("=" * 80)
print(f'''aria2c \\
  --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0" \\
  --header="Cookie: {header_format}" \\
  --header="Referer: https://angels.love/" \\
  --max-connection-per-server=16 \\
  --split=16 \\
  --min-split-size=1M \\
  --continue=true \\
  --dir=/Volumes/Ripping/ \\
  --out="test-download.mp4" \\
  "<URL>"
''')

print("\n" + "=" * 80)
print("To save cookies.txt file for use with --load-cookies:")
print("=" * 80)
print("python cookies_to_aria2.py > cookies.txt")
print("aria2c --load-cookies=cookies.txt --user-agent=\"...\" <URL>")
