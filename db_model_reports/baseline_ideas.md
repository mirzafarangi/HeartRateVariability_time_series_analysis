Below is a clean, implementation-ready blueprint for your baseline API (using your canonical naming and DB v4.1). It is aligned exactly to the Baseline Tab — Final Product Blueprint you approved, and it avoids terms like “enhanced.” It defines one endpoint—/api/v1/analytics/baseline—that returns everything your iOS Baseline tab needs for the four metrics (RMSSD, SDNN, SD2/SD1, Min HR): fixed (m-point) baseline stats + dynamic (n-point) rolling series, in a compact, predictable schema.

⸻

1) Endpoint

GET /api/v1/analytics/baseline

Purpose
Provide all inputs needed to render the Baseline tab for wake_check sessions:
	•	Fixed baseline (m-point) statistics and constant bands per metric
	•	Dynamic baseline (n-point rolling) per-session values + rolling stats per metric
	•	Light, ready-to-plot structure (no client computation required beyond drawing)

Tag scope: tag='wake_check' only.

⸻

2) Query Parameters

Param	Type	Required	Default	Notes
user_id	UUID	Yes	—	Must pass UUID validation.
m	int	No	14	Fixed baseline window. Uses last m valid sessions per metric. Min 3.
n	int	No	7	Rolling window size for dynamic stats. Min 2.
metrics	CSV list	No	rmssd,sdnn,sd2_sd1,mean_hr	Must be a subset of VALID_METRICS (9). Unknowns ignored with warning.
max_sessions	int	No	null (no cap)	Optional server-side cap on returned dynamic sessions (latest K by time). This is a payload control; not a modeling parameter.
tz	string	No	UTC	Formatting hint for timestamps in any server-side summaries (payload still returns ISO with offsets).

Validation bounds
	•	m: 3–200 (reject outside)
	•	n: 2–200 (reject outside)
	•	max_sessions: ≥ 10 if provided (soft minimum; else ignore and warn)

⸻

3) Response (200 OK)

Top-level envelope:

{
  "status": "success",
  "api_version": "5.3.1",
  "user_id": "....",
  "tag": "wake_check",
  "metrics": ["rmssd","sdnn","sd2_sd1","mean_hr"],
  "m_points_requested": 14,
  "m_points_actual": 12,
  "n_points_requested": 7,
  "n_points_actual": 7,
  "total_sessions": 238,
  "max_sessions_applied": null,
  "updated_at": "2025-08-21T21:00:00Z",
  "fixed_baseline": { /* per-metric stats */ },
  "dynamic_baseline": [ /* per-session rows */ ],
  "warnings": [ /* optional strings */ ],
  "notes": {
    "method": "SD_median computed as MAD × 1.4826",
    "bands": "±1 SD and ±2 SD envelopes for fixed mean and rolling mean",
    "insufficient_band_rule": "Bands hidden for metrics with <5 points"
  }
}

3.1 fixed_baseline (per metric)

Constant (flat) reference computed from the last m valid values for that metric among wake_check:

"fixed_baseline": {
  "rmssd": {
    "count": 12,
    "mean": 45.2,
    "sd": 12.3,
    "median": 43.8,
    "sd_median": 11.5,                 // MAD * 1.4826
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
  },
  "sdnn": { /* same fields */ },
  "sd2_sd1": { /* same fields */ },
  "mean_hr": { /* same fields */ }
}

Notes
	•	m_points_actual may be < m_points_requested if there are fewer than m valid metric values.
	•	If count < 5, clients should hide fixed SD bands for that metric.

3.2 dynamic_baseline (per session)

Sorted ascending by recorded_at (chronological). Each row carries the raw values for requested metrics, plus rolling stats (window n) for those metrics.

