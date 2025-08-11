# Baseline Analytics Endpoint Blueprint v5.3.1

## Overview
The baseline analytics endpoint provides comprehensive HRV baseline analysis for wake_check sessions, supporting both fixed m-point and dynamic n-point rolling baseline models with statistical bands, trend analysis, and multi-metric support.

## Endpoint Definition

### URL
```
GET /api/v1/analytics/baseline
```

### Purpose
Compute and return baseline statistics for wake_check sessions, including:
- Fixed baseline statistics from the most recent m sessions
- Dynamic rolling baseline with n-point window for each session
- Trend analysis comparing current values to baselines
- Statistical significance and direction indicators
- SD bands for visualization (±1 SD and ±2 SD)

## Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `user_id` | UUID | Yes | - | User identifier |
| `m` | Integer | No | 14 | Number of sessions for fixed baseline (1-30) |
| `n` | Integer | No | 7 | Rolling window size for dynamic baseline (3-14) |
| `metrics` | String | No | "rmssd,sdnn,sd2_sd1,mean_hr" | Comma-separated metric names |
| `max_sessions` | Integer | No | 300 | Maximum sessions in response (10-500) |

### Supported Metrics
- `rmssd` - Root Mean Square of Successive Differences
- `sdnn` - Standard Deviation of NN intervals  
- `sd2_sd1` - Ratio of SD2 to SD1 (Poincaré plot)
- `mean_hr` - Mean Heart Rate
- `pnn50` - Percentage of successive differences > 50ms
- `cv_rr` - Coefficient of Variation of RR intervals
- `defa` - Detrended Fluctuation Analysis
- `mean_rr` - Mean RR interval

### Validation Rules
- `user_id` must be valid UUID format
- `m` must be between 1 and 30
- `n` must be between 3 and 14
- `n` cannot exceed `m`
- `metrics` must contain valid metric names
- `max_sessions` must be between 10 and 500

## Response Structure

### Success Response (200 OK)
```json
{
  "status": "success",
  "api_version": "5.3.1",
  "user_id": "7015839c-4659-4b6c-821c-2906e710a2db",
  "tag": "wake_check",
  "metrics": ["rmssd", "sdnn", "sd2_sd1", "mean_hr"],
  "m_points_requested": 14,
  "m_points_actual": 12,
  "n_points_requested": 7,
  "n_points_actual": 7,
  "total_sessions": 238,
  "max_sessions_applied": 300,
  "updated_at": "2025-08-21T21:00:00Z",
  "fixed_baseline": { /* ... */ },
  "dynamic_baseline": [ /* ... */ ],
  "warnings": [ /* ... */ ],
  "notes": { /* ... */ }
}
```

### Fixed Baseline Structure
For each requested metric, provides comprehensive statistics:

```json
"fixed_baseline": {
  "rmssd": {
    "count": 12,
    "mean": 45.2,
    "sd": 12.3,
    "median": 43.8,
    "sd_median": 11.5,
    "mean_minus_1sd": 32.9,
    "mean_plus_1sd": 57.5,
    "mean_minus_2sd": 20.6,
    "mean_plus_2sd": 69.8,
    "median_minus_1sd": 32.3,
    "median_plus_1sd": 55.3,
    "median_minus_2sd": 20.8,
    "median_plus_2sd": 66.8,
    "min": 21.3,
    "max": 73.4,
    "range": 52.1
  }
}
```

#### Fixed Baseline Fields
- `count` - Number of sessions used (≤ m)
- `mean` - Arithmetic mean of metric values
- `sd` - Standard deviation
- `median` - Median value
- `sd_median` - Median Absolute Deviation × 1.4826
- `mean_minus_1sd` - Lower 1 SD band (mean-based)
- `mean_plus_1sd` - Upper 1 SD band (mean-based)
- `mean_minus_2sd` - Lower 2 SD band (mean-based)
- `mean_plus_2sd` - Upper 2 SD band (mean-based)
- `median_minus_1sd` - Lower 1 SD band (median-based)
- `median_plus_1sd` - Upper 1 SD band (median-based)
- `median_minus_2sd` - Lower 2 SD band (median-based)
- `median_plus_2sd` - Upper 2 SD band (median-based)
- `min` - Minimum value in baseline
- `max` - Maximum value in baseline
- `range` - max - min

