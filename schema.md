# HRV App Unified Data Schema Architecture

> **CRITICAL**: This document serves as the canonical blueprint for rebuilding the entire HRV system. All architectural decisions, data models, and integration patterns are documented here.

## **DATABASE SCHEMA**

**⚠️ IMPORTANT:** The complete, production-ready database schema is now consolidated in:

📄 **`database_schema_final.sql`** - Single Source of Truth

This file includes:
- All table definitions (profiles, sessions)
- Individual HRV metric columns (mean_hr, mean_rr, count_rr, rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1)
- Database functions (get_user_session_statistics, get_recent_user_sessions)
- Performance indexes and constraints
- Row Level Security (RLS) policies
- Triggers and automation
- Complete permissions and documentation

**For new deployments:** Use `database_schema_final.sql` only. All previous patch files (migrate_schema.sql, add_missing_functions.sql, fix_function_ambiguity.sql) are now obsolete.

---

## **OVERVIEW**

The unified schema implements a clean, extensible architecture with:
- **Base Tags**: 6 allowed session types
- **Semantic Subtags**: Always present with clear meaning
- **Event Grouping**: Sleep intervals grouped, others standalone
- **Single Source of Truth**: One schema across iOS, API, and DB

---

## **TAG STRUCTURE SPECIFICATION**

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

### **iOS Recording Workflow Implementation**

#### **Recording Mode Differentiation**
The iOS app implements two distinct recording modes based on the selected tag:

**1. Single Recording Mode (Non-Sleep Tags)**
- **Triggers**: `rest`, `experiment_paired_pre`, `experiment_paired_post`, `experiment_duration`, `breath_workout`
- **Behavior**: Timer-based recording for selected duration X minutes
  - **Auto-Stop**: Session automatically ends when timer countdown reaches zero
  - **Manual Stop**: User can stop early, but only complete recorded data is processed
- **UI**: "Start Recording" button
- **Session Creation**: 
  - `eventId = 0` (no grouping)
  - `subtag = "{tag}_single"` (e.g., "rest_single")
  - Duration determined by user selection (1-60 minutes)

**2. Auto-Recording Mode (Sleep Tag)**
- **Triggers**: `sleep` tag selection
- **Behavior**: Continuous automatic interval recording
  - **Auto-Progression**: Each interval records for selected duration X minutes, then automatically starts next interval
  - **Sequence**: `sleep_interval_1` → `sleep_interval_2` → `sleep_interval_3` → ... (continuous)
  - **Manual Stop**: User can stop entire sleep event at any time, processing all completed intervals
- **UI**: "Start Auto-Recording Sleep Event" button → "Stop Auto-Recording" button
- **Session Creation**:
  - `eventId > 0` (grouped sessions, starts from 1001)
  - `subtag = "sleep_interval_N"` (e.g., "sleep_interval_1", "sleep_interval_2")
  - Each interval has same duration as configured

#### **Recording Configuration Flow**
```swift
// User selects tag and duration in ConfigCard
func updateRecordingConfiguration(tag: SessionTag, duration: Int) {
    coreState.selectedTag = tag
    coreState.selectedDuration = duration
    
    if tag.isAutoRecordingMode { // Sleep tag
        let sleepEventId = coreState.nextSleepEventId // Auto-increment from 1001
        coreState.recordingMode = .autoRecording(
            sleepEventId: sleepEventId, 
            intervalDuration: duration, 
            currentInterval: 1
        )
    } else { // Non-sleep tags
        coreState.recordingMode = .single(tag: tag, duration: duration)
    }
}
```

#### **Session Recording and Tagging Logic**

**Single Recording Example (Rest Tag):**
```swift
// User presses "Start Recording" in RecordingCard
func startSingleRecording(tag: SessionTag, duration: Int) {
    recordingManager.startRecording(
        tag: tag,                    // .rest, .experiment_paired_pre, etc.
        duration: TimeInterval(duration * 60), // Convert minutes to seconds
        heartRatePublisher: bleManager.heartRatePublisher,
        subtag: nil,                 // Auto-assigned as "{tag}_single"
        sleepEventId: nil            // No grouping for single sessions
    )
    
    // RecordingManager automatically:
    // 1. Creates timer for specified duration
    // 2. Auto-stops when timer expires
    // 3. Processes only complete recorded data if manually stopped early
}
```

**Auto-Recording Example (Sleep Tag):**
```swift
// User presses "Start Auto-Recording Sleep Event" in RecordingCard
func startSleepIntervalRecording(sleepEventId: Int, intervalDuration: Int, intervalNumber: Int) {
    let subtag = "sleep_interval_\(intervalNumber)" // Auto-generated
    
    recordingManager.startRecording(
        tag: .sleep,
        duration: TimeInterval(intervalDuration * 60), // Convert minutes to seconds
        heartRatePublisher: bleManager.heartRatePublisher,
        subtag: subtag,              // "sleep_interval_1", "sleep_interval_2", etc.
        sleepEventId: sleepEventId   // Groups all intervals (1001, 1002, etc.)
    )
}

// Auto-continuation logic in CoreEngine.onRecordingCompleted()
func onRecordingCompleted() {
    switch coreState.recordingMode {
    case .single:
        // Single recording completed - session processed and queued
        break
        
    case .autoRecording(let sleepEventId, let intervalDuration, let currentInterval):
        // Sleep interval completed - automatically start next interval
        let nextInterval = currentInterval + 1
        coreState.recordingMode = .autoRecording(
            sleepEventId: sleepEventId, 
            intervalDuration: intervalDuration, 
            currentInterval: nextInterval
        )
        
        // Auto-start next interval after 1 second delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            if self.coreState.isInAutoRecordingMode {
                self.startSleepIntervalRecording(
                    sleepEventId: sleepEventId, 
                    intervalDuration: intervalDuration, 
                    intervalNumber: nextInterval
                )
            }
        }
    }
}
```