"dynamic_baseline": [
  {
    "session_id": "caa3...8b8",
    "timestamp": "2025-08-01T06:55:00Z",
    "duration_minutes": 5,
    "session_index": 1,                 // chronological index across wake_check
    "metrics": {
      "rmssd": 48.5,
      "sdnn": 55.2,
      "sd2_sd1": 1.45,
      "mean_hr": 60.5
    },
    "rolling_stats": {
      "rmssd": {
        "window_size": 7,
        "mean": 46.3,
        "sd": 8.2,
        "mean_minus_1sd": 38.1,
        "mean_plus_1sd": 54.5,
        "mean_minus_2sd": 29.9,
        "mean_plus_2sd": 62.7
      },
      "sdnn": { /* same fields */ },
      "sd2_sd1": { /* same fields */ },
      "mean_hr": { /* same fields */ }
    },
    "trends": {
      "rmssd": {
        "delta_vs_fixed": 3.3,            // value - fixed.mean
        "pct_vs_fixed": 7.3,              // 100*delta/fixed.mean
        "delta_vs_rolling": 2.2,          // value - rolling.mean
        "pct_vs_rolling": 4.9,            // 100*delta/rolling.mean
        "z_fixed": 0.27,                  // (value - fixed.mean)/fixed.sd  (if sd>0)
        "z_rolling": 0.27,                // (value - roll.mean)/roll.sd   (if sd>0)
        "direction": "above_baseline",    // above_baseline | below_baseline | stable
        "significance": "not_significant" // per thresholds in §6.3
      },
      "sdnn": { /* same */ },
      "sd2_sd1": { /* same */ },
      "mean_hr": { /* same */ }
    },
    "flags": ["artifact_corrected"],      // optional
    "tags": ["wake_check_single"]         // mirrors canonical subtag if helpful
  }
  // ...
]

Payload control
If max_sessions is provided, only the latest K sessions (post-computation) are returned; session_index still reflects global ordering (i.e., it is not re-based to 1).

⸻

4) Computation Details

4.1 Data selection
	•	Source: public.sessions
	•	Filter: user_id = :user_id AND tag = 'wake_check'
	•	Order: ORDER BY recorded_at ASC
	•	Valid value rule: include a metric value only if not NULL and within chk_metric_ranges_soft.

4.2 Fixed baseline (m-point)
	•	For each metric, take last m non-null values by recorded_at.
	•	Compute:
	•	mean, sd (population SD or sample SD; schema uses STDDEV_POP in rolling; use population SD consistently)
	•	median, sd_median = MAD × 1.4826
	•	Bands: mean ± {1,2}×sd; median ± {1,2}×sd_median
	•	min, max, range, count
	•	If count < 5, return stats but flag that bands are statistically weak; clients hide ribbons.

4.3 Dynamic baseline (n-point rolling)
	•	Use DB function: public.fn_baseline_points(p_user_id, p_metric, p_window := n)
	•	Returns per-point t (timestamp), value, rolling_avg, rolling_sd.
	•	Join each returned row to the corresponding session (session_id, duration_minutes), and compute session_index as the 1-based rank over all wake_check sessions by time.
	•	For each metric at each session:
	•	Rolling bands: rolling_avg ± {1,2}×rolling_sd
	•	delta_vs_fixed = value - fixed.mean (if fixed count ≥ 1)
	•	pct_vs_fixed = 100 * delta_vs_fixed / fixed.mean (if fixed.mean ≠ 0)
	•	delta_vs_rolling = value - rolling_avg (if rolling available)
	•	pct_vs_rolling = 100 * delta_vs_rolling / rolling_avg (if rolling_avg ≠ 0)
	•	z_fixed = (value - fixed.mean) / fixed.sd (if fixed.sd > 0)
	•	z_rolling = (value - rolling_avg) / rolling_sd (if rolling_sd > 0)

4.4 Direction & significance (for KPI and tooltips)
	•	Direction (vs fixed):
	•	If |delta_vs_fixed| / fixed.mean < 0.05 → stable
	•	Else if delta_vs_fixed > 0 → above_baseline
	•	Else → below_baseline
	•	Significance (z vs fixed if possible; else vs rolling):
	•	|z| >= 2.58 → highly_significant (p<0.01, two-tailed, normal approx)
	•	|z| >= 1.96 → significant      (p<0.05)
	•	|z| >= 1.64 → marginally_significant (p<0.10)
	•	else not_significant

