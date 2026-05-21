from __future__ import annotations

import logging
import random
import string
import time
from typing import Any

import requests

from config.settings import settings

log = logging.getLogger(__name__)


def wait_for_service(url: str | None = None, timeout: int | None = None) -> bool:
    url = url or f"{settings.api_base_url}/swagger/index.html"
    timeout = timeout or settings.service_startup_timeout
    deadline = time.time() + timeout

    log.info("waiting for service at %s...", url)
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code < 500:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(settings.service_startup_poll_interval)

    raise RuntimeError(f"service not ready after {timeout}s")


def random_string(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=length))


def random_integration_payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "name": f"integration-{random_string()}",
        "type": random.choice(["github", "gitlab", "jira", "aws"]),
    }
    base.update(overrides)
    return base


def random_asset_payload(integration_id: str, **overrides: Any) -> dict[str, Any]:
    base = {
        "name": f"asset-{random_string()}",
        "description": f"test asset {random_string(10)}",
        "integration_id": integration_id,
    }
    base.update(overrides)
    return base


def extract_id(body: dict[str, Any]) -> Any:
    for key in ("id", "ID", "uuid"):
        if key in body:
            return body[key]
    raise KeyError(f"no id field found in: {list(body.keys())}")
