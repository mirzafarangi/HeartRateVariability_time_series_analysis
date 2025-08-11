# Trends Tab Architecture Guide

## 🎯 Architecture Decision: API-Only Approach

### Why Use API Instead of Direct Database Access?

1. **Security** - iOS app never sees DB credentials
2. **Consistency** - Single source of truth for business logic
3. **Performance** - API uses DB indexes automatically
4. **Caching** - API can cache results (future enhancement)
5. **Clean Architecture** - Separation of concerns

### How It Works

```
iOS App → API Endpoints → DB Functions → Indexed Queries
         ↓
    JSON Response
         ↓
    UI Display
```

## 📊 The 5 Analytics Models

### 1. Baseline Analytics
- **Endpoint:** `/api/v1/analytics/baseline`
- **DB Function:** `fn_baseline_points()`
- **Index Used:** `idx_sessions_user_time`
- **Data:** Wake check sessions over time
- **Purpose:** Track morning HRV trends

### 2. Micro-Sleep Analytics  
- **Endpoint:** `/api/v1/analytics/micro-sleep`
- **DB Function:** `fn_micro_sleep_points()`
- **Index Used:** `idx_sleep_event_interval_order`
- **Data:** Per-interval sleep HRV
- **Purpose:** Analyze sleep quality progression

### 3. Macro-Sleep Analytics
- **Endpoint:** `/api/v1/analytics/macro-sleep`
- **DB Function:** `fn_macro_sleep_points()`
- **Index Used:** `idx_sleep_latest_event`
- **Data:** Full night aggregation
- **Purpose:** Overall sleep quality score

### 4. Day-Load Analytics
- **Endpoint:** `/api/v1/analytics/day-load`
- **DB Function:** `fn_day_load_points()`
- **Index Used:** `idx_pairing_by_date`
- **Data:** Morning vs evening HRV
- **Purpose:** Daily stress accumulation

### 5. Experiment Analytics
- **Endpoint:** `/api/v1/analytics/experiment`
- **DB Function:** `fn_experiment_points()`
- **Index Used:** `idx_sessions_user_time`
- **Data:** Protocol effectiveness
- **Purpose:** A/B test interventions

## 🏗️ Implementation Structure

### View Layer (TrendsTabView.swift)
```swift
// Minimal, academic UI
// 5 cards displaying analytics
// Time window selector (7, 14, 30, 90 days)
// Pull-to-refresh functionality
```

### ViewModel Layer (TrendsViewModel.swift)
```swift
// Parallel API calls for performance
// Data processing and formatting
// Loading state management
// Error handling
```

### API Layer (APIClient.swift)
```swift
// 5 new analytics methods
// Query parameter construction
// Authentication headers
// JSON response handling
```

## 📈 Data Flow Example

```swift
// User opens Trends tab
TrendsTabView.onAppear()
    ↓
// ViewModel fetches all 5 models in parallel
TrendsViewModel.fetchAllAnalytics(window: 7)
    ↓
// API calls execute simultaneously
APIClient.fetchBaselineAnalytics()
APIClient.fetchMicroSleepAnalytics()
APIClient.fetchMacroSleepAnalytics()
APIClient.fetchDayLoadAnalytics()
APIClient.fetchExperimentAnalytics()
    ↓
// API queries database using indexes
GET /api/v1/analytics/baseline?user_id=X&metric=rmssd&window=7
    ↓
// Database executes optimized query
SELECT * FROM sessions WHERE user_id=X ORDER BY recorded_at
(Uses idx_sessions_user_time for O(log n) performance)
    ↓
// Results displayed in cards
AnalyticsCard shows primary metric, trend, secondary metrics
```

## 🎨 UI Design Principles

### Minimal Academic Style
- Clean cards with essential metrics
- No decorative elements
- Focus on data clarity
- Consistent spacing and typography

### Information Hierarchy
1. **Primary Value** - Large, bold (28pt)
2. **Trend Indicator** - Icon + text
3. **Secondary Metrics** - Small, supporting data
4. **Time Window** - Top selector

### Color Coding
- **Orange** - Baseline (morning)
- **Indigo** - Micro-sleep (intervals)
- **Purple** - Macro-sleep (full night)
- **Green** - Day-load (recovery)
- **Blue** - Experiments (protocols)

## 🚀 Performance Optimizations

### Parallel Execution
All 5 analytics calls run simultaneously:
```swift
await withTaskGroup(of: Void.self) { group in
    group.addTask { await self.fetchBaseline() }
    group.addTask { await self.fetchMicroSleep() }
    // ... etc
}
```

### Index Utilization
Each query uses specific indexes:
- No table scans
- O(log n) lookups
- Sorted results without sorting

### Caching Strategy (Future)
```swift
// In-memory cache for current session
// Redis cache for API layer
// 5-minute TTL for analytics
```

## 📝 Testing Your Implementation

### 1. Verify Data Availability
```bash
# Check you have all session types
curl "http://localhost:8000/api/v1/analytics/baseline?user_id=YOUR_ID&metric=rmssd&window=7"
```

### 2. Test Each Model
- Baseline: Requires wake_check sessions
- Micro-sleep: Requires sleep intervals
- Macro-sleep: Requires complete sleep events
- Day-load: Requires paired wake/pre-sleep
- Experiment: Requires experiment sessions

### 3. UI Verification
- All 5 cards should load
- Time window changes update all cards
- Pull-to-refresh works
- Error states handled gracefully

## 🔧 Troubleshooting

### No Data Showing?
1. Check UserDefaults has userId
2. Verify sessions exist in DB
3. Check API is running
4. Look for console errors

### Slow Performance?
1. Verify indexes exist in DB
2. Check network latency
3. Consider reducing window size
4. Add loading indicators

### Wrong Data?
1. Verify timezone handling (UTC)
2. Check metric parameter
3. Validate window calculation
4. Review data processing logic

## 📚 Key Takeaways

1. **Always use API** - Never direct DB access from iOS
2. **Leverage indexes** - They're already optimized
3. **Parallel calls** - Don't wait sequentially
4. **Clean UI** - Academic, minimal, focused
5. **Error handling** - Graceful degradation

This architecture ensures:
- ✅ Security (no DB credentials in app)
- ✅ Performance (indexed queries)
- ✅ Maintainability (single source of truth)
- ✅ Scalability (can add caching layer)
- ✅ Clean code (separation of concerns)
