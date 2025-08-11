Baseline Tab — Flask Prototype Plot Report (for iOS Implementation)

This report specifies exactly how to turn the /api/v1/analytics/baseline response into the Baseline tab UI. It aligns with your v5.3.1 endpoint and the DB v4.1 functions. No code here—just a precise blueprint your iOS and Flask-prototype teams can execute 1:1.

⸻

1) Scope & Objectives
	•	Tag: wake_check
	•	Metrics: rmssd, sdnn, sd2_sd1, mean_hr
	•	Models:
	•	Fixed baseline (m-point): constant reference computed from last m valid sessions per metric.
	•	Dynamic baseline (n-point rolling): rolling stats per session using window n.
	•	X-domain: Equal spacing by Session Index (primary axis) with sparse real Date/Time (secondary, top axis) to preserve temporal context without uneven gaps.
	•	UI Deliverables:
	1.	Header with four KPI chips (one per metric)
	2.	Single Global Style Key (legend card)
	3.	Four stacked plots (small multiples, shared x)
	4.	Collapsible stats table
	5.	Footnotes/Methods block

⸻

2) API Contract (what we request & expect)

Endpoint
GET /api/v1/analytics/baseline

Core parameters
	•	user_id: UUID (required)
	•	m: int (default 14; allowed 1–30 in your doc; recommended floor 5 for meaningful bands)
	•	n: int (default 7; allowed 3–14; may be ≤ m; if you enforce n <= m, reflect in validation)
	•	metrics: csv (default rmssd,sdnn,sd2_sd1,mean_hr)
	•	max_sessions: int (payload control; default 300; 10–500)

Response (selected fields used by client)
	•	fixed_baseline[metric]: count, mean, sd, median, sd_median, mean±1/2sd, median±1/2sd, min, max, range
	•	dynamic_baseline[] (chronological):
	•	session_id, timestamp (UTC ISO), duration_minutes, session_index
	•	metrics[metric]: raw value
	•	rolling_stats[metric]: window_size (n), mean, sd, mean±1/2sd
	•	trends[metric]: delta_vs_fixed, pct_vs_fixed, delta_vs_rolling, pct_vs_rolling, z_fixed, z_rolling, direction, significance
	•	Top-level bookkeeping: m_points_requested/actual, n_points_requested/actual, total_sessions, updated_at, warnings[], notes{}

Optional (recommended)
	•	rolling_stats[metric].window_count (effective k at series head; see below)
	•	m_points_actual_by_metric (per-metric actual sample count used for fixed baseline)

⸻

3) Page Information Architecture (order on screen)
	1.	Header / At-a-glance
	•	Four KPI chips (RMSSD, SDNN, SD2/SD1, Mean HR), each shows:
	•	Latest session value (most recent in current viewport if k≠All; else global latest)
	•	Δ vs fixed baseline mean (absolute and %)
	•	Δ vs rolling mean (optional second line if space)
	•	Direction label (stable / above_baseline / below_baseline; include significance if desired)
	•	Context line: Fixed m={m}, Rolling n={n} · Updated {updated_at} (UTC; client may also show local)
	2.	Global Style Key (Legend card) — one shared legend for all plots
	•	Solid line: Fixed baseline (m)
	•	Dashed line: Rolling mean (n)
	•	Two ribbons: ±1 SD (darker) and ±2 SD (lighter)
	•	Filled circles: Sessions
	•	Hollow diamonds: Outliers (if enabled)
	•	Small note: Timescale: Session Index (equal spacing) · Real Date/Time shown on top axis
	3.	Plots (four stacked small multiples, shared x)
	•	Order: RMSSD, SDNN, SD2/SD1, Mean HR
	•	Shared x-domain; pan/zoom synchronized
	•	Primary x (bottom axis on bottom plot only): Session Index (equal spacing)
	•	Secondary x (top axis on bottom plot only): sparse real Date/Time ticks
	•	Y-axis labels (each plot): include units
	•	Inline labels near right edge: “Fixed baseline”, “Rolling mean” (avoid per-plot box legends)
	•	Layers (z-order):
	1.	±2 SD band (fixed or rolling, see below)
	2.	±1 SD band
	3.	Rolling mean (dashed)
	4.	Fixed baseline mean (solid)
	5.	Session points (size by duration optional; default constant size in iOS)
	6.	Outliers (optional diamond overlay)
	7.	Event markers (optional vertical rules)
	4.	Collapsible Stats Table
	•	Columns: Session # | DateTime | RMSSD | SDNN | SD2/SD1 | Mean HR | Roll RMSSD | Roll SDNN | Flags/Tags
	•	Option: sync rows to visible x-range (toggle)
	5.	Footnotes/Methods
	•	Define SD bands; Median-based SD (MAD × 1.4826); interpretation notes; non-negative clamp rule (display-only)

