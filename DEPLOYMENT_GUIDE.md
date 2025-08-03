# HRV Brain API - Deployment Guide (Supabase Edition)

## 🚀 Overview

Deploy the HRV Brain API v3.3.4 with Supabase PostgreSQL backend. This guide covers deployment to platforms like Render, Railway, or Heroku while maintaining connection to your Supabase database.

## 📋 Prerequisites

- ✅ Supabase project created (`atriom_hrv_db`)
- ✅ Database schema deployed (via `setup_database_supabase.py`)
- ✅ GitHub repository with API code
- ✅ Deployment platform account (Render/Railway/Heroku)

## 🏗️ Architecture

```
iOS App → API (Render/Railway) → Supabase PostgreSQL
                ↓
        Edge Functions (Optional)
```

## 📁 Project Structure

```
/api_hrv/
├── app.py                      # Main Flask application
├── hrv_metrics.py             # NumPy-based HRV calculations
├── database_config.py         # Supabase connection management
├── database_schema.sql        # Complete database schema
├── requirements.txt           # Python dependencies
├── .env.supabase             # Environment variables (local)
├── .gitignore                # Git ignore rules
└── DEPLOYMENT_GUIDE.md       # This file
```

## 🔧 Environment Variables

Create these environment variables in your deployment platform:

```bash
# Supabase Database Connection
SUPABASE_DB_HOST=db.zluwfmovtmlijawhelzi.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=Slavoj@!64Su
SUPABASE_DB_PORT=5432

# Application Settings
FLASK_ENV=production
PORT=5000

# Optional: Supabase API (for future features)
SUPABASE_URL=https://zluwfmovtmlijawhelzi.supabase.co
SUPABASE_ANON_KEY=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

## 🚀 Deployment Options

### Option 1: Render (Recommended)

#### Step 1: Connect GitHub Repository
1. Go to [render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository: `hrv-ios-api`
4. Select the `/api_hrv` directory

#### Step 2: Configure Service
```yaml
# Build Command
pip install -r requirements.txt

# Start Command
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120

# Environment
Python Version: 3.11
```

#### Step 3: Set Environment Variables
Add all environment variables from the list above in Render dashboard.

#### Step 4: Deploy
Click "Create Web Service" - deployment will start automatically.

### Option 2: Railway

#### Step 1: Connect Repository
1. Go to [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository

#### Step 2: Configure
```bash
# Railway will auto-detect Python and use:
# Build: pip install -r requirements.txt
# Start: gunicorn app:app --bind 0.0.0.0:$PORT
```

#### Step 3: Environment Variables
Add environment variables in Railway dashboard.

### Option 3: Heroku

#### Step 1: Create Procfile
```bash
echo "web: gunicorn app:app --bind 0.0.0.0:\$PORT --workers 2" > Procfile
```

#### Step 2: Deploy
```bash
heroku create your-hrv-api
heroku config:set SUPABASE_DB_HOST=db.zluwfmovtml...
# Add other environment variables
git push heroku main
```

## 🧪 Testing Deployment

### 1. Health Check
```bash
curl https://your-api-url.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "3.3.4",
  "timestamp": "2025-08-03T15:30:00Z",
  "database": "supabase-postgresql"
}
```

### 2. Detailed Health Check
```bash
curl https://your-api-url.com/health/detailed
```

### 3. Test Session Upload
```bash
curl -X POST https://your-api-url.com/api/v1/sessions/upload \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-123-456-789",
    "user_id": "your-user-id",
    "tag": "rest",
    "subtag": "rest_single",
    "event_id": 0,
    "duration_minutes": 5,
    "recorded_at": "2025-08-03T15:30:00Z",
    "rr_intervals": [800, 820, 810, 830, 825, 815, 835, 820, 810, 825, 840, 815, 825, 835, 820]
  }'
