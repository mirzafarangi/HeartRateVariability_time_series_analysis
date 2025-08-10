# Blueprint: Profile Tab Architecture
## LUMENIS Brain Control System

### Overview
The Profile tab serves as the intelligent control center for LUMENIS, the HRV Analyzer assistant. It features a minimal academic design with sophisticated real-time monitoring, secret interactions, and a unique brain control mechanism through the phi (φ) symbol.

---

## 1. Architecture Components

### 1.1 Core State Management
```swift
// Authentication & UI State
@StateObject private var authService = SupabaseAuthService.shared
@State private var showingSignOutAlert = false
@State private var showingErrorAlert = false
@State private var showingSuccessAlert = false

// LED Dashboard State
@State private var apiPulse = false      // Pulsing animation state
@State private var dbPulse = false       // Pulsing animation state
@State private var apiStatus = false     // API health status
@State private var dbStatus = false      // Database health status
@State private var isPhiChecking = false // Orange LED state during phi refresh

// Status Monitoring
@State private var statusLogs: [String] = []
@State private var lastCheckTime = Date()
@State private var isCheckingStatus = false

// Secret Signature Animation
@State private var phaseShift: Double = 0
```

### 1.2 Timer-Based Monitoring
```swift
private let timer = Timer.publish(every: 30, on: .main, in: .common).autoconnect()
```
- Automatic health checks every 30 seconds
- Non-intrusive background monitoring
- Maintains real-time status awareness

---

## 2. Visual Design System

### 2.1 Academic Minimal Aesthetic
- **Background**: Light gray (`Color(.systemGray6)`)
- **Typography**: Monospaced for technical data, ultralight for branding
- **Color Palette**: 
  - Black with opacity variations (0.1 - 0.8)
  - Status colors: Green (healthy), Red (error), Orange (checking)
  - Subtle white overlays for depth

### 2.2 Layout Structure
```
┌─────────────────────────────┐
│       LUMENIS               │  <- Branding header
│         ─────               │  <- Minimal divider
├─────────────────────────────┤
│  @ user@email.com           │  <- User identity
│  # UUID                     │
│  xxxxxxxx-xxxx-xxxx-xxxx    │
├─────────────────────────────┤
│  Auth: ● Connected          │  <- Authentication status
├─────────────────────────────┤
│  ┌─────┐     ┌─────┐       │  <- LED Dashboard
│  │ API │     │ DB  │       │
│  │  ●  │     │  ●  │       │
│  └─────┘     └─────┘       │
├─────────────────────────────┤
│  ┌─────────────────────┐   │  <- LUMENIS Log Box
│  │ Hello, I'm LUMENIS...│   │
│  │ Status: API:● DB:●   │   │
│  │ ─────────────────    │   │
│  │ [11:30:45] API: ✓    │   │
│  │ [11:30:45] DB: ✓     │   │
│  └─────────────────────┘   │
├─────────────────────────────┤
│           φ                 │  <- Secret phi button
│     1.618033988749...       │  <- Golden ratio
├─────────────────────────────┤
│       TERMINATE             │  <- Sign out
└─────────────────────────────┘
```

---

## 3. LED Dashboard System

### 3.1 LED State Machine
```swift
enum LEDState {
    case healthy    // Green - Service responding
    case error      // Red - Service down
    case checking   // Orange - Status check in progress
}
```

### 3.2 Visual Implementation
- **Dual-layer design**: 
  - Outer pulse ring (24x24 pts)
  - Inner status indicator (12x12 pts)
- **Animation**: Pulsing effect at 1.5s intervals
- **Color transitions**: Smooth state changes

### 3.3 LED Color Logic
```swift
// Main LED color determination
Circle()
    .fill(isPhiChecking ? Color.orange : (status ? Color.green : Color.red))

// Pulse ring color
Circle()
    .fill(isPhiChecking ? Color.orange.opacity(0.2) : 
          (pulse ? Color.green.opacity(0.2) : Color.clear))
```

---

## 4. LUMENIS Brain Control

### 4.1 Status Log Box Design
- **Integrated greeting**: "Hello, I'm LUMENIS, your HRV Analyzer assistant"
- **Inline status indicators**: Real-time API/DB status dots
- **Log history**: Last 4 status entries with timestamps
- **Visual styling**: 
  - White semi-transparent background
  - Rounded corners (6pt radius)
  - Subtle border stroke

### 4.2 Log Entry Format
```
[HH:mm:ss] API: ✓ | DB: ✗
  → API error: Connection timeout...
  → DB: Not authenticated
```

### 4.3 Status Messages
- Connection success: `✓` checkmark
- Connection failure: `✗` cross
- Error details: Prefixed with `→` arrow
- Truncated to 30 chars for long errors

---

## 5. Phi (φ) Secret Mechanism

### 5.1 Philosophy
The phi symbol represents the golden ratio (1.618...), symbolizing perfect harmony and balance. It serves as a hidden "brain restart" button for LUMENIS.

### 5.2 Interaction Flow
```swift
@MainActor
private func phiRefresh() async {
    // 1. Clear and reset
    statusLogs.removeAll()
    statusLogs.append("Got you! φ clicked - LUMENIS brain refresh initiated...")
    
    // 2. Set orange LED state
    isPhiChecking = true
    apiStatus = false
    dbStatus = false
    
    // 3. Visual feedback delay
    try? await Task.sleep(nanoseconds: 500_000_000)
    
    // 4. Execute health checks
    await checkSystemStatus()
    
    // 5. Reset to normal state
    isPhiChecking = false
    
    // 6. Completion message
    statusLogs.append("[timestamp] Brain refresh complete")
}
```