⸻

4) Axes & Labeling (shared x with real-time context)
	•	Primary x: Session Index (equal spacing), ticks budget ~8–12.
	•	Secondary x (top): Real Date/Time labels (UTC or localized by the app). Use sparse ticks (e.g., every 5th session or adaptive).
	•	Format:
	•	default: YYYY-MM-DD HH
	•	if :00 minutes, omit minutes; if tight, fallback to YYYY-MM-DD
	•	Tooltips/crosshair: Always show full timestamp YYYY-MM-DD HH:mm, Session #, then metric detail.
	•	Y-axes per plot:
	•	RMSSD (ms), SDNN (ms): non-negative; clamp bands at 0 for display (do not change API values)
	•	SD2/SD1 (ratio): >0
	•	Mean HR (bpm): typically integer; include 0 line only if helpful

⸻

5) Parameters m, n, and k (how the UI uses them)
	•	m (fixed baseline): determines constant mean/SD and bands from the last m valid sessions per metric. Show m in header and legend note.
	•	n (rolling window): per-session rolling stats computed with window n. Show n in legend note.
	•	Effective window at series head: fewer than n samples; if you add window_count, tooltips can display (n=7, k=3).
	•	k (viewport sessions): UI-only view size, not a model parameter.
	•	Presets: All | 30 | 90 (or phone 60, tablet 90).
	•	Pan/zoom to adjust; table can follow view.
	•	KPIs compute against latest in view when k≠All.

⸻

6) Visual Encoding (per metric plot)
	•	Fixed baseline mean (from fixed_baseline[metric].mean): solid line.
	•	Rolling mean (from rolling_stats[metric].mean): dashed line.
	•	Bands
	•	Fixed bands (constant across x): mean±1sd, mean±2sd from fixed_baseline.
	•	Rolling bands (dynamic): rolling mean ± 1/2 sd from rolling_stats.
	•	Display policy:
	•	Primary: show fixed bands by default.
	•	Optional: provide an advanced toggle to overlay rolling bands; if both shown, keep fixed as blue ribbons and rolling as faint orange ribbons to avoid confusion.
	•	Insufficient data: if count < 5 for fixed baseline, hide fixed bands and show a footnote; similarly you may hide rolling bands when window_count < 3 (policy choice).
	•	Session points: Render all available values (metrics[metric]) at their Session Index x-position.
	•	Size: constant; hover/tap highlights.
	•	Optional: size by duration_minutes if you want an extra channel (keep subtle).
	•	Outliers: Optional. Mark points beyond ±2 SD of rolling or a consistent rule (e.g., 1.5×IQR). Tooltip must state rule.

⸻

7) Units & Precision (display-only)
	•	RMSSD, SDNN: 1 decimal (ms)
	•	SD2/SD1: 2 decimals (ratio)
	•	Mean HR: 0 decimals (bpm)
	•	Percent deltas: 1 decimal
	•	Z-scores: 2 decimals

Compute with full precision; round on serialization/formatting only.

⸻

8) KPI Chips (one per metric)

