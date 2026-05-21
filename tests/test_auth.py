from __future__ import annotations

import re
import pytest
import requests

from config.settings import settings
from utils.swagger import get_all_routes

pytestmark = pytest.mark.auth

PROBE_PATH = "/api/v1/integrations"


class TestNoCredentials:

    def test_no_auth_returns_401(self, service_ready):
        resp = requests.get(f"{settings.api_base_url}{PROBE_PATH}", timeout=settings.request_timeout)
        assert resp.status_code == 401

    def test_empty_auth_header_returns_401(self, service_ready):
        resp = requests.get(
            f"{settings.api_base_url}{PROBE_PATH}",
            headers={"Authorization": ""},
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401

    def test_malformed_basic_token_returns_401(self, service_ready):
        resp = requests.get(
            f"{settings.api_base_url}{PROBE_PATH}",
            headers={"Authorization": "Basic NOT_VALID_BASE64!!!"},
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401

    def test_bearer_token_not_accepted(self, service_ready):
        resp = requests.get(
            f"{settings.api_base_url}{PROBE_PATH}",
            headers={"Authorization": "Bearer fake.jwt.token"},
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401


class TestWrongCredentials:

    def test_unknown_username_returns_401(self, service_ready):
        resp = requests.get(
            f"{settings.api_base_url}{PROBE_PATH}",
            auth=("nonexistent_user", "test123"),
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401

    def test_wrong_password_returns_401(self, service_ready):
        resp = requests.get(
            f"{settings.api_base_url}{PROBE_PATH}",
            auth=(settings.user1_name, "wrong_password"),
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401

    def test_swapped_passwords_returns_401(self, service_ready):
        resp = requests.get(
            f"{settings.api_base_url}{PROBE_PATH}",
            auth=(settings.user1_name, settings.user2_password),
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401

    def test_empty_password_returns_401(self, service_ready):
        resp = requests.get(
            f"{settings.api_base_url}{PROBE_PATH}",
            auth=(settings.user1_name, ""),
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401

    def test_empty_username_returns_401(self, service_ready):
        resp = requests.get(
            f"{settings.api_base_url}{PROBE_PATH}",
            auth=("", settings.user1_password),
            timeout=settings.request_timeout,
        )
        assert resp.status_code == 401


class TestValidCredentials:

    def test_user1_can_access_integrations(self, client_user1):
        resp = client_user1.get(PROBE_PATH)
        resp.assert_status(200)

    def test_user2_can_access_integrations(self, client_user2):
        resp = client_user2.get(PROBE_PATH)
        resp.assert_status(200)

    def test_user1_can_create_integration(self, client_user1):
        from utils.helpers import random_integration_payload, extract_id
        resp = client_user1.post(PROBE_PATH, json=random_integration_payload())
        resp.assert_status(200, 201)
        try:
            client_user1.delete(f"{PROBE_PATH}/{extract_id(resp.json())}")
        except Exception:
            pass

    def test_user2_can_create_integration(self, client_user2):
        from utils.helpers import random_integration_payload, extract_id
        resp = client_user2.post(PROBE_PATH, json=random_integration_payload())
        resp.assert_status(200, 201)
        try:
            client_user2.delete(f"{PROBE_PATH}/{extract_id(resp.json())}")
        except Exception:
            pass


class TestSecurityHeaders:

    def test_401_has_www_authenticate_header(self, service_ready):
        resp = requests.get(f"{settings.api_base_url}{PROBE_PATH}", timeout=settings.request_timeout)
        assert resp.status_code == 401
        if "WWW-Authenticate" not in resp.headers:
            pytest.xfail("WWW-Authenticate missing from 401 response - RFC 7235 recommendation")

    def test_401_body_has_no_stack_trace(self, service_ready):
        resp = requests.get(f"{settings.api_base_url}{PROBE_PATH}", timeout=settings.request_timeout)
        body = resp.text.lower()
        for leak in ["stack trace", "goroutine", "panic:", "/home/", "runtime error"]:
            assert leak not in body, f"response leaks internal info ({leak!r}): {resp.text[:300]}"


class TestAllRoutesRequireAuth:

    @pytest.fixture(scope="class")
    def all_routes(self, openapi_spec):
        return get_all_routes()

    def test_all_get_routes_reject_unauthenticated_requests(self, all_routes, service_ready):
        skip_prefixes = ("/swagger", "/ping", "/health", "/metrics")
        protected = [
            r for r in all_routes
            if r["method"] == "get"
            and not any(r["path"].startswith(p) for p in skip_prefixes)
        ]

        failures = []
        for route in protected:
            path = re.sub(r"\{[^}]+\}", "1", route["path"])
            full_path = f"/api/v1{path}"
            try:
                resp = requests.get(f"{settings.api_base_url}{full_path}", timeout=settings.request_timeout)
                if resp.status_code not in (401, 400):
                    failures.append(f"GET {full_path} -> {resp.status_code} (expected 401)")
            except Exception as exc:
                failures.append(f"GET {full_path} raised {exc}")

        assert not failures, "unprotected routes found:\n" + "\n".join(failures)
