# HRV Brain API Schema Documentation

**Version:** 5.0.0 Polish Architecture  
**Date:** 2025-08-07  
**Status:** Production Ready with Trend Analysis  
**Branch:** fresh_polish_api  
**Architecture:** polish_architecture.md v1.0

## Overview

Complete centralized API implementation for HRV session processing and RMSSD trend analysis. Implements the full polish_architecture.md specification with three clinical-grade trend endpoints, unified JSON response schema, and modular backend statistical processing.

## Architecture

### Core Components

**Primary Application:** `app.py` (15.2KB)
- Flask web application with CORS enabled
- PostgreSQL connection pooling via psycopg2
- Comprehensive error handling and logging
- Production-ready with Gunicorn WSGI server
- **NEW:** Three trend analysis endpoints with unified JSON schema

**Core Dependencies:**
- `database_config.py` - Database connection management and configuration
- `hrv_metrics.py` - Pure NumPy implementation of 9 HRV metrics
- `session_validator.py` - Modular validation system with enhanced error reporting
- **NEW:** `trend_analyzer.py` - Centralized trend analysis with rolling averages, baselines, SD bands

**Database Components:**
- `database_schema.sql` - Complete schema with trend analysis indexes
- `add_aggregated_view.sql` - Aggregated sleep events view
- `deploy_aggregated_view.py` - Database deployment script

### Database Integration

**Database:** PostgreSQL via Supabase  
**Connection:** ThreadedConnectionPool for production scalability  
**Schema:** Unified sessions table with 9 HRV metric columns  
**Authentication:** Environment variable based configuration  
**NEW Views:** `aggregated_sleep_events` - Pre-computed sleep event aggregations  
**NEW Indexes:** Optimized indexes for trend queries (rest, sleep interval, sleep event)  

## API Endpoints

**Total Endpoints:** 8 (5 core + 3 trend analysis)

### Health Monitoring

#### GET /health
Basic health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-08-07T16:22:50.123Z",
  "version": "4.0.0"
}
```

#### GET /health/detailed
Comprehensive health check with database connectivity validation.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-08-07T16:22:50.123Z",
  "version": "4.0.0",
  "database": "connected",
  "components": {
    "api": "healthy",
    "database": "connected"
  }
}
```

### Session Management

#### POST /api/v1/sessions/upload
Upload and process HRV session data with automatic metric calculation.

**Request Body:**
```json
{
  "user_id": "7015839c-4659-4b6c-821c-2906e710a2db",
  "session_id": "B3F0F515-B9EC-4CE7-B123-6DDF19FD2CCA",
  "tag": "rest",
  "subtag": "rest_single",
  "event_id": 0,
  "duration_minutes": 5,
  "recorded_at": "2025-08-07T16:22:50.123Z",
  "rr_intervals": [856.2, 847.3, 862.1, ...]
}
```

**Response (Success):**
```json
{
  "success": true,
  "session_id": "B3F0F515-B9EC-4CE7-B123-6DDF19FD2CCA",
  "status": "completed",
  "hrv_metrics": {
    "count_rr": 287,
    "mean_rr": 855.93,
    "sdnn": 16.39,
    "rmssd": 4.07,
    "pnn50": 0.0,
    "cv_rr": 1.91,
    "mean_hr": 70.1,
    "defa": 1.23,
    "sd2_sd1": 8.05
  },
  "processed_at": "2025-08-07T16:22:51.456Z"
}
```

**Response (Validation Error):**
```json
{
  "error": "Validation failed",
  "details": {
    "is_valid": false,
    "errors": [
      {
        "field": "rr_intervals",
        "message": "Insufficient RR intervals for analysis",
        "code": "MIN_COUNT_ERROR"
      }
    ],
    "warnings": []
  },
  "message": "Please check the data format and try again"
}
```

#### GET /api/v1/sessions/statistics/{user_id}
Retrieve session statistics aggregated by tag for a specific user.

**Response:**
```json
{
  "processed_total": 31,
  "processed_by_tag": {
    "rest": 8,
    "sleep": 23
  },
  "raw_total": 31,
  "raw_by_tag": {
    "rest": 8,
    "sleep": 23
  },
  "sleep_events": 1
}
```

#### DELETE /api/v1/sessions/{session_id}
Delete a specific session by session ID.

**Response (Success):**
```json
{
  "success": true,
  "session_id": "B3F0F515-B9EC-4CE7-B123-6DDF19FD2CCA",
  "message": "Session deleted successfully"
}
```

**Response (Not Found):**
```json
{
  "error": "Session not found"
}
```

### Trend Analysis Endpoints

**NEW:** Three clinical-grade trend analysis endpoints implementing the unified JSON response schema from polish_architecture.md.

#### GET /api/v1/trends/rest
Analyze non-sleep session trend (RMSSD over time).

**Parameters:**
- `user_id` (required): User ID for trend analysis

**Data Source:** Sessions with tag='rest', event_id=0

