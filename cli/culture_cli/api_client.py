"""HTTP client for Culture API."""

import os
from typing import Self

import httpx


class CultureAPIClient:
    """Client for interacting with the Culture API."""

    def __init__(self, base_url: str | None = None):
        """Initialize the API client.

        Args:
            base_url: Base URL for the API. Defaults to CULTURE_API_URL env var
                     or http://localhost:8000
        """
        if base_url is None:
            base_url = os.environ.get("CULTURE_API_URL", "http://localhost:8000")
        self.client = httpx.Client(base_url=base_url, timeout=30.0)

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # Sites endpoints

    def get_sites(self, linked: bool | None = None) -> list[dict]:
        """Get all sites.

        Args:
            linked: Filter by link status. True=linked only, False=unlinked only,
                   None=all sites

        Returns:
            List of site dictionaries
        """
        params = {}
        if linked is not None:
            params["linked"] = str(linked).lower()
        response = self.client.get("/sites", params=params)
        response.raise_for_status()
        return response.json()

    def get_site(self, uuid: str) -> dict:
        """Get a specific site by UUID.

        Args:
            uuid: Site UUID

        Returns:
            Site dictionary with external_ids
        """
        response = self.client.get(f"/sites/{uuid}")
        response.raise_for_status()
        return response.json()

    def link_site(self, uuid: str, target: str, external_id: str) -> dict:
        """Link a site to an external system.

        Args:
            uuid: Site UUID
            target: Target system name (stashapp or stashdb)
            external_id: External ID value

        Returns:
            Response with confirmation message
        """
        response = self.client.post(
            f"/sites/{uuid}/link",
            json={"target": target, "external_id": external_id},
        )
        response.raise_for_status()
        return response.json()
