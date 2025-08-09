# Event ID Assignment Rules (DB-assigned, Sleep Event–Based)

## What `event_id` means

- `event_id` groups **all sleep intervals from one continuous sleep event** for a given user
- `event_id` is **monotonic per user** (`1, 2, 3, …`)
- The **database**, not the client, assigns and attaches `event_id`

## Client Rules

### Non-sleep sessions
- Types: `wake_check`, `pre_sleep`, `experiment`
- Must send `event_id: 0` (mandatory)
- Stored value remains `0`

### Sleep sessions
- Tag: `tag='sleep'`
- Send `event_id: 0` for **every** interval (or omit it)
- The database will **assign or attach** the correct `event_id`
- *Advanced: the client may send `event_id > 0` to explicitly attach/backfill; the DB will validate*

## Server/DB Rules (on insert)

**Before constraints**, a trigger runs:

1. **First interval of a new sleep event**
   - If `tag='sleep'`, `interval_number = 1`, and `event_id = 0`
   - → Allocate a new `event_id` (next integer for that user)

2. **Subsequent intervals of an existing sleep event**
   - If `tag='sleep'`, `interval_number > 1`, and `event_id = 0`
   - → Attach to the current in-progress event **only if** the user's latest stored interval is exactly `interval_number - 1`
   - If not, reject with error: *"No existing sleep event to attach; upload `sleep_interval_1` first or provide event_id."*

3. **Explicit event_id provided**
   - If the client sends `event_id > 0`, the DB honors it but enforces:
     - The event belongs to the same user
     - The (`event_id`, `interval_number`) pair is unique

## Constraints After Trigger

- Non-sleep rows: always `event_id = 0`
- Sleep rows: always `event_id > 0`
- Unique index: `(user_id, event_id, interval_number)` to prevent duplicates

## Canonical Scenarios

### 1. Continuous sleep event with restarts

**T0** – Start recording
- Insert: `sleep_interval_1`, `event_id=0`
- → DB allocates `event_id=1`

**T1** – Continue recording
- Insert: `sleep_interval_2`, `event_id=0`
- → DB sees max interval=1 → attach to `event_id=1`

**T2** – Continue recording
- Insert: `sleep_interval_3`, `event_id=0`
- → DB sees max interval=2 → attach to `event_id=1`

**Result:** All intervals belong to the same sleep event (`event_id=1`)

### 2. New, separate sleep event

**T0** – Start new sleep
- Insert: `sleep_interval_1`, `event_id=0`
- → DB allocates `event_id=2`

**Result:** New `event_id` for this separate sleep event

### 3. Out-of-order upload

**T0** – Upload `sleep_interval_2` first, `event_id=0`
- → DB rejects: "No existing sleep event to attach…"

**T1** – Upload `sleep_interval_1`, `event_id=0`
- → DB allocates `event_id=3`

**T2** – Re-upload `sleep_interval_2`, `event_id=0`
- → DB sees max interval=1 → attach to `event_id=3`

**Result:** Correct grouping preserved; no accidental mis-attachment

### 4. Explicit backfill to a known event

- Insert: `sleep_interval_4`, `event_id=5`
- → DB validates and inserts into `event_id=5`

### 5. Duplicate protection

- Same `session_id` → API returns `status: duplicate`
- Same `(event_id, interval_number)` for sleep → DB rejects via unique index

### 6. Multi-device edge case

If two devices start `sleep_interval_1` with `event_id=0` at the same time:
- DB allocates **distinct event_ids** (e.g., 7 and 8) for each insert
- Product policy should prevent multiple concurrent sleep events for a user

## Practical Client Guidance

### For sleep:
- Always send `subtag`: `sleep_interval_1`, `sleep_interval_2`, … (canonical pattern)
- Always send `event_id: 0` (or omit) unless intentionally backfilling
- Always start with `sleep_interval_1` when beginning a new sleep event

### For non-sleep:
- Always send `event_id: 0`

## Why This Design

- No pre-allocation endpoint required
- Single-transaction insert logic
- Safe restarts and partial uploads
- Prevents mis-grouping across separate sleep events
- Fully supports analytics across all 5 models without time-of-day assumptions