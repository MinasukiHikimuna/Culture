"""Database engine and session management."""

import os
import threading

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


load_dotenv()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""



# Thread-safe engine singleton
_engine = None
_engine_lock = threading.Lock()


def get_engine():
    """Get or create the database engine (thread-safe singleton)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                db_url = os.getenv("CONNECTION_STRING")
                if not db_url:
                    raise ValueError("CONNECTION_STRING environment variable not set")
                _engine = create_engine(
                    db_url,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                )
    return _engine


# Thread-safe session factory
_Session = None
_session_lock = threading.Lock()


def get_session():
    """Get a new database session."""
    global _Session
    if _Session is None:
        with _session_lock:
            if _Session is None:
                _Session = sessionmaker(bind=get_engine())
    return _Session()