#### **Sleep Event Management**
```swift
struct SleepEvent {
    let id: Int              // 1001, 1002, 1003...
    var intervalCount: Int   // Number of completed intervals
    var isActive: Bool       // Currently recording intervals
    
    // Sleep events auto-increment: first = 1001, second = 1002, etc.
    static func nextEventId(from history: [SleepEvent]) -> Int {
        let maxId = history.map { $0.id }.max() ?? 1000
        return maxId + 1
    }
}
```

#### **RecordingManager Timer Implementation**
```swift
class RecordingManager: ObservableObject {
    @Published var isRecording: Bool = false
    @Published var recordingProgress: Double = 0.0 // 0.0 to 1.0
    @Published var remainingTime: Int = 0 // seconds remaining
    @Published var elapsedTime: Int = 0 // seconds elapsed
    
    private var recordingTimer: Timer?
    private var progressTimer: Timer?
    
    func startRecording(tag: SessionTag, duration: TimeInterval, heartRatePublisher: AnyPublisher<Int, Never>, subtag: String? = nil, sleepEventId: Int? = nil) {
        // Create session with auto-assigned subtag and eventId
        currentSession = Session(
            userId: userId,
            tag: tag.rawValue,
            subtag: subtag ?? "\(tag.rawValue)_single", // Auto-assign if not provided
            eventId: sleepEventId ?? 0, // 0 for single sessions, >0 for grouped
            duration: Int(duration / 60), // Convert seconds to minutes
            rrIntervals: []
        )
        
        setupRecordingTimer(duration: Int(duration / 60))
        startHeartRateCollection(heartRatePublisher)
    }
    
    private func setupRecordingTimer(duration: Int) {
        let totalSeconds = duration * 60
        remainingTime = totalSeconds
        elapsedTime = 0
        recordingProgress = 0.0
        
        // Main timer - AUTO-STOPS recording when duration expires
        recordingTimer = Timer.scheduledTimer(withTimeInterval: TimeInterval(totalSeconds), repeats: false) { [weak self] _ in
            Task { @MainActor in
                self?.stopRecording() // Automatic stop when timer expires
            }
        }
        
        // Progress timer - updates UI every second
        progressTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.updateProgress()
            }
        }
    }
    
    func stopRecording() {
        // Can be called by:
        // 1. Timer expiration (automatic)
        // 2. User manual stop (early termination)
        // 3. Auto-recording stop (ends entire sleep event)
        
        recordingTimer?.invalidate()
        progressTimer?.invalidate()
        
        // Process only the data that was actually recorded
        if heartRateData.count >= 10 { // Minimum data threshold
            let completedSession = Session(
                id: currentSession?.id ?? UUID().uuidString,
                userId: currentSession?.userId ?? "",
                tag: currentSession?.tag ?? "",
                subtag: currentSession?.subtag ?? "",
                eventId: currentSession?.eventId ?? 0,
                duration: currentSession?.duration ?? 0,
                rrIntervals: heartRateData, // Only recorded data
                recordedAt: recordingStartTime ?? Date()
            )
            
            // Emit completion event
            CoreEvents.shared.emit(.recordingCompleted(session: completedSession))
            
            // Queue for API processing
            CoreEngine.shared.processCompletedSession(completedSession)
        }
        
        // Reset state
        isRecording = false
        currentSession = nil
        heartRateData = []
    }
}
```

---

## **iOS TO API DATA FORMAT**

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

### **CRITICAL: SUBTAG AND EVENT_ID ARE ALWAYS NON-OPTIONAL**

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



---

## **POSTGRESQL DATABASE SCHEMA**

### Database Architecture
**Version**: 4.2.0 ULTIMATE (Single Source of Truth)
**File**: `database_schema_final.sql`
**Connection**: Supabase PostgreSQL with Transaction Pooler (IPv4 compatible)
**Authentication**: Supabase Auth integration with Row Level Security

### Core Tables

#### Profiles Table
```sql
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Row Level Security policies
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = id);
```

