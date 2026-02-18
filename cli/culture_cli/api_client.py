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

    def create_site(
        self,
        short_name: str,
        name: str,
        url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> dict:
        """Create a new site.

        Args:
            short_name: Short identifier for the site
            name: Full site name
            url: Base URL of the site
            username: Optional username for site authentication
            password: Optional password for site authentication

        Returns:
            Dictionary with created site info including uuid
        """
        payload: dict[str, str] = {"short_name": short_name, "name": name, "url": url}
        if username is not None:
            payload["username"] = username
        if password is not None:
            payload["password"] = password
        response = self.client.post("/sites", json=payload)
        response.raise_for_status()
        return response.json()

    # Releases endpoints

    def get_releases(
        self,
        site: str,
        tag: str | None = None,
        performer: str | None = None,
        limit: int | None = None,
        desc: bool = False,
    ) -> list[dict]:
        """Get releases for a site.

        Args:
            site: Site identifier (UUID, short_name, or name)
            tag: Optional tag filter (UUID, short_name, or name)
            performer: Optional performer filter (UUID, short_name, or name)
            limit: Optional limit on number of results
            desc: Sort by release date descending (newest first)

        Returns:
            List of release dictionaries
        """
        params: dict[str, str | int] = {"site": site}
        if tag is not None:
            params["tag"] = tag
        if performer is not None:
            params["performer"] = performer
        if limit is not None:
            params["limit"] = limit
        if desc:
            params["desc"] = "true"
        response = self.client.get("/releases", params=params)
        response.raise_for_status()
        return response.json()

    def get_download_summary(
        self,
        site: str,
        downloads: str = "all",
        has_file: str | None = None,
        missing_file: str | None = None,
        has_content: str | None = None,
        missing_content: str | None = None,
        limit: int | None = None,
        desc: bool = False,
    ) -> list[dict]:
        """Get per-release download summary for a site.

        Args:
            site: Site identifier (UUID, short_name, or name)
            downloads: Basic filter: 'all' (default) or 'none'
            has_file: Filter to releases with this file_type
            missing_file: Filter to releases missing this file_type
            has_content: Filter to releases with this content_type
            missing_content: Filter to releases missing this content_type
            limit: Optional limit on number of results
            desc: Sort by release date descending (newest first)

        Returns:
            List of release download summary dictionaries
        """
        params: dict[str, str | int] = {"site": site}
        if downloads != "all":
            params["downloads"] = downloads
        if has_file is not None:
            params["has_file"] = has_file
        if missing_file is not None:
            params["missing_file"] = missing_file
        if has_content is not None:
            params["has_content"] = has_content
        if missing_content is not None:
            params["missing_content"] = missing_content
        if limit is not None:
            params["limit"] = limit
        if desc:
            params["desc"] = "true"
        response = self.client.get("/downloads", params=params)
        response.raise_for_status()
        return response.json()

    def get_release(self, uuid: str) -> dict:
        """Get detailed information about a specific release.

        Args:
            uuid: Release UUID

        Returns:
            Release dictionary with performers, tags, downloads, and external_ids
        """
        response = self.client.get(f"/releases/{uuid}")
        response.raise_for_status()
        return response.json()

    def link_release(self, uuid: str, target: str, external_id: str) -> dict:
        """Link a release to an external system.

        Args:
            uuid: Release UUID
            target: Target system name (stashapp or stashdb)
            external_id: External ID value

        Returns:
            Response with confirmation message
        """
        response = self.client.post(
            f"/releases/{uuid}/link",
            json={"target": target, "external_id": external_id},
        )
        response.raise_for_status()
        return response.json()

    def delete_release(self, uuid: str) -> dict:
        """Delete a release from the database.

        Args:
            uuid: Release UUID

        Returns:
            Response with deletion details (release_name, site_name, downloads)
        """
        response = self.client.delete(f"/releases/{uuid}")
        response.raise_for_status()
        return response.json()

    # Downloads endpoints

    def get_download(self, uuid: str) -> dict:
        """Get details about a specific download.

        Args:
            uuid: Download UUID

        Returns:
            Download dictionary with release and site context
        """
        response = self.client.get(f"/downloads/{uuid}")
        response.raise_for_status()
        return response.json()

    def delete_download(self, uuid: str) -> dict:
        """Delete a single download from the database.

        Args:
            uuid: Download UUID

        Returns:
            Response with deletion details (site_name, release_name, release_uuid,
            saved_filename, file_type, content_type, variant, external_ids_deleted)
        """
        response = self.client.delete(f"/downloads/{uuid}")
        response.raise_for_status()
        return response.json()

    # Performers endpoints

    def get_performers(
        self,
        site: str,
        name: str | None = None,
        unmapped_only: bool = False,
        target_system: str = "stashapp",
        limit: int | None = None,
    ) -> list[dict]:
        """Get performers for a site.

        Args:
            site: Site identifier (UUID, short_name, or name)
            name: Optional name filter (case-insensitive)
            unmapped_only: Only show performers without external IDs
            target_system: Target system to check for unmapped filter
            limit: Optional limit on number of results

        Returns:
            List of performer dictionaries
        """
        params: dict[str, str | int | bool] = {"site": site}
        if name is not None:
            params["name"] = name
        if unmapped_only:
            params["unmapped_only"] = True
            params["target_system"] = target_system
        if limit is not None:
            params["limit"] = limit
        response = self.client.get("/performers", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("items", []) if isinstance(data, dict) else data

    def get_performer(self, uuid: str) -> dict:
        """Get detailed information about a specific performer.

        Args:
            uuid: Performer UUID

        Returns:
            Performer dictionary with external_ids
        """
        response = self.client.get(f"/performers/{uuid}")
        response.raise_for_status()
        return response.json()

    def link_performer(self, uuid: str, target: str, external_id: str) -> dict:
        """Link a performer to an external system.

        Args:
            uuid: Performer UUID
            target: Target system name (stashapp or stashdb)
            external_id: External ID value

        Returns:
            Response with confirmation message
        """
        response = self.client.post(
            f"/performers/{uuid}/link",
            json={"target": target, "external_id": external_id},
        )
        response.raise_for_status()
        return response.json()
