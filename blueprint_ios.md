# Blueprint: iOS HRV Brain App Architecture

## Overview
This document defines the complete architecture, authentication system, and data flows for the iOS HRV Brain app. It covers the core components including authentication management, network layer, recording system, and session management across all tabs.

---

## 1. System Architecture

### 1.1 Core Components

```
ios_hrv/
├── Core/                       # Core system services
│   ├── SupabaseAuthService    # Unified authentication & token management
│   ├── CoreEngine             # Master orchestrator
│   ├── APIClient              # Network layer for API communication
│   ├── RecordingManager       # HRV recording logic
│   ├── QueueManager           # Upload queue management
│   ├── BLEManager             # Bluetooth/sensor connectivity
│   └── DatabaseSessionManager # Local session persistence
├── Models/                     # Data models
│   ├── UnifiedModels          # Core data structures
│   └── Enums                  # App-wide enumerations
├── UI/                        # User interface
│   ├── Tabs/                  # Main tab views
│   └── Components/            # Reusable UI components
└── Managers/                  # (Legacy - being phased out)
    └── HRVNetworkManager
```

### 1.2 Authentication System

#### SupabaseAuthService (Singleton)
The unified authentication service manages all auth-related operations:

```swift
@MainActor
class SupabaseAuthService: ObservableObject {
    static let shared = SupabaseAuthService()
    
    // Published state
    @Published var isAuthenticated: Bool
    @Published var currentUser: SupabaseUser?
    @Published var userId: String?
    @Published var userEmail: String?
    @Published var errorMessage: String?
    @Published var successMessage: String?
    
    // Core features:
    // - JWT token storage (access + refresh tokens)
    // - Automatic token refresh every 30 seconds
    // - Session persistence across app launches
    // - Emergency re-authentication fallback
    // - Supabase API integration
}
```

#### Authentication Flow

```
1. App Launch
   └── SupabaseAuthService.loadStoredSession()
       ├── Load tokens from Keychain
       ├── Validate JWT expiration
       └── Start token monitoring timer

2. Sign In
   └── SupabaseAuthService.signIn(email, password)
       ├── POST to Supabase /auth/v1/token
       ├── Store access_token + refresh_token
       ├── Store user credentials (emergency fallback)
       └── Update published state

3. Token Refresh (Automatic)
   └── Timer triggers every 30 seconds
       ├── Check if token expires within 5 minutes
       ├── Use refresh_token to get new access_token
       ├── If refresh fails → try stored credentials
       └── Update stored tokens

4. API Calls
   └── APIClient.addAuthHeaders()
       └── Get current access_token from SupabaseAuthService
           └── Add "Bearer {token}" to Authorization header
```

#### Token Storage

```swift
Keychain keys:
- "supabase_access_token"    // JWT access token
- "supabase_refresh_token"   // JWT refresh token  
- "supabase_user_id"         // User UUID
- "supabase_user_email"      // User email
- "supabase_stored_password" // Emergency fallback
```

### 1.3 Network Management

#### APIClient
Centralized API communication layer:

```swift
class APIClient {
    private let baseURL = "https://hrv-brain-api-production.up.railway.app"
    
    // Endpoints
    func uploadSession(_ session: RawSession) async throws -> SessionUploadResponse
    func getSessionStatus(_ sessionId: String) async throws -> SessionStatusResponse
    func getProcessedSessions(userId: String) async throws -> [ProcessedSession]
    func getSessionStatistics(userId: String) async throws -> SessionStatistics
    func getHealthStatus() async throws -> HealthResponse
    
    // All requests automatically include Supabase JWT token
    private func addAuthHeaders(to request: inout URLRequest) async {
        if let token = await SupabaseAuthService.shared.getCurrentAccessToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
    }
}
```

#### Network Flow

```
User Action → CoreEngine → APIClient → Railway API → Supabase DB
                  ↑            ↓
           SupabaseAuthService provides JWT token
```

---

## 2. Record Tab

### 2.1 Purpose
The Record tab is the primary interface for capturing HRV data from the Apple Watch. It manages the complete recording lifecycle from session initiation to queue management and API upload.

### 2.2 Architecture Components

```
RecordTabView
    ├── SensorCard (Sensor/Auth status, connectivity)
    ├── ConfigCard (Recording mode/config state + status)
    ├── RecordingCard (Controls: start/stop, duration, tag)
    ├── QueueCard (Upload queue, API validation & DB status)
    └── CoreEngine (EnvironmentObject – recording engine/state)
```

### 2.3 Recording Flow

#### Step 1: Session Configuration
```swift
// User selects canonical tag/duration in UI (RecordingCard/ConfigCard)
// Subtag is auto-assigned per canonical rules (sleep uses interval numbering)
```

