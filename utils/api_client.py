from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from requests import Response
from requests.auth import HTTPBasicAuth

from config.settings import settings

log = logging.getLogger(__name__)


class APIResponse:
    def __init__(self, response: Response) -> None:
        self._r = response

    @property
    def status_code(self) -> int:
        return self._r.status_code

    @property
    def headers(self) -> dict:
        return dict(self._r.headers)

    @property
    def elapsed_ms(self) -> float:
        return self._r.elapsed.total_seconds() * 1000

    def json(self) -> Any:
        return self._r.json()

    def text(self) -> str:
        return self._r.text

    def assert_status(self, *expected: int) -> "APIResponse":
        assert self.status_code in expected, (
            f"Expected {expected}, got {self.status_code}. Body: {self._r.text[:500]}"
        )
        return self

    def assert_json_key(self, key: str) -> "APIResponse":
        body = self.json()
        assert key in body, f"Key '{key}' not found in response: {body}"
        return self

    def __repr__(self) -> str:
        return f"<APIResponse {self.status_code} {self.elapsed_ms:.1f}ms>"


class APIClient:
    """HTTP client scoped to a single user's session."""

    def __init__(
        self,
        username: str,
        password: str,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self.username = username
        self.base_url = (base_url or str(settings.api_base_url)).rstrip("/")
        self.timeout = timeout or settings.request_timeout

        self._session = requests.Session()
        self._session.auth = HTTPBasicAuth(username, password)
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, *, json: Any = None,
                 params: Optional[dict] = None, headers: Optional[dict] = None,
                 auth: Optional[tuple] = None, **kwargs: Any) -> APIResponse:
        url = self._url(path)
        log.debug("%s %s payload=%s", method.upper(), url, json)
        raw = self._session.request(
            method, url, json=json, params=params,
            headers=headers, auth=auth, timeout=self.timeout, **kwargs,
        )
        resp = APIResponse(raw)
        log.debug("<- %s %s %dms", resp.status_code, url, resp.elapsed_ms)
        return resp

    def get(self, path: str, **kw: Any) -> APIResponse:
        return self._request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> APIResponse:
        return self._request("POST", path, **kw)

    def put(self, path: str, **kw: Any) -> APIResponse:
        return self._request("PUT", path, **kw)

    def patch(self, path: str, **kw: Any) -> APIResponse:
        return self._request("PATCH", path, **kw)

    def delete(self, path: str, **kw: Any) -> APIResponse:
        return self._request("DELETE", path, **kw)

    def request_without_auth(self, method: str, path: str, **kw: Any) -> APIResponse:
        return self._request(method, path, auth=(), **kw)

    def close(self) -> None:
        self._session.close()