#### Sessions Table (Unified Raw + Processed)
```sql
CREATE TABLE IF NOT EXISTS public.sessions (
    -- Core identifiers
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Session metadata (UNIFIED SCHEMA)
    tag VARCHAR(50) NOT NULL,           -- rest, sleep, experiment_paired_pre, etc.
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
    
    -- Legacy support (backward compatibility)
    sleep_event_id INTEGER,
    hrv_metrics JSONB,
    
    -- Individual HRV metrics (FINAL SCHEMA - v4.1.0+)
    mean_hr NUMERIC(6,2),              -- Mean heart rate in BPM
    mean_rr NUMERIC(8,2),              -- Mean RR interval in ms
    count_rr INTEGER,                  -- Total count of RR intervals
    rmssd NUMERIC(8,2),                -- Root Mean Square of Successive Differences (ms)
    sdnn NUMERIC(8,2),                 -- Standard Deviation of NN intervals (ms)
    pnn50 NUMERIC(6,2),                -- Percentage of NN intervals > 50ms different
    cv_rr NUMERIC(6,2),                -- Coefficient of Variation of RR intervals
    defa NUMERIC(6,3),                 -- Detrended Fluctuation Analysis Alpha1
    sd2_sd1 NUMERIC(6,3),              -- Poincaré plot SD2/SD1 ratio
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_tag CHECK (tag IN ('rest', 'sleep', 'experiment_paired_pre', 'experiment_paired_post', 'experiment_duration', 'breath_workout')),
    CONSTRAINT valid_event_id CHECK (event_id >= 0),
    CONSTRAINT valid_duration CHECK (duration_minutes > 0),
    CONSTRAINT valid_rr_count CHECK (rr_count > 0)
);
```

### Row Level Security
```sql
-- Enable RLS for sessions table
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

-- Users can only access their own sessions
CREATE POLICY "Users can view own sessions" ON public.sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sessions" ON public.sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions" ON public.sessions
    FOR UPDATE USING (auth.uid() = user_id);
```

### Database Functions

#### User Session Statistics Function
```sql
CREATE OR REPLACE FUNCTION get_user_session_statistics(target_user_id UUID)
RETURNS TABLE(
    uploaded_total BIGINT,
    processed_total BIGINT,
    sleep_events BIGINT,
    uploaded_by_tag JSONB,
    processed_by_tag JSONB
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) FILTER (WHERE status != 'completed') as uploaded_total,
        COUNT(*) FILTER (WHERE status = 'completed') as processed_total,
        COUNT(DISTINCT event_id) FILTER (WHERE tag = 'sleep' AND event_id > 0) as sleep_events,
        jsonb_object_agg(tag, count) FILTER (WHERE status != 'completed') as uploaded_by_tag,
        jsonb_object_agg(tag, count) FILTER (WHERE status = 'completed') as processed_by_tag
    FROM (
        SELECT tag, status, COUNT(*) as count
        FROM public.sessions
        WHERE user_id = target_user_id
        GROUP BY tag, status
    ) subquery;
END;
$$;
```

#### Recent User Sessions Function
```sql
CREATE OR REPLACE FUNCTION get_recent_user_sessions(
    target_user_id UUID,
    session_limit INTEGER DEFAULT 10,
    session_offset INTEGER DEFAULT 0
)
RETURNS TABLE(
    session_id UUID,
    user_id UUID,
    tag VARCHAR,
    subtag VARCHAR,
    event_id INTEGER,
    duration_minutes INTEGER,
    recorded_at TIMESTAMP WITH TIME ZONE,
    rr_count INTEGER,
    status VARCHAR,
    processed_at TIMESTAMP WITH TIME ZONE,
    mean_hr NUMERIC,
    mean_rr NUMERIC,
    count_rr INTEGER,
    rmssd NUMERIC,
    sdnn NUMERIC,
    pnn50 NUMERIC,
    cv_rr NUMERIC,
    defa NUMERIC,
    sd2_sd1 NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.session_id, s.user_id, s.tag, s.subtag, s.event_id,
        s.duration_minutes, s.recorded_at, s.rr_count, s.status, s.processed_at,
        s.mean_hr, s.mean_rr, s.count_rr, s.rmssd, s.sdnn, s.pnn50, s.cv_rr, s.defa, s.sd2_sd1,
        s.created_at, s.updated_at
    FROM public.sessions s
    WHERE s.user_id = target_user_id
    ORDER BY s.recorded_at DESC
    LIMIT session_limit
    OFFSET session_offset;
END;
$$;
```

### Performance Indexes
```sql
-- Primary performance indexes
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_tag ON public.sessions(user_id, tag);
CREATE INDEX IF NOT EXISTS idx_sessions_user_status ON public.sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_recorded_at ON public.sessions(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_event_id ON public.sessions(event_id) WHERE event_id > 0;
CREATE INDEX IF NOT EXISTS idx_sessions_sleep_events ON public.sessions(user_id, event_id) WHERE tag = 'sleep';

-- Profile indexes
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);
```

### Database Connection Configuration

#### Production Configuration (database_config.py)
```python
class DatabaseConfig:
    def __init__(self):
        # Supabase PostgreSQL with Transaction Pooler (IPv4 compatible)
        self.host = "aws-0-eu-central-1.pooler.supabase.com"
        self.database = "postgres"
        self.user = "postgres.hmckwsyksbckxfxuzxca"
        self.password = os.environ.get('SUPABASE_DB_PASSWORD')
        self.port = 6543  # Transaction Pooler port for Railway compatibility
        
        # IPv4 resolution for Railway compatibility
        self.ipv4_host = self._resolve_to_ipv4(self.host)
        
        # Connection pool settings (standardized)
        self.min_connections = 1
        self.max_connections = 20
```