#### Step 2: Recording Initiation
```swift
// User taps "Start Recording"
CoreEngine.startRecordingWithCurrentMode()
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
// ConfigCard presents live status/telemetry
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
// CoreEngine finalizes the session
    ↓
Create queue item:
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
QueueManager.addSession(session)
```

### 2.4 Queue Management

#### Queue States
```swift
enum QueueStatus {
    case pending    // Waiting for upload
    case uploading  // Currently sending to API
    case completed  // Successfully uploaded
    case failed     // Upload failed, will retry
}
```

#### Upload Process + Validation/DB status
```swift
QueueManager.processQueue()
    ↓
For each pending queue item:
  1. APIClient.uploadSession(session)
  2. POST /api/v1/sessions/upload
  3. Response fields:
     - validation_report → mapped to ValidationReport (Codable)
     - db_status (e.g., "inserted", "skipped", "error")
  4. Mark status: .completed or .failed (with retry policy)
  5. For sleep: if API returns new event_id, reuse the same event_id for subsequent intervals that night
```

QueueCard UI shows, per item:
- Status: Valid/Invalid from `validationReport.validationResult.isValid`
- Durations: iOS vs RR, match flag, tolerance
- RR analysis: count, avg RR
- Errors/Warnings lists
- Endpoint: API base URL (via `APIClient().baseURLString`) and route

### 1.5 Multi-Interval Sleep Recording

For sleep sessions with multiple intervals:

```swift
// First interval
sleep_interval_1: event_id = 0 → API returns event_id = 123

// Subsequent intervals (same night)
sleep_interval_2: event_id = 123 (reuse)
sleep_interval_3: event_id = 123 (reuse)

// New night
sleep_interval_1: event_id = 0 → API returns event_id = 124
```

### 1.6 UI Components (current)

#### RecordingCard
- Canonical tag/duration selectors
- Start/Stop controls depending on state
- Auto subtag per tag; sleep uses interval numbering

#### ConfigCard (During Recording)
- Live elapsed time/progress
- Current heart rate / RR count
- Recording mode/status indicator
- Stop control

#### QueueCard
- Pending/Uploading/Completed/Failed items
- Validation report + DB status display
- Retry failed uploads / Clear completed
- Copy full report (includes endpoint details)

---

## 3. Sessions Tab

### 3.1 Purpose
The Sessions tab provides comprehensive session management with direct database access for real-time updates, session browsing, and deletion capabilities.

### 3.2 Architecture Components

```
SessionsTabView
    ├── SessionDiagnosticsCard (DB/Counts/Debug info)
    ├── SessionAccordionView (Expandable sessions-by-tag)
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

### 3.4 Session Display

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

### 2.6 UI Components (current)

#### SessionDiagnosticsCard
```
┌─────────────────────────────────────────────┐
│ 🔧 Database Diagnostics                     │
│ Total Sessions: N                           │
│ Status/Debug: dynamic info                  │
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

## 6. Core System Components

### 6.1 CoreEngine (Master Orchestrator)

```swift
@MainActor
class CoreEngine: ObservableObject {
    static let shared = CoreEngine()
    
    // Managers
    private let authService: SupabaseAuthService
    private let bleManager: BLEManager
    private let recordingManager: RecordingManager
    private let queueManager: QueueManager
    private let apiClient: APIClient
    
    // Published State
    @Published var coreState: CoreState
    @Published var isAuthenticated: Bool
    @Published var userId: String?
    
    // Coordinates all app operations
    func startRecordingWithCurrentMode()
    func stopRecording()
    func processQueue()
    func loadSessions()
}
```

### 6.2 RecordingManager

Handles all recording logic:

```swift
class RecordingManager: ObservableObject {
    @Published var isRecording: Bool
    @Published var currentSession: RecordingSession?
    @Published var recordingMode: RecordingMode
    
    // Recording modes
    enum RecordingMode {
        case single(tag: SessionTag, duration: Int)
        case autoRecording(intervals: [Int], currentInterval: Int)
    }
    
    // Core functions
    func startRecording(tag: SessionTag, subtag: String, duration: Int)
    func stopRecording()
    func processRRIntervals(_ intervals: [Double])
}
```

### 6.3 QueueManager

Manages upload queue:

```swift
class QueueManager: ObservableObject {
    @Published var queueItems: [QueueItem]
    @Published var isProcessing: Bool
    
    // Queue operations
    func addSession(_ session: RawSession)
    func processQueue() async
    func retryFailed()
    func clearCompleted()
}
```

### 6.4 BLEManager

Bluetooth and sensor connectivity:

```swift
class BLEManager: ObservableObject {
    @Published var connectionState: ConnectionState
    @Published var sensorInfo: SensorInfo?
    @Published var heartRate: Double?
    @Published var rrIntervals: [Double]
    
    func startScanning()
    func connect(to device: BLEDevice)
    func startHRVCapture()
    func stopHRVCapture()
}
```

---

## 7. Error Handling

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
