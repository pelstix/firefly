from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import jsonschema
import requests

from config.settings import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_spec() -> dict[str, Any]:
    url = settings.swagger_doc_url
    resp = requests.get(url, timeout=settings.request_timeout)
    resp.raise_for_status()
    return resp.json()


def get_all_routes() -> list[dict[str, str]]:
    spec = get_spec()
    routes = []
    for path, methods in spec.get("paths", {}).items():
        for method in methods:
            if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}:
                routes.append({"method": method.lower(), "path": path})
    return routes


def resolve_schema_ref(ref: str, spec: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref supported, got: {ref!r}")
    parts = ref.lstrip("#/").split("/")
    node: Any = spec
    for part in parts:
        node = node[part]
    return node


def get_response_schema(path: str, method: str, status_code: int) -> dict[str, Any] | None:
    spec = get_spec()
    try:
        operation = spec["paths"][path][method.lower()]
        response_def = operation["responses"][str(status_code)]
        if "content" in response_def:
            schema = response_def["content"]["application/json"]["schema"]
        elif "schema" in response_def:
            schema = response_def["schema"]
        else:
            return None
        if "$ref" in schema:
            schema = resolve_schema_ref(schema["$ref"], spec)
        return schema
    except (KeyError, TypeError):
        return None


def validate_response_body(body: Any, path: str, method: str, status_code: int) -> list[str]:
    schema = get_response_schema(path, method, status_code)
    if schema is None:
        return []
    spec = get_spec()
    resolver = jsonschema.RefResolver.from_schema(spec)
    validator = jsonschema.Draft4Validator(schema, resolver=resolver)
    return [e.message for e in validator.iter_errors(body)]


def get_all_schemas() -> dict[str, dict[str, Any]]:
    spec = get_spec()
    if "components" in spec:
        return spec["components"].get("schemas", {})
    return spec.get("definitions", {})
