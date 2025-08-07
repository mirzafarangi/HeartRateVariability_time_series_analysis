# HRV Brain API Schema Documentation

**Version:** 4.0.0 Fresh Start  
**Date:** 2025-08-07  
**Status:** Production Ready  
**Branch:** fresh_polish_api  

## Overview

Clean, minimal API implementation focused exclusively on core HRV session processing. All charting and visualization functionality has been removed to establish a clean foundation for future clinical-grade implementations.

## Architecture

### Core Components

**Primary Application:** `app.py` (12.8KB)
- Flask web application with CORS enabled
- PostgreSQL connection pooling via psycopg2
- Comprehensive error handling and logging
- Production-ready with Gunicorn WSGI server

**Dependencies:**
- `database_config.py` - Database connection management and configuration
- `hrv_metrics.py` - Pure NumPy implementation of 9 HRV metrics
- `session_validator.py` - Modular validation system with enhanced error reporting

### Database Integration

**Database:** PostgreSQL via Supabase  
**Connection:** ThreadedConnectionPool for production scalability  
**Schema:** Unified sessions table with 9 HRV metric columns  
**Authentication:** Environment variable based configuration  

## API Endpoints

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

## Removed Functionality

The following components have been completely removed in this clean version:

- All plot generation endpoints and logic
- Chart rendering and visualization code
- Trend analysis and statistical plotting
- Image generation and storage
- Batch processing endpoints
- Plot storage database tables

This creates a clean foundation focused exclusively on core session processing, ready for future clinical-grade charting implementations with centralized architecture.

## API Versioning

**Current Version:** v1  
**Base Path:** /api/v1  
**Versioning Strategy:** URL path versioning  

Future versions will maintain backward compatibility while introducing new features in a structured, maintainable manner.
