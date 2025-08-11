#!/bin/bash

# Test Railway Deployment
# Replace YOUR_RAILWAY_URL with your actual Railway deployment URL

RAILWAY_URL="https://YOUR_RAILWAY_URL.railway.app"

echo "Testing Railway Deployment..."
echo "================================"

# Test 1: Health Check
echo -e "\n1. Testing Health Endpoint:"
curl -s "${RAILWAY_URL}/health" | python3 -m json.tool

# Test 2: Detailed Health Check
echo -e "\n2. Testing Detailed Health:"
curl -s "${RAILWAY_URL}/health/detailed" | python3 -m json.tool

# Test 3: Baseline Analytics (with test user)
echo -e "\n3. Testing Baseline Analytics:"
TEST_USER_ID="842f03e2-b958-416a-b6fc-757a31f3c5ad"
curl -s "${RAILWAY_URL}/api/v1/analytics/baseline?user_id=${TEST_USER_ID}&metric=rmssd&window=10" | python3 -m json.tool | head -20

# Test 4: Check if API accepts connections
echo -e "\n4. Testing API Availability:"
response=$(curl -s -o /dev/null -w "%{http_code}" "${RAILWAY_URL}/health")
if [ $response -eq 200 ]; then
    echo "✅ API is responding correctly (HTTP 200)"
else
    echo "❌ API returned HTTP $response"
fi

echo -e "\n================================"
echo "Test Complete!"
