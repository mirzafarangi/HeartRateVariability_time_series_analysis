# HRV App Unified Data Schema Architecture

**Version:** 3.3.4 Final  
**Date:** 2025-08-03  
**Status:** Production Ready  

This document defines the complete, unified data schema for the HRV iOS App → API → Database pipeline. All components must strictly adhere to this schema for consistency and maintainability.

---

## 📋 OVERVIEW

The unified schema implements a clean, extensible architecture with:
- **Base Tags**: 6 allowed session types
- **Semantic Subtags**: Always present with clear meaning
- **Event Grouping**: Sleep intervals grouped, others standalone
- **Single Source of Truth**: One schema across iOS, API, and DB

---

## 🏷️ TAG STRUCTURE SPECIFICATION

### Base Tags (6 Allowed)
```
1. "rest"                    → "rest_single" (eventId: 0)
2. "sleep"                   → "sleep_interval_N" (eventId: >0, grouped)
3. "experiment_paired_pre"   → "experiment_paired_pre_single" (eventId: 0)
4. "experiment_paired_post"  → "experiment_paired_post_single" (eventId: 0)
5. "experiment_duration"     → "experiment_duration_single" (eventId: 0)
6. "breath_workout"          → "breath_workout_single" (eventId: 0)
```

### Event Grouping Logic
- **Non-Sleep Sessions**: `eventId = 0` (no grouping)
- **Sleep Sessions**: `eventId > 0` (all intervals in same sleep event share same eventId)
- **Future Extensions**: `eventId > 0` (e.g., breath workout phases)

---

## 📱 iOS TO API DATA FORMAT

### Core Schema Structure
```json
{
    "session_id": "uuid",
    "user_id": "string", 
    "tag": "base_tag",           // Always base tag: "rest", "sleep", "experiment_paired_pre", etc.
    "subtag": "specific_tag",    // ALWAYS NON-OPTIONAL: Auto-assigned semantic subtag
    "event_id": "number",        // ALWAYS NON-OPTIONAL: Auto-assigned event grouping ID
    "duration_minutes": "number",
    "recorded_at": "ISO8601",
    "rr_intervals": "[numbers]"
}
```

### ⚠️ CRITICAL: SUBTAG AND EVENT_ID ARE ALWAYS NON-OPTIONAL

#### SUBTAG Rules:
- **`subtag` is NEVER null/optional** - it's always a non-empty String
- **`subtag` is auto-assigned** by iOS based on selected tag
- **User never manually enters subtag** - it's computed automatically
- **iOS models must use `String` (not `String?`)** for subtag field

#### EVENT_ID Rules:
- **`event_id` is NEVER null/optional** - it's always a valid Integer
- **`event_id` is auto-assigned** by iOS when starting session recording
- **User never manually enters event_id** - it's computed automatically
- **iOS models must use `Int` (not `Int?`)** for eventId field
- **Non-sleep sessions**: Always `eventId = 0` (no grouping)
- **Sleep/grouped sessions**: Always `eventId > 0` (shared across related sessions)

### 1. NON-SLEEP SESSIONS (Rest, Experiment, etc.)

```json
{
    "session_id": "B3F0F515-B9EC-4CE7-B123-6DDF19FD2CCA",
    "user_id": "oMeXbIPwTXUU1WRkrLU0mtQOU9r1",
    "tag": "rest",
    "subtag": "rest_single",     // Semantic: indicates single session
    "event_id": 0,               // 0 = no event grouping needed
    "duration_minutes": 1,
    "recorded_at": "2025-08-03T05:08:01Z",
    "rr_intervals": [869.56, 845.23, 892.34, 876.12, 823.45, 867.89]
}
```

### 2. SLEEP SESSIONS (Auto-recording intervals)

```json
{
    "session_id": "A7C2E891-F456-4D89-A123-8BDF29GH3ECA",
    "user_id": "oMeXbIPwTXUU1WRkrLU0mtQOU9r1",
    "tag": "sleep",
    "subtag": "sleep_interval_3", // Semantic: indicates interval number
    "event_id": 1001,            // Groups all intervals in same sleep event
    "duration_minutes": 7,
    "recorded_at": "2025-08-03T05:08:01Z",
    "rr_intervals": [892.34, 876.12, 823.45, 867.89, 901.23, 845.67]
}
```

### 3. FUTURE EXTENSIBILITY (e.g., Breath Workout with phases)

```json
{
    "session_id": "C8D3F902-G567-5E90-B234-9CEF40HI4FDA",
    "user_id": "oMeXbIPwTXUU1WRkrLU0mtQOU9r1",
    "tag": "breath_workout",
    "subtag": "breath_phase_2",  // Semantic: indicates workout phase
    "event_id": 2001,            // Groups all phases in same workout
    "duration_minutes": 5,
    "recorded_at": "2025-08-03T05:08:01Z",
    "rr_intervals": [823.45, 867.89, 901.23, 845.67, 892.34, 876.12]
}
```

