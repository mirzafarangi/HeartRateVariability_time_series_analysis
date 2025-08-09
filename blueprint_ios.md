# Blueprint: iOS HRV Brain App - Record & Sessions Tabs

## Overview
This document defines the canonical architecture and data flows for the iOS HRV Brain app's Record and Sessions tabs. These two tabs form the core user experience for HRV recording, processing, and session management.

---

## 1. Record Tab

### 1.1 Purpose
The Record tab is the primary interface for capturing HRV data from the Apple Watch. It manages the complete recording lifecycle from session initiation to queue management and API upload.

### 1.2 Architecture Components

```
RecordTabView
    ├── RecordingCard (Session Configuration)
    ├── ConfigCard (Active Recording Display)
    ├── QueueCard (Upload Management)
    └── CoreEngine (Recording Engine)
```

### 1.3 Recording Flow

#### Step 1: Session Configuration
```swift
// User selects a canonical tag in RecordingCard
enum SessionTag: String {
    case wake_check = "wake_check"
    case pre_sleep = "pre_sleep"
    case sleep = "sleep"
    case experiment = "experiment"
}

// Subtag is auto-assigned based on tag
func getSubtag(for tag: SessionTag, interval: Int = 1) -> String {
    switch tag {
    case .wake_check:
        return "wake_check_single"
    case .pre_sleep:
        return "pre_sleep_single"
    case .sleep:
        return "sleep_interval_\(interval)"
    case .experiment:
        return "experiment_protocol_breathing"
    }
}
```

#### Step 2: Recording Initiation
```swift
// User taps "Start Recording"
RecordingManager.startRecording(
    tag: selectedTag,
    subtag: autoAssignedSubtag,
    eventId: 0  // Always 0 for client
)
    ↓
CoreEngine.startWatchRecording()
    ↓
Apple Watch HRV Capture
```

#### Step 3: Data Collection
```swift
// Real-time RR intervals from Apple Watch
struct LiveHRVData {
    let rrIntervals: [Double]  // milliseconds
    let timestamp: Date
    let heartRate: Double
}

// CoreEngine processes incoming data
CoreEngine.processHRVData(liveData)
    ↓
ConfigCard displays:
    - Elapsed time
    - Current heart rate
    - RR interval count
    - Recording status
```

#### Step 4: Recording Completion
```swift
// User taps "Stop Recording" or auto-stop triggers
RecordingManager.stopRecording()
    ↓
Create QueueCard:
{
    "session_id": "uuid_without_hyphens",
    "user_id": "authenticated_user_id",
    "tag": "wake_check",
    "subtag": "wake_check_single",
    "event_id": 0,
    "recorded_at": "2025-08-09T10:30:00Z",
    "duration_minutes": 5,
    "rr_intervals": [800, 820, 810, ...]
}
    ↓
QueueManager.addToQueue(queueCard)
```

### 1.4 Queue Management

#### Queue States
```swift
enum QueueStatus {
    case pending    // Waiting for upload
    case uploading  // Currently sending to API
    case completed  // Successfully uploaded
    case failed     // Upload failed, will retry
}
```

#### Upload Process
```swift
QueueManager.processQueue()
    ↓
For each pending QueueCard:
    1. APIClient.uploadSession(queueCard)
    2. POST to /api/v1/sessions/upload
    3. Handle response:
        - Success: Mark completed, store event_id if sleep
        - Failure: Retry with exponential backoff
    4. Update QueueCard status
```

### 1.5 Multi-Interval Sleep Recording

For sleep sessions with multiple intervals:

```swift
// First interval
sleep_interval_1: event_id = 0 → API returns event_id = 123

// Subsequent intervals (same night)
sleep_interval_2: event_id = 123 (use returned ID)
sleep_interval_3: event_id = 123 (use returned ID)

// New night
sleep_interval_1: event_id = 0 → API returns event_id = 124
```

### 1.6 UI Components

#### RecordingCard
- Tag selector (4 canonical options)
- Duration selector (5, 10, 15 minutes)
- Start Recording button
- Auto-assigns subtag based on tag

#### ConfigCard (During Recording)
- Live elapsed time
- Current heart rate
- RR interval count
- Stop Recording button
- Visual recording indicator

#### QueueCard
- List of pending uploads
- Upload status for each session
- Retry failed uploads
- Clear completed items

---

## 2. Sessions Tab

### 2.1 Purpose
The Sessions tab provides comprehensive session management with direct database access for real-time updates, session browsing, and deletion capabilities.

### 2.2 Architecture Components

```
SessionsTabView
    ├── DebugDiagnosticsCard (DB Connection Status)
    ├── SessionsByTagCard (Accordion View)
    │   ├── Wake Check Sessions
    │   ├── Pre-Sleep Sessions
    │   ├── Sleep Sessions
    │   └── Experiment Sessions
    └── SessionDataCard (Latest Session Details)
```

