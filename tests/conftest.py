import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    """Provide a test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers():
    """Provide authentication headers for tests."""
    # This template is in dev mode with AUTH_ENABLED=0, so auth headers are optional.
    return {}