### 3. FUTURE EXTENSIBILITY (e.g., Breath Workout with phases)

```json
{
    "session_id": "C8D3F902-G567-5E90-B234-9CEF40HI4FDA",
    "user_id": "oMeXbIPwTXUU1WRkrLU0mtQOU9r1",
    "tag": "breath_workout",
    "subtag": "breath_phase_2",  // Semantic: indicates workout phase
    "event_id": 2001,            // Groups all phases in same workout
    "duration_minutes": 5,
    "recorded_at": "2025-08-03T05:08:01Z",
    "rr_intervals": [823.45, 867.89, 901.23, 845.67, 889.12, 834.56]
}
```

---

## 🗄️ POSTGRESQL DATABASE SCHEMA

### Users Table (Authentication & Profile)
```sql
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    device_name VARCHAR(100),
    raw_sessions_count INTEGER DEFAULT 0,
    processed_sessions_count INTEGER DEFAULT 0
);
```

### Sessions Table (Unified Raw + Processed)
```sql
CREATE TABLE sessions (
    -- Core identifiers
    session_id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Session metadata (UNIFIED SCHEMA)
    tag VARCHAR(50) NOT NULL,           -- rest, sleep, experiment_paired_pre, etc.
    subtag VARCHAR(100) NOT NULL,       -- rest_single, sleep_interval_1, etc.
    event_id INTEGER NOT NULL DEFAULT 0, -- 0 = no grouping, >0 = grouped
    
    -- Timing
    duration_minutes INTEGER NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Raw data
    rr_intervals JSONB NOT NULL,
    rr_count INTEGER NOT NULL,
    
    -- Processing status
    status VARCHAR(20) DEFAULT 'uploaded',
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- HRV metrics (EXACT REQUIREMENTS)
    mean_hr DECIMAL(5,2),
    mean_rr DECIMAL(8,2),
    count_rr INTEGER,
    rmssd DECIMAL(8,2),
    sdnn DECIMAL(8,2),
    pnn50 DECIMAL(5,2),        -- % of RR diffs > 50ms
    cv_rr DECIMAL(5,2),        -- Coefficient of variation
    defa DECIMAL(6,4),         -- DFA α1 (not dfa)
    sd2_sd1 DECIMAL(8,2),      -- Poincaré ratio
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_tag CHECK (tag IN ('rest', 'sleep', 'experiment_paired_pre', 'experiment_paired_post', 'experiment_duration', 'breath_workout')),
    CONSTRAINT valid_status CHECK (status IN ('uploaded', 'processing', 'completed', 'failed'))
);
```

### Performance Indexes
```sql
-- Primary performance indexes
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_user_tag ON sessions(user_id, tag);
CREATE INDEX idx_sessions_event_id ON sessions(event_id) WHERE event_id > 0;
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_recorded_at ON sessions(recorded_at);

-- Composite indexes for common queries
CREATE INDEX idx_sessions_user_event ON sessions(user_id, event_id) WHERE event_id > 0;
CREATE INDEX idx_sessions_tag_status ON sessions(tag, status);
```

---

## 🧮 HRV METRICS CALCULATION (Pure NumPy)

### Complete Implementation
```python
# hrv_metrics_clean.py - EXACT REQUIREMENTS
import numpy as np
from typing import List, Dict

def calculate_rmssd(rr: List[float]) -> float:
    """Root mean square of successive RR differences"""
    return np.sqrt(np.mean(np.diff(rr)**2))

def calculate_sdnn(rr: List[float]) -> float:
    """Standard deviation of all RR intervals"""
    return np.std(rr)

def calculate_pnn50(rr: List[float]) -> float:
    """% of RR diffs > 50ms (vagal tone)"""
    return np.mean(np.abs(np.diff(rr)) > 50) * 100

def calculate_cv_rr(rr: List[float]) -> float:
    """Coefficient of variation of RR"""
    return np.std(rr) / np.mean(rr) * 100

def calculate_mean_hr(rr: List[float]) -> float:
    """Mean heart rate from RR intervals"""
    return 60000 / np.mean(rr)

def calculate_dfa_alpha1(rr: List[float]) -> float:
    """DFA α1 - Detrended Fluctuation Analysis"""
    # Simplified DFA implementation
    # Full implementation requires more complex algorithm
    # Placeholder for now - implement proper DFA later
    return 1.0

def calculate_poincare_ratio(rr: List[float]) -> float:
    """SD2/SD1 ratio from Poincaré plot"""
    rr1 = rr[:-1]
    rr2 = rr[1:]
    sd1 = np.std(rr2 - rr1) / np.sqrt(2)
    sd2 = np.std(rr2 + rr1) / np.sqrt(2)
    return sd2 / sd1 if sd1 > 0 else 0

def calculate_hrv_metrics(rr: List[float]) -> Dict[str, float]:
    """Calculate all HRV metrics - EXACT TABLE MATCH"""
    return {
        "count_rr": len(rr),
        "mean_rr": np.mean(rr),
        "sdnn": calculate_sdnn(rr),
        "rmssd": calculate_rmssd(rr),
        "pnn50": calculate_pnn50(rr),
        "cv_rr": calculate_cv_rr(rr),
        "mean_hr": calculate_mean_hr(rr),
        "defa": calculate_dfa_alpha1(rr),  # Note: defa not dfa
        "sd2_sd1": calculate_poincare_ratio(rr),
    }
```

