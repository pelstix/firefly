from __future__ import annotations

import pytest
import jsonschema
import schemathesis.openapi as st_openapi

from config.settings import settings
from utils.swagger import get_spec, get_all_routes, get_response_schema, get_all_schemas

pytestmark = pytest.mark.contract

INTEGRATIONS_PATH = "/api/v1/integrations"


class TestSpecStructure:

    def test_swagger_endpoint_reachable(self, service_ready):
        import requests
        resp = requests.get(settings.swagger_doc_url, timeout=settings.request_timeout)
        assert resp.status_code == 200

    def test_spec_is_valid_json(self, service_ready):
        import requests
        resp = requests.get(settings.swagger_doc_url, timeout=settings.request_timeout)
        try:
            resp.json()
        except Exception as exc:
            pytest.fail(f"spec is not valid JSON: {exc}")

    def test_spec_has_info_and_title(self, openapi_spec):
        assert "info" in openapi_spec
        assert "title" in openapi_spec["info"]
        assert "version" in openapi_spec["info"]

    def test_spec_has_paths(self, openapi_spec):
        assert "paths" in openapi_spec
        assert len(openapi_spec["paths"]) > 0

    def test_spec_declares_basic_auth_scheme(self, openapi_spec):
        schemes = (
            openapi_spec.get("components", {}).get("securitySchemes", {})
            or openapi_spec.get("securityDefinitions", {})
        )
        has_basic = any(
            s.get("type") in ("http", "basic") and
            (s.get("scheme") == "basic" or s.get("type") == "basic")
            for s in schemes.values()
        )
        if not has_basic:
            pytest.xfail("BUG: spec doesn't declare a basicAuth security scheme")

    def test_schema_refs_all_resolve(self, openapi_spec):
        errors = []
        for name, schema in get_all_schemas().items():
            try:
                jsonschema.Draft4Validator.check_schema(schema)
            except Exception as exc:
                errors.append(f"schema '{name}': {exc}")
        assert not errors, "\n".join(errors)


class TestAllPathsRespond:

    def test_no_route_returns_5xx_for_valid_auth(self, client_user1, openapi_spec):
        import re
        failures = []
        for route in get_all_routes():
            if route["method"] != "get":
                continue
            if route["path"].startswith("/swagger"):
                continue
            path = re.sub(r"\{[^}]+\}", "1", route["path"])
            full_path = f"/api/v1{path}"
            try:
                resp = client_user1.get(full_path)
                if resp.status_code >= 500:
                    failures.append(f"GET {full_path} -> {resp.status_code}")
            except Exception as exc:
                failures.append(f"GET {full_path} raised {exc}")
        assert not failures, "routes returning 5xx:\n" + "\n".join(failures)


class TestResponseSchema:

    @pytest.mark.xfail(reason="BUG: GET /integrations returns null instead of [] for empty list")
    def test_list_integrations_matches_spec_schema(self, client_user1, openapi_spec):
        resp = client_user1.get(INTEGRATIONS_PATH)
        if resp.status_code != 200:
            pytest.skip(f"endpoint returned {resp.status_code}")
        schema = get_response_schema("/integrations", "get", 200)
        if schema is None:
            pytest.skip("no response schema defined in spec")
        resolver = jsonschema.RefResolver.from_schema(openapi_spec)
        errors = [e.message for e in jsonschema.Draft4Validator(schema, resolver=resolver).iter_errors(resp.json())]
        assert not errors, "response violates schema:\n" + "\n".join(errors)

    def test_get_integration_by_id_matches_spec_schema(self, client_user1, created_integration, openapi_spec):
        resp = client_user1.get(f"{INTEGRATIONS_PATH}/{created_integration['id']}")
        resp.assert_status(200)
        schema = get_response_schema("/integrations/{id}", "get", 200)
        if schema is None:
            pytest.skip("no schema defined for GET /integrations/{id}")
        resolver = jsonschema.RefResolver.from_schema(openapi_spec)
        errors = [e.message for e in jsonschema.Draft4Validator(schema, resolver=resolver).iter_errors(resp.json())]
        assert not errors, "\n".join(errors)

    def test_json_endpoints_return_correct_content_type(self, client_user1):
        resp = client_user1.get(INTEGRATIONS_PATH)
        resp.assert_status(200)
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_404_response_is_json(self, client_user1):
        resp = client_user1.get(f"{INTEGRATIONS_PATH}/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        try:
            resp.json()
        except Exception:
            pytest.fail("404 response is not valid JSON")

    def test_create_integration_response_matches_schema(self, client_user1, openapi_spec):
        from utils.helpers import random_integration_payload, extract_id
        payload = random_integration_payload()
        resp = client_user1.post(INTEGRATIONS_PATH, json=payload)
        if resp.status_code not in (200, 201):
            pytest.skip(f"create failed with {resp.status_code}")
        schema = get_response_schema("/integrations", "post", resp.status_code)
        if schema is None:
            pytest.skip(f"no schema for POST /integrations {resp.status_code}")
        resolver = jsonschema.RefResolver.from_schema(openapi_spec)
        errors = [e.message for e in jsonschema.Draft4Validator(schema, resolver=resolver).iter_errors(resp.json())]
        try:
            client_user1.delete(f"{INTEGRATIONS_PATH}/{extract_id(resp.json())}")
        except Exception:
            pass
        assert not errors, "\n".join(errors)


def test_schemathesis_auto_contract(service_ready, openapi_spec):
    spec_for_test = dict(openapi_spec)
    spec_for_test["host"] = settings.api_base_url.replace("http://", "").replace("https://", "")

    schema = st_openapi.from_dict(spec_for_test)

    failures = []
    for operation in schema.get_all_operations():
        op = operation.ok()
        for case in op.make_case():
            try:
                response = case.call(auth=settings.user1_auth)
                if response.status_code >= 500:
                    failures.append(f"{op.method.upper()} {op.path} -> {response.status_code}")
            except Exception as exc:
                failures.append(f"{op.method.upper()} {op.path} raised {exc}")
            break

    assert not failures, "schemathesis found 5xx responses:\n" + "\n".join(failures)
