from __future__ import annotations

import random
import string

from locust import HttpUser, between, task, events
from locust.env import Environment

INTEGRATIONS_PATH = "/api/v1/integrations"
ASSETS_PATH = "/api/v1/assets"
USER1 = ("test1", "test123")
USER2 = ("test2", "test456")
MIN_RPS = 1000 / 60


def _rand(prefix: str = "x") -> str:
    return f"{prefix}-{''.join(random.choices(string.ascii_lowercase, k=6))}"


def _integration_payload() -> dict:
    return {"name": _rand("integration"), "type": random.choice(["github", "gitlab", "jira"])}


class ReadHeavyUser(HttpUser):
    weight = 7
    wait_time = between(0.05, 0.2)

    def on_start(self):
        self.client.auth = USER1

    @task(10)
    def list_integrations(self):
        self.client.get(INTEGRATIONS_PATH, name="GET /integrations")

    @task(2)
    def create_and_delete(self):
        resp = self.client.post(INTEGRATIONS_PATH, json=_integration_payload(), name="POST /integrations")
        if resp.status_code in (200, 201):
            i = resp.json().get("id")
            if i:
                self.client.delete(f"{INTEGRATIONS_PATH}/{i}", name="DELETE /integrations/{id}")


class WriteHeavyUser(HttpUser):
    weight = 2
    wait_time = between(0.1, 0.4)

    def on_start(self):
        self.client.auth = USER1
        self._ids: list[str] = []

    def on_stop(self):
        for i in self._ids:
            self.client.delete(f"{INTEGRATIONS_PATH}/{i}", name="[teardown]")

    @task(3)
    def create_integration(self):
        resp = self.client.post(INTEGRATIONS_PATH, json=_integration_payload(), name="POST /integrations")
        if resp.status_code in (200, 201):
            i = resp.json().get("id")
            if i:
                self._ids.append(i)

    @task(3)
    def list_integrations(self):
        self.client.get(INTEGRATIONS_PATH, name="GET /integrations")

    @task(1)
    def delete_one(self):
        if self._ids:
            i = self._ids.pop(random.randrange(len(self._ids)))
            self.client.delete(f"{INTEGRATIONS_PATH}/{i}", name="DELETE /integrations/{id}")


class TenantUser2(HttpUser):
    weight = 1
    wait_time = between(0.05, 0.2)

    def on_start(self):
        self.client.auth = USER2

    @task(5)
    def list_integrations(self):
        self.client.get(INTEGRATIONS_PATH, name="GET /integrations [user2]")

    @task(1)
    def create_integration(self):
        resp = self.client.post(INTEGRATIONS_PATH, json=_integration_payload(), name="POST /integrations [user2]")
        if resp.status_code in (200, 201):
            i = resp.json().get("id")
            if i:
                self.client.delete(f"{INTEGRATIONS_PATH}/{i}", name="DELETE /integrations/{id} [user2]")


@events.quitting.add_listener
def _assert_thresholds(environment: Environment, **_kwargs):
    stats = environment.runner.stats.total
    error_rate = stats.fail_ratio
    p95 = stats.get_response_time_percentile(0.95) or 0

    print(f"\n  Total: {stats.num_requests} | Failures: {stats.num_failures}")
    print(f"  Error rate: {error_rate * 100:.2f}% | RPS: {stats.total_rps:.2f} | P95: {p95:.0f}ms")

    failures = []
    if stats.total_rps < MIN_RPS:
        failures.append(f"RPS {stats.total_rps:.2f} < {MIN_RPS:.2f}")
    if error_rate > 0.01:
        failures.append(f"error rate {error_rate*100:.2f}% > 1%")
    if p95 > 500:
        failures.append(f"p95 {p95:.0f}ms > 500ms")

    if failures:
        print("  SLA violations: " + ", ".join(failures))
        environment.process_exit_code = 1
    else:
        print("  All SLAs met")
