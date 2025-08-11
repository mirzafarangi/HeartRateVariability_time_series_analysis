#!/bin/bash

# Comprehensive Railway Deployment Test
RAILWAY_URL="https://hrv-brain-api-production.up.railway.app"
TEST_USER_ID="842f03e2-b958-416a-b6fc-757a31f3c5ad"

echo "🚀 Testing Railway Deployment: $RAILWAY_URL"
echo "================================================"

# Test 1: Basic Health
echo -e "\n✅ Test 1: Health Check"
curl -s "${RAILWAY_URL}/health" | python3 -m json.tool

# Test 2: Detailed Health
echo -e "\n✅ Test 2: Detailed Health (DB Connection)"
curl -s "${RAILWAY_URL}/health/detailed" | python3 -m json.tool

# Test 3: Baseline Analytics - RMSSD
echo -e "\n✅ Test 3: Baseline Analytics (RMSSD)"
curl -s "${RAILWAY_URL}/api/v1/analytics/baseline?user_id=${TEST_USER_ID}&metric=rmssd&window=5" | python3 -m json.tool | head -20

# Test 4: Baseline Analytics - SDNN
echo -e "\n✅ Test 4: Baseline Analytics (SDNN)"
curl -s "${RAILWAY_URL}/api/v1/analytics/baseline?user_id=${TEST_USER_ID}&metric=sdnn&window=5" | python3 -m json.tool | head -20

# Test 5: Micro-sleep Analytics
echo -e "\n✅ Test 5: Micro-sleep Analytics"
curl -s "${RAILWAY_URL}/api/v1/analytics/micro-sleep?user_id=${TEST_USER_ID}&window=5" | python3 -m json.tool | head -20

# Test 6: Macro-sleep Analytics
echo -e "\n✅ Test 6: Macro-sleep Analytics"
curl -s "${RAILWAY_URL}/api/v1/analytics/macro-sleep?user_id=${TEST_USER_ID}&window=5" | python3 -m json.tool | head -20

# Test 7: Day-load Analytics
echo -e "\n✅ Test 7: Day-load Analytics"
curl -s "${RAILWAY_URL}/api/v1/analytics/day-load?user_id=${TEST_USER_ID}&min_hours=0&max_hours=24" | python3 -m json.tool | head -20

# Test 8: Experiment Analytics
echo -e "\n✅ Test 8: Experiment Analytics"
curl -s "${RAILWAY_URL}/api/v1/analytics/experiment?user_id=${TEST_USER_ID}&protocol=baseline" | python3 -m json.tool | head -20

echo -e "\n================================================"
echo "✨ All endpoint tests complete!"
