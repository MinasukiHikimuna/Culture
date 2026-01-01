"""Pytest configuration and fixtures."""

import pytest


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--check-output",
        action="store_true",
        default=False,
        help="Only verify existing output files, don't run extraction",
    )


@pytest.fixture
def check_output_only(request):
    """Fixture to check if we should only verify existing files."""
    return request.config.getoption("--check-output")
