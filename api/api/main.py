"""FastAPI application entry point for Culture API."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import face_matching, performers, releases, sites


app = FastAPI(
    title="Culture API",
    description="Backend API for Culture platform",
    version="0.1.0",
)

# Configure CORS
# Set CORS_ORIGINS environment variable for production (comma-separated)
cors_origins = os.environ.get("CORS_ORIGINS")
if cors_origins:
    origins = [o.strip() for o in cors_origins.split(",")]
else:
    # Safe defaults for local development
    origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sites.router, prefix="/sites", tags=["sites"])
app.include_router(releases.router, prefix="/releases", tags=["releases"])
app.include_router(performers.router, prefix="/performers", tags=["performers"])
app.include_router(
    face_matching.router, prefix="/face-matching", tags=["face-matching"]
)


@app.get("/health")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
