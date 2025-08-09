#!/bin/bash
set -e

echo "🚀 Starting Lumenis API v5.3.1"
echo "📊 Database: $SUPABASE_DB_HOST"
echo "🔧 Workers: 2, Threads: 4"
echo "⏱️ Timeout: 120s"

# Run migrations if needed
# python3 check_db.py

# Start gunicorn with optimal settings
exec gunicorn app:app \
  --bind "0.0.0.0:${PORT:-5000}" \
  --workers 2 \
  --threads 4 \
  --worker-class gthread \
  --timeout 120 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  --capture-output \
  --enable-stdio-inheritance