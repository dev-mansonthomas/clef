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


@pytest.fixture(autouse=True)
def reset_cache_after_test():
    """Reset the global cache singleton after each test to prevent event loop leaks.

    TestClient creates its own event loop. If the app startup connects to Redis,
    that connection is bound to the TestClient's loop. When the loop closes, the
    connection becomes stale but the cache singleton still holds it, causing
    'Future attached to a different loop' errors in subsequent tests.
    """
    yield
    from app.cache import get_cache
    cache = get_cache()
    if cache._connected:
        cache.client = None
        cache._connected = False

