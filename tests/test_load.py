from __future__ import annotations

import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import List

import pytest
import requests

from config.settings import settings

pytestmark = pytest.mark.load

INTEGRATIONS_PATH = "/api/v1/integrations"
DURATION = 30
THREADS = 20
TARGET_RPS = settings.load_test_min_rps
MAX_ERROR_RATE = settings.load_test_max_failure_rate
MAX_P95_MS = settings.load_test_max_p95_ms


@dataclass
class LoadResult:
    latencies_ms: List[float] = field(default_factory=list)
    errors: int = 0
    total: int = 0
    elapsed_seconds: float = 0.0

    @property
    def rps(self) -> float:
        return self.total / self.elapsed_seconds if self.elapsed_seconds else 0.0

    @property
    def error_rate(self) -> float:
        return self.errors / self.total if self.total else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        s = sorted(self.latencies_ms)
        return s[int(len(s) * 0.95)]

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    def __str__(self):
        return (
            f"total={self.total} errors={self.errors} ({self.error_rate*100:.1f}%) "
            f"rps={self.rps:.1f} mean={self.mean_ms:.0f}ms p95={self.p95_ms:.0f}ms"
        )


def _run_load(url: str, auth: tuple, duration: int, threads: int) -> LoadResult:
    result = LoadResult()
    lock = threading.Lock()
    stop = threading.Event()

    def worker():
        session = requests.Session()
        session.auth = auth
        while not stop.is_set():
            t0 = time.perf_counter()
            try:
                resp = session.get(url, timeout=5)
                ms = (time.perf_counter() - t0) * 1000
                with lock:
                    result.latencies_ms.append(ms)
                    result.total += 1
                    if resp.status_code >= 500:
                        result.errors += 1
            except Exception:
                with lock:
                    result.errors += 1
                    result.total += 1
        session.close()

    workers = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
    t_start = time.perf_counter()
    for w in workers:
        w.start()

    time.sleep(duration)
    stop.set()
    for w in workers:
        w.join(timeout=5)

    result.elapsed_seconds = time.perf_counter() - t_start
    return result


@pytest.fixture(scope="module")
def load_result(service_ready):
    url = f"{settings.api_base_url}{INTEGRATIONS_PATH}"
    result = _run_load(url, settings.user1_auth, DURATION, THREADS)
    print(f"\n[load] {result}")
    return result


class TestThroughput:

    def test_meets_1000_requests_per_minute(self, load_result):
        assert load_result.rps >= TARGET_RPS, (
            f"throughput too low: {load_result.rps:.2f} rps (need {TARGET_RPS:.2f})\n{load_result}"
        )

    def test_enough_requests_were_made(self, load_result):
        assert load_result.total >= 100, f"only {load_result.total} requests made"


class TestErrorRate:

    def test_error_rate_under_1_percent(self, load_result):
        assert load_result.error_rate <= MAX_ERROR_RATE, (
            f"error rate {load_result.error_rate*100:.1f}% exceeds {MAX_ERROR_RATE*100:.0f}%\n{load_result}"
        )


class TestLatency:

    def test_p95_under_500ms(self, load_result):
        assert load_result.p95_ms <= MAX_P95_MS, (
            f"p95 latency {load_result.p95_ms:.0f}ms exceeds {MAX_P95_MS}ms\n{load_result}"
        )

    def test_mean_latency_under_200ms(self, load_result):
        assert load_result.mean_ms < 200, f"mean latency {load_result.mean_ms:.0f}ms is too high"


class TestStability:

    def test_service_still_responds_after_load(self, load_result, client_user1):
        resp = client_user1.get(INTEGRATIONS_PATH)
        resp.assert_status(200)

    def test_response_data_not_corrupted_after_load(self, load_result, client_user1):
        resp = client_user1.get(INTEGRATIONS_PATH)
        resp.assert_status(200)
        assert isinstance(resp.json(), (list, dict))
