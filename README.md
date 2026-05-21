# test-integration-api — test suite

Automated test suite for `infralightio/test-integration-api`.

## Running

Requires Docker. Single command:

```bash
make run
```

Starts the API container, waits for it to be healthy, runs the full pytest suite, then runs the Locust load test. Reports land in `./reports/`.

Local development (API already running on :8080):

```bash
make test
make test-auth
make test-tenant
make load
```

## Structure

```
config/settings.py              - all config, driven by env vars
utils/api_client.py             - http client wrapper
utils/swagger.py                - spec loader + schema validation helpers
utils/helpers.py                - shared test utilities
tests/test_auth.py              - auth/authz tests
tests/test_crud.py              - CRUD lifecycle tests (integrations + assets)
tests/test_tenant_isolation.py  - multi-tenant isolation tests
tests/test_contract.py          - OpenAPI contract tests + schemathesis
tests/test_load.py              - load/perf tests (threaded)
load/locustfile.py              - locust scenarios for full load test
conftest.py                     - fixtures
```

## API structure

Two resources:
- Integrations: `POST /api/v1/integrations` with `{name, type}`
- Assets: `POST /api/v1/assets` with `{name, description, integration_id}`, listed via `GET /api/v1/assets?integrationId=xxx`

## Configuration

All values configurable via env vars or `.env` file (see `.env.example`).

| Variable | Default |
|---|---|
| `API_BASE_URL` | `http://localhost:8080` |
| `USER1_NAME` / `USER1_PASSWORD` | `test1` / `test123` |
| `USER2_NAME` / `USER2_PASSWORD` | `test2` / `test456` |
| `LOAD_TEST_USERS` | `20` |
| `LOAD_TEST_DURATION` | `60s` |

## Bugs found

Tests that confirm real API bugs are marked `xfail` — they show as expected failures in the report with the bug description.

---

**BUG-001 — Tenant isolation bypass via direct ID access (IDOR) [Critical]**

`GET /api/v1/integrations/{id}` as user2 with user1's id returns 200. The list endpoint filters by tenant but the individual resource endpoint does not.

```bash
curl -u test1:test123 -X POST http://localhost:8080/api/v1/integrations \
  -H 'Content-Type: application/json' -d '{"name":"secret","type":"github"}'
# -> {"id":"abc-123"}

curl -u test2:test456 http://localhost:8080/api/v1/integrations/abc-123
# returns 200 — should be 404
```

---

**BUG-002 — PUT /integrations endpoint not implemented [High]**

`PUT /integrations` is declared in the spec with `{id, name}` in the body but returns `404 page not found`. Update for integrations is completely non-functional.

---

**BUG-003 — Empty body causes 500 on POST /integrations [High]**

Sending `{}` to `POST /api/v1/integrations` returns 500. Should return 400. Server panics on missing required fields instead of validating input.

---

**BUG-004 — DELETE /integrations/{id} returns 200 for non-existent id [Medium]**

Deleting an integration that doesn't exist returns 200 instead of 404. No existence check before deletion.

---

**BUG-005 — POST /assets accepts request without integration_id [Medium]**

Creating an asset without `integration_id` returns 201. The field is declared in the schema but not validated server-side.

---

**BUG-006 — PATCH /assets with non-existent id returns 500 [High]**

Patching an asset that doesn't exist returns 500 instead of 404. Same panic pattern as BUG-003.

---

**BUG-007 — DELETE /assets/{id} returns 204 for non-existent id [Medium]**

Same as BUG-004 for assets. No existence check before deletion.

---

**BUG-008 — Spec missing securityDefinitions [Low]**

The spec doesn't declare a `securityDefinitions` block despite the service requiring Basic Auth. Auto-generated clients won't include auth headers.

---

**BUG-009 — API write path degrades under sequential POST load [High]**

After around 20 sequential `POST /api/v1/integrations` requests the API starts timing out on new writes. GET requests continue working. Likely a connection pool or goroutine leak triggered by repeated writes.

---

**BUG-010 — GET /integrations returns null instead of [] for empty list [Medium]**

When no integrations exist, `GET /api/v1/integrations` returns JSON `null` instead of `[]`. The spec declares the response type as array.

```bash
curl -u test1:test123 http://localhost:8080/api/v1/integrations
# returns: null
# should return: []
```
