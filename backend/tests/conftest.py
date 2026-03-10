"""Pytest configuration and fixtures."""
import os
import pytest

# Set USE_MOCKS before any imports
os.environ["USE_MOCKS"] = "true"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    # Already set above, but keep for clarity
    os.environ["USE_MOCKS"] = "true"
    yield

