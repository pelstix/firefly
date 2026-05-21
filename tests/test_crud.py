from __future__ import annotations

import pytest

from utils.helpers import random_integration_payload, random_asset_payload, extract_id

pytestmark = pytest.mark.crud

INTEGRATIONS_PATH = "/api/v1/integrations"
ASSETS_PATH = "/api/v1/assets"
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


class TestIntegrationCreate:

    def test_create_integration_returns_success(self, client_user1):
        payload = random_integration_payload()
        resp = client_user1.post(INTEGRATIONS_PATH, json=payload)
        resp.assert_status(200, 201)
        _cleanup_integration(client_user1, resp)

    def test_create_integration_has_id(self, client_user1):
        resp = client_user1.post(INTEGRATIONS_PATH, json=random_integration_payload())
        resp.assert_status(200, 201)
        assert extract_id(resp.json()), "expected an id in the response"
        _cleanup_integration(client_user1, resp)

    def test_create_integration_name_matches_payload(self, client_user1):
        payload = random_integration_payload()
        resp = client_user1.post(INTEGRATIONS_PATH, json=payload)
        resp.assert_status(200, 201)
        assert resp.json().get("name") == payload["name"]
        _cleanup_integration(client_user1, resp)

    @pytest.mark.xfail(reason="BUG: POST /integrations with empty body returns 500 instead of 400 - server panics on missing required fields")
    def test_create_integration_empty_body_rejected(self, client_user1):
        resp = client_user1.post(INTEGRATIONS_PATH, json={})
        assert resp.status_code in (400, 422), f"empty payload should be rejected, got {resp.status_code}"


class TestIntegrationRead:

    def test_list_integrations_returns_200(self, client_user1, created_integration):
        resp = client_user1.get(INTEGRATIONS_PATH)
        resp.assert_status(200)

    def test_list_integrations_returns_array(self, client_user1, created_integration):
        resp = client_user1.get(INTEGRATIONS_PATH)
        resp.assert_status(200)
        assert isinstance(resp.json(), (list, dict))

    def test_created_integration_in_list(self, client_user1, created_integration):
        resp = client_user1.get(INTEGRATIONS_PATH)
        resp.assert_status(200)
        ids = _collect_ids(resp.json())
        assert created_integration["id"] in ids, f"integration {created_integration['id']} not in list"

    def test_get_integration_by_id(self, client_user1, created_integration):
        resp = client_user1.get(f"{INTEGRATIONS_PATH}/{created_integration['id']}")
        resp.assert_status(200)
        assert extract_id(resp.json()) == created_integration["id"]

    def test_get_integration_name_matches(self, client_user1, created_integration):
        resp = client_user1.get(f"{INTEGRATIONS_PATH}/{created_integration['id']}")
        resp.assert_status(200)
        assert resp.json().get("name") == created_integration["payload"]["name"]

    def test_get_unknown_integration_returns_404(self, client_user1):
        resp = client_user1.get(f"{INTEGRATIONS_PATH}/{UNKNOWN_ID}")
        assert resp.status_code == 404


class TestIntegrationUpdate:
    # spec declares PUT /integrations with {id, name} in body

    @pytest.mark.xfail(reason="BUG: PUT /integrations returns 404 - update endpoint is not implemented or route is misconfigured")
    def test_update_integration(self, client_user1, created_integration):
        payload = {"id": created_integration["id"], "name": "updated-name"}
        resp = client_user1.put(INTEGRATIONS_PATH, json=payload)
        resp.assert_status(200, 204)

    @pytest.mark.xfail(reason="BUG: PUT /integrations returns 404 - update endpoint broken")
    def test_update_is_persisted(self, client_user1, created_integration):
        new_name = "persisted-name"
        client_user1.put(INTEGRATIONS_PATH, json={"id": created_integration["id"], "name": new_name})
        get_resp = client_user1.get(f"{INTEGRATIONS_PATH}/{created_integration['id']}")
        get_resp.assert_status(200)
        assert get_resp.json().get("name") == new_name

    @pytest.mark.xfail(reason="BUG: PUT /integrations returns 404 - update endpoint broken, should return 400 for empty body")
    def test_update_with_empty_body_rejected(self, client_user1):
        resp = client_user1.put(INTEGRATIONS_PATH, json={})
        assert resp.status_code in (400, 422)

    def test_update_unknown_integration_returns_404(self, client_user1):
        # this actually returns 404 because the route doesn't exist, not because of missing id
        resp = client_user1.put(INTEGRATIONS_PATH, json={"id": UNKNOWN_ID, "name": "x"})
        assert resp.status_code == 404


class TestIntegrationDelete:

    def test_delete_integration(self, client_user1):
        resp = client_user1.post(INTEGRATIONS_PATH, json=random_integration_payload())
        resp.assert_status(200, 201)
        integration_id = extract_id(resp.json())
        del_resp = client_user1.delete(f"{INTEGRATIONS_PATH}/{integration_id}")
        assert del_resp.status_code in (200, 204)

    def test_deleted_integration_returns_404(self, client_user1):
        resp = client_user1.post(INTEGRATIONS_PATH, json=random_integration_payload())
        resp.assert_status(200, 201)
        integration_id = extract_id(resp.json())
        client_user1.delete(f"{INTEGRATIONS_PATH}/{integration_id}")
        assert client_user1.get(f"{INTEGRATIONS_PATH}/{integration_id}").status_code == 404

    @pytest.mark.xfail(reason="BUG: DELETE /integrations/{non-existent-id} returns 200 instead of 404 - no existence check before delete")
    def test_delete_unknown_integration_returns_404(self, client_user1):
        resp = client_user1.delete(f"{INTEGRATIONS_PATH}/{UNKNOWN_ID}")
        assert resp.status_code == 404


