# HRV Brain System - Final Blueprint

**Version:** 7.0.0 FINAL CLEAN BLUEPRINT  
**Status:** Production Ready  
**Last Updated:** August 2025

This document serves as the **single, authoritative blueprint** for the complete HRV Brain system. All development, deployment, and maintenance must reference only this document.

## 📂 Repository Structure

- **API Repository:** [hrv-brain-api](https://github.com/mirzafarangi/api_hrv) (Branch: `fresh_api`)
- **iOS Repository:** [hrv-brain-ios](https://github.com/mirzafarangi/ios_hrv) (Branch: `fresh_ios`)
- **Production API:** https://hrv-brain-api-production.up.railway.app
- **Database:** PostgreSQL on Supabase with Row Level Security

## 🎯 System Overview

HRV Brain is a comprehensive heart rate variability analysis system consisting of:
- **iOS App:** SwiftUI-based mobile application for HRV session recording and analysis
- **API Backend:** Python Flask API for session processing and trends analysis
- **Database:** PostgreSQL with unified schema for all HRV data and user management
- **Trends Analysis:** Three distinct analysis modes for different HRV insights

## 📊 Trends Analysis - Three Core Scenarios

### 1. Rest Trend Analysis
**Purpose:** Track individual rest session HRV metrics over time  
**Data Source:** All sessions with `tag = 'rest'` and `event_id = 0`  
**Visualization:** Individual data points (RMSSD, SDNN) plotted chronologically  
**Use Case:** Monitor baseline HRV recovery and daily variations  

### 2. Sleep Event Trend Analysis
**Purpose:** Analyze intervals within the most recent sleep event  
**Data Source:** Sessions with `tag = 'sleep'` and `event_id = MAX(event_id)`  
**Visualization:** Sleep intervals (sleep_interval_1, sleep_interval_2, etc.) from latest sleep event  
**Use Case:** Detailed analysis of sleep quality and HRV patterns within a single sleep session  

### 3. Sleep Baseline Trend Analysis
**Purpose:** Track aggregated sleep event performance over time  
**Data Source:** All sleep events grouped by `event_id`, aggregated per event  
**Visualization:** Each point represents averaged HRV metrics for an entire sleep event  
**Use Case:** Long-term sleep quality trends and event-to-event comparisons  

### Event ID Logic
- **`event_id = 0`:** No grouping (rest, experiment sessions, breath workouts)
- **`event_id > 0`:** Grouped sessions (sleep intervals within the same sleep event)

## 🗄️ Database Schema

### Core Tables

#### `public.profiles`
Extends Supabase auth.users with HRV-specific profile data.

```sql
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    full_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### `public.sessions`
Unified table storing both raw RR intervals and processed HRV metrics.

```sql
CREATE TABLE public.sessions (
    -- Core identifiers
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Session metadata
    tag VARCHAR(50) NOT NULL,           -- rest, sleep, experiment_*, breath_workout
    subtag VARCHAR(100) NOT NULL,       -- rest_single, sleep_interval_1, etc.
    event_id INTEGER NOT NULL DEFAULT 0, -- 0 = no grouping, >0 = grouped
    
    -- Timing
    duration_minutes INTEGER NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Raw data
    rr_intervals DECIMAL[] NOT NULL,    -- Array of RR intervals in milliseconds
    rr_count INTEGER NOT NULL,
    
    -- Processing status
    status VARCHAR(20) DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'completed', 'failed')),
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- HRV Metrics (9 individual columns)
    mean_hr NUMERIC(6,2),      -- Average heart rate (BPM)
    mean_rr NUMERIC(8,2),      -- Average RR interval (ms)
    count_rr INTEGER,          -- Count of RR intervals
    rmssd NUMERIC(8,2),        -- Root Mean Square of Successive Differences (ms)
    sdnn NUMERIC(8,2),         -- Standard Deviation of NN intervals (ms)
    pnn50 NUMERIC(5,2),        -- Percentage of successive RR intervals > 50ms (%)
    cv_rr NUMERIC(5,2),        -- Coefficient of Variation of RR intervals (%)
    defa NUMERIC(8,4),         -- Detrended Fluctuation Analysis Alpha1
    sd2_sd1 NUMERIC(8,4)       -- Poincaré plot SD2/SD1 ratio
);
```

### Canonical Tag System
- **rest** → `rest_single` (event_id: 0)
- **sleep** → `sleep_interval_1`, `sleep_interval_2`, etc. (event_id: >0, grouped)
- **experiment_paired_pre** → `experiment_paired_pre_single` (event_id: 0)
- **experiment_paired_post** → `experiment_paired_post_single` (event_id: 0)
- **experiment_duration** → `experiment_duration_single` (event_id: 0)
- **breath_workout** → `breath_phase_1`, `breath_phase_2`, etc. (event_id: >0, grouped)

### Performance Indexes

```sql
-- Rest Trend: All sessions with tag='rest'
CREATE INDEX idx_rest_trend 
ON sessions(user_id, recorded_at DESC, rmssd, sdnn) WHERE tag = 'rest';

-- Sleep Baseline: Aggregation by event_id
CREATE INDEX idx_sleep_baseline 
ON sessions(user_id, event_id, rmssd, sdnn) WHERE tag = 'sleep' AND event_id > 0;

