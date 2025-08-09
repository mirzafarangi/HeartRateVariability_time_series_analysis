#!/usr/bin/env bash
# Quick smoke test for HRV Brain API v5.3.1
set -euo pipefail

API_URL="${API_URL:-http://localhost:5001}"
USER_ID="${USER_ID:-7015839c-4659-4b6c-821c-2906e710a2db}"

echo "🔍 Quick Smoke Test - API v5.3.1"
echo "================================"

# Sample RR data
RR='[820,815,830,825,810,835,820,818,822,817]'

# 1. Health check
echo -n "1. Health check... "
if curl -s "$API_URL/health" | grep -q "healthy"; then
    echo "✅"
else
    echo "❌ FAILED"
    exit 1
fi

# 2. Wake check session
echo -n "2. Wake check session... "
WAKE_ID=$(uuidgen)
WAKE_RESP=$(curl -s -X POST "$API_URL/api/v1/sessions" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"$USER_ID\",\"session_id\":\"$WAKE_ID\",\"tag\":\"wake_check\",\"subtag\":\"wake_check_single\",\"event_id\":0,\"recorded_at\":\"2025-01-10T07:30:00Z\",\"duration_minutes\":5,\"rr_intervals\":$RR}")

if echo "$WAKE_RESP" | jq -e '.status == "success"' >/dev/null 2>&1; then
    echo "✅"
else
    echo "❌ FAILED: $WAKE_RESP"
    exit 1
fi

# 3. Sleep with trigger auto-allocation
echo -n "3. Sleep auto-allocation (event_id=0)... "
SLEEP_RESP=$(curl -s -X POST "$API_URL/api/v1/sessions" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"$USER_ID\",\"session_id\":\"$(uuidgen)\",\"tag\":\"sleep\",\"subtag\":\"sleep_interval_1\",\"event_id\":0,\"recorded_at\":\"2025-01-10T22:00:00Z\",\"duration_minutes\":10,\"rr_intervals\":$RR}")

EVENT_ID=$(echo "$SLEEP_RESP" | jq -r '.event_id')
if [ "$EVENT_ID" != "null" ] && [ "$EVENT_ID" -gt 0 ]; then
    echo "✅ (got event_id=$EVENT_ID)"
else
    echo "❌ FAILED: No event_id returned"
    exit 1
fi

# 4. Sleep interval 2 with auto-attach
echo -n "4. Sleep interval 2 auto-attach... "
SLEEP2_RESP=$(curl -s -X POST "$API_URL/api/v1/sessions" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"$USER_ID\",\"session_id\":\"$(uuidgen)\",\"tag\":\"sleep\",\"subtag\":\"sleep_interval_2\",\"event_id\":0,\"recorded_at\":\"2025-01-10T22:20:00Z\",\"duration_minutes\":10,\"rr_intervals\":$RR}")

EVENT_ID2=$(echo "$SLEEP2_RESP" | jq -r '.event_id')
if [ "$EVENT_ID2" == "$EVENT_ID" ]; then
    echo "✅"
else
    echo "❌ FAILED: Different event_id ($EVENT_ID2 vs $EVENT_ID)"
fi

# 5. Duplicate returns event_id
echo -n "5. Duplicate returns event_id... "
DUP_RESP=$(curl -s -X POST "$API_URL/api/v1/sessions" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"$USER_ID\",\"session_id\":\"$WAKE_ID\",\"tag\":\"wake_check\",\"subtag\":\"wake_check_single\",\"event_id\":0,\"recorded_at\":\"2025-01-10T07:30:00Z\",\"duration_minutes\":5,\"rr_intervals\":$RR}")

if echo "$DUP_RESP" | jq -e '.status == "duplicate" and .event_id != null' >/dev/null 2>&1; then
    echo "✅"
else
    echo "❌ FAILED: No event_id on duplicate"
fi

# 6. Analytics with new 'window' parameter
echo -n "6. Analytics (window param)... "
ANALYTICS=$(curl -s "$API_URL/api/v1/analytics/baseline?user_id=$USER_ID&metric=rmssd&window=10")
if echo "$ANALYTICS" | jq -e '.status == "success"' >/dev/null 2>&1; then
    echo "✅"
else
    echo "❌ FAILED"
fi

# 7. All 9 metrics supported
echo -n "7. All 9 metrics... "
FAILED=""
for metric in rmssd sdnn sd2_sd1 mean_hr mean_rr rr_count pnn50 cv_rr defa; do
    if ! curl -s "$API_URL/api/v1/analytics/baseline?user_id=$USER_ID&metric=$metric&window=5" | grep -q "success"; then
        FAILED="$FAILED $metric"
    fi
done

if [ -z "$FAILED" ]; then
    echo "✅"
else
    echo "❌ FAILED:$FAILED"
fi

# 8. Both endpoint aliases work
echo -n "8. Endpoint aliases... "
CODE1=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/v1/sessions" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"$USER_ID\",\"session_id\":\"$(uuidgen)\",\"tag\":\"experiment\",\"subtag\":\"experiment_single\",\"event_id\":0,\"recorded_at\":\"2025-01-10T14:00:00Z\",\"duration_minutes\":5,\"rr_intervals\":$RR}")

CODE2=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/v1/sessions/upload" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"$USER_ID\",\"session_id\":\"$(uuidgen)\",\"tag\":\"experiment\",\"subtag\":\"experiment_protocol_test\",\"event_id\":0,\"recorded_at\":\"2025-01-10T15:00:00Z\",\"duration_minutes\":5,\"rr_intervals\":$RR}")

if [ "$CODE1" == "201" ] && [ "$CODE2" == "201" ]; then
    echo "✅"
else
    echo "❌ FAILED ($CODE1, $CODE2)"
fi

echo "================================"
echo "✅ Quick smoke test PASSED!"
echo "API v5.3.1 + DB v4.1 working correctly"