**Note**: All statistics except `count` are `null` when count < 5 (insufficient data).

### Dynamic Baseline Structure
Array of session objects, ordered by timestamp (oldest to newest):

```json
"dynamic_baseline": [
  {
    "session_id": "caa3...8b8",
    "timestamp": "2025-08-01T06:55:00Z",
    "duration_minutes": 5,
    "session_index": 221,
    "metrics": {
      "rmssd": 48.5,
      "sdnn": 55.2,
      "sd2_sd1": 1.45,
      "mean_hr": 60.5
    },
    "rolling_stats": { /* ... */ },
    "trends": { /* ... */ },
    "flags": [],
    "tags": ["wake_check_single"]
  }
]
```

#### Session Fields
- `session_id` - Unique session identifier
- `timestamp` - ISO 8601 UTC timestamp
- `duration_minutes` - Session duration
- `session_index` - 1-based index in user's history
- `metrics` - Current session metric values
- `rolling_stats` - n-point rolling window statistics
- `trends` - Comparison to baselines
- `flags` - Special condition indicators
- `tags` - Session classification tags

### Rolling Statistics Structure
For each metric, computed from n previous sessions:

```json
"rolling_stats": {
  "rmssd": {
    "window_size": 7,
    "mean": 46.3,
    "sd": 8.2,
    "mean_minus_1sd": 38.1,
    "mean_plus_1sd": 54.5,
    "mean_minus_2sd": 29.9,
    "mean_plus_2sd": 62.7
  }
}
```

#### Rolling Stats Fields
- `window_size` - Actual window size used (≤ n)
- `mean` - Rolling mean
- `sd` - Rolling standard deviation
- `mean_minus_1sd` - Lower 1 SD band
- `mean_plus_1sd` - Upper 1 SD band
- `mean_minus_2sd` - Lower 2 SD band
- `mean_plus_2sd` - Upper 2 SD band

### Trends Structure
Comparison of current value to baselines:

```json
"trends": {
  "rmssd": {
    "delta_vs_fixed": 3.3,
    "pct_vs_fixed": 7.3,
    "delta_vs_rolling": 2.2,
    "pct_vs_rolling": 4.9,
    "z_fixed": 0.27,
    "z_rolling": 0.27,
    "direction": "above_baseline",
    "significance": "not_significant"
  }
}
```

#### Trend Fields
- `delta_vs_fixed` - Absolute difference from fixed mean
- `pct_vs_fixed` - Percentage change from fixed mean
- `delta_vs_rolling` - Absolute difference from rolling mean
- `pct_vs_rolling` - Percentage change from rolling mean
- `z_fixed` - Z-score relative to fixed baseline
- `z_rolling` - Z-score relative to rolling baseline
- `direction` - "above_baseline", "below_baseline", or "at_baseline"
- `significance` - "significant" (|z| > 2), "notable" (|z| > 1), or "not_significant"

**Note**: Deltas and percentages are `null` when baselines have insufficient data.

### Warnings Array
Informational messages about data processing:

```json
"warnings": [
  "rmssd: fixed bands hidden (count < 5)",
  "max_sessions=300 applied (payload truncated)",
  "max_sessions=50 is below recommended minimum of 100"
]
```

### Notes Object
Methodology and interpretation guidance:

```json
"notes": {
  "method": "SD_median computed as MAD × 1.4826",
  "bands": "±1 SD and ±2 SD envelopes for fixed mean and rolling mean",
  "insufficient_band_rule": "Bands hidden for metrics with <5 points"
}
```

## Error Responses

### 400 Bad Request
Invalid parameters or validation failure:

```json
{
  "error": "Invalid user_id format",
  "details": "user_id must be a valid UUID"
}
```

### 404 Not Found
No data available:

```json
{
  "error": "No wake_check sessions found for user"
}
```

### 500 Internal Server Error
Database or processing error:

```json
{
  "error": "Analytics query failed"
}
```

## Complete Examples

### Example 1: Default Parameters
**Request:**
```bash
GET /api/v1/analytics/baseline?user_id=7015839c-4659-4b6c-821c-2906e710a2db
```