```

## 📊 API Endpoints

### Core Endpoints
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed system status
- `POST /api/v1/sessions/upload` - Upload and process session
- `GET /api/v1/sessions/status/<session_id>` - Get session status
- `GET /api/v1/sessions/processed/<user_id>` - Get processed sessions
- `GET /api/v1/sessions/statistics/<user_id>` - Get user statistics
- `DELETE /api/v1/sessions/<session_id>` - Delete session

### Request/Response Format
All endpoints follow the exact schema.md specification:

#### Session Upload Request:
```json
{
  "session_id": "UUID",
  "user_id": "UUID", 
  "tag": "rest|sleep|experiment_paired_pre|experiment_paired_post|experiment_duration|breath_workout",
  "subtag": "semantic_tag",
  "event_id": 0,
  "duration_minutes": 1-30,
  "recorded_at": "ISO8601",
  "rr_intervals": [numbers]
}
```

#### HRV Metrics Response:
```json
{
  "status": "completed",
  "session_id": "UUID",
  "processed_at": "ISO8601",
  "hrv_metrics": {
    "mean_hr": 75.5,
    "mean_rr": 825.3,
    "count_rr": 42,
    "rmssd": 45.2,
    "sdnn": 52.1,
    "pnn50": 25.8,
    "cv_rr": 6.3,
    "defa": 1.1234,
    "sd2_sd1": 2.45
  }
}
```

## 🔒 Security Considerations

### Database Security
- ✅ Row Level Security (RLS) enabled in Supabase
- ✅ User data isolation enforced
- ✅ Connection pooling with secure credentials
- ✅ Environment variables for sensitive data

### API Security
- ✅ Input validation on all endpoints
- ✅ UUID validation for user/session IDs
- ✅ Rate limiting (configure in deployment platform)
- ✅ CORS configured for cross-origin requests

## 📈 Monitoring & Maintenance

### Logs
- Application logs available in deployment platform dashboard
- Database logs available in Supabase dashboard
- Health check endpoints for monitoring

### Performance
- Connection pooling (1-20 connections)
- Efficient database queries with indexes
- Pagination for large data sets
- Optimized HRV calculations

### Scaling
- Horizontal scaling supported (multiple workers)
- Database connection pool handles concurrent requests
- Supabase auto-scales database resources

## 🔄 CI/CD Pipeline

### Automatic Deployment
1. Push code to GitHub repository
2. Deployment platform detects changes
3. Runs build process (`pip install -r requirements.txt`)
4. Starts application (`gunicorn app:app`)
5. Health checks verify deployment

### Environment Management
- Development: Local with `.env.supabase`
- Production: Environment variables in deployment platform
- Database: Single Supabase instance for both environments

## 🆘 Troubleshooting

### Common Issues

#### Database Connection Failed
```bash
# Check environment variables
echo $SUPABASE_DB_HOST
echo $SUPABASE_DB_PASSWORD

# Test connection manually
python -c "from database_config import db_config; print(db_config.test_connection())"
```

#### HRV Metrics Calculation Error
```bash
# Test HRV calculations
python -c "from hrv_metrics import calculate_hrv_metrics; print(calculate_hrv_metrics([800,820,810,830,825]))"
```

#### Deployment Build Failed
- Check `requirements.txt` for correct versions
- Ensure Python 3.11+ compatibility
- Verify all files are committed to repository

### Support
- Supabase Dashboard: Monitor database performance
- Deployment Platform Logs: Check application errors
- Health Endpoints: Verify system status

## ✅ Deployment Checklist

- [ ] Supabase project created and database schema deployed
- [ ] GitHub repository with clean API code
- [ ] Environment variables configured in deployment platform
- [ ] Deployment platform connected to repository
- [ ] Health checks passing
- [ ] Test session upload successful
- [ ] iOS app updated with new API endpoint URL

## 🎉 Success!

Your HRV Brain API is now deployed with:
- ✅ Supabase PostgreSQL backend
- ✅ All 9 HRV metrics from schema.md
- ✅ Unified data schema
- ✅ Production-ready performance
- ✅ Secure multi-tenant architecture

**Next Steps:**
1. Update iOS app with new API endpoint URL
2. Test end-to-end session upload and processing
3. Monitor performance and logs
4. Scale as needed based on usage
