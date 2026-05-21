from __future__ import annotations

import pytest

from utils.helpers import random_integration_payload, random_asset_payload, extract_id

pytestmark = pytest.mark.tenant

INTEGRATIONS_PATH = "/api/v1/integrations"
ASSETS_PATH = "/api/v1/assets"
DENIED = (403, 404)


class TestIntegrationIsolation:

    def test_user2_list_has_no_user1_integrations(self, client_user1, client_user2, created_integration):
        resp = client_user2.get(INTEGRATIONS_PATH)
        resp.assert_status(200)
        assert created_integration["id"] not in _ids(resp.json()), (
            f"user1's integration {created_integration['id']} is visible to user2 - tenant isolation broken"
        )

    def test_user1_list_has_no_user2_integrations(self, client_user1, client_user2, created_integration_user2):
        resp = client_user1.get(INTEGRATIONS_PATH)
        resp.assert_status(200)
        assert created_integration_user2["id"] not in _ids(resp.json()), (
            f"user2's integration {created_integration_user2['id']} is visible to user1 - tenant isolation broken"
        )

    def test_user2_cannot_get_user1_integration(self, client_user2, created_integration):
        resp = client_user2.get(f"{INTEGRATIONS_PATH}/{created_integration['id']}")
        assert resp.status_code in DENIED, (
            f"user2 accessed user1's integration - got {resp.status_code}"
        )

    def test_user1_cannot_get_user2_integration(self, client_user1, created_integration_user2):
        resp = client_user1.get(f"{INTEGRATIONS_PATH}/{created_integration_user2['id']}")
        assert resp.status_code in DENIED, (
            f"user1 accessed user2's integration - got {resp.status_code}"
        )

    def test_user2_cannot_delete_user1_integration(self, client_user2, created_integration):
        resp = client_user2.delete(f"{INTEGRATIONS_PATH}/{created_integration['id']}")
        assert resp.status_code in DENIED

    def test_user1_cannot_delete_user2_integration(self, client_user1, created_integration_user2):
        resp = client_user1.delete(f"{INTEGRATIONS_PATH}/{created_integration_user2['id']}")
        assert resp.status_code in DENIED


class TestAssetIsolation:

    def test_user2_cannot_get_user1_asset(self, client_user2, created_asset):
        resp = client_user2.get(f"{ASSETS_PATH}/{created_asset['id']}")
        assert resp.status_code in DENIED, (
            f"user2 accessed user1's asset - got {resp.status_code}"
        )

    def test_user2_assets_list_excludes_user1_assets(self, client_user1, client_user2, created_asset, created_integration_user2):
        # user2 lists assets for their own integration - should not see user1's assets
        resp = client_user2.get(ASSETS_PATH, params={"integrationId": created_integration_user2["id"]})
        if resp.status_code != 200:
            pytest.skip("user2 has no integration to list assets for")
        assert created_asset["id"] not in _ids(resp.json()), (
            f"user1's asset {created_asset['id']} visible in user2's asset list"
        )

    def test_user2_cannot_delete_user1_asset(self, client_user2, created_asset):
        resp = client_user2.delete(f"{ASSETS_PATH}/{created_asset['id']}")
        assert resp.status_code in DENIED


class TestDataIndependence:

    def test_same_integration_payload_creates_separate_records(self, client_user1, client_user2):
        payload = random_integration_payload(name="shared-name")

        r1 = client_user1.post(INTEGRATIONS_PATH, json=payload)
        r2 = client_user2.post(INTEGRATIONS_PATH, json=payload)
        r1.assert_status(200, 201)
        r2.assert_status(200, 201)

        id1 = extract_id(r1.json())
        id2 = extract_id(r2.json())
        assert id1 != id2, f"both tenants got the same integration id ({id1})"

        client_user1.delete(f"{INTEGRATIONS_PATH}/{id1}")
        client_user2.delete(f"{INTEGRATIONS_PATH}/{id2}")

    def test_deleting_user1_integration_does_not_affect_user2(self, client_user1, client_user2):
        payload = random_integration_payload(name="delete-isolation-test")
        r1 = client_user1.post(INTEGRATIONS_PATH, json=payload)
        r2 = client_user2.post(INTEGRATIONS_PATH, json=payload)
        r1.assert_status(200, 201)
        r2.assert_status(200, 201)

        id1 = extract_id(r1.json())
        id2 = extract_id(r2.json())

        client_user1.delete(f"{INTEGRATIONS_PATH}/{id1}")

        still_there = client_user2.get(f"{INTEGRATIONS_PATH}/{id2}")
        assert still_there.status_code == 200, "user2's integration disappeared after deleting user1's"

        client_user2.delete(f"{INTEGRATIONS_PATH}/{id2}")


def _ids(body) -> list:
    if isinstance(body, list):
        return [_get_id(i) for i in body if isinstance(i, dict)]
    for key in ("items", "data", "results"):
        if key in body and isinstance(body[key], list):
            return [_get_id(i) for i in body[key] if isinstance(i, dict)]
    return []


def _get_id(item: dict):
    for key in ("id", "ID", "uuid"):
        if key in item:
            return item[key]
    return None
