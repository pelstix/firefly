#!/usr/bin/env bash
set -euo pipefail

REPORT_DIR="${REPORT_DIR:-reports}"
API_URL="${API_BASE_URL:-http://localhost:8080}"
LOAD_USERS="${LOAD_TEST_USERS:-20}"
LOAD_SPAWN="${LOAD_TEST_SPAWN_RATE:-10}"
LOAD_DURATION="${LOAD_TEST_DURATION:-60s}"

mkdir -p "$REPORT_DIR"

echo ""
echo "TEST AUTOMATION SUITE - infralightio API"
echo "API URL    : $API_URL"
echo "Report dir : $REPORT_DIR"
echo ""

PYTEST_EXIT=0
python -m pytest \
  tests/ \
  --html="$REPORT_DIR/pytest_report.html" \
  --self-contained-html \
  --tb=short \
  --timeout=30 \
  -v \
  --junitxml="$REPORT_DIR/junit.xml" \
  -m "not load" \
  || PYTEST_EXIT=$?

echo ""
if [ $PYTEST_EXIT -eq 0 ]; then
  echo "pytest: all tests passed"
else
  echo "pytest: some tests failed (exit $PYTEST_EXIT)"
fi

echo ""
echo "Running Locust load test (${LOAD_DURATION}, ${LOAD_USERS} users)..."
LOCUST_EXIT=0
python -m locust \
  -f load/locustfile.py \
  --headless \
  --users "$LOAD_USERS" \
  --spawn-rate "$LOAD_SPAWN" \
  --run-time "$LOAD_DURATION" \
  --host "$API_URL" \
  --html "$REPORT_DIR/load_report.html" \
  --csv "$REPORT_DIR/load" \
  2>&1 | tee "$REPORT_DIR/locust.log" \
  || LOCUST_EXIT=$?

echo ""
if [ $LOCUST_EXIT -eq 0 ]; then
  echo "Locust: SLAs met"
else
  echo "Locust: SLA violation (exit $LOCUST_EXIT)"
fi

echo ""
echo "SUMMARY"
echo "Functional tests : $([ $PYTEST_EXIT -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
echo "Load tests       : $([ $LOCUST_EXIT -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
echo ""
echo "Reports written to: $REPORT_DIR/"
echo "  $REPORT_DIR/pytest_report.html"
echo "  $REPORT_DIR/load_report.html"
echo "  $REPORT_DIR/junit.xml"
echo ""

FINAL_EXIT=$(( PYTEST_EXIT | LOCUST_EXIT ))
exit $FINAL_EXIT
