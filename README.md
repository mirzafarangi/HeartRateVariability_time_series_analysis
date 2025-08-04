# HRV Brain API & Database - Production System v5.0.0
**Complete Backend Implementation for HRV Analysis Platform**

> **🎯 BLUEPRINT STATUS**: This README serves as the canonical deployment guide for the entire backend system. Follow these instructions for guaranteed successful deployment.

**Version:** 5.0.0 FINAL  
**Architecture:** Railway + Supabase PostgreSQL + iOS Swift SDK  
**Language:** Python 3.11 + NumPy + Flask  
**Status:** ✅ Production Ready + iOS Integrated  
**API URL:** https://hrv-brain-api-production.up.railway.app  
**Database:** Supabase PostgreSQL with Transaction Pooler  

## 🏗️ **SYSTEM ARCHITECTURE**

### **Core Components**
- **Flask API**: RESTful endpoints for session management and HRV processing
- **PostgreSQL Database**: Supabase-hosted with Row Level Security
- **HRV Engine**: NumPy-based calculations for 9 physiological metrics
- **Authentication**: Supabase Auth integration
- **Deployment**: Railway with auto-scaling and CI/CD

### **Key Features**
- **9 HRV Metrics**: RMSSD, SDNN, pNN50, CV_RR, DFA α1, SD2/SD1, Mean HR/RR, Count RR
- **Real-time Processing**: Async session processing with status tracking
- **User Isolation**: Multi-tenant architecture with secure data separation
- **iOS Integration**: Direct PostgREST client support for mobile apps
- **Production Ready**: Health monitoring, error handling, logging
- **Scalable**: Auto-scaling deployment with database connection pooling
**API URL:** https://hrv-brain-api-production.up.railway.app  
**Database:** Supabase PostgreSQL (Transaction Pooler, IPv4-compatible)  

## Overview

The HRV Brain API is a scientific computing platform for Heart Rate Variability (HRV) analysis, implementing a unified data schema across iOS applications, REST API endpoints, and PostgreSQL database storage. The system processes RR interval data from cardiac sensors and computes nine established HRV metrics using pure NumPy implementations.

## Architecture

```
iOS Application → Railway API (Python/Flask) → Supabase PostgreSQL
                 (HRV Calculations)           (Data Persistence + RLS)
```

**Design Principles:**
- **Single Source of Truth**: Unified schema across all components
- **Scientific Accuracy**: Pure NumPy implementations of established HRV metrics
- **Data Integrity**: PostgreSQL with Row Level Security (RLS)
- **Scalability**: Connection pooling and cloud-native deployment

## HRV Metrics Implementation

The system implements nine established HRV metrics following scientific literature:

### Time Domain Metrics
- **RMSSD**: Root Mean Square of Successive Differences
- **SDNN**: Standard Deviation of NN intervals
- **pNN50**: Percentage of NN intervals differing by >50ms
- **CV_RR**: Coefficient of Variation of RR intervals

### Frequency Domain Metrics
- **Mean HR**: Average heart rate (beats per minute)
- **Mean RR**: Average RR interval duration (milliseconds)

### Non-linear Metrics
- **DFA α1**: Detrended Fluctuation Analysis short-term scaling exponent
- **SD2/SD1**: Poincaré plot ellipse ratio
- **Count RR**: Total number of valid RR intervals

## Data Schema

### Session Structure
```json
{
  "session_id": "UUID",
  "user_id": "UUID", 
  "tag": "base_tag",
  "subtag": "semantic_subtag",
  "event_id": "integer",
  "duration_minutes": "number",
  "recorded_at": "ISO8601_timestamp",
  "rr_intervals": ["array_of_milliseconds"]
}
```

### Tag Classification System
- **rest**: Single resting measurements (event_id: 0)
- **sleep**: Multi-interval sleep recordings (event_id: >0, grouped)
- **experiment_paired_pre**: Pre-intervention measurements
- **experiment_paired_post**: Post-intervention measurements
- **experiment_duration**: Duration-based experiments
- **breath_workout**: Breathing exercise sessions

### Event Grouping Logic
- **Standalone Sessions**: event_id = 0 (rest, experiments, breathing)
- **Grouped Sessions**: event_id > 0 (sleep intervals share same event_id)

## API Endpoints

### Core Endpoints
- `POST /api/v1/sessions/upload` - Upload and process HRV session
- `GET /api/v1/sessions/status/<session_id>` - Get processing status
- `GET /api/v1/sessions/processed/<user_id>` - Retrieve processed sessions
- `GET /api/v1/sessions/statistics/<user_id>` - Get session statistics
- `DELETE /api/v1/sessions/<session_id>` - Delete session data

### Health Monitoring
- `GET /health` - Basic health check
- `GET /health/detailed` - Comprehensive system status

## Database Schema

### Tables
- **public.profiles**: User profiles extending Supabase auth.users
- **public.sessions**: Unified raw and processed session data

