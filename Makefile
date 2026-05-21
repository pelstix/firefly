#Test Automation for infralightio/test-integration-api
 

.PHONY: all run test test-smoke test-auth test-crud test-tenant test-contract \
        test-load load clean logs help

COMPOSE   = docker compose
REPORT    = reports/pytest_report.html
API_URL  ?= http://localhost:8080

##@ Main targets

all: run   ## Default: run the complete test suite

run:       ## Run everything (API + tests + load) with a single command
	$(COMPOSE) up --build --abort-on-container-exit --exit-code-from tests
	@echo ""
	@echo "Reports written to ./reports/"

##@ Local development targets (requires API already running on port 8080)

test:             ## Run full pytest suite (no load) against local API
	pytest tests/ -m "not load" \
	  --html=$(REPORT) --self-contained-html \
	  -v

test-smoke:       ## Run smoke tests only (fast, < 30s)
	pytest tests/ -m smoke -v

test-auth:        ## Run authentication tests only
	pytest tests/test_auth.py -v

test-crud:        ## Run CRUD tests only
	pytest tests/test_crud.py -v

test-tenant:      ## Run tenant isolation tests only
	pytest tests/test_tenant_isolation.py -v

test-contract:    ## Run OpenAPI contract tests only
	pytest tests/test_contract.py -v

test-load:        ## Run pytest load tests only
	pytest tests/test_load.py -v -s

load:             ## Run Locust load test (headless, 60s) against local API
	locust -f load/locustfile.py \
	  --headless \
	  --users 20 \
	  --spawn-rate 10 \
	  --run-time 60s \
	  --host $(API_URL) \
	  --html reports/load_report.html \
	  --csv reports/load

load-ui:          ## Open Locust web UI (manual control)
	locust -f load/locustfile.py --host $(API_URL)

##@ Utility

clean:            ## Remove generated reports and caches
	rm -rf reports/* .pytest_cache __pycache__ **/__pycache__ *.pyc

logs:             ## Tail docker compose logs
	$(COMPOSE) logs -f

help:             ## Show this help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} \
	  /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
