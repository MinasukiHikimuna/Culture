"""Configuration settings for the Culture API."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Repository root for .env file location
# Path: config.py -> api -> api -> Culture
_REPO_ROOT = Path(__file__).parent.parent.parent


def load_env() -> None:
    """Load environment variables from .env file."""
    env_path = _REPO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()


def get_connection_string() -> str:
    """Get PostgreSQL connection string from environment variables.

    Returns:
        Connection string for Culture Extractor database

    Raises:
        ValueError: If required environment variables are not set
    """
    user = os.environ.get("CE_DB_USERNAME")
    pw = os.environ.get("CE_DB_PASSWORD")
    host = os.environ.get("CE_DB_HOST")
    port = os.environ.get("CE_DB_PORT")
    db = os.environ.get("CE_DB_NAME")

    missing = []
    if not user:
        missing.append("CE_DB_USERNAME")
    if not pw:
        missing.append("CE_DB_PASSWORD")
    if not host:
        missing.append("CE_DB_HOST")
    if not port:
        missing.append("CE_DB_PORT")
    if not db:
        missing.append("CE_DB_NAME")

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please set them in .env file at: {_REPO_ROOT / '.env'}"
        )

    return f"dbname={db} user={user} password={pw} host={host} port={port}"


def get_metadata_base_path() -> Path | None:
    """Get the base path for metadata files.

    Returns:
        Path to metadata directory, or None if not configured
    """
    path = os.environ.get("CE_METADATA_BASE_PATH")
    if path:
        return Path(path)
    return None