**Response:**
```json
{
  "status": "success",
  "api_version": "5.3.1",
  "user_id": "7015839c-4659-4b6c-821c-2906e710a2db",
  "tag": "wake_check",
  "metrics": ["rmssd", "sdnn", "sd2_sd1", "mean_hr"],
  "m_points_requested": 14,
  "m_points_actual": 14,
  "n_points_requested": 7,
  "n_points_actual": 7,
  "total_sessions": 156,
  "max_sessions_applied": null,
  "updated_at": "2025-08-11T19:30:00Z",
  "fixed_baseline": {
    "rmssd": {
      "count": 14,
      "mean": 42.5,
      "sd": 8.3,
      "median": 41.2,
      "sd_median": 7.8,
      "mean_minus_1sd": 34.2,
      "mean_plus_1sd": 50.8,
      "mean_minus_2sd": 25.9,
      "mean_plus_2sd": 59.1,
      "median_minus_1sd": 33.4,
      "median_plus_1sd": 49.0,
      "median_minus_2sd": 25.6,
      "median_plus_2sd": 56.8,
      "min": 28.4,
      "max": 58.7,
      "range": 30.3
    },
    "sdnn": { /* similar structure */ },
    "sd2_sd1": { /* similar structure */ },
    "mean_hr": { /* similar structure */ }
  },
  "dynamic_baseline": [
    {
      "session_id": "abc123",
      "timestamp": "2025-08-10T06:30:00Z",
      "duration_minutes": 5,
      "session_index": 143,
      "metrics": {
        "rmssd": 44.2,
        "sdnn": 52.1,
        "sd2_sd1": 1.38,
        "mean_hr": 62.3
      },
      "rolling_stats": {
        "rmssd": {
          "window_size": 7,
          "mean": 43.1,
          "sd": 6.2,
          "mean_minus_1sd": 36.9,
          "mean_plus_1sd": 49.3,
          "mean_minus_2sd": 30.7,
          "mean_plus_2sd": 55.5
        }
        /* other metrics */
      },
      "trends": {
        "rmssd": {
          "delta_vs_fixed": 1.7,
          "pct_vs_fixed": 4.0,
          "delta_vs_rolling": 1.1,
          "pct_vs_rolling": 2.6,
          "z_fixed": 0.20,
          "z_rolling": 0.18,
          "direction": "above_baseline",
          "significance": "not_significant"
        }
        /* other metrics */
      },
      "flags": [],
      "tags": ["wake_check_single"]
    }
    /* ... more sessions ... */
  ],
  "warnings": [],
  "notes": {
    "method": "SD_median computed as MAD × 1.4826",
    "bands": "±1 SD and ±2 SD envelopes for fixed mean and rolling mean",
    "insufficient_band_rule": "Bands hidden for metrics with <5 points"
  }
}
```

### Example 2: Custom Parameters with Limited Data
**Request:**
```bash
GET /api/v1/analytics/baseline?user_id=7015839c-4659-4b6c-821c-2906e710a2db&m=10&n=5&metrics=rmssd,mean_hr&max_sessions=50
```

**Response:**
```json
{
  "status": "success",
  "api_version": "5.3.1",
  "user_id": "7015839c-4659-4b6c-821c-2906e710a2db",
  "tag": "wake_check",
  "metrics": ["rmssd", "mean_hr"],
  "m_points_requested": 10,
  "m_points_actual": 8,
  "n_points_requested": 5,
  "n_points_actual": 5,
  "total_sessions": 8,
  "max_sessions_applied": null,
  "updated_at": "2025-08-11T19:30:00Z",
  "fixed_baseline": {
    "rmssd": {
      "count": 8,
      "mean": 38.5,
      "sd": 5.2,
      /* ... rest of statistics ... */
    },
    "mean_hr": {
      "count": 8,
      "mean": 65.3,
      "sd": 4.8,
      /* ... rest of statistics ... */
    }
  },
  "dynamic_baseline": [
    /* 8 session objects with rolling_stats and trends */
  ],
  "warnings": [],
  "notes": {
    "method": "SD_median computed as MAD × 1.4826",
    "bands": "±1 SD and ±2 SD envelopes for fixed mean and rolling mean",
    "insufficient_band_rule": "Bands hidden for metrics with <5 points"
  }
}
```

### Example 3: Insufficient Data Response
**Request:**
```bash
GET /api/v1/analytics/baseline?user_id=new-user-uuid
```

