"""Shared utilities for API routers."""

from fastapi import HTTPException

from libraries.client_culture_extractor import ClientCultureExtractor


def resolve_site(client: ClientCultureExtractor, site: str) -> tuple[str, str]:
    """Resolve site identifier to UUID and name.

    Args:
        client: Culture Extractor database client
        site: Site identifier (UUID, short_name, or name)

    Returns:
        Tuple of (site_uuid, site_name)

    Raises:
        HTTPException: If site is not found
    """
    sites_df = client.get_sites()
    site_match = sites_df.filter(
        (sites_df["ce_sites_short_name"] == site)
        | (sites_df["ce_sites_uuid"] == site)
        | (sites_df["ce_sites_name"] == site)
    )

    if site_match.is_empty():
        raise HTTPException(status_code=404, detail=f"Site '{site}' not found")

    return site_match["ce_sites_uuid"][0], site_match["ce_sites_name"][0]