**Response:**
```json
{
  "raw": [
    { "date": "2025-08-05", "rmssd": 42.1 },
    { "date": "2025-08-06", "rmssd": 44.3 }
  ],
  "rolling_avg": [
    { "date": "2025-08-06", "rmssd": 43.2 }
  ],
  "percentile_10": 40.0,
  "percentile_90": 49.0
}
```

**Features:**
- Rolling average (trailing N=3) if ≥3 points
- No baseline (non-sleep data)
- No SD bands (non-sleep data)
- Percentiles if ≥30 sessions

#### GET /api/v1/trends/sleep-interval
Analyze sleep intervals trend (all intervals from latest sleep event).

**Parameters:**
- `user_id` (required): User ID for trend analysis

**Data Source:** Sessions with tag='sleep', event_id=latest

**Response:**
```json
{
  "raw": [
    { "date": "2025-08-06", "rmssd": 45.2 },
    { "date": "2025-08-06", "rmssd": 43.8 }
  ],
  "rolling_avg": [
    { "date": "2025-08-06", "rmssd": 44.5 }
  ],
  "baseline": 44.0,
  "sd_band": {
    "upper": 46.0,
    "lower": 42.0
  },
  "percentile_10": 40.0,
  "percentile_90": 49.0
}
```

**Features:**
- Rolling average (trailing N=3)
- Sleep 7-day baseline (computed from all sleep data)
- SD Band: ±1 SD from 7-day baseline
- Percentiles if sufficient data

#### GET /api/v1/trends/sleep-event
Analyze aggregated sleep event trend (one point per sleep event).

**Parameters:**
- `user_id` (required): User ID for trend analysis

**Data Source:** `aggregated_sleep_events` view

**Response:**
```json
{
  "raw": [
    { "date": "2025-08-05", "rmssd": 44.1 },
    { "date": "2025-08-06", "rmssd": 45.3 },
    { "date": "2025-08-07", "rmssd": 43.8 }
  ],
  "rolling_avg": [
    { "date": "2025-08-07", "rmssd": 44.4 }
  ],
  "baseline": 44.2,
  "sd_band": {
    "upper": 45.8,
    "lower": 42.6
  }
}
```

**Features:**
- Rolling average over event means
- Optional 7-event baseline
- SD Band: ±1 SD of event averages
- Percentiles only if ≥30 events

## Trend Analysis Architecture

### TrendAnalyzer Class (`trend_analyzer.py`)

**Core Methods:**
- `analyze_rest_trend()` - Non-sleep session analysis
- `analyze_sleep_interval_trend()` - Latest sleep event intervals
- `analyze_sleep_event_trend()` - Aggregated sleep events

**Statistical Features:**
- Rolling average calculation (trailing N=3)
- Sleep baseline computation (7-day average)
- SD band calculation (±1 standard deviation)
- Percentile analysis (10th/90th percentiles)
- Timezone-aware datetime handling

**Unified JSON Schema:**
All trend endpoints return the same structured format with optional fields based on data availability and trend type.

### Database Views

#### aggregated_sleep_events
```sql
CREATE VIEW aggregated_sleep_events AS
SELECT
  user_id,
  event_id,
  MIN(recorded_at) AS event_start,
  MAX(recorded_at) AS event_end,
  AVG(rmssd) AS avg_rmssd,
  COUNT(*) AS interval_count,
  STDDEV(rmssd) AS rmssd_stddev
FROM sessions
WHERE tag = 'sleep' AND event_id > 0
GROUP BY user_id, event_id;
```

## Data Processing Pipeline

### Session Upload Flow

1. **Request Validation**
   - JSON payload validation
   - Enhanced validation via `session_validator.py`
   - Field type checking and format validation
   - Cross-field relationship validation

2. **Data Cleaning**
   - User ID format validation (Supabase compatible)
   - Session ID UUID validation
   - Tag validation against canonical list
   - RR intervals quality assessment

3. **HRV Calculation**
   - Pure NumPy implementation via `hrv_metrics.py`
   - All 9 metrics calculated: count_rr, mean_rr, sdnn, rmssd, pnn50, cv_rr, mean_hr, defa, sd2_sd1
   - Robust error handling for edge cases

4. **Database Storage**
   - Single transaction insert to sessions table
   - Automatic timestamp generation
   - Connection pool management
   - Commit/rollback error handling

5. **Response Generation**
   - NumPy type conversion for JSON serialization
   - Comprehensive success/error responses
   - Detailed logging for debugging

## Validation System

### Modular Validators

**RequiredFieldValidator:** Ensures all mandatory fields are present  
**UserIdValidator:** Validates Supabase user ID format (flexible UUID)  
**SessionIdValidator:** Validates session ID as strict UUID  
**TagValidator:** Validates against canonical tag list  
**EventIdValidator:** Validates event ID with type conversion  
**RRIntervalsValidator:** Validates RR interval data quality  
**SubtagValidator:** Validates optional subtag field  

### Validation Features

- Comprehensive error reporting with field context
- Warning system for non-critical issues
- Data cleaning and type conversion
- Cross-field relationship validation
- Extensible architecture for future validation rules

## HRV Metrics Implementation

### Calculated Metrics