⸻

5) Error Handling
	•	400 Bad Request
	•	Missing user_id, invalid UUID format
	•	Invalid m, n, max_sessions bounds
	•	Invalid metrics values (return 400 if none valid; else proceed and add a warnings entry)
	•	404 Not Found
	•	No wake_check sessions for user
	•	200 Success with warnings
	•	m_points_actual < m_points_requested
	•	n_points_actual < n_points_requested
	•	max_sessions_applied truncated the returned rows
	•	Metrics dropped due to no valid values
	•	500
	•	Database failures (propagate a generic message and log details server-side)

Example warning payload:

"warnings": [
  "metrics[pnn50] ignored (not requested)",
  "rmssd: fixed bands hidden (count < 5)",
  "max_sessions=300 applied (payload truncated)"
]


⸻

6) Implementation Notes (Server)

6.1 SQL usage
	•	Rolling: call public.fn_baseline_points once per requested metric with p_window = n.
	•	Fixed: select last m valid values per metric from sessions and compute stats in SQL (or fetch and compute in Python; SQL is preferred for consistency/perf).
	•	Join to sessions to retrieve session_id, duration_minutes, subtag, etc.

6.2 Parameter normalization
	•	Accept metrics in any case; normalize to lowercase.
	•	Deduplicate metrics; keep original order if provided; else use default [rmssd, sdnn, sd2_sd1, mean_hr].

6.3 Limits & performance
	•	If max_sessions is provided, compute stats on full data, then truncate returned array to latest K sessions (do not affect modeling).
	•	Consider server cap (e.g., 10k sessions) with a clear warning if exceeded.

6.4 Timezones
	•	All timestamps in payload are ISO 8601 with timezone (UTC recommended).
	•	Client can format to local time; server does not localize data labels.

⸻

7) Contract → iOS Rendering Map
	•	KPI chips: For each metric, the client takes the last element of dynamic_baseline to read:
	•	metrics[metric] → latest value
	•	trends[metric].delta_vs_fixed, pct_vs_fixed
	•	trends[metric].delta_vs_rolling, pct_vs_rolling
	•	trends[metric].direction + significance
	•	Plots (4 stacked):
	•	X = session_index (equal spacing).
	•	Top axis sparse datetime = timestamp from every ~5th row in dynamic_baseline.
	•	Y:
	•	Dots: metrics[metric]
	•	Dashed line: rolling_stats[metric].mean
	•	Fixed mean: fixed_baseline[metric].mean (horizontal rule)
	•	Bands:
	•	Rolling ribbons: rolling mean ± {1,2}×rolling sd per row
	•	Fixed ribbons: use constant fixed_baseline[metric].mean ± {1,2}×fixed sd across x (hide if count < 5)
	•	Table:
	•	One row per element of dynamic_baseline with columns for Session #, DateTime, the four metrics, and select rolling values (e.g., rolling mean for RMSSD, SDNN).

⸻

8) Example Minimal Success Response (trimmed)

