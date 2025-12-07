"""FastAPI dependency injection for database clients."""

from collections.abc import Generator
from functools import lru_cache

from api.config import get_connection_string, load_env
from libraries.client_culture_extractor import ClientCultureExtractor


# Load environment on module import
load_env()


@lru_cache
def get_connection_string_cached() -> str:
    """Get cached connection string."""
    return get_connection_string()


def get_ce_client() -> Generator[ClientCultureExtractor]:
    """Provide a Culture Extractor client as a FastAPI dependency.

    Yields:
        ClientCultureExtractor instance
    """
    client = ClientCultureExtractor(get_connection_string_cached())
    try:
        yield client
    finally:
        client.close()
