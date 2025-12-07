"""FastAPI application entry point for Culture API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import performers, releases, sites


app = FastAPI(
    title="Culture API",
    description="Backend API for Culture platform",
    version="0.1.0",
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sites.router, prefix="/sites", tags=["sites"])
app.include_router(releases.router, prefix="/releases", tags=["releases"])
app.include_router(performers.router, prefix="/performers", tags=["performers"])


@app.get("/health")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