### 2.3 Data Access Pattern

```swift
// Direct database access via Supabase SDK
DatabaseSessionManager
    ↓
PostgrestClient (Supabase SDK)
    ↓
SELECT * FROM sessions WHERE user_id = ?
    ↓
Transform to DatabaseSession models
    ↓
Display in UI
```

### 2.4 Session Display

#### Session Row Format
Each session displays:
```
┌─────────────────────────────────────────────┐
│ 📅 Aug 9, 2025 10:30 AM                    │
│ wake_check/wake_check_single • 5 min       │
│ [Completed] 72 BPM                          │
└─────────────────────────────────────────────┘

For sleep with events:
┌─────────────────────────────────────────────┐
│ 📅 Aug 9, 2025 11:00 PM                    │
│ sleep/sleep_interval_1 Event #3 • 90 min   │
│ [Completed] 65 BPM                          │
└─────────────────────────────────────────────┘
```

#### Accordion Grouping
Sessions are grouped by tag with expandable sections:
```
▼ Wake Check (12 sessions)
  - wake_check/wake_check_single
  - wake_check/wake_check_paired_day_pre
  
▼ Sleep (8 sessions)
  - sleep/sleep_interval_1 Event #3
  - sleep/sleep_interval_2 Event #3
  - sleep/sleep_interval_1 Event #4
  
▶ Pre-Sleep (5 sessions)
▶ Experiment (3 sessions)
```

### 2.5 Database Operations

#### Fetch Sessions
```swift
func getSessionsByTag(userId: String) async -> [String: [DatabaseSession]] {
    let query = postgrestClient
        .from("sessions")
        .select("*")
        .eq("user_id", value: userId)
        .order("recorded_at", ascending: false)
    
    let sessions = try await query.execute()
    return groupByTag(sessions)
}
```

#### Delete Session
```swift
func deleteSession(sessionId: String) async -> Result<Void, Error> {
    let query = postgrestClient
        .from("sessions")
        .delete()
        .eq("session_id", value: sessionId)
    
    try await query.execute()
    // Automatic UI refresh after deletion
}
```

### 2.6 UI Components

#### DebugDiagnosticsCard
```
┌─────────────────────────────────────────────┐
│ 🔧 Database Diagnostics                     │
│ Status: Connected ✓                         │
│ Sessions: 28 total                          │
│ Last sync: 2 seconds ago                    │
│ [View Debug Logs]                           │
└─────────────────────────────────────────────┘
```

#### SessionDataCard (Latest Session)
```
┌─────────────────────────────────────────────┐
│ Latest Session Details                      │
│                                              │
│ Tag: wake_check                             │
│ Subtag: wake_check_single                   │
│ Event ID: 0                                 │
│ Duration: 5 minutes                         │
│ Recorded: Aug 9, 2025 10:30 AM             │
│                                              │
│ HRV Metrics:                                │
│ • Mean HR: 72 BPM                          │
│ • RMSSD: 42.5 ms                           │
│ • SDNN: 38.2 ms                            │
│ • PNN50: 18.5%                             │
│                                              │
│ [Delete Session]                            │
└─────────────────────────────────────────────┘
```

---

## 3. Data Flow Examples

### 3.1 Complete Recording to Display Flow

```
1. USER ACTION: Start wake_check recording
   RecordTabView → RecordingCard
   
2. RECORDING: Capture HRV data for 5 minutes
   CoreEngine → Apple Watch → RR Intervals
   
3. COMPLETION: Create queue entry
   RecordingManager → QueueCard:
   {
     "session_id": "abc123...",
     "tag": "wake_check",
     "subtag": "wake_check_single",
     "event_id": 0,
     "rr_intervals": [800, 820, 810...]
   }
   
4. UPLOAD: Send to API
   QueueManager → APIClient → POST /api/v1/sessions/upload
   
5. API PROCESSING:
   - Validate canonical tag/subtag
   - Calculate HRV metrics
   - Insert into database
   - Return success with event_id
   
6. DATABASE: Session stored
   sessions table:
   - session_id: abc123...
   - tag: wake_check
   - subtag: wake_check_single
   - event_id: 0
   - mean_hr: 72.5
   - rmssd: 42.5
   - [all other metrics]
   
7. DISPLAY: View in Sessions tab
   SessionsTabView → DatabaseSessionManager → Supabase
   Shows: "wake_check/wake_check_single • 5 min"
```

### 3.2 Sleep Recording with Event ID

