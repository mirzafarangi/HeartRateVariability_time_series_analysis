**Final Clean API + Chart Architecture for HRV Trend Analysis (v1.0)**

**Author:** System Architect - HRV Project\
**Date:** 2025-08-07\
**Version:** 1.0 - Stable Production Planning\
**Scope:** RMSSD trend plots (Non-sleep, Sleep Interval, Sleep Event)

---

## I. OBJECTIVE

Design a fully centralized and production-grade pipeline to support RMSSD-based HRV visualizations, covering three clinical scenarios:

- Non-sleep session trend
- Sleep interval trend (within one event)
- Sleep event (aggregated) trend

With full support for:

- Clean Swift Charts rendering
- Overlay features: rolling average, baseline, SD bands, percentiles
- Scalable data architecture
- Unified API responses

---

## II. DATABASE DESIGN (PostgreSQL via Supabase)

**A. sessions Table (Already Finalized)**

- All data is session-based
- Tags: `rest`, `sleep`, etc.
- `event_id`: groups multiple sleep intervals
- HRV metrics stored in normalized columns: `rmssd`, `sdnn`, etc.

**B. Required Indexes**

- `idx_rest_trend` → for non-sleep plots
- `idx_sleep_event_intervals` → for sleep interval plots
- `idx_sleep_baseline`, `idx_sleep_event` → for event aggregation

**C. Derived Table (View or Materialized View)**

- Create a view `aggregated_sleep_events`:

```sql
CREATE VIEW aggregated_sleep_events AS
SELECT
  user_id,
  event_id,
  MIN(recorded_at) AS event_start,
  MAX(recorded_at) AS event_end,
  AVG(rmssd) AS avg_rmssd
FROM sessions
WHERE tag = 'sleep' AND event_id > 0
GROUP BY user_id, event_id;
```

---

## III. API DESIGN (Python Backend - Flask)

**A. New Endpoints**

| Endpoint                            | Description                                         |
| ----------------------------------- | --------------------------------------------------- |
| `GET /api/v1/trends/rest`           | Non-sleep session trend                             |
| `GET /api/v1/trends/sleep-interval` | Sleep intervals trend (all intervals of last event) |
| `GET /api/v1/trends/sleep-event`    | Aggregated sleep event trend                        |

**B. Common JSON Response Schema**

All endpoints return this exact format:

```json
{
  "raw": [
    { "date": "2025-08-05", "rmssd": 42.1 },
    { "date": "2025-08-06", "rmssd": 44.3 }
  ],
  "rolling_avg": [
    { "date": "2025-08-06", "rmssd": 43.2 }
  ],
  "baseline": 44.0,
  "sd_band": {
    "upper": 46.0,
    "lower": 42.0
  },
  "percentile_10": 40.0,
  "percentile_90": 49.0
}
```

**C. Backend Responsibilities**

- Rolling avg (trailing N=3)
- Sleep baseline: only for `/sleep-interval` and `/sleep-event`
- SD band: use ±1 SD around 7-day average
- Percentiles: require minimum 30 sessions
- If data not available (e.g., no baseline), skip field in JSON

---

## IV. FRONTEND ARCHITECTURE (Swift Charts)

**A. Structure**

- Each chart is fed from one endpoint response
- Charts are modular: one generic Chart component renders all 3 plot types
- ViewModel fetches from API, parses into observable state

**B. Visual Layers (Each Chart)**

| Layer             | Element              | Style               |
| ----------------- | -------------------- | ------------------- |
| Raw RMSSD         | PointMark + LineMark | Solid Blue          |
| Rolling Avg       | LineMark             | Dashed Blue.opacity |
| Baseline          | RuleMark             | Solid Gray          |
| SD Band           | AreaMark             | Blue.opacity fill   |
| 10/90 Percentiles | RuleMark             | Dashed Gray         |

**C. Logic**

- Chart renders what the API provides
- If `baseline` is null → skip line
- If `percentile_10` missing → skip reference lines

---

## V. THREE PLOT SCENARIOS

### 1. Non-Sleep Session Trend

- Source: sessions table
- Filter: tag = 'rest', event\_id = 0
- X-axis: `recorded_at`
- Y-axis: `rmssd`
- Overlays:
  - Rolling avg: enabled if ≥3 points
  - No baseline (non-sleep)
  - No SD band
  - Percentiles optional if ≥30

### 2. Sleep Interval Trend

- Source: sessions table
- Filter: tag = 'sleep', event\_id = last N (default = latest)
- X-axis: `recorded_at`
- Y-axis: `rmssd`
- Overlays:
  - Rolling avg
  - Sleep 7-day baseline (computed from all sleep data)
  - SD Band: ±1 SD from 7-day baseline
  - Percentiles: optional if enough data

### 3. Sleep Event Aggregated Trend

- Source: aggregated\_sleep\_events view (or raw query)
- X-axis: `event_start`
- Y-axis: average RMSSD per event
- Overlays:
  - Rolling avg: over event means
  - Baseline: optional 7-event baseline
  - SD Band: ±1 SD of event averages
  - Percentiles: only if ≥30 events

---

## VI. Summary of Clean Architecture Principles

| Principle              | Achieved? | Mechanism                                   |
| ---------------------- | --------- | ------------------------------------------- |
| Single source of truth | ✅         | Backend owns full HRV logic                 |
| Clear layering         | ✅         | API → ViewModel → SwiftUI Charts            |
| No spaghetti           | ✅         | Single component renders all three charts   |
| Scalable               | ✅         | Add SDNN, pNN50, etc. using same pattern    |
| Visual clarity         | ✅         | Consistent color, layers, legend, fallbacks |

---

## VII. Implementation Notes

- API should use cached queries (daily refresh recommended)
- iOS should cache last received JSON in local storage (for offline view)
- Initial chart load = load from cache, then refresh on button tap
- All API JSONs must return only numerical values — no images, no rendering hints

---


This concludes the clean, scalable, and centralized HRV trend plotting pipeline — fully production-ready, with modular extensibility.

