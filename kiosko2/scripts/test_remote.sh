#!/bin/bash
#
# Remote Testing Script for Kiosko2
# Run this from Windows (via Git Bash/WSL) or any machine to test the Pi deployment.
#
# Usage: ./test_remote.sh [PI_HOST] [API_KEY]
#
# Environment variables:
#   KIOSKO_REMOTE_URL  - Base URL of the deployed backend (e.g., http://192.168.1.100:8000)
#   KIOSKO_TEST_API_KEY - API key for test endpoints
#

set -e

# Configuration
PI_HOST="${1:-${KIOSKO_REMOTE_URL:-http://raspberrypi.local:8000}}"
API_KEY="${2:-${KIOSKO_TEST_API_KEY:-}}"

# Colors (works in Git Bash)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local name="$1"
    local expected_code="$2"
    local method="$3"
    local endpoint="$4"
    local body="$5"
    
    log_info "Testing: $name"
    
    local curl_opts="-s -w '%{http_code}' -o /tmp/response.json"
    
    if [ -n "$API_KEY" ]; then
        curl_opts="$curl_opts -H 'X-Test-API-Key: $API_KEY'"
    fi
    
    if [ "$method" = "POST" ]; then
        curl_opts="$curl_opts -X POST -H 'Content-Type: application/json'"
        if [ -n "$body" ]; then
            curl_opts="$curl_opts -d '$body'"
        fi
    fi
    
    local status_code
    status_code=$(eval "curl $curl_opts '${PI_HOST}${endpoint}'")
    
    if [ "$status_code" = "$expected_code" ]; then
        log_pass "$name (HTTP $status_code)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        log_fail "$name (Expected HTTP $expected_code, got $status_code)"
        cat /tmp/response.json 2>/dev/null || true
        echo ""
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

echo "========================================"
echo "Kiosko2 Remote E2E Tests"
echo "Target: $PI_HOST"
echo "========================================"
echo ""

# Test 1: Health check
run_test "Health check" "200" "GET" "/api/v1/health"

# Test 2: List cabins
run_test "List cabins" "200" "GET" "/api/v1/cabins/"

# Test 3: Get specific cabin
run_test "Get cabin CABINA-01" "200" "GET" "/api/v1/cabins/CABINA-01"

# Test 4: Presence status
run_test "Presence status" "200" "GET" "/api/v1/presence/" || true  # May fail if MQTT not connected

# Test 5: API key protected endpoint (ping)
if [ -n "$API_KEY" ]; then
    run_test "Test endpoint (ping)" "200" "GET" "/api/v1/test/ping"
else
    log_info "Skipping API key tests (no API key provided)"
fi

# Test 6: Full store/retrieve flow (requires API key)
if [ -n "$API_KEY" ]; then
    log_info "Testing store/retrieve vehicle flow..."
    
    # Cleanup
    run_test "Cleanup" "200" "POST" "/api/v1/test/cleanup" "{}"
    
    # Store vehicle
    log_info "Storing vehicle..."
    curl -s -X POST "${PI_HOST}/api/v1/test/store-vehicle" \
        -H "Content-Type: application/json" \
        -H "X-Test-API-Key: $API_KEY" \
        -d '{"cabin_id": "CABINA-01", "vehicle_plate": "TEST-123"}' \
        -o /tmp/store_response.json
    
    TOKEN=$(cat /tmp/store_response.json | grep -o '"ticket_token":"[^"]*"' | cut -d'"' -f4)
    
    if [ -n "$TOKEN" ]; then
        log_pass "Store vehicle (token: ${TOKEN:0:8}...)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        
        # Retrieve vehicle
        log_info "Retrieving vehicle..."
        curl -s -X POST "${PI_HOST}/api/v1/test/retrieve-vehicle" \
            -H "Content-Type: application/json" \
            -H "X-Test-API-Key: $API_KEY" \
            -d "{\"token\": \"$TOKEN\"}" \
            -o /tmp/retrieve_response.json
        
        SUCCESS=$(cat /tmp/retrieve_response.json | grep -o '"success":true' || echo "")
        if [ -n "$SUCCESS" ]; then
            log_pass "Retrieve vehicle"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            log_fail "Retrieve vehicle"
            cat /tmp/retrieve_response.json
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        log_fail "Store vehicle (no token returned)"
        cat /tmp/store_response.json
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
fi

# Summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo -e "Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Failed: ${RED}${TESTS_FAILED}${NC}"
echo ""

if [ $TESTS_FAILED -gt 0 ]; then
    exit 1
fi

exit 0
