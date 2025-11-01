"""Configuration utilities for Culture Extractor CLI."""

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# Add libraries to path
_REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from libraries.client_culture_extractor import ClientCultureExtractor


class Config:
    """Configuration manager for the CLI."""

    def __init__(self):
        """Initialize configuration by loading .env file."""
        # Load .env from repository root
        env_path = _REPO_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        else:
            load_dotenv()  # Try default locations

    def get_connection_string(self) -> str:
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

    def get_client(self) -> ClientCultureExtractor:
        """Get Culture Extractor client instance.

        Returns:
            ClientCultureExtractor instance connected to the database
        """
        connection_string = self.get_connection_string()
        return ClientCultureExtractor(connection_string)


# Global config instance
config = Config()