#### Database Manager (database_manager.py)
```python
def setup_schema():
    """Execute the unified database schema from database_schema_final.sql"""
    schema_file = Path('database_schema_final.sql')
    
    with open(schema_file, 'r') as f:
        schema_sql = f.read()
    
    conn = get_database_connection()
    cur = conn.cursor()
    cur.execute(schema_sql)
    conn.commit()
    
    logger.info("Database schema setup complete")

def validate_connection():
    """Validate database connection and schema integrity"""
    conn = get_database_connection()
    cur = conn.cursor()
    
    # Check table existence
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = [row[0] for row in cur.fetchall()]
    
    required_tables = ['profiles', 'sessions']
    for table in required_tables:
        if table not in tables:
            raise Exception(f"Required table {table} not found")
    
    logger.info("Database validation complete")
```

---

## **HRV METRICS CALCULATION (Pure NumPy)**

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

## **API IMPLEMENTATION**

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
          data['recorded_at'], data['rr_intervals'],
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
```

#### **2. Get Processed Sessions**
```python
@app.route('/api/v1/sessions/processed/<user_id>', methods=['GET'])
def get_processed_sessions(user_id: str):
    """
    Get all processed sessions for a user with pagination
    Returns sessions with embedded HRV metrics object for iOS compatibility
    """
    # Features:
    # - Pagination support (limit/offset parameters, max 100 per request)
    # - UUID validation for user_id
    # - Returns only completed sessions (status = 'completed')
    # - Formats HRV metrics as nested object for iOS parsing
    # - Includes total_count for pagination UI
    
    # Response Format:
    {
        "sessions": [
            {
                "session_id": "uuid",
                "tag": "rest",
                "subtag": "rest_single",
                "event_id": 0,
                "duration_minutes": 5,
                "recorded_at": "2024-01-15T10:30:00Z",
                "processed_at": "2024-01-15T10:30:05Z",
                "status": "completed",
                "hrv_metrics": {
                    "mean_hr": 72.5,
                    "mean_rr": 827.3,
                    "count_rr": 360,
                    "rmssd": 45.2,
                    "sdnn": 52.1,
                    "pnn50": 15.8,
                    "cv_rr": 6.3,
                    "defa": 1.245,
                    "sd2_sd1": 2.15
                }
            }
        ],
        "total_count": 25,
        "limit": 50,
        "offset": 0
    }
```

#### **3. Session Statistics**
```python
@app.route('/api/v1/sessions/statistics/<user_id>', methods=['GET'])
def get_session_statistics(user_id: str):
    """
    Get comprehensive session statistics using PostgreSQL function
    """
    # Uses database function: get_user_session_statistics(target_user_id)
    # Returns aggregated statistics by tag and status
    # Includes sleep event grouping analysis
    
    # Response Format:
    {
        "uploaded_total": 5,
        "processed_total": 20,
        "sleep_events": 3,
        "uploaded_by_tag": {
            "rest": 2,
            "sleep": 3
        },
        "processed_by_tag": {
            "rest": 15,
            "sleep": 5
        }
    }
```

#### **4. Session Status Check**
```python
@app.route('/api/v1/sessions/status/<session_id>', methods=['GET'])
def get_session_status(session_id: str):
    """
    Get processing status of a specific session
    """
    # Returns session status and basic metadata
    # Used for upload confirmation and debugging
