# HRV Brain API - Unified Deployment Guide

## ✅ DEPLOYMENT SUCCESSFUL

**Status**: 🎉 **DEPLOYED AND WORKING + iOS FIXES**  
**API URL**: https://hrv-brain-api-production.up.railway.app  
**Version**: 4.1.0 Final  
**Date**: 2025-08-04  

## 🚀 Overview

Deploy the HRV Brain API v4.0.0 to **Railway** with Supabase PostgreSQL backend. This unified setup provides clean, production-ready deployment with proper schema consistency and authentication.

### ✅ Verified Working Configuration
- **Platform**: Railway (Nixpacks + Python 3.11)
- **Database**: Supabase PostgreSQL (Transaction Pooler, IPv4-compatible)
- **Security**: Rotated API keys, secrets management
- **Health Check**: `/health` endpoint responding correctly

## 📋 Prerequisites

- ✅ Supabase project created (`atriom_hrv_db`)
- ✅ Database schema deployed (via `database_manager.py reset`)
- ✅ GitHub repository with clean API code
- ✅ Railway account (free tier available)

## 🚀 RAILWAY DEPLOYMENT STEPS

### Step 1: Verify Clean File Structure

Ensure your repository has the unified, clean file structure:

```bash
# Verify clean API folder structure
ls -la /Users/ashkanbeheshti/Desktop/hrv-ios-api/api_hrv/

# Should include ONLY:
# ✅ app.py (Main Flask API)
# ✅ database_config.py (DB connection)
# ✅ database_manager.py (DB setup/validation)
# ✅ hrv_metrics.py (HRV calculations)
# ✅ schema.md (Golden reference)
# ✅ requirements.txt (Dependencies)
# ✅ .env.railway (Environment template)
# ✅ README.md & DEPLOYMENT_GUIDE.md (Documentation)
# ✅ Railway deployment files (nixpacks.toml, railway.json, runtime.txt)
```

### Step 2: Setup Database Schema

Before deployment, ensure your Supabase database has the unified schema:

```bash
# Navigate to API folder
cd /Users/ashkanbeheshti/Desktop/hrv-ios-api/api_hrv

# Reset database with clean, unified schema
python3 database_manager.py reset

# Verify schema is correct
python3 database_manager.py validate
```

### Step 3: Create Railway Account & Deploy

1. **Sign up at [railway.app](https://railway.app)** (free tier available)
2. **Click "New Project"** → **"Deploy from GitHub repo"**
3. **Connect Repository**: Select `hrv-ios-api`
4. **Configure Service**:
   - **Root Directory**: `/api_hrv`
   - **Runtime**: Automatically detected (Python 3.11)
   - **Build**: Automatically uses `requirements.txt`
   - **Start**: Automatically uses `gunicorn`

### Step 4: Set Environment Variables

**CRITICAL**: Copy ALL variables from `.env.railway` to Railway dashboard:

```bash
# === SUPABASE DATABASE CONNECTION ===
SUPABASE_DB_HOST=db.zluwfmovtmlijawhelzi.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=Slavoj@!64Su
SUPABASE_DB_PORT=5432

# === SUPABASE AUTHENTICATION ===
SUPABASE_URL=https://zluwfmovtmlijawhelzi.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpsdXdmbW92dG1saWphd2hlbHppIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQyMjE4OTIsImV4cCI6MjA2OTc5Nzg5Mn0.fZDlNtT5rhbaxQ3iQRlkmgE6gP3Wav7EFD_Dp4dHC2o
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpsdXdmbW92dG1saWphd2hlbHppIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NDIyMTg5MiwiZXhwIjoyMDY5Nzk3ODkyfQ.lf_Ls_7MVykV_P-4gitP1QLo9PJxSrDRX1VMty_rnuA

# === FLASK CONFIGURATION ===
FLASK_ENV=production
PORT=5000
PYTHON_VERSION=3.11.0
```

### Step 5: Deploy & Verify

1. **Railway will automatically**:
   - Clone your repository from GitHub
   - Install Python dependencies from `requirements.txt`
   - Start your Flask application with `gunicorn`
   - Provide a public URL

2. **Your API will be available at**:
   ```
   https://your-project-name.up.railway.app
   ```

3. **Verify deployment**:
   ```bash
   # Test health endpoint
   curl https://your-project-name.up.railway.app/health
   
   # Should return:
   # {"status": "healthy", "timestamp": "...", "database": "connected"}

## 🏗️ Unified Architecture

```
iOS App → Railway (Python/Flask/NumPy) → Supabase PostgreSQL
          (Auto-scaling, CI/CD)        (Unified Schema, RLS)
```

**Why This Unified Architecture:**
- ✅ **Clean Schema**: `profiles` table (not `users`) with proper foreign keys
- ✅ **Unified Auth**: Service role for server, anon key + JWT for client
- ✅ **Railway Deployment**: Reliable Python/NumPy support
- ✅ **Auto-scaling**: Railway handles traffic automatically
- ✅ **CI/CD**: Automatic deployments from GitHub
- ✅ **Cost-effective**: Free tier for development

## 📁 Clean Project Structure

```
/api_hrv/
├── app.py                      # Main Flask API
├── database_config.py         # Database connection
├── database_manager.py        # Database setup/validation
├── hrv_metrics.py             # HRV calculations
├── schema.md                  # Golden reference
├── requirements.txt           # Dependencies
├── .env.railway              # Environment variables
├── README.md                  # Documentation
├── DEPLOYMENT_GUIDE.md       # This file
└── (Railway deployment files)
```

## 🧪 Testing Deployment

### 1. Health Check
```bash
curl https://your-project-name.up.railway.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "4.0.0",
  "timestamp": "2025-08-03T21:30:00Z",
  "database": "connected"
}
```

### 2. Test Database Connection
```bash
# Locally test database manager
python3 database_manager.py validate
```

## 🎯 Summary

✅ **Clean Architecture**: Unified schema with `profiles` table  
✅ **Railway Deployment**: Reliable Python/NumPy support  
✅ **Supabase Integration**: Proper authentication and RLS  
✅ **Production Ready**: Health checks and error handling  

**Your API is now deployed and ready for iOS integration!**
