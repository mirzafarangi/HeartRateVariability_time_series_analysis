# HRV Brain System - Complete Architecture Blueprint v5.0.0
**Canonical Documentation for Full System Rebuild**

> **🎯 PURPOSE**: This document serves as the definitive blueprint for rebuilding the entire HRV system from scratch. Every architectural decision, integration pattern, and implementation detail is documented here.

## 📋 **SYSTEM OVERVIEW**

### **Architecture Stack**
- **Frontend**: iOS Swift/SwiftUI App with Supabase Swift SDK
- **Backend**: Python Flask API deployed on Railway
- **Database**: Supabase PostgreSQL with Row Level Security
- **Authentication**: Hybrid approach (HTTP for auth, SDK for data)

### **Key Architectural Decisions Made**
1. **Authentication Strategy**: HTTP-based auth (SupabaseAuthService) + SDK for database queries
2. **Data Access Pattern**: Direct PostgREST client for iOS Sessions tab
3. **Database Schema**: Individual HRV metric columns (not JSONB)
4. **Deployment**: Railway for API, Supabase for database
5. **Error Handling**: Comprehensive debug logging throughout stack

---

## 🗄️ **DATABASE ARCHITECTURE**

### **Core Tables**
```sql
-- Profiles table (extends Supabase auth.users)
public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions table (unified schema)
public.sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    tag TEXT NOT NULL,                    -- "rest", "sleep", "exercise", etc.
    subtag TEXT NOT NULL,                 -- "rest_single", "sleep_interval_1", etc.
    event_id INTEGER NOT NULL DEFAULT 0, -- 0 for standalone, >0 for grouped
    duration_minutes INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    rr_count INTEGER,
    status TEXT NOT NULL DEFAULT 'raw',  -- 'raw', 'processing', 'completed', 'failed'
    processed_at TIMESTAMPTZ,
    
    -- Individual HRV Metrics (9 total)
    mean_hr DECIMAL(6,2),
    mean_rr DECIMAL(8,3),
    count_rr INTEGER,
    rmssd DECIMAL(8,3),
    sdnn DECIMAL(8,3),
    pnn50 DECIMAL(6,3),
    cv_rr DECIMAL(6,3),
    defa DECIMAL(8,6),
    sd2_sd1 DECIMAL(8,3),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### **Critical Database Functions**
```sql
-- User session statistics
CREATE OR REPLACE FUNCTION get_user_session_statistics(p_user_id UUID)
RETURNS TABLE(
    raw_total BIGINT,
    processed_total BIGINT,
    sleep_events BIGINT,
    raw_by_tag JSONB,
    processed_by_tag JSONB
);

-- Recent user sessions
CREATE OR REPLACE FUNCTION get_recent_user_sessions(p_user_id UUID, p_limit INTEGER DEFAULT 10)
RETURNS TABLE(
    session_id UUID,
    tag TEXT,
    subtag TEXT,
    status TEXT,
    recorded_at TIMESTAMPTZ
);
```

---

## 🔌 **API ARCHITECTURE**

### **Core Endpoints**
```python
# Session Management
POST   /api/v1/sessions/upload          # Upload raw session data
GET    /api/v1/sessions/status/<id>     # Get processing status
GET    /api/v1/sessions/processed/<uid> # Get processed sessions
GET    /api/v1/sessions/statistics/<uid># Get user statistics
DELETE /api/v1/sessions/<id>            # Delete session

# Health Monitoring
GET    /health                          # Basic health check
GET    /health/detailed                 # Comprehensive system status
```

### **HRV Metrics Calculation**
```python
def calculate_hrv_metrics(rr_intervals: List[float]) -> Dict[str, float]:
    """Calculate all 9 HRV metrics matching database schema"""
    return {
        "mean_hr": 60000.0 / np.mean(rr_intervals),
        "mean_rr": np.mean(rr_intervals),
        "count_rr": len(rr_intervals),
        "rmssd": np.sqrt(np.mean(np.diff(rr_intervals) ** 2)),
        "sdnn": np.std(rr_intervals, ddof=1),
        "pnn50": calculate_pnn50(rr_intervals),
        "cv_rr": (np.std(rr_intervals, ddof=1) / np.mean(rr_intervals)) * 100,
        "defa": calculate_dfa_alpha1(rr_intervals),
        "sd2_sd1": calculate_poincare_ratio(rr_intervals)
    }
```

### **Database Connection**
```python
# Supabase PostgreSQL with Transaction Pooler (IPv4 compatible)
DATABASE_URL = "postgresql://postgres.hmckwsyksbckxfxuzxca:PASSWORD@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
```

---

## 📱 **iOS ARCHITECTURE**

### **Core Components**
```swift
// Authentication (HTTP-based)
SupabaseAuthService.shared  // HTTP requests for auth operations

// Database Access (SDK-based)
DatabaseSessionManager      // PostgREST client for direct DB queries

// Data Models (Unified Schema)
struct DatabaseSession: Codable {
    let sessionId: String      // session_id
    let userId: String         // user_id
    let tag: String           // tag
    let subtag: String        // subtag
    let eventId: Int          // event_id
    // ... all 9 HRV metrics
}
```

### **Supabase Configuration**
```swift
struct SupabaseConfig {
    static let url = "https://hmckwsyksbckxfxuzxca.supabase.co"
    static let anonKey = "sb_publishable_oRjabmXPVvT5QMv_5Ec92A_Ytc6xrFr"
    