```

#### **5. Session Deletion**
```python
@app.route('/api/v1/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """
    Delete a session (both raw and processed data)
    """
    # Validates session ownership via user context
    # Removes all session data including RR intervals
```

#### **6. Health Checks**
```python
@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    
@app.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with database connectivity"""
    # Tests database connection pool
    # Validates schema integrity
    # Returns system status and metrics
```

### **Data Validation & Processing**

#### **Schema Validation**
```python
def validate_session_data(data: Dict) -> Dict[str, str]:
    """
    Validate session data against schema.md requirements
    """
    # Required fields validation:
    required_fields = [
        'session_id', 'user_id', 'tag', 'subtag', 'event_id',
        'duration_minutes', 'recorded_at', 'rr_intervals'
    ]
    
    # Tag validation (must be in allowed list)
    # UUID format validation
    # RR intervals array validation
    # Duration and timing validation
```

#### **HRV Metrics Calculation**
```python
# Integration with hrv_metrics.py
hrv_metrics = calculate_hrv_metrics(data['rr_intervals'])

# Returns all 9 metrics:
{
    'mean_hr': float,      # Mean heart rate (BPM)
    'mean_rr': float,      # Mean RR interval (ms)
    'count_rr': int,       # Total RR intervals
    'rmssd': float,        # RMSSD (ms)
    'sdnn': float,         # SDNN (ms)
    'pnn50': float,        # pNN50 (%)
    'cv_rr': float,        # CV of RR intervals (%)
    'defa': float,         # DFA Alpha1
    'sd2_sd1': float       # Poincaré SD2/SD1 ratio
}
```

---

## **iOS IMPLEMENTATION**

### Architecture Overview
The iOS app implements a hybrid authentication and direct database access pattern:

**Authentication Layer**: HTTP-based Supabase authentication via SupabaseAuthService
**Database Layer**: Direct PostgreSQL access via Supabase Swift SDK PostgREST client
**UI Layer**: SwiftUI with clean separation between Record tab and Sessions tab functionality

### **Complete User Workflow: From Signup to Session Processing**

#### **1. User Authentication Flow**
```swift
// User signup/login via SupabaseAuthService (HTTP-based)
class SupabaseAuthService: ObservableObject {
    @Published var isAuthenticated = false
    @Published var currentUser: SupabaseUser?
    @Published var userId: String?
    
    func signUp(email: String, password: String) async throws {
        // HTTP POST to Supabase Auth API
        // Creates user in auth.users table
        // Auto-creates profile in public.profiles table (via trigger)
    }
    
    func signIn(email: String, password: String) async throws {
        // HTTP POST to Supabase Auth API
        // Returns JWT token for authenticated requests
        // Sets userId for session creation
    }
}
```

#### **2. Record Tab Workflow**

**Step 1: Sensor Connection (SensorCard)**
```swift
// User connects to Polar H10 sensor
class BLEManager: ObservableObject {
    @Published var connectionState: SensorConnectionState = .disconnected
    @Published var heartRatePublisher: AnyPublisher<Int, Never>
    
    func connectToSensor() {
        // Bluetooth connection to Polar H10
        // Provides real-time heart rate data stream
    }
}
```

**Step 2: Recording Configuration (ConfigCard)**
```swift
// User selects tag and duration
struct ConfigCard: View {
    @EnvironmentObject var coreEngine: CoreEngine
    
    var body: some View {
        // Tag Picker: rest, sleep, experiment_paired_pre, etc.
        Picker("Session Type", selection: $coreEngine.coreState.selectedTag) {
            ForEach(SessionTag.allCases) { tag in
                Text(tag.displayName).tag(tag)
            }
        }
        
        // Duration Slider: 1-60 minutes
        Slider(value: $coreEngine.coreState.selectedDuration, in: 1...60, step: 1)
        
        // Auto-recording mode indicator for sleep tag
        if coreEngine.coreState.selectedTag.isAutoRecordingMode {
            Text("Sleep mode records continuous intervals until you stop")
        }
    }
}
```

**Step 3: Session Recording (RecordingCard)**
```swift
struct RecordingCard: View {
    @EnvironmentObject var coreEngine: CoreEngine
    
    var body: some View {
        // Recording button changes based on mode and state
        Button(action: {
            if coreEngine.coreState.isRecording {
                if coreEngine.coreState.isInAutoRecordingMode {
                    coreEngine.stopAutoRecording() // Stops entire sleep event, processes all completed intervals
                } else {
                    coreEngine.stopRecording() // Stops single session early, processes recorded data
                }
            } else {
                coreEngine.startRecordingWithCurrentMode() // Starts timer-based recording
            }
        }) {
            HStack {
                Image(systemName: recordingButtonIcon)
                Text(recordingButtonText) // "Start Recording" vs "Start Auto-Recording Sleep Event" vs "Stop Auto-Recording"
            }
        }
        
        // Live recording progress with timer countdown
        if coreEngine.coreState.isRecording {
            // Progress bar showing timer countdown
            ProgressView(value: coreEngine.coreState.recordingProgress) {
                Text("Recording Progress")
            }
            
            // Real-time heart rate from Polar H10
            Text("❤️ \(coreEngine.coreState.currentHeartRate) BPM")
            
            // Timer countdown (auto-stops when reaches 0:00)
            Text("⏱️ \(formatTime(coreEngine.coreState.remainingTime)) remaining")
                .foregroundColor(coreEngine.coreState.remainingTime < 30 ? .red : .blue)
            
            // Sleep interval indicator (auto-recording mode only)
            if coreEngine.coreState.isInAutoRecordingMode {
                Text("Sleep Interval \(coreEngine.coreState.currentSleepIntervalNumber)")
                    .font(.caption)
                    .foregroundColor(.orange)
            }
        }
    }
}
```

**Step 4: Session Processing Queue (QueueCard)**
```swift
// Completed sessions are queued for API processing
struct QueueCard: View {
    @EnvironmentObject var coreEngine: CoreEngine
    
    var body: some View {
        ForEach(coreEngine.coreState.queueItems) { item in
            HStack {
                Text("\(item.session.tagEmoji) \(item.session.tag)")
                Text(item.session.subtag) // Shows auto-assigned subtag
                Spacer()
                Text(item.status.displayText) // "Queued", "Uploading", "Completed", "Failed"
            }
        }
    }
}
```

#### **3. Sessions Tab Workflow (Direct Database Access)**

**Database Session Manager (Supabase SDK)**
```swift
class DatabaseSessionManager: ObservableObject {
    @Published var sessions: [DatabaseSession] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    func loadSessions(for userId: String) {
        // Direct PostgREST query to sessions table
        let authenticatedClient = PostgrestClient(
            url: URL(string: "\(SupabaseConfig.url)/rest/v1")!,
            headers: [
                "apikey": SupabaseConfig.anonKey,
                "Authorization": "Bearer \(userToken)"
            ]
        )
        
        // Query with RLS enforcement
        authenticatedClient
            .from("sessions")
            .select("*")
            .eq("user_id", value: userId)
            .order("recorded_at", ascending: false)
            .execute()
    }
}
```

**Sessions Display**
```swift
struct SessionsTabView: View {
    @StateObject private var databaseSessionManager = DatabaseSessionManager()
    @EnvironmentObject var coreEngine: CoreEngine
    
    var body: some View {
        ScrollView {
            // Debug & Diagnostics Card
            DebugDiagnosticsCard(manager: databaseSessionManager)
            
            // Session Data Cards
            ForEach(databaseSessionManager.sessions) { session in
                SessionDataCard(session: session)
            }
        }
        .onAppear {
            if let userId = coreEngine.userId {
                databaseSessionManager.loadSessions(for: userId)
            }
        }
    }
}
```

### Core Components

#### Authentication Service (HTTP-based)
```swift
@MainActor
class SupabaseAuthService: ObservableObject {
    static let shared = SupabaseAuthService()
    
    @Published var isAuthenticated = false
    @Published var currentUser: SupabaseUser?
    @Published var userEmail: String?
    @Published var userId: String?
    
    private let supabaseURL = "https://hmckwsyksbckxfxuzxca.supabase.co"
    private let supabaseKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." // Production anon key
    
    // HTTP-based authentication methods
    func signUp(email: String, password: String) async throws
    func signIn(email: String, password: String) async throws
    func signOut() async throws
    func getCurrentAccessToken() async -> String?
}
```

#### Database Session Manager (SDK-based)
```swift
@MainActor
class DatabaseSessionManager: ObservableObject {
    @Published var sessions: [DatabaseSession] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var debugInfo: [String] = []
    
    private let supabase = SupabaseConfig.client
    
    func loadSessions(for userId: String) {
        // Uses authenticated PostgREST client for direct database queries
        // Bypasses API layer for Sessions tab data loading
    }
}
```

### Data Models

#### Session Model (Recording)
```swift
struct Session: Codable, Identifiable {
    let id: String               // session_id (UUID)
    let userId: String          // user_id (Supabase auth.users.id)
    let tag: String             // Base tag: "rest", "sleep", etc.
    let subtag: String          // Auto-assigned: "rest_single", "sleep_interval_1"
    let eventId: Int            // 0 = standalone, >0 = grouped
    let duration: Int           // duration_minutes
    let recordedAt: Date        // recorded_at (ISO8601)
    let rrIntervals: [Double]   // rr_intervals (milliseconds)
    
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

#### Database Session Model (Display)
```swift
struct DatabaseSession: Codable, Identifiable {
    let sessionId: String        // session_id
    let userId: String          // user_id
    let tag: String             // tag
    let subtag: String          // subtag
    let eventId: Int            // event_id (API: snake_case, iOS: camelCase)
    let status: String          // status: "raw", "processing", "completed", "failed"
    let durationMinutes: Int    // duration_minutes (API: snake_case, iOS: camelCase)
    let recordedAt: Date        // recorded_at
    let processedAt: Date?      // processed_at
    
    // HRV Metrics (all 9 metrics, optional for incomplete processing)
    let meanHr: Double?         // mean_hr
    let meanRr: Double?         // mean_rr
    let countRr: Int?           // count_rr
    let rmssd: Double?          // rmssd
    let sdnn: Double?           // sdnn
    let pnn50: Double?          // pnn50
    let cvRr: Double?           // cv_rr
    let defa: Double?           // defa
    let sd2Sd1: Double?         // sd2_sd1
    
    var id: String { sessionId }
}
```

#### HRV Metrics Model
```swift
struct HRVMetrics: Codable {
    let meanHr: Double?          // mean_hr (optional for null handling)
    let meanRr: Double?          // mean_rr
    let countRr: Int?            // count_rr
    let rmssd: Double?           // rmssd
    let sdnn: Double?            // sdnn
    let pnn50: Double?           // pnn50
    let cvRr: Double?            // cv_rr
    let defa: Double?            // defa
    let sd2Sd1: Double?          // sd2_sd1
    
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

### Tab Architecture

#### Record Tab
- **Purpose**: HRV session recording and upload
- **Components**: SensorCard, ConfigCard, RecordingCard, QueueCard
- **Data Flow**: Recording → Session creation → API upload via HTTP
- **Authentication**: Uses SupabaseAuthService.shared.userId for session ownership

#### Sessions Tab
- **Purpose**: Display all user sessions with debug diagnostics
- **Data Access**: Direct PostgreSQL queries via Supabase Swift SDK
- **Authentication**: Uses authenticated PostgREST client with user JWT token
- **Components**: SessionDataCard, DebugDiagnosticsCard, EmptySessionsCard

### Session Creation Logic

#### Non-Sleep Sessions
```swift
currentSession = Session(
    userId: userId,
    tag: tag.rawValue,                    // "rest", "exercise", etc.
    subtag: "\(tag.rawValue)_single",     // "rest_single", "exercise_single"
    eventId: 0,                           // Standalone session
    duration: Int(duration),
    rrIntervals: []
)
```

#### Sleep Sessions (Grouped)
```swift
let subtag = "sleep_interval_\(intervalNumber)"  // sleep_interval_1, sleep_interval_2
let sleepEventId = generateSleepEventId()        // Shared across all intervals

currentSession = Session(
    userId: userId,
    tag: "sleep",
    subtag: subtag,
    eventId: sleepEventId,                // Grouped sessions
    duration: Int(duration),
    rrIntervals: []
)
```

### Supabase Configuration
```swift
struct SupabaseConfig {
    static let url = "https://hmckwsyksbckxfxuzxca.supabase.co"
    static let anonKey = "sb_publishable_oRjabmXPVvT5QMv_5Ec92A_Ytc6xrFr"
    
    static let client = PostgrestClient(
        url: URL(string: "\(url)/rest/v1")!,
        schema: "public",
        headers: [
            "apikey": anonKey,
            "Authorization": "Bearer \(anonKey)"
        ],
        logger: nil
    )
}
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

*This unified schema ensures consistency across all components and serves as the single source of truth for the entire HRV application ecosystem.*

---

## 🚀 DEPLOYMENT LESSONS LEARNED

### Successful Railway + Supabase Deployment

**Final Working Configuration:**
- **API URL**: https://hrv-brain-api-production.up.railway.app
- **Database**: Supabase PostgreSQL (Transaction Pooler, IPv4-compatible)
- **Environment**: Railway with Nixpacks + Python 3.11

### 🔧 Critical Issues Resolved

#### 1. **Security Issue**: Exposed Secrets
- **Problem**: Supabase credentials exposed in GitHub
- **Solution**: Rotated all API keys, removed .env files from git, added .env* to .gitignore

#### 2. **Dependency Issue**: Missing Python Packages
- **Problem**: Flask app crashed on startup due to missing `PyJWT` and `supabase` imports
- **Solution**: Added to requirements.txt:
  ```
  PyJWT==2.8.0
  supabase==1.0.4
  ```

#### 3. **Gunicorn Issue**: Invalid Arguments
- **Problem**: `railway.json` used invalid `--keepalive 2` argument
- **Solution**: Removed invalid argument from startCommand:
  ```json
  "startCommand": "gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120"
  ```

#### 4. **Database Schema Migration**: Individual HRV Columns (v4.1.0)
- **Problem**: Database had `hrv_metrics` JSONB column, but API expected individual columns
- **Solution**: Added 9 individual HRV metric columns via migration:
  ```sql
  ALTER TABLE sessions ADD COLUMN mean_hr NUMERIC(6,2),
  ADD COLUMN mean_rr NUMERIC(8,2), ADD COLUMN count_rr INTEGER,
  ADD COLUMN rmssd NUMERIC(8,2), ADD COLUMN sdnn NUMERIC(8,2),
  ADD COLUMN pnn50 NUMERIC(6,2), ADD COLUMN cv_rr NUMERIC(6,2),
  ADD COLUMN defa NUMERIC(6,3), ADD COLUMN sd2_sd1 NUMERIC(6,3);
  ```

#### 5. **iOS JSON Serialization Crash**: Heart Rate Validation
- **Problem**: Division by zero when heart rate = 0, causing infinite RR intervals and JSON crash
- **Solution**: Added validation in `RecordingManager.swift`:
  ```swift
  guard heartRate > 0 && heartRate <= 300 else { return }
  guard rrInterval >= 300 && rrInterval <= 2000 && rrInterval.isFinite else { return }
  ```

#### 6. **Database Connection**: IPv4 Compatibility
- **Problem**: Railway IPv4-only networking couldn't connect to Supabase Direct Connection
- **Solution**: Used Supabase Transaction Pooler (port 6543, IPv4-compatible):
  ```
  SUPABASE_DB_HOST=aws-0-eu-central-1.pooler.supabase.com
  SUPABASE_DB_PORT=6543
  ```



### Key Takeaways for Future Deployments
1. **Always use Supabase Transaction Pooler** for Railway/Heroku deployments
2. **Check railway.json for invalid Gunicorn arguments** before deployment
3. **Verify all Python imports have corresponding requirements.txt entries**
4. **Rotate secrets immediately** if exposed in version control
5. **Test health endpoint locally** before deploying to production

---

## **DEPLOYMENT ARCHITECTURE**

### **Railway API Deployment**

#### **nixpacks.toml Configuration**
```toml
# Railway deployment configuration
[phases.setup]
nixPkgs = ["python311", "postgresql"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "gunicorn --bind 0.0.0.0:$PORT app:app"
```

#### **Production requirements.txt**
```txt
Flask==2.3.3
Flask-CORS==4.0.0
psycopg2-binary==2.9.9
numpy==1.26.4
setuptools==69.5.1
gunicorn==21.2.0
Werkzeug==2.3.7
supabase==1.0.4
PyJWT==2.8.0
```

### **Environment Configuration**

#### **Production Environment (Railway)**
```bash
# Database Configuration
DATABASE_URL=postgresql://postgres.hmckwsyksbckxfxuzxca:PASSWORD@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
SUPABASE_DB_HOST=aws-0-eu-central-1.pooler.supabase.com
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres.hmckwsyksbckxfxuzxca
SUPABASE_DB_PASSWORD=your_password_here
SUPABASE_DB_PORT=6543

# Supabase Configuration
SUPABASE_URL=https://hmckwsyksbckxfxuzxca.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... # Production anon key

# Application Configuration
FLASK_ENV=production
PORT=5000
PYTHON_VERSION=3.11.0
```

---

## **CRITICAL FIXES IMPLEMENTED**

### **1. Date Decoding Fix (iOS)**
**Problem**: iOS couldn't parse API responses with microseconds + timezone offset  
**Solution**:
```swift
// Fixed iOS date parsing for API responses with microseconds + timezone
let iso8601Formatter = ISO8601DateFormatter()
iso8601Formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

// Usage in DatabaseSession model
static let dateFormatter: ISO8601DateFormatter = {
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    return formatter
}()
```

### **2. PostgreSQL Array Format Fix (API)**
**Problem**: RR intervals were stored as JSON strings instead of native PostgreSQL arrays  
**Solution**:
```python
# Fixed RR intervals storage - use native PostgreSQL arrays
cursor.execute("""
    INSERT INTO sessions (rr_intervals) VALUES (%s)
""", [rr_intervals])  # Python list → PostgreSQL DECIMAL[]

# NOT: json.dumps(rr_intervals) - this was the bug
```

### **3. Authentication Token Fix (iOS)**
**Problem**: PostgREST client wasn't properly authenticated with user tokens  
**Solution**:
```swift
// Fixed PostgREST authentication with proper user tokens
guard let userToken = await SupabaseAuthService.shared.getCurrentAccessToken() else {
    throw DatabaseError.authenticationFailed
}

let authenticatedClient = PostgrestClient(
    url: URL(string: "\(SupabaseConfig.url)/rest/v1")!,
    headers: [
        "apikey": SupabaseConfig.anonKey,
        "Authorization": "Bearer \(userToken)"
    ]
)
```

### **4. API Key Format Fix**
**Problem**: Using placeholder/example API keys instead of production format  
**Solution**:
```swift
// Use correct anon key format (production)
static let anonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." // Production anon key
// NOT: "sb_publishable_..." - this was placeholder format
```

### **5. Connection Pool IPv4 Resolution Fix**
**Problem**: Railway deployment couldn't resolve IPv6 hostnames  
**Solution**:
```python
def _resolve_to_ipv4(self, hostname: str) -> str:
    """Resolve hostname to IPv4 address for Railway compatibility"""
    try:
        addresses = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if addresses:
            ipv4_addr = addresses[0][4][0]
            logger.info(f"Resolved {hostname} to IPv4: {ipv4_addr}")
            return ipv4_addr
        else:
            return hostname
    except Exception as e:
        logger.warning(f"Failed to resolve {hostname} to IPv4: {e}")
        return hostname
```

---

## **DATA FLOW ARCHITECTURE**

### **Complete Session Lifecycle**
```
iOS Recording → API Processing → Database Storage → iOS Display

1. iOS RecordingManager captures RR intervals from HealthKit
2. Session uploaded to API via HTTP POST /api/v1/sessions/upload
3. API validates schema, calculates HRV metrics using NumPy
4. Processed session stored in PostgreSQL with individual metric columns
5. iOS Sessions tab queries via PostgREST client (direct database access)
6. Data displayed in clean card-based UI with debug diagnostics
```

### **Session Data Model Evolution**
```
Raw Session (iOS) → API Processing → Database Storage → Display (iOS)

{                    {                 sessions table      DatabaseSession
  sessionId,         sessionId,        session_id,         sessionId,
  userId,            userId,           user_id,            userId,
  tag,               tag,              tag,                tag,
  subtag,            subtag,           subtag,             subtag,
  eventId,           eventId,          event_id,           eventId,
  rrIntervals        rrIntervals       rr_intervals,       (not included)
}                    + HRV metrics     mean_hr, rmssd...   meanHr, rmssd...
```

### **Authentication Flow**
```
1. User signup/login via SupabaseAuthService (HTTP-based)
2. JWT token stored securely in iOS
3. API calls use Bearer token for authentication
4. PostgREST client uses same token for direct database queries
5. Row Level Security enforces user isolation at database level
```

---

## **DEPLOYMENT CHECKLIST**

### **Database Deployment**
- [ ] Deploy `database_schema_final.sql` to Supabase
- [ ] Configure Row Level Security policies
- [ ] Set up database functions and triggers
- [ ] Verify IPv4/Transaction Pooler connectivity
- [ ] Test database functions (get_user_session_statistics, get_recent_user_sessions)

### **API Deployment**
- [ ] Deploy to Railway with `nixpacks.toml`
- [ ] Configure environment variables (DATABASE_URL, SUPABASE_*)
- [ ] Test all endpoints with health checks
- [ ] Verify database connectivity and connection pooling
- [ ] Test HRV metrics calculation with sample data

### **iOS Configuration**
- [ ] Install Supabase Swift SDK (PostgREST, Auth modules)
- [ ] Configure SupabaseConfig with correct keys and URLs
- [ ] Implement hybrid authentication pattern
- [ ] Test Sessions tab with PostgREST client
- [ ] Verify date parsing and JSON decoding

### **Integration Testing**
- [ ] End-to-end session recording → processing → display
- [ ] Authentication flow (signup → login → database access)
- [ ] Error handling and debug logging
- [ ] Performance and scalability testing
- [ ] Cross-platform data consistency verification

---

## **RELATED DOCUMENTATION**

- `database_schema_final.sql` - Complete database schema
- `README.md` - Deployment and setup instructions
- `admin_db_api_control.ipynb` - Admin management notebook
- iOS `DatabaseSessionManager.swift` - Direct database access implementation
- API `app.py` - Complete Flask application

---

**Last Updated**: 2025-08-04  
**Version**: 6.0.0 FINAL CONSOLIDATED  
**Status**: Production Ready - Single Golden Asset  
**Maintainer**: Atriom.Studio
