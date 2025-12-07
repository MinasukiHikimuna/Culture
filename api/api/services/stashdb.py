"""StashDB GraphQL client for performer lookups.

This service provides async access to StashDB for performer details,
aliases, and search functionality.
"""

import os
from dataclasses import dataclass

import httpx


@dataclass
class StashDBPerformer:
    """Performer data from StashDB."""

    id: str
    name: str
    disambiguation: str | None
    aliases: list[str]
    country: str | None
    image_url: str | None


class StashDBClient:
    """Async client for StashDB GraphQL API."""

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize the client.

        Args:
            endpoint: StashDB GraphQL endpoint URL
            api_key: API key for authentication
        """
        self.endpoint = endpoint or os.environ.get(
            "STASHDB_ENDPOINT", "https://stashdb.org/graphql"
        )
        self.api_key = api_key or os.environ.get("STASHDB_API_KEY", "")

    async def get_performer(self, performer_id: str) -> StashDBPerformer | None:
        """Get performer details by ID.

        Args:
            performer_id: StashDB performer UUID

        Returns:
            StashDBPerformer or None if not found
        """
        query = """
            query FindPerformer($id: ID!) {
                findPerformer(id: $id) {
                    id
                    name
                    disambiguation
                    aliases
                    country
                    images {
                        id
                        url
                    }
                }
            }
        """

        result = await self._gql_query(query, {"id": performer_id})
        if not result or "data" not in result:
            return None

        performer_data = result["data"].get("findPerformer")
        if not performer_data:
            return None

        return self._parse_performer(performer_data)

    async def search_performers(
        self,
        query: str,
        limit: int = 10,
    ) -> list[StashDBPerformer]:
        """Search performers by name.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching performers
        """
        gql_query = """
            query SearchPerformers($term: String!, $limit: Int!) {
                searchPerformer(term: $term, limit: $limit) {
                    id
                    name
                    disambiguation
                    aliases
                    country
                    images {
                        id
                        url
                    }
                }
            }
        """

        result = await self._gql_query(gql_query, {"term": query, "limit": limit})
        if not result or "data" not in result:
            return []

        performers_data = result["data"].get("searchPerformer", [])
        return [self._parse_performer(p) for p in performers_data]

    def _parse_performer(self, data: dict) -> StashDBPerformer:
        """Parse performer data from GraphQL response.

        Args:
            data: Raw performer data dict

        Returns:
            StashDBPerformer instance
        """
        images = data.get("images", [])
        image_url = images[0]["url"] if images else None

        return StashDBPerformer(
            id=data["id"],
            name=data["name"],
            disambiguation=data.get("disambiguation"),
            aliases=data.get("aliases", []),
            country=data.get("country"),
            image_url=image_url,
        )

    async def _gql_query(
        self, query: str, variables: dict | None = None
    ) -> dict | None:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Response dict or None on error
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Apikey"] = self.api_key

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.endpoint,
                json={"query": query, "variables": variables},
                headers=headers,
            )

        if response.status_code != 200:
            return None

        return response.json()
