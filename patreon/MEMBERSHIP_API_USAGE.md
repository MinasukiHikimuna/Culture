# Patreon Membership API Usage

The cookie scraper now supports the Patreon `/api/current_user` endpoint to automatically discover all campaigns you have memberships with. This eliminates the need to manually specify creator names and provides powerful bulk scraping capabilities.

## New Features

### 1. List All Memberships

Get a complete list of all campaigns you have memberships with:

```bash
python scripts/cookie_scraper.py list --cookies-file cookies.json
```

This will show:

- Campaign names and vanity URLs
- Campaign IDs
- Membership type (FREE/PAID)
- NSFW status
- Summary statistics

### 2. Multi-Creator Scraping

Scrape multiple creators at once based on your memberships:

```bash
# Scrape ALL campaigns you have memberships with
python scripts/cookie_scraper.py multi --cookies-file cookies.json

# Scrape only PAID memberships
python scripts/cookie_scraper.py multi --cookies-file cookies.json --paid-only

# Scrape specific creators
python scripts/cookie_scraper.py multi --cookies-file cookies.json --creators creator1 creator2 creator3

# Scrape without downloading media (URLs only)
python scripts/cookie_scraper.py multi --cookies-file cookies.json --no-download
```

### 3. Enhanced Single Creator Scraping

The original single creator functionality is now available under the `single` subcommand:

```bash
python scripts/cookie_scraper.py single creator_name --cookies-file cookies.json
```

## API Endpoint Details

The new functionality uses this Patreon API endpoint:

```
GET https://www.patreon.com/api/current_user?include=active_memberships.campaign&fields[campaign]=avatar_photo_image_urls%2Cname%2Cpublished_at%2Curl%2Cvanity%2Cis_nsfw%2Curl_for_current_user&fields[member]=is_free_member%2Cis_free_trial&json-api-version=1.0&json-api-use-default-includes=false
```

This returns:

- User profile information
- All active memberships
- Campaign details for each membership
- Membership status (free/paid/trial)

## Data Structure

Each campaign object contains:

```json
{
  "campaign_id": "12345678",
  "name": "Creator Name",
  "vanity": "creator_vanity_url",
  "url": "https://www.patreon.com/creator_vanity_url",
  "url_for_current_user": "https://www.patreon.com/c/creator_vanity_url",
  "is_nsfw": true,
  "published_at": "2024-01-01T00:00:00.000+00:00",
  "is_free_member": false,
  "is_free_trial": false,
  "avatar_urls": {
    "default": "https://...",
    "thumbnail": "https://..."
    // ... other sizes
  }
}
```

## Benefits

1. **No Manual Campaign Discovery**: Automatically finds all your memberships
2. **Bulk Operations**: Scrape multiple creators efficiently
3. **Filtering Options**: Focus on paid memberships or specific creators
4. **Campaign ID Optimization**: Uses known campaign IDs instead of searching
5. **Membership Awareness**: Knows your access level for each creator

## Usage Examples

### Discover Your Memberships

```bash
# See what campaigns you have access to
python scripts/cookie_scraper.py list --cookies-file cookies.json
```

### Bulk Scrape Paid Content

```bash
# Download all content from paid memberships
python scripts/cookie_scraper.py multi --cookies-file cookies.json --paid-only
```

### Selective Scraping

```bash
# Scrape only specific high-priority creators
python scripts/cookie_scraper.py multi --cookies-file cookies.json --creators creator1 creator2
```

### URL Extraction Only

```bash
# Get media URLs without downloading (for analysis)
python scripts/cookie_scraper.py multi --cookies-file cookies.json --no-download
```

## Rate Limiting

The multi-creator scraper includes:

- 1-second delay between API requests
- 2-second delay between different creators
- Respectful request patterns

## Error Handling

- Individual creator failures don't stop the entire batch
- Detailed error reporting for each creator
- Summary statistics at the end
- Graceful handling of authentication issues

## Testing

Use the test script to verify your setup:

```bash
python test_membership_api.py
```

This will show your memberships and provide usage examples specific to your account.