1. **count_rr** - Total number of RR intervals
2. **mean_rr** - Average RR interval duration (ms)
3. **sdnn** - Standard deviation of all RR intervals (ms)
4. **rmssd** - Root mean square of successive RR differences (ms)
5. **pnn50** - Percentage of RR differences > 50ms (%)
6. **cv_rr** - Coefficient of variation of RR intervals (%)
7. **mean_hr** - Average heart rate (bpm)
8. **defa** - DFA α1 (Detrended Fluctuation Analysis)
9. **sd2_sd1** - Poincaré plot SD2/SD1 ratio

### Implementation Details

- Pure NumPy implementation for performance
- Robust handling of edge cases and invalid data
- Physiological validation of RR intervals
- Standardized calculation methods following HRV analysis best practices

## Database Schema

### Sessions Table Structure

```sql
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    tag VARCHAR(50) NOT NULL,
    subtag VARCHAR(100),
    event_id INTEGER DEFAULT 0,
    duration_minutes INTEGER,
    recorded_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'completed',
    rr_intervals DECIMAL[],
    rr_count INTEGER,
    mean_hr DECIMAL(5,2),
    mean_rr DECIMAL(8,3),
    count_rr INTEGER,
    rmssd DECIMAL(8,3),
    sdnn DECIMAL(8,3),
    pnn50 DECIMAL(5,2),
    cv_rr DECIMAL(5,2),
    defa DECIMAL(8,3),
    sd2_sd1 DECIMAL(8,3)
);
```

## Error Handling

### HTTP Status Codes

- **200** - Success
- **400** - Bad Request (validation errors)
- **404** - Not Found (session not found)
- **405** - Method Not Allowed
- **500** - Internal Server Error

### Error Response Format

```json
{
  "error": "Error type",
  "details": "Detailed error information",
  "message": "User-friendly error message"
}
```

## Production Configuration

### Environment Variables

```
SUPABASE_DB_HOST=db.hmckwsyksbckxfxuzxca.supabase.co
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=[REDACTED]
SUPABASE_DB_PORT=5432
FLASK_ENV=production
```

### Deployment

**Platform:** Railway  
**Runtime:** Python 3.11  
**WSGI Server:** Gunicorn  
**Process Management:** ThreadedConnectionPool  
**Health Checks:** /health endpoint  

### Dependencies

```
Flask==3.0.0
Flask-CORS==4.0.0
psycopg2-binary==2.9.9
numpy==1.26.4
python-dotenv==1.0.0
gunicorn==21.2.0
Werkzeug==3.0.1
setuptools==69.5.1
PyJWT==2.8.0
supabase==2.3.4
matplotlib==3.7.2
seaborn==0.12.2
pandas==2.1.1
```

## Diagnostic Tools

### Available Scripts

**debug_db_connection.py** - Database connectivity testing  
**debug_rls_access.py** - Row Level Security validation  
**diagnose_user_data.py** - User data integrity analysis  
**session_validator.py** - Standalone validation testing  

## Architecture Compliance

### polish_architecture.md Implementation

**✅ Database Design (Section II):**
- Sessions table with event_id grouping ✅
- Required indexes for trend queries ✅
- aggregated_sleep_events view ✅

**✅ API Design (Section III):**
- Three trend endpoints as specified ✅
- Unified JSON response schema ✅
- Backend statistical processing ✅

**✅ Backend Responsibilities:**
- Rolling average (trailing N=3) ✅
- Sleep baseline calculation ✅
- SD band computation ✅
- Percentile analysis ✅
- Graceful fallback for missing data ✅

### Production Features

**Scalability:**
- Optimized database indexes for trend queries
- Connection pooling for concurrent requests
- Efficient aggregated views for complex queries

**Reliability:**
- Comprehensive error handling
- Timezone-aware datetime processing
- Robust data validation and cleaning

**Maintainability:**
- Modular trend analysis architecture
- Clean separation of concerns
- Comprehensive logging and monitoring

## API Versioning

**Current Version:** v1  
**Base Path:** /api/v1  
**Versioning Strategy:** URL path versioning  
**Architecture Version:** polish_architecture.md v1.0

### Endpoint Summary

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/health` | GET | Basic health check | ✅ Active |
| `/health/detailed` | GET | Database connectivity check | ✅ Active |
| `/api/v1/sessions/upload` | POST | Upload and process sessions | ✅ Active |
| `/api/v1/sessions/statistics/{user_id}` | GET | User session statistics | ✅ Active |
| `/api/v1/sessions/{session_id}` | DELETE | Delete session | ✅ Active |
| `/api/v1/trends/rest` | GET | Non-sleep trend analysis | ✅ NEW |
| `/api/v1/trends/sleep-interval` | GET | Sleep interval trend analysis | ✅ NEW |
| `/api/v1/trends/sleep-event` | GET | Sleep event trend analysis | ✅ NEW |

**Total Active Endpoints:** 8  
**Core Processing:** 5 endpoints  
**Trend Analysis:** 3 endpoints  

Future versions will maintain backward compatibility while introducing new HRV metrics (SDNN, pNN50, etc.) using the same unified architecture pattern.