-- Sleep Event: Last event intervals
CREATE INDEX idx_sleep_event_intervals 
ON sessions(user_id, event_id, recorded_at, rmssd, sdnn, subtag) WHERE tag = 'sleep' AND event_id > 0;

-- Helper: Find latest sleep event_id quickly
CREATE INDEX idx_latest_sleep_event 
ON sessions(user_id, event_id DESC) WHERE tag = 'sleep' AND event_id > 0;
```

## 🚀 API Architecture

**Production URL:** https://hrv-brain-api-production.up.railway.app  
**Framework:** Flask + PostgreSQL (Supabase)  
**Deployment:** Railway with auto-deploy from GitHub  
**Authentication:** Supabase JWT + Row Level Security  

### Core Endpoints

#### Session Management
```
POST /api/v1/sessions/upload          - Upload and process HRV session
GET  /api/v1/sessions/status/{id}     - Get session processing status
GET  /api/v1/sessions/processed/{uid} - Get user's processed sessions
GET  /api/v1/sessions/statistics/{uid} - Get user session statistics
DELETE /api/v1/sessions/{id}          - Delete session
```

#### Trends Analysis
```
POST /api/v1/trends/refresh           - Generate all three trend types
```

**Request:**
```json
{
  "user_id": "user-uuid-here"
}
```

**Response:**
```json
{
  "rest_trend": {
    "data": [...],
    "count": 5,
    "description": "Individual rest sessions (tag=rest, event_id=0)"
  },
  "sleep_event": {
    "data": [...],
    "count": 4,
    "latest_event_id": 1007,
    "description": "Latest sleep event intervals (tag=sleep, event_id=1007)"
  },
  "sleep_baseline": {
    "data": [...],
    "count": 7,
    "description": "Aggregated sleep events (tag=sleep, grouped by event_id)"
  },
  "generated_at": "2025-08-07T00:00:00Z",
  "user_id": "user-uuid-here"
}
```

#### Health & System
```
GET  /health                          - Basic health check
GET  /health/detailed                 - Detailed system status
```

## 📱 iOS Architecture

**Framework:** SwiftUI + Supabase Swift SDK  
**Pattern:** MVVM with ObservableObject managers  
**Authentication:** HTTP-based SupabaseAuthService  
**Database:** Direct PostgREST queries via Supabase SDK  

### App Structure
```
ios_hrv/
├── Core/                    # Core engine and business logic
├── Managers/               # Data managers (HRVNetworkManager, TrendsManager)
├── Models/                 # Data models (Session, TrendsModels, etc.)
├── UI/
│   ├── Tabs/              # Main tab views (Record, Sessions, Trends, Profile)
│   ├── Components/        # Reusable UI components
│   └── MainContentView.swift
└── Utilities/             # Helper utilities
```

### Key Features
- **Centralized Networking:** HRVNetworkManager with caching and rate limiting
- **Persistent Cache:** UserDefaults-based plot data storage
- **Three-Card Trends UI:** Clean, minimal design with SwiftUI Charts
- **1-Minute Fetch Cooldown:** Rate limiting with proper UX feedback
- **Direct DB Access:** Sessions tab uses Supabase SDK for real-time data

## 🔄 Data Flow

### Session Recording Flow
```
iOS Record Tab → CoreEngine → Supabase Database → Sessions Tab (real-time)
```

### Trends Analysis Flow
```
iOS Trends Tab → HRVNetworkManager → API /trends/refresh → Database Queries → JSON Response → SwiftUI Charts
```

### Authentication Flow
```
iOS Auth → SupabaseAuthService → Supabase Auth → JWT Token → Row Level Security
```

## 🛠️ Deployment

### Database (Supabase)
1. Deploy `database_schema.sql` to create all tables, indexes, and policies
2. Configure Row Level Security for user data isolation
3. Set up connection pooling for API access

### API (Railway)
1. Connect GitHub repository (fresh_api branch)
2. Configure environment variables:
   ```
   SUPABASE_DB_HOST=db.xxx.supabase.co
   SUPABASE_DB_NAME=postgres
   SUPABASE_DB_USER=postgres
   SUPABASE_DB_PASSWORD=xxx
   SUPABASE_DB_PORT=5432
   FLASK_ENV=production
   ```
3. Auto-deploy enabled from GitHub pushes

### iOS App
1. Configure Supabase credentials in SupabaseConfig.swift
2. Build and deploy via Xcode/TestFlight
3. Ensure API URL points to production Railway deployment

## 🧪 Testing

### API Testing
```bash
# Health check
curl https://hrv-brain-api-production.up.railway.app/health

# Trends analysis (requires valid user_id)
curl -X POST https://hrv-brain-api-production.up.railway.app/api/v1/trends/refresh \
  -H "Content-Type: application/json" \
  -d '{"user_id": "valid-user-uuid"}'
```

### iOS Testing
1. Record sessions using Record tab
2. Verify data appears in Sessions tab
3. Test Trends tab with three-card layout
4. Validate caching and rate limiting behavior

---

**This blueprint represents the complete, production-ready HRV Brain system architecture. All implementation details are available in the respective GitHub repositories.**