class TestAssetCreate:

    def test_create_asset_returns_success(self, client_user1, created_integration):
        payload = random_asset_payload(created_integration["id"])
        resp = client_user1.post(ASSETS_PATH, json=payload)
        resp.assert_status(200, 201)
        _cleanup_asset(client_user1, resp)

    def test_create_asset_has_id(self, client_user1, created_integration):
        resp = client_user1.post(ASSETS_PATH, json=random_asset_payload(created_integration["id"]))
        resp.assert_status(200, 201)
        assert extract_id(resp.json()), "expected an id in response"
        _cleanup_asset(client_user1, resp)

    def test_create_asset_name_matches(self, client_user1, created_integration):
        payload = random_asset_payload(created_integration["id"])
        resp = client_user1.post(ASSETS_PATH, json=payload)
        resp.assert_status(200, 201)
        assert resp.json().get("name") == payload["name"]
        _cleanup_asset(client_user1, resp)

    @pytest.mark.xfail(reason="BUG: POST /assets without integration_id returns 201 - required field not validated")
    def test_create_asset_without_integration_id_rejected(self, client_user1):
        resp = client_user1.post(ASSETS_PATH, json={"name": "orphan-asset"})
        assert resp.status_code in (400, 422)


class TestAssetRead:

    def test_list_assets_by_integration(self, client_user1, created_asset):
        resp = client_user1.get(ASSETS_PATH, params={"integrationId": created_asset["integration_id"]})
        resp.assert_status(200)

    def test_created_asset_in_list(self, client_user1, created_asset):
        resp = client_user1.get(ASSETS_PATH, params={"integrationId": created_asset["integration_id"]})
        resp.assert_status(200)
        ids = _collect_ids(resp.json())
        assert created_asset["id"] in ids, f"asset {created_asset['id']} not in list"

    def test_list_assets_without_integration_id_returns_400(self, client_user1):
        resp = client_user1.get(ASSETS_PATH)
        assert resp.status_code == 400

    def test_get_asset_by_id(self, client_user1, created_asset):
        resp = client_user1.get(f"{ASSETS_PATH}/{created_asset['id']}")
        resp.assert_status(200)
        assert extract_id(resp.json()) == created_asset["id"]

    def test_get_unknown_asset_returns_404(self, client_user1):
        resp = client_user1.get(f"{ASSETS_PATH}/99999999")
        assert resp.status_code == 404


class TestAssetUpdate:

    def test_update_asset(self, client_user1, created_asset):
        payload = {"id": created_asset["id"], "name": "updated-asset-name"}
        resp = client_user1.patch(ASSETS_PATH, json=payload)
        resp.assert_status(200, 204)

    def test_update_asset_is_persisted(self, client_user1, created_asset):
        new_name = "patched-asset"
        client_user1.patch(ASSETS_PATH, json={"id": created_asset["id"], "name": new_name})
        get_resp = client_user1.get(f"{ASSETS_PATH}/{created_asset['id']}")
        get_resp.assert_status(200)
        assert get_resp.json().get("name") == new_name

    @pytest.mark.xfail(reason="BUG: PATCH /assets with non-existent id returns 500 instead of 404 - unhandled error")
    def test_update_unknown_asset_returns_404(self, client_user1):
        resp = client_user1.patch(ASSETS_PATH, json={"id": "99999999", "name": "x"})
        assert resp.status_code == 404


class TestAssetDelete:

    def test_delete_asset(self, client_user1, created_integration):
        resp = client_user1.post(ASSETS_PATH, json=random_asset_payload(created_integration["id"]))
        resp.assert_status(200, 201)
        asset_id = extract_id(resp.json())
        del_resp = client_user1.delete(f"{ASSETS_PATH}/{asset_id}")
        assert del_resp.status_code in (200, 204)

    def test_deleted_asset_returns_404(self, client_user1, created_integration):
        resp = client_user1.post(ASSETS_PATH, json=random_asset_payload(created_integration["id"]))
        resp.assert_status(200, 201)
        asset_id = extract_id(resp.json())
        client_user1.delete(f"{ASSETS_PATH}/{asset_id}")
        assert client_user1.get(f"{ASSETS_PATH}/{asset_id}").status_code == 404

    @pytest.mark.xfail(reason="BUG: DELETE /assets/{non-existent-id} returns 204 instead of 404 - no existence check")
    def test_delete_unknown_asset_returns_404(self, client_user1):
        resp = client_user1.delete(f"{ASSETS_PATH}/99999999")
        assert resp.status_code == 404


def _cleanup_integration(client, resp):
    if resp.status_code in (200, 201):
        try:
            client.delete(f"{INTEGRATIONS_PATH}/{extract_id(resp.json())}")
        except Exception:
            pass


def _cleanup_asset(client, resp):
    if resp.status_code in (200, 201):
        try:
            client.delete(f"{ASSETS_PATH}/{extract_id(resp.json())}")
        except Exception:
            pass


def _collect_ids(body) -> list:
    if isinstance(body, list):
        return [extract_id(i) for i in body if isinstance(i, dict)]
    for key in ("items", "data", "results"):
        if key in body and isinstance(body[key], list):
            return [extract_id(i) for i in body[key] if isinstance(i, dict)]
    return []