```
Night 1 - First Recording:
1. Start sleep recording (interval 1)
2. QueueCard: event_id = 0
3. API assigns: event_id = 123
4. Store event_id for this night

Night 1 - Second Recording:
1. Continue sleep (interval 2)
2. QueueCard: event_id = 123 (reuse)
3. API accepts with same event_id
4. Both intervals grouped under Event #123

Night 2 - New Recording:
1. Start new sleep (interval 1)
2. QueueCard: event_id = 0
3. API assigns: event_id = 124
4. New sleep event created
```

### 3.3 Session Deletion Flow

```
1. USER ACTION: Swipe to delete in Sessions tab
   SessionRowView → onDelete callback
   
2. DATABASE OPERATION:
   DatabaseSessionManager.deleteSession(sessionId)
   → Supabase SDK → DELETE FROM sessions
   
3. UI UPDATE:
   - Remove from local state
   - Refresh session list
   - Update statistics
   - Show confirmation
```

---

## 4. Canonical Rules Enforcement

### 4.1 Tag Validation
```swift
// Only these tags are allowed
let allowedTags = ["wake_check", "pre_sleep", "sleep", "experiment"]

// Enforced at:
- RecordingCard: UI only shows canonical options
- QueueCard: Validates before upload
- API: Rejects non-canonical tags
- Database: CHECK constraint on tag column
```

### 4.2 Subtag Patterns
```swift
// Strict subtag patterns per tag
wake_check → "wake_check_single" | "wake_check_paired_day_pre"
pre_sleep → "pre_sleep_single"
sleep → "sleep_interval_[1-9][0-9]*"
experiment → "experiment_protocol_.*"

// Auto-assigned by iOS, validated by API
```

### 4.3 Event ID Rules
```swift
// Client always sends 0
queueCard.event_id = 0

// Database assigns for sleep
IF tag = 'sleep' AND subtag = 'sleep_interval_1':
    ASSIGN new event_id
ELSE IF tag = 'sleep':
    USE existing event_id for user
ELSE:
    KEEP event_id = 0
```

---

## 5. Error Handling

### 5.1 Recording Errors
```swift
// Watch connection lost
CoreEngine.handleWatchDisconnection()
→ Show alert: "Apple Watch disconnected"
→ Save partial data if possible

// Insufficient RR intervals
if rrIntervals.count < 10 {
    Show alert: "Not enough data collected"
    Discard recording
}
```

### 5.2 Upload Errors
```swift
// Network failure
QueueManager.handleUploadError(error)
→ Mark as failed
→ Retry with exponential backoff
→ Max 3 retries

// Validation failure
API returns 400: "Invalid tag"
→ Mark as permanently failed
→ Show error to user
→ Allow manual correction
```

### 5.3 Database Errors
```swift
// Connection failure
DatabaseSessionManager.handleConnectionError()
→ Show offline indicator
→ Cache operations locally
→ Retry when connection restored

// Constraint violation
"Duplicate session_id"
→ Skip duplicate
→ Continue with next operation
```

---

## 6. Security & Authentication

### 6.1 User Authentication
```swift
// Supabase Auth
SupabaseAuthService.authenticate()
→ Get JWT token
→ Store user_id
→ Use for all operations
```

### 6.2 Data Access
```swift
// Row Level Security (RLS)
- Users can only see their own sessions
- user_id validated on every operation
- No cross-user data leakage
```

---

## 7. Performance Optimizations

### 7.1 Queue Processing
- Batch uploads when possible
- Exponential backoff for retries
- Clear completed items periodically

### 7.2 Database Queries
- Paginated session fetching
- Indexed on user_id and recorded_at
- Grouped queries for statistics

### 7.3 UI Responsiveness
- Async/await for all DB operations
- Optimistic UI updates
- Background queue processing

---

## 8. Testing Scenarios

### 8.1 Record Tab Testing
1. Start recording → Verify subtag auto-assignment
2. Complete recording → Check queue entry creation
3. Upload session → Verify API response
4. Check event_id → Confirm proper allocation for sleep

### 8.2 Sessions Tab Testing
1. Load sessions → Verify all fields displayed
2. Expand accordion → Check tag grouping
3. Delete session → Confirm removal from DB
4. Refresh → Verify latest data

### 8.3 End-to-End Testing
1. Record wake_check for 5 minutes
2. Wait for upload completion
3. Navigate to Sessions tab
4. Verify session appears with correct tag/subtag
5. Delete session
6. Confirm removal

---

## Summary

The Record and Sessions tabs work in perfect harmony:

- **Record Tab**: Captures HRV data, manages queue, uploads to API
- **Sessions Tab**: Displays all sessions, provides management, direct DB access
- **Data Flow**: Record → Queue → API → Database → Sessions Display
- **Canonical Compliance**: Enforced at every layer (UI, API, DB)
- **User Experience**: Seamless recording, automatic processing, real-time updates

This architecture ensures data integrity, canonical compliance, and optimal user experience throughout the HRV recording and management lifecycle.