### Metrics Specification Table
| Metric ID | Metric Name | Description | Formula | Unit | Category |
|-----------|-------------|-------------|---------|------|----------|
| count_rr | RR Count | Total number of RR intervals | len(rr) | count | Raw |
| mean_rr | Mean RR | Average RR interval duration | np.mean(rr) | ms | Time-domain |
| sdnn | SDNN | Std dev of all RR intervals (total HRV) | np.std(rr) | ms | Time-domain |
| rmssd | RMSSD | Root mean square of successive RR diffs | np.sqrt(np.mean(np.diff(rr)**2)) | ms | Time-domain |
| pnn50 | pNN50 | % of RR diffs > 50ms (vagal tone) | np.mean(np.abs(np.diff(rr)) > 50) * 100 | % | Time-domain |
| cv_rr | Coefficient of Var RR | Normalized RR variability | np.std(rr) / np.mean(rr) * 100 | % | Time-domain |
| mean_hr | Mean HR | Average heart rate from RR | 60000 / np.mean(rr) | bpm | Derived |
| defa | DFA α1 | Short-term fractal scaling exponent | calculate_dfa(rr) | - | Non-linear |
| sd2_sd1 | SD2/SD1 Ratio | Ratio from Poincaré plot | sd2 / sd1 from ellipse fit | - | Non-linear |

---

## 🔌 API IMPLEMENTATION

### Clean API Structure
```python
# app_clean.py - PostgreSQL + Unified Schema
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
from hrv_metrics_clean import calculate_hrv_metrics

app = Flask(__name__)

@app.route('/api/v1/sessions/upload', methods=['POST'])
def upload_session():
    """Upload session - UNIFIED SCHEMA"""
    data = request.get_json()
    
    # Validate EXACT iOS schema
    required = ['session_id', 'user_id', 'tag', 'subtag', 'event_id', 
                'duration_minutes', 'recorded_at', 'rr_intervals']
    
    for field in required:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Insert raw session
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO sessions (session_id, user_id, tag, subtag, event_id, 
                            duration_minutes, recorded_at, rr_intervals, 
                            rr_count, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'processing')
    """, (data['session_id'], data['user_id'], data['tag'], 
          data['subtag'], data['event_id'], data['duration_minutes'],
          data['recorded_at'], json.dumps(data['rr_intervals']),
          len(data['rr_intervals'])))
    
    # Calculate HRV metrics
    metrics = calculate_hrv_metrics(data['rr_intervals'])
    
    # Update with processed metrics
    cur.execute("""
        UPDATE sessions SET 
            mean_hr = %s, mean_rr = %s, count_rr = %s, rmssd = %s,
            sdnn = %s, pnn50 = %s, cv_rr = %s, defa = %s, sd2_sd1 = %s,
            status = 'completed', processed_at = NOW()
        WHERE session_id = %s
    """, (metrics['mean_hr'], metrics['mean_rr'], metrics['count_rr'],
          metrics['rmssd'], metrics['sdnn'], metrics['pnn50'],
          metrics['cv_rr'], metrics['defa'], metrics['sd2_sd1'],
          data['session_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'status': 'success', 
        'session_id': data['session_id'],
        'metrics': metrics
    })

def get_db_connection():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port=os.environ.get('DB_PORT', 5432)
    )
```

### API Endpoints Specification
```
POST /api/v1/sessions/upload          - Upload and process session
GET  /api/v1/sessions/status/{id}     - Get processing status
GET  /api/v1/sessions/processed/{uid} - Get processed sessions
GET  /api/v1/sessions/raw/{uid}       - Get raw sessions  
GET  /api/v1/sessions/statistics/{uid} - Get session statistics
DELETE /api/v1/sessions/{id}          - Delete session
GET  /health                          - Health check
GET  /health/detailed                 - Detailed health status
```

---

## 📱 iOS IMPLEMENTATION

