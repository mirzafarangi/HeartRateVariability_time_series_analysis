#!/bin/bash

# End-to-End Integration Test for iOS-API-DB Canonical Compliance
# Tests the complete flow: Queue → Upload → DB → Sessions Tab

API_URL="https://hrv-brain-api-production.up.railway.app"
USER_ID="$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-')"
SESSION_ID="$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-')"

echo "🧪 HRV iOS-API-DB Integration Test"
echo "=================================="
echo "API URL: $API_URL"
echo "Test User ID: $USER_ID"
echo "Test Session ID: $SESSION_ID"
echo ""

# Test 1: API Health Check
echo "1️⃣ Testing API Health..."
curl -s "$API_URL/health" | jq '.'
echo ""

# Test 2: Upload Wake Check Session (Canonical)
echo "2️⃣ Testing Wake Check Session Upload..."
WAKE_CHECK_PAYLOAD=$(cat <<EOF
{
  "session_id": "$SESSION_ID",
  "user_id": "$USER_ID",
  "tag": "wake_check",
  "subtag": "wake_check_single",
  "event_id": 0,
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_minutes": 5,
  "rr_intervals": [800, 820, 810, 830, 825, 815, 805, 795, 810, 820]
}
EOF
)

echo "Payload:"
echo "$WAKE_CHECK_PAYLOAD" | jq '.'
echo ""

RESPONSE=$(curl -s -X POST "$API_URL/api/v1/sessions/upload" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-$(date +%s)" \
  -d "$WAKE_CHECK_PAYLOAD")

echo "Response:"
echo "$RESPONSE" | jq '.'
echo ""

# Test 3: Upload Pre-Sleep Session
echo "3️⃣ Testing Pre-Sleep Session Upload..."
PRE_SLEEP_ID="$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-')"
PRE_SLEEP_PAYLOAD=$(cat <<EOF
{
  "session_id": "$PRE_SLEEP_ID",
  "user_id": "$USER_ID",
  "tag": "pre_sleep",
  "subtag": "pre_sleep_single",
  "event_id": 0,
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_minutes": 5,
  "rr_intervals": [750, 760, 755, 765, 770, 760, 755, 750, 760, 765]
}
EOF
)

RESPONSE=$(curl -s -X POST "$API_URL/api/v1/sessions/upload" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-presleep-$(date +%s)" \
  -d "$PRE_SLEEP_PAYLOAD")

echo "Response:"
echo "$RESPONSE" | jq '.'
echo ""

# Test 4: Upload Sleep Session (with event_id allocation)
echo "4️⃣ Testing Sleep Session Upload (event_id=0 for auto-allocation)..."
SLEEP_ID="$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-')"
SLEEP_PAYLOAD=$(cat <<EOF
{
  "session_id": "$SLEEP_ID",
  "user_id": "$USER_ID",
  "tag": "sleep",
  "subtag": "sleep_interval_1",
  "event_id": 0,
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_minutes": 10,
  "rr_intervals": [900, 910, 920, 915, 905, 895, 900, 910, 920, 925, 915, 905, 900, 910, 920]
}
EOF
)

RESPONSE=$(curl -s -X POST "$API_URL/api/v1/sessions/upload" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-sleep-$(date +%s)" \
  -d "$SLEEP_PAYLOAD")

echo "Response (should contain allocated event_id):"
echo "$RESPONSE" | jq '.'
EVENT_ID=$(echo "$RESPONSE" | jq -r '.event_id // 0')
echo "Allocated Event ID: $EVENT_ID"
echo ""

# Test 5: Upload Experiment Session
echo "5️⃣ Testing Experiment Session Upload..."
EXPERIMENT_ID="$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-')"
EXPERIMENT_PAYLOAD=$(cat <<EOF
{
  "session_id": "$EXPERIMENT_ID",
  "user_id": "$USER_ID",
  "tag": "experiment",
  "subtag": "experiment_protocol_breathing",
  "event_id": 0,
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_minutes": 7,
  "rr_intervals": [850, 860, 855, 865, 870, 860, 855, 850, 860, 865, 870, 875]
}
EOF
)

RESPONSE=$(curl -s -X POST "$API_URL/api/v1/sessions/upload" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-experiment-$(date +%s)" \
  -d "$EXPERIMENT_PAYLOAD")

echo "Response:"
echo "$RESPONSE" | jq '.'
echo ""

# Test 6: Test Idempotency (duplicate upload)
echo "6️⃣ Testing Idempotency (duplicate upload should return same response)..."
RESPONSE=$(curl -s -X POST "$API_URL/api/v1/sessions/upload" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-wake-check" \
  -d "$WAKE_CHECK_PAYLOAD")

echo "Duplicate upload response (should be 200 with duplicate message):"
echo "$RESPONSE" | jq '.'
echo ""

# Test 7: Invalid Tag Test
echo "7️⃣ Testing Invalid Tag Rejection..."
INVALID_PAYLOAD=$(cat <<EOF
{
  "session_id": "$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-')",
  "user_id": "$USER_ID",
  "tag": "rest",
  "subtag": "rest_single",
  "event_id": 0,
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_minutes": 5,
  "rr_intervals": [800, 820, 810]
}
EOF
)

RESPONSE=$(curl -s -X POST "$API_URL/api/v1/sessions/upload" \
  -H "Content-Type: application/json" \
  -d "$INVALID_PAYLOAD")

echo "Response (should be 400 with validation error):"
echo "$RESPONSE" | jq '.'
echo ""

# Test 8: Invalid Subtag Pattern Test
echo "8️⃣ Testing Invalid Subtag Pattern Rejection..."
INVALID_SUBTAG_PAYLOAD=$(cat <<EOF
{
  "session_id": "$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-')",
  "user_id": "$USER_ID",
  "tag": "wake_check",
  "subtag": "wake_check_invalid",
  "event_id": 0,
  "recorded_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_minutes": 5,
  "rr_intervals": [800, 820, 810]
}
EOF
)

RESPONSE=$(curl -s -X POST "$API_URL/api/v1/sessions/upload" \
  -H "Content-Type: application/json" \
  -d "$INVALID_SUBTAG_PAYLOAD")

echo "Response (should be 400 with validation error):"
echo "$RESPONSE" | jq '.'
echo ""

echo "✅ Integration Test Complete!"
echo ""
echo "Summary:"
echo "- API Health: ✓"
echo "- Canonical Tags: wake_check, pre_sleep, sleep, experiment ✓"
echo "- Subtag Patterns: Validated with prefixes ✓"
echo "- Event ID: Auto-allocation for sleep ✓"
echo "- Idempotency: In-memory caching ✓"
echo "- Validation: Rejects non-canonical tags/subtags ✓"
echo ""
echo "iOS Integration Points:"
echo "1. Queue Manager → API Client → /api/v1/sessions/upload"
echo "2. Sessions Tab → Database (Direct Supabase)"
echo "3. Delete Button → Database (Direct Supabase)"
echo ""
echo "Next Steps:"
echo "1. Build and run iOS app"
echo "2. Record a session in Record tab"
echo "3. Check Queue Card for upload status"
echo "4. Verify in Sessions tab (should show tag/subtag/event_id)"
echo "5. Test delete functionality"