### Key Features
- **Row Level Security**: User data isolation
- **Automatic Triggers**: Session counting and timestamp management
- **Helper Functions**: Statistics aggregation and data retrieval
- **Performance Indexes**: Optimized queries for user_id and timestamps

## Deployment

### Railway Configuration
- **Runtime**: Python 3.11.9
- **Dependencies**: Flask, NumPy, psycopg2-binary, Gunicorn
- **Health Checks**: Automatic monitoring and restart policies
- **Environment**: Production-ready with connection pooling

### Environment Variables
```bash
SUPABASE_DB_HOST=db.zluwfmovtmlijawhelzi.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=[secure_password]
SUPABASE_DB_PORT=5432
FLASK_ENV=production
```

## File Structure

```
/api_hrv/
├── app.py                      # Main Flask application (22KB)
├── hrv_metrics.py             # NumPy HRV calculations (11KB)
├── database_config.py         # Connection management
├── database_schema.sql        # Complete PostgreSQL schema (20KB)
├── schema.md                  # Golden reference documentation (17KB)
├── requirements.txt           # Python dependencies
├── railway.json               # Railway deployment configuration
├── runtime.txt                # Python version specification
├── nixpacks.toml             # Build configuration
├── setup_database_supabase.py # Database initialization
├── cleanup_database.py       # Maintenance utilities
└── validate_db_connection.py  # Connection diagnostics
```

## Scientific Validation

### HRV Metric Accuracy
- **RMSSD**: Implements standard successive difference calculation
- **SDNN**: Population standard deviation of RR intervals
- **DFA α1**: Detrended fluctuation analysis with minimum 50 intervals
- **Poincaré**: Ellipse fitting for SD1/SD2 calculation

### Data Quality Assurance
- **Input Validation**: Schema compliance checking
- **Range Validation**: Physiologically plausible RR intervals
- **Statistical Validation**: Minimum data requirements for metrics
- **Error Handling**: Graceful degradation for insufficient data

## Performance Characteristics

### Computational Complexity
- **Time Domain**: O(n) for n RR intervals
- **DFA Calculation**: O(n log n) with minimum 50 intervals
- **Database Operations**: Indexed queries with sub-second response

### Scalability Metrics
- **Connection Pool**: 1-20 concurrent database connections
- **Request Handling**: 2 Gunicorn workers with keepalive
- **Memory Usage**: Optimized NumPy operations for large datasets

## Integration Guidelines

### iOS Application Integration
1. Implement Supabase authentication
2. Use unified session schema for uploads
3. Handle offline queuing for network resilience
4. Implement proper error handling and retry logic

### API Client Implementation
- **Authentication**: Supabase JWT tokens
- **Rate Limiting**: Respect connection pool limits
- **Error Handling**: Parse structured error responses
- **Data Validation**: Client-side schema validation recommended

## Maintenance

### Database Maintenance
- **Backup Strategy**: Supabase automatic backups
- **Schema Updates**: Version-controlled migrations
- **Performance Monitoring**: Query optimization and indexing
- **Data Cleanup**: Automated session lifecycle management

### API Maintenance
- **Health Monitoring**: Automated health checks
- **Log Analysis**: Structured logging for debugging
- **Performance Metrics**: Response time and error rate monitoring
- **Security Updates**: Regular dependency updates

## Deployment Configuration

### Production Environment
The system is deployed on Railway with Supabase PostgreSQL backend using the following configuration:

**Database Connection**: Supabase Transaction Pooler (IPv4-compatible)
- Host: aws-0-eu-central-1.pooler.supabase.com
- Port: 6543 (Transaction Pooler)
- Connection pooling: 15 connections per user+database combination

**Application Server**: Gunicorn WSGI with optimized configuration
- Workers: 2 (Railway Nano compute)
- Timeout: 120 seconds
- Worker class: sync
- Max requests: 1000 per worker

**Critical Dependencies**:
- PyJWT==2.8.0 (JWT token handling)
- supabase==2.3.4 (Database client)
- psycopg2-binary==2.9.9 (PostgreSQL adapter)
- numpy==1.26.4 (HRV calculations)

### Deployment Lessons
Key issues resolved during production deployment:

1. **IPv4 Compatibility**: Railway requires Supabase Transaction Pooler instead of Direct Connection
2. **Gunicorn Arguments**: Invalid `--keepalive` argument removed from railway.json configuration
3. **Import Dependencies**: Missing PyJWT and supabase packages added to requirements.txt
4. **Security Management**: API keys rotated and environment variables properly configured

## References

This implementation follows established HRV analysis methodologies from:
- Task Force of the European Society of Cardiology (1996)
- Peng et al. (1995) for DFA implementation
- Brennan et al. (2001) for Poincaré plot analysis
- Shaffer & Ginsberg (2017) for contemporary HRV guidelines

## Production URL

**API Base URL**: https://hrv-brain-api-production.up.railway.app

**Health Check**: https://hrv-brain-api-production.up.railway.app/health