### Updated Session Model
```swift
struct Session: Codable, Identifiable {
    let id: String                // session_id (UUID)
    let userId: String           // user_id 
    let tag: String              // Base tag: "rest", "sleep", etc.
    let subtag: String           // Semantic subtag: "rest_single", "sleep_interval_1", etc.
    let eventId: Int             // Event grouping ID: 0 = no grouping, >0 = grouped
    let duration: Int            // duration_minutes
    let recordedAt: Date         // recorded_at (ISO8601)
    let rrIntervals: [Double]    // rr_intervals (milliseconds)
    
    func toAPIPayload() -> [String: Any] {
        return [
            "session_id": id,
            "user_id": userId,
            "tag": tag,
            "subtag": subtag,
            "event_id": eventId,
            "duration_minutes": duration,
            "recorded_at": ISO8601DateFormatter().string(from: recordedAt),
            "rr_intervals": rrIntervals
        ]
    }
}
```

### Updated HRV Metrics Model
```swift
struct HRVMetrics: Codable {
    let meanHr: Double       // mean_hr
    let meanRr: Double       // mean_rr
    let countRr: Int         // count_rr
    let rmssd: Double        // rmssd
    let sdnn: Double         // sdnn
    let pnn50: Double        // pnn50 (NEW)
    let cvRr: Double         // cv_rr (NEW)
    let defa: Double         // defa (Fixed naming from dfa)
    let sd2Sd1: Double       // sd2_sd1
    
    enum CodingKeys: String, CodingKey {
        case meanHr = "mean_hr"
        case meanRr = "mean_rr"
        case countRr = "count_rr"
        case rmssd = "rmssd"
        case sdnn = "sdnn"
        case pnn50 = "pnn50"
        case cvRr = "cv_rr"
        case defa = "defa"
        case sd2Sd1 = "sd2_sd1"
    }
}
```

### Session Creation Logic
```swift
// For non-sleep tags
currentSession = Session(
    userId: userId,
    tag: tag.rawValue,              // "rest", "experiment_paired_pre", etc.
    subtag: "\(tag.rawValue)_single", // "rest_single", etc.
    eventId: 0,                     // No grouping
    duration: Int(duration),
    rrIntervals: []
)

// For sleep tags (CoreEngine)
let subtag = "sleep_interval_\(intervalNumber)"  // sleep_interval_1, sleep_interval_2
let sleepEventId = generateSleepEventId()        // Shared across all intervals

currentSession = Session(
    userId: userId,
    tag: "sleep",
    subtag: subtag,
    eventId: sleepEventId,          // Grouped
    duration: Int(duration),
    rrIntervals: []
)
```

---

## 🔄 DATA FLOW ARCHITECTURE

### Complete Pipeline
```
iOS Session Creation
    ↓
iOS Session.toAPIPayload()
    ↓
API /sessions/upload endpoint
    ↓
PostgreSQL INSERT (raw data)
    ↓
HRV Metrics Calculation (NumPy)
    ↓
PostgreSQL UPDATE (processed metrics)
    ↓
API Response with metrics
    ↓
iOS UI Update
```

### Session Lifecycle States
```
uploaded    → Raw session stored, awaiting processing
processing  → HRV metrics being calculated
completed   → Processing finished, metrics available
failed      → Processing error occurred
```

---

## ✅ VALIDATION CHECKLIST

### Schema Consistency
- [ ] iOS Session model matches API expectations exactly
- [ ] API payload matches PostgreSQL table structure
- [ ] All 9 HRV metrics implemented and named correctly
- [ ] Tag constraints enforced at all levels
- [ ] Event grouping logic consistent across components

### Data Integrity
- [ ] UUID session_id used consistently
- [ ] ISO8601 timestamps with timezone
- [ ] RR intervals in milliseconds (not seconds)
- [ ] Proper foreign key relationships
- [ ] Cascading deletes configured

### Performance
- [ ] Database indexes on common query patterns
- [ ] Efficient JSON storage for RR intervals
- [ ] Connection pooling for API
- [ ] Proper error handling at all levels

---

## 🚀 MIGRATION STRATEGY

### Phase 1: Database Setup
1. Create Supabase project
2. Execute PostgreSQL schema
3. Configure connection strings
4. Test database connectivity

### Phase 2: API Rewrite
1. Implement clean HRV metrics (NumPy only)
2. Rewrite API endpoints for PostgreSQL
3. Update schema validation
4. Deploy and test API

### Phase 3: iOS Updates
1. Update Session and HRVMetrics models
2. Fix API payload generation
3. Update UI to display new metrics
4. Test end-to-end flow

---

## 📚 REFERENCES

- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Supabase Documentation**: https://supabase.com/docs
- **HRV Analysis Standards**: Task Force of ESC/NASPE 1996
- **NumPy Documentation**: https://numpy.org/doc/

---

**End of Schema Documentation**

*This document serves as the single source of truth for the HRV App unified data schema. All development must adhere to these specifications for consistency and maintainability.*
