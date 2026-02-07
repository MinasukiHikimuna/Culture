"""Stashapp GraphQL client for local Stashapp queries.

This service provides async access to Stashapp for performer lookups
and search functionality.
"""

import os
from dataclasses import dataclass

import httpx


@dataclass
class StashappPerformer:
    """Performer data from Stashapp."""

    id: int
    name: str
    disambiguation: str | None
    aliases: list[str]
    stashdb_id: str | None


class StashappClient:
    """Async client for Stashapp GraphQL API."""

    def __init__(
        self,
        scheme: str | None = None,
        host: str | None = None,
        port: str | None = None,
        api_key: str | None = None,
    ):
        """Initialize the client.

        Args:
            scheme: HTTP scheme (http or https)
            host: Stashapp host
            port: Stashapp port
            api_key: API key for authentication
        """
        self.scheme = scheme or os.environ.get("MAIN_STASHAPP_SCHEME", "http")
        self.host = host or os.environ.get("MAIN_STASHAPP_HOST", "localhost")
        self.port = port or os.environ.get("MAIN_STASHAPP_PORT", "9999")
        self.api_key = api_key or os.environ.get("MAIN_STASHAPP_API_KEY", "")
        self.endpoint = f"{self.scheme}://{self.host}:{self.port}/graphql"

    async def get_performer_by_stashdb_id(
        self, stashdb_id: str
    ) -> StashappPerformer | None:
        """Get performer by their StashDB ID.

        Args:
            stashdb_id: StashDB performer UUID

        Returns:
            StashappPerformer or None if not found
        """
        query = """
            query FindPerformers($stashdb_id: String!) {
                findPerformers(
                    performer_filter: {
                        stash_id_endpoint: {
                            endpoint: "https://stashdb.org/graphql"
                            stash_id: $stashdb_id
                            modifier: EQUALS
                        }
                    }
                ) {
                    performers {
                        id
                        name
                        disambiguation
                        alias_list
                        stash_ids {
                            endpoint
                            stash_id
                        }
                    }
                }
            }
        """

        result = await self._gql_query(query, {"stashdb_id": stashdb_id})
        if not result or "data" not in result:
            return None

        performers = result["data"].get("findPerformers", {}).get("performers", [])
        if not performers:
            return None

        return self._parse_performer(performers[0])

    async def search_performers(
        self,
        query: str,
        limit: int = 10,
    ) -> list[StashappPerformer]:
        """Search performers by name.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching performers
        """
        gql_query = """
            query FindPerformers($filter: FindFilterType!) {
                findPerformers(filter: $filter) {
                    performers {
                        id
                        name
                        disambiguation
                        alias_list
                        stash_ids {
                            endpoint
                            stash_id
                        }
                    }
                }
            }
        """

        variables = {
            "filter": {
                "q": query,
                "per_page": limit,
            }
        }

        result = await self._gql_query(gql_query, variables)
        if not result or "data" not in result:
            return []

        performers = result["data"].get("findPerformers", {}).get("performers", [])
        return [self._parse_performer(p) for p in performers]

    def _parse_performer(self, data: dict) -> StashappPerformer:
        """Parse performer data from GraphQL response.

        Args:
            data: Raw performer data dict

        Returns:
            StashappPerformer instance
        """
        # Extract StashDB ID from stash_ids
        stashdb_id = None
        for stash_id in data.get("stash_ids", []):
            if stash_id.get("endpoint") == "https://stashdb.org/graphql":
                stashdb_id = stash_id.get("stash_id")
                break

        return StashappPerformer(
            id=int(data["id"]),
            name=data["name"],
            disambiguation=data.get("disambiguation"),
            aliases=data.get("alias_list", []),
            stashdb_id=stashdb_id,
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
            headers["ApiKey"] = self.api_key

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.endpoint,
                json={"query": query, "variables": variables},
                headers=headers,
            )

        if response.status_code != 200:
            return None

        return response.json()