**Response:**
```json
{
  "status": "success",
  "api_version": "5.3.1",
  "user_id": "new-user-uuid",
  "tag": "wake_check",
  "metrics": ["rmssd", "sdnn", "sd2_sd1", "mean_hr"],
  "m_points_requested": 14,
  "m_points_actual": 3,
  "n_points_requested": 7,
  "n_points_actual": 3,
  "total_sessions": 3,
  "max_sessions_applied": null,
  "updated_at": "2025-08-11T19:30:00Z",
  "fixed_baseline": {
    "rmssd": {
      "count": 3,
      "mean": null,
      "sd": null,
      "median": null,
      "sd_median": null,
      "mean_minus_1sd": null,
      "mean_plus_1sd": null,
      "mean_minus_2sd": null,
      "mean_plus_2sd": null,
      "median_minus_1sd": null,
      "median_plus_1sd": null,
      "median_minus_2sd": null,
      "median_plus_2sd": null,
      "min": null,
      "max": null,
      "range": null
    }
    /* other metrics with null values */
  },
  "dynamic_baseline": [
    /* 3 sessions with limited rolling_stats */
  ],
  "warnings": [
    "rmssd: fixed bands hidden (count < 5)",
    "sdnn: fixed bands hidden (count < 5)",
    "sd2_sd1: fixed bands hidden (count < 5)",
    "mean_hr: fixed bands hidden (count < 5)"
  ],
  "notes": {
    "method": "SD_median computed as MAD × 1.4826",
    "bands": "±1 SD and ±2 SD envelopes for fixed mean and rolling mean",
    "insufficient_band_rule": "Bands hidden for metrics with <5 points"
  }
}
```

## Implementation Details

### Data Processing Pipeline
1. **Session Retrieval**: Fetch all wake_check sessions for user from database
2. **Metric Extraction**: Extract requested metrics from each session
3. **Fixed Baseline Calculation**: Compute statistics from most recent m sessions
4. **Dynamic Baseline Processing**: For each session, calculate n-point rolling statistics
5. **Trend Analysis**: Compare current values to fixed and rolling baselines
6. **Response Truncation**: Apply max_sessions limit if needed
7. **Warning Generation**: Add informational messages about data processing

### Statistical Methods
- **Standard Deviation**: Population SD formula (N denominator)
- **Median Absolute Deviation**: MAD × 1.4826 for robust SD estimate
- **Z-Score**: (value - mean) / sd
- **Percentage Change**: ((new - old) / old) × 100
- **Significance Levels**: |z| > 2 (significant), |z| > 1 (notable)

### Performance Considerations
- Results are computed on-demand (not cached)
- Database query optimized with proper indexing
- Response size limited by max_sessions parameter
- Numeric values rounded to 2 decimal places

### Edge Cases
- **New Users**: Returns empty baselines with appropriate warnings
- **Insufficient Data**: Returns null statistics when count < 5
- **Missing Metrics**: Handles sessions with partial metric data
- **Large Datasets**: Truncates response with max_sessions parameter

## iOS Integration Guidelines

### Plotting Requirements
1. **Fixed Baseline Bands**: Plot mean ± 1SD and ± 2SD as horizontal reference lines
2. **Dynamic Values**: Plot session metrics as time series points
3. **Rolling Bands**: Overlay rolling mean ± 1SD as dynamic envelope
4. **Significance Markers**: Highlight points where |z| > 2
5. **Trend Indicators**: Show direction arrows for above/below baseline

### Data Refresh Strategy
- Poll endpoint on tab activation
- Cache response for 5 minutes
- Refresh after new wake_check session upload
- Show loading state during fetch

### Error Handling
- Display cached data if available during errors
- Show user-friendly messages for common errors
- Provide retry mechanism for network failures
- Fall back to limited view with available data

## Version History
- **v5.3.1** (Current): Production-ready baseline endpoint with complete statistics
- **v5.3.0**: Added dynamic baseline and trend analysis
- **v5.2.0**: Initial fixed baseline implementation

## Security Considerations
- User UUID validation prevents unauthorized access
- No PII exposed in response
- Rate limiting recommended (100 requests/minute)
- CORS configured for authorized origins only

## Future Enhancements
- Caching layer for improved performance
- Baseline comparison between time periods
- Anomaly detection algorithms
- Personalized baseline recommendations
- Export functionality for baseline data