### 5.3 Visual Feedback
- **Rotation animation**: Continuous 360° rotation over 20 seconds
- **Subtle presence**: Low opacity (0.15) for the symbol
- **Click response**: Immediate orange LED feedback
- **Log interaction**: "Got you!" acknowledgment

---

## 6. Health Check Methods

### 6.1 API Health Check
```swift
private func checkAPIHealth() async -> Bool {
    // Target: Railway deployment
    let url = "https://hrv-brain-api-production.up.railway.app/health"
    
    // Simple HTTP GET request
    let (_, response) = try await URLSession.shared.data(from: url)
    
    // Success: HTTP 200
    // Failure: Any other status code or network error
}
```

### 6.2 Database Health Check
```swift
private func checkDBHealth() async -> Bool {
    // Step 1: Verify authentication
    guard authService.isAuthenticated else {
        statusLogs.append("  → DB: Not authenticated")
        return false
    }
    
    // Step 2: Get access token
    guard let token = await authService.getCurrentAccessToken() else {
        statusLogs.append("  → DB: No access token")
        return false
    }
    
    // Step 3: Create authenticated client
    let client = PostgrestClient(
        url: URL(string: "\(SupabaseConfig.url)/rest/v1")!,
        headers: ["Authorization": "Bearer \(token)"]
    )
    
    // Step 4: Test query
    let _ = try await client
        .from("sessions")
        .select("id", head: true)
        .limit(1)
        .execute()
}
```

---

## 7. Refresh Mechanisms

### 7.1 Automatic Refresh
- **Trigger**: Timer fires every 30 seconds
- **Behavior**: Silent background check
- **LED state**: Normal green/red based on results

### 7.2 Manual Refresh (Pull-to-Refresh)
- **Trigger**: User pulls down on status log
- **Behavior**: Standard iOS refresh gesture
- **LED state**: Normal status colors

### 7.3 Phi Refresh (Secret)
- **Trigger**: Tap on φ symbol
- **Behavior**: Complete brain restart
- **LED state**: Orange during check, then results
- **Special**: Clears all logs, shows greeting

---

## 8. User Identity Display

### 8.1 Email Display
```swift
HStack {
    Text("@")  // Prefix symbol
    Text(authService.userEmail ?? "null")
}
```

### 8.2 UUID Display
```swift
VStack {
    HStack {
        Text("#")     // Hash prefix
        Text("UUID")  // Label
    }
    Text(authService.userId ?? "00000000-0000-0000-0000-000000000000")
        .textCase(.lowercase)
}
```

### 8.3 Authentication Status
```swift
HStack {
    Circle()
        .fill(authService.isAuthenticated ? Color.green : Color.red)
        .frame(width: 8, height: 8)
    Text(authService.isAuthenticated ? "Connected" : "Disconnected")
}
```

---

## 9. Mathematical Easter Eggs

### 9.1 Lunar Phase Calculation
```swift
private var lunarPhase: Double {
    let knownNewMoon = Date(timeIntervalSince1970: 1704067200)
    let lunarCycle = 29.53059 * 24 * 60 * 60 // seconds
    let elapsed = now.timeIntervalSince(knownNewMoon)
    return (elapsed.truncatingRemainder(dividingBy: lunarCycle)) / lunarCycle
}
```
- Hidden lunar phase tracking
- Represents collaboration cycles
- Not visible in UI (internal calculation)

### 9.2 Golden Ratio Display
- φ = 1.618033988749...
- Symbol of mathematical perfection
- Secret interaction trigger

---

## 10. Error Handling

### 10.1 Network Errors
- Graceful degradation to red LED
- Error message in status log
- Truncated to prevent overflow

### 10.2 Authentication Errors
- Clear messaging: "Not authenticated"
- Red status indicator
- Prevents database queries

### 10.3 Token Expiration
- Detected during health check
- Logged as "No access token"
- Triggers re-authentication flow

---

## 11. Performance Optimizations

### 11.1 Debouncing
- Phi refresh has 0.5s delay for visual feedback
- Prevents rapid repeated triggers

### 11.2 Log Management
- Maximum 20 entries retained
- Automatic cleanup of old entries
- Memory efficient string storage

### 11.3 Animation Efficiency
- Uses SwiftUI native animations
- Hardware accelerated transforms
- Minimal CPU usage for continuous rotation

---

## 12. Security Considerations

### 12.1 Token Handling
- Access tokens fetched on-demand
- Never stored in state
- Cleared on sign out

### 12.2 API Endpoints
- Health check is unauthenticated (public)
- Database queries require valid JWT
- Row-level security enforced

### 12.3 User Privacy
- UUID displayed but truncated visually
- Email shown only to authenticated user
- No sensitive data in logs

---

## Summary

The Profile tab represents a sophisticated blend of minimal academic design and powerful functionality. Through the LUMENIS brain control system, users have both automatic monitoring and secret manual control via the phi mechanism. The LED dashboard provides instant visual feedback, while the integrated log box maintains a conversation-like interaction with the intelligent assistant.

Key innovations:
- **Phi refresh**: Secret brain restart mechanism
- **LED state machine**: Three-color status system
- **LUMENIS personality**: Conversational log interactions
- **Academic aesthetic**: Clean, scientific, professional
- **Real-time monitoring**: 30-second automatic health checks

This architecture creates a unique user experience that feels both professional and secretly playful, embodying the spirit of scientific exploration with hidden depths of functionality.
