#!/bin/bash
# Railway startup script for HRV Brain API
# Bypasses Railway's automatic Gunicorn argument injection

echo "🚀 Starting HRV Brain API with custom Gunicorn configuration..."

# Use explicit Gunicorn command with known-good arguments
exec /opt/venv/bin/gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 120 \
    --worker-class sync \
    --max-requests 1000 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