Given the latest visible session (respecting k viewport):
	•	Value: metrics[metric]
	•	Δ vs fixed: value - fixed_baseline[metric].mean + percent
	•	Δ vs rolling (optional): value - rolling_stats[metric].mean + percent
	•	Direction: from trends[metric].direction and significance (e.g., stable, above_baseline, below_baseline; append significant when |z| ≥ 1.96 if space)

Formatting example:
RMSSD 34.1 ms · +2.1 (+6.0%) vs fixed · stable

⸻

9) Tooltips / Crosshair (synchronized across plots)

When hovering/tapping at Session Index S:
	•	Header: Session S · 2025-08-21 21:00
	•	For the active plot metric:
	•	Value: 44.2 ms
	•	Fixed mean (m=14): 42.5 ms
	•	Rolling (n=7[, k=5]): 43.1 ms  (include k if you add window_count)
	•	Bands: ±1 SD [36.9, 49.3] · ±2 SD [30.7, 55.5] (for whichever band type is visible: fixed or rolling)
	•	Δ vs fixed: +1.7 (+4.0%) · z: 0.20
	•	Δ vs rolling: +1.1 (+2.6%) · z: 0.18
	•	Direction: above_baseline (not significant)

⸻

10) Colors, Lines, and Styling (academic, accessible)
	•	Palette (Okabe–Ito):
	•	Fixed baseline (lines & ribbons): Blue #0072B2
	•	Rolling mean (line & ribbons): Vermillion #D55E00
	•	Session points: neutral Gray fill #7F7F7F, stroke #4D4D4D
	•	Outliers: Red #CC0000
	•	Event markers: Black with low alpha
	•	Bands:
	•	±2 SD: 15% alpha
	•	±1 SD: 25% alpha
	•	Line styles:
	•	Fixed: solid 2.0–2.5 pt
	•	Rolling: dashed 2.0 pt (dash length ~6–8 px)
	•	Typography (SF):
	•	Titles 17–19 pt semibold; axes 13–15 pt; ticks 11–12 pt; legend/key 12–13 pt

⸻

11) Plot Composition Details (per metric)

For each of the four plots:
	•	X series:
	•	session_index (from dynamic_baseline[] order; 1..N after truncation)
	•	Secondary x reference: timestamp for sparse real-time ticks on the bottom plot’s top axis
	•	Y series:
	•	Points: metrics[metric]
	•	Fixed mean: horizontal line at fixed_baseline[metric].mean
	•	Fixed bands (if count ≥ 5): horizontal ribbons using mean±1sd and mean±2sd
	•	Rolling mean: line connecting rolling_stats[metric].mean across sessions
	•	Rolling bands (optional): ribbons using per-row mean±sd/±2sd
	•	Clamping rule: If metric is non-negative (RMSSD, SDNN, Mean HR), clamp band lower edge at 0 on display only.

⸻

12) Table Schema

Default collapsed on phone; sticky header on scroll.

Columns:
	•	Session # (session_index)
	•	Date/Time (UTC → localized in app)
	•	Metrics: RMSSD, SDNN, SD2/SD1, Mean HR
	•	Rolling: Roll RMSSD (mean), Roll SDNN (mean)
(Optionally include rolling SD; or show on tap/expand)
	•	Flags/Tags (e.g., wake_check_single, artifact-corrected)

Optional: When the user zooms/pans, table can filter to visible session range.

⸻

13) Performance & Payload Handling
	•	Initial viewport k: Phone 60, Tablet 90 (or presets: All | 30 | 90).
	•	max_sessions: Server truncates at tail; client shows warning banner if truncation applied.
	•	Virtualize table for large N.
	•	Numeric rounding only in UI—not in computations used for deltas/z if you implement those client-side later. (Server already provides trend numbers.)
	•	Preload draw order: bands → lines → points for fast perceived rendering.

⸻