{
  "status": "success",
  "api_version": "5.3.1",
  "user_id": "7015839c-4659-4b6c-821c-2906e710a2db",
  "tag": "wake_check",
  "metrics": ["rmssd","sdnn","sd2_sd1","mean_hr"],
  "m_points_requested": 14,
  "m_points_actual": 12,
  "n_points_requested": 7,
  "n_points_actual": 7,
  "total_sessions": 238,
  "max_sessions_applied": 300,
  "updated_at": "2025-08-21T21:00:00Z",
  "fixed_baseline": {
    "rmssd": {
      "count": 12, "mean": 45.2, "sd": 12.3, "median": 43.8, "sd_median": 11.5,
      "mean_minus_1sd": 32.9, "mean_plus_1sd": 57.5,
      "mean_minus_2sd": 20.6, "mean_plus_2sd": 69.8,
      "median_minus_1sd": 32.3, "median_plus_1sd": 55.3,
      "median_minus_2sd": 20.8, "median_plus_2sd": 66.8,
      "min": 21.3, "max": 73.4, "range": 52.1
    },
    "sdnn": { /* ... */ },
    "sd2_sd1": { /* ... */ },
    "mean_hr": { /* ... */ }
  },
  "dynamic_baseline": [
    {
      "session_id": "caa3...8b8",
      "timestamp": "2025-08-01T06:55:00Z",
      "duration_minutes": 5,
      "session_index": 221,
      "metrics": { "rmssd": 48.5, "sdnn": 55.2, "sd2_sd1": 1.45, "mean_hr": 60.5 },
      "rolling_stats": {
        "rmssd": {
          "window_size": 7, "mean": 46.3, "sd": 8.2,
          "mean_minus_1sd": 38.1, "mean_plus_1sd": 54.5,
          "mean_minus_2sd": 29.9, "mean_plus_2sd": 62.7
        },
        "sdnn": { /* ... */ },
        "sd2_sd1": { /* ... */ },
        "mean_hr": { /* ... */ }
      },
      "trends": {
        "rmssd": {
          "delta_vs_fixed": 3.3, "pct_vs_fixed": 7.3,
          "delta_vs_rolling": 2.2, "pct_vs_rolling": 4.9,
          "z_fixed": 0.27, "z_rolling": 0.27,
          "direction": "above_baseline", "significance": "not_significant"
        },
        "sdnn": { /* ... */ },
        "sd2_sd1": { /* ... */ },
        "mean_hr": { /* ... */ }
      },
      "flags": [],
      "tags": ["wake_check_single"]
    }
    /* ... latest K rows if max_sessions applied ... */
  ],
  "warnings": [
    "rmssd: fixed bands hidden (count < 5)",
    "max_sessions=300 applied (payload truncated)"
  ],
  "notes": {
    "method": "SD_median computed as MAD × 1.4826",
    "bands": "±1 SD and ±2 SD envelopes for fixed mean and rolling mean",
    "insufficient_band_rule": "Bands hidden for metrics with <5 points"
  }
}


⸻

9) Security & Operational Notes
	•	Auth/RLS: Use service role on server to bypass RLS for analytics reads; or ensure policies allow user-scoped reads.
	•	Throughput: Call fn_baseline_points once per requested metric; use a single connection and reuse where possible.
	•	Numerics: Cast DB decimals to floats in JSON. Return null when values/SD unavailable (client should handle gracefully).
	•	Idempotency: GET is idempotent; no special handling required.

⸻

10) Alignment to Baseline Tab (iOS)

This response directly supports:
	•	KPI chips: latest dynamic_baseline[-1] per metric + deltas + direction/significance.
	•	Small multiples: per-session metrics[metric] (points), rolling_stats[metric].mean (dashed), fixed mean (rule), fixed and rolling bands.
	•	Axes: session_index for spacing; timestamp for top datetime ticks.
	•	Table: lift directly from dynamic_baseline rows.

⸻

11) FAQ / Design Decisions
	•	Why no k in the API? k is a view concern. Use max_sessions only to limit payload size, not to change modeling.
	•	Why both fixed and rolling bands? Fixed bands show long-term variance; rolling bands show local variance—both are useful and visually distinct.
	•	What if fixed.sd = 0 or rolling_sd = 0? Return z_* = null; bands collapse to the mean line; client draws a single rule.
	•	What if few sessions? You’ll still get values and means; bands may be hidden (count < 5) and a warning is included.

⸻

This blueprint is faithful to your canonical API v5.3.1 and DB schema v4.1, uses original names (fn_baseline_points, no “enhanced”), and is engineered to drop into your Flask service so the iOS Baseline tab can render exactly as specified—four stacked plots, shared x by session index, top datetime axis, a single global legend grammar, and KPI chips driven by precise deltas and labels.