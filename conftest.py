from __future__ import annotations

import logging
import pytest

from config.settings import settings
from utils.api_client import APIClient
from utils.helpers import wait_for_service, random_integration_payload, random_asset_payload, extract_id
from utils.swagger import get_spec

log = logging.getLogger(__name__)

INTEGRATIONS_PATH = "/api/v1/integrations"
ASSETS_PATH = "/api/v1/assets"


@pytest.fixture(scope="session")
def service_ready():
    wait_for_service()
    yield


@pytest.fixture(scope="session")
def openapi_spec(service_ready):
    return get_spec()


@pytest.fixture()
def client_user1(service_ready) -> APIClient:
    client = APIClient(username=settings.user1_name, password=settings.user1_password)
    yield client
    client.close()


@pytest.fixture()
def client_user2(service_ready) -> APIClient:
    client = APIClient(username=settings.user2_name, password=settings.user2_password)
    yield client
    client.close()


@pytest.fixture()
def unauthenticated_client(service_ready) -> APIClient:
    client = APIClient(username="nobody", password="wrongpassword")
    yield client
    client.close()


# Session-scoped to avoid exhausting the API's write capacity (see BUG-009)
@pytest.fixture(scope="session")
def session_integration(service_ready):
    client = APIClient(username=settings.user1_name, password=settings.user1_password)
    payload = random_integration_payload()
    resp = client.post(INTEGRATIONS_PATH, json=payload)
    if resp.status_code not in (200, 201):
        pytest.skip(f"could not create session integration: {resp.status_code}")
    body = resp.json()
    integration_id = extract_id(body)
    yield {"id": integration_id, "payload": payload, "body": body}
    try:
        client.delete(f"{INTEGRATIONS_PATH}/{integration_id}")
    except Exception:
        pass
    client.close()


@pytest.fixture(scope="session")
def session_integration_user2(service_ready):
    client = APIClient(username=settings.user2_name, password=settings.user2_password)
    payload = random_integration_payload()
    resp = client.post(INTEGRATIONS_PATH, json=payload)
    if resp.status_code not in (200, 201):
        pytest.skip(f"could not create user2 session integration: {resp.status_code}")
    body = resp.json()
    integration_id = extract_id(body)
    yield {"id": integration_id, "payload": payload, "body": body}
    try:
        client.delete(f"{INTEGRATIONS_PATH}/{integration_id}")
    except Exception:
        pass
    client.close()


@pytest.fixture()
def created_integration(session_integration):
    return session_integration


@pytest.fixture()
def created_integration_user2(session_integration_user2):
    return session_integration_user2


@pytest.fixture()
def created_asset(client_user1, session_integration):
    integration_id = session_integration["id"]
    payload = random_asset_payload(integration_id)
    resp = client_user1.post(ASSETS_PATH, json=payload)
    if resp.status_code not in (200, 201):
        pytest.skip(f"asset creation failed: {resp.status_code}")
    body = resp.json()
    asset_id = extract_id(body)
    yield {"id": asset_id, "payload": payload, "body": body, "integration_id": integration_id}
    try:
        client_user1.delete(f"{ASSETS_PATH}/{asset_id}")
    except Exception:
        pass


@pytest.fixture()
def created_asset_user2(client_user2, session_integration_user2):
    integration_id = session_integration_user2["id"]
    payload = random_asset_payload(integration_id)
    resp = client_user2.post(ASSETS_PATH, json=payload)
    if resp.status_code not in (200, 201):
        pytest.skip(f"asset creation failed for user2: {resp.status_code}")
    body = resp.json()
    asset_id = extract_id(body)
    yield {"id": asset_id, "payload": payload, "body": body, "integration_id": integration_id}
    try:
        client_user2.delete(f"{ASSETS_PATH}/{asset_id}")
    except Exception:
        pass


def pytest_configure(config):
    config.addinivalue_line("markers", "auth: authentication & authorization tests")
    config.addinivalue_line("markers", "crud: create/read/update/delete tests")
    config.addinivalue_line("markers", "contract: OpenAPI contract / schema tests")
    config.addinivalue_line("markers", "tenant: multi-tenant isolation tests")
    config.addinivalue_line("markers", "load: performance / load tests")
    config.addinivalue_line("markers", "smoke: quick sanity check")