    // PostgREST client for database operations
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

### **Sessions Tab Implementation**
```swift
// Direct database queries using PostgREST
let response: [DatabaseSession] = try await authenticatedClient
    .from("sessions")
    .select("session_id, user_id, tag, subtag, ...")
    .eq("user_id", value: userId)
    .order("recorded_at", ascending: false)
    .execute()
    .value
```

---

## 🔐 **AUTHENTICATION ARCHITECTURE**

### **Hybrid Authentication Strategy**
1. **SupabaseAuthService**: HTTP-based authentication for signup/login
2. **DatabaseSessionManager**: Uses authenticated user tokens for database access
3. **Token Flow**: HTTP auth → JWT token → PostgREST Bearer authentication

```swift
// Authentication flow
let userToken = await SupabaseAuthService.shared.getCurrentAccessToken()
let authenticatedClient = PostgrestClient(
    url: URL(string: "\(SupabaseConfig.url)/rest/v1")!,
    headers: [
        "apikey": SupabaseConfig.anonKey,
        "Authorization": "Bearer \(userToken)"
    ]
)
```

---

## 🚀 **DEPLOYMENT ARCHITECTURE**

### **Railway API Deployment**
```toml
# nixpacks.toml
[phases.setup]
nixPkgs = ["python311", "postgresql"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "gunicorn --bind 0.0.0.0:$PORT app:app"
```

### **Environment Variables**
```bash
# Railway Environment
DATABASE_URL=postgresql://postgres.hmckwsyksbckxfxuzxca:PASSWORD@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://hmckwsyksbckxfxuzxca.supabase.co
SUPABASE_ANON_KEY=sb_publishable_oRjabmXPVvT5QMv_5Ec92A_Ytc6xrFr
PORT=8000
```

---

## 🔧 **CRITICAL FIXES IMPLEMENTED**

### **1. Date Decoding Fix (iOS)**
```swift
// Fixed iOS date parsing for API responses with microseconds + timezone
let iso8601Formatter = ISO8601DateFormatter()
iso8601Formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
```

### **2. PostgreSQL Array Format Fix (API)**
```python
# Fixed RR intervals storage - use native PostgreSQL arrays
cursor.execute("""
    INSERT INTO sessions (rr_intervals) VALUES (%s)
""", [rr_intervals])  # Python list → PostgreSQL DECIMAL[]
```

### **3. Authentication Token Fix (iOS)**
```swift
// Fixed PostgREST authentication with proper user tokens
guard let userToken = await SupabaseAuthService.shared.getCurrentAccessToken()
let authenticatedClient = PostgrestClient(headers: [
    "Authorization": "Bearer \(userToken)"
])
```

### **4. API Key Format Fix**
```swift
// Use correct anon key format (not JWT)
static let anonKey = "sb_publishable_oRjabmXPVvT5QMv_5Ec92A_Ytc6xrFr"
```

---

## 📊 **DATA FLOW ARCHITECTURE**

### **Session Recording → Processing → Display**
```
iOS Recording → Raw Session Upload → API Processing → Database Storage → iOS Display

1. iOS RecordingManager captures RR intervals
2. Session uploaded to API via HTTP POST
3. API calculates HRV metrics using NumPy
4. Processed session stored in PostgreSQL
5. iOS Sessions tab queries via PostgREST client
6. Data displayed in clean card-based UI
```

### **Session Data Model Evolution**
```
Raw Session (iOS) → API Processing → Database Storage → Display (iOS)

{                    {                 sessions table      DatabaseSession
  sessionId,         sessionId,        session_id,         sessionId,
  userId,            userId,           user_id,            userId,
  tag,               tag,              tag,                tag,
  rrIntervals        rrIntervals       mean_hr,            meanHr,
}                    }                 rmssd, ...          rmssd, ...
```

---

## 🧪 **TESTING & DEBUGGING**

### **iOS Debug Logging**
```swift
// Comprehensive debug information in Sessions tab
self.debugInfo.append("🔄 Starting Supabase Swift SDK session load")
self.debugInfo.append("🔐 Using authenticated user token")
self.debugInfo.append("📊 Database Schema: v5.0.0 FINAL")
```

### **API Health Monitoring**
```python
@app.route('/health/detailed')
def detailed_health():
    return {
        "status": "healthy",
        "database": "connected",
        "schema_version": "5.0.0",
        "deployment": "railway"
    }
```

---

## 🎯 **REBUILD CHECKLIST**

### **Database Setup**
- [ ] Deploy `database_schema_final.sql` to Supabase
- [ ] Configure Row Level Security policies
- [ ] Set up database functions and triggers
- [ ] Verify IPv4/Transaction Pooler connectivity

### **API Deployment**
- [ ] Deploy to Railway with `nixpacks.toml`
- [ ] Configure environment variables
- [ ] Test all endpoints with health checks
- [ ] Verify database connectivity

### **iOS Configuration**
- [ ] Install Supabase Swift SDK (PostgREST, Auth modules)
- [ ] Configure SupabaseConfig with correct keys
- [ ] Implement hybrid authentication pattern
- [ ] Test Sessions tab with PostgREST client

### **Integration Testing**
- [ ] End-to-end session recording → processing → display
- [ ] Authentication flow (signup → login → database access)
- [ ] Error handling and debug logging
- [ ] Performance and scalability testing

---

## 📚 **RELATED DOCUMENTATION**

- `database_schema_final.sql` - Complete database schema
- `README.md` - Deployment and setup instructions
- `admin_db_api_control.ipynb` - Admin management notebook
- iOS `DatabaseSessionManager.swift` - Direct database access implementation
- API `app.py` - Complete Flask application

---

**Last Updated**: 2025-08-04  
**Version**: 5.0.0 FINAL  
**Status**: Production Ready  
**Maintainer**: Atriom.Studio