14) Error & Low-data States
	•	No sessions: show empty state with short copy: “No wake_check sessions yet.”
	•	Low data (count < 5 for a metric): hide fixed bands for that metric; footnote says “SD bands require ≥5 sessions.”
	•	Rolling at series head: if window_count < 3, optionally hide rolling bands but keep rolling mean line.
	•	API errors: keep last cached view; show non-blocking error banner.

⸻

15) QA Checklist (acceptance criteria)
	•	Shared x-range; pan/zoom sync across all four plots.
	•	Bottom plot shows bottom x-axis (Session Index) and top axis with sparse real Date/Time.
	•	Bands never visually dip below 0 for non-negative metrics (display clamp only).
	•	KPI chips update when viewport k changes.
	•	Tooltips show exact values and context (m, n, and if available window_count).
	•	Fixed bands hidden for metrics where fixed_baseline[metric].count < 5.
	•	Colors/lines match legend grammar; inline labels don’t overlap data.
	•	Table optionally syncs to visible range; sorts and scrolls well at high N.
	•	Performance: no stutter at N≈300 on device.

⸻

16) Example Data Mapping (from the API to layers)

For RMSSD at session S:
	•	Point: dynamic_baseline[S].metrics.rmssd
	•	Rolling mean: dynamic_baseline[S].rolling_stats.rmssd.mean
	•	Rolling bands (if enabled):
	•	mean_minus_1sd → lower1; mean_plus_1sd → upper1
	•	mean_minus_2sd → lower2; mean_plus_2sd → upper2
	•	Fixed mean/bands: from fixed_baseline.rmssd
	•	mean line, constant ribbons at ±1/±2 SD
	•	Tooltip deltas/z: from dynamic_baseline[S].trends.rmssd

Repeat mapping identically for SDNN, SD2/SD1, Mean HR.

⸻

17) State & Refresh
	•	Fetch on tab focus and after new session upload.
	•	Cache latest successful response for 5 minutes (client).
	•	Display updated_at in header; update when new fetch completes.
	•	Respect max_sessions returned—don’t assume full history.

⸻

18) Optional Enhancements (non-blocking)
	•	Add rolling_stats[metric].window_count to improve tooltips for early points.
	•	Add m_points_actual_by_metric to decide band visibility per plot precisely.
	•	Add a user “Advanced” toggle to switch band source (Fixed vs Rolling).
	•	Add outlier markers with a clearly stated rule (e.g., beyond rolling ±2 SD).

⸻

19) Implementation priorities for Flask Prototype (to mirror iOS)
	1.	Call /api/v1/analytics/baseline with user_id, m, n, metrics, max_sessions.
	2.	Render the Global Style Key, then four plots (order as above) with shared x-domain.
	3.	Use Session Index as x; show sparse real Date/Time ticks on the bottom chart’s top axis.
	4.	Draw fixed mean & bands (default). Provide a switch to overlay rolling bands for internal testing.
	5.	KPI chips derived from the latest visible session; recompute when pan/zoom or k preset changes.
	6.	Collapsible table; optional “sync to view” toggle.
	7.	Footer footnotes; show any warnings[] prominently but non-blocking.

⸻

20) Acceptance Example (what “done” looks like)
	•	Four stacked charts with blue fixed bands (±2 faint, ±1 darker), blue solid fixed mean, orange dashed rolling mean, gray points.
	•	Bottom chart shows bottom axis (Session Index) and top axis (real dates).
	•	Global legend once; no per-plot box legends; small inline text labels “Fixed baseline” and “Rolling mean” at right edge of each plot.
	•	KPI chips reflect latest visible session and show Δ vs fixed and direction.
	•	Bands hidden for metrics with <5 fixed points; note explains why.
	•	Table toggles to show visible sessions only.
	•	Interactions are smooth; no jank at 300 sessions.

⸻

This document is the source of truth for your Flask prototype and the iOS Baseline tab. If you add window_count and m_points_actual_by_metric to the API, tooltips and band-visibility logic become even clearer, but everything above works with the current v5.3.1 shape you shipped.