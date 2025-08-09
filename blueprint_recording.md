**Lumenis Project — Canonical Tagging, Recording Flow, and Database Integration Specification**

**Version:** 1.0

**Date:** 2025-08-09

**Audience:** iOS engineers, backend/API developers, data scientists

**Status:** Approved and locked for implementation

---

## **1. Purpose**

This document defines the **canonical tag, subtag, and event_id model** for session recordings, the **recording flow logic** on iOS, and the **database integration rules** on the Supabase backend.

Its goal is to:

- Provide **one unambiguous specification** for all recording scenarios.
- Ensure iOS, backend, and analytics teams implement **exactly the same rules**.
- Guarantee that all stored sessions are **valid by database constraints** and **ready for analytics models** without post-processing.

---

## **2. Canonical Tag Model**

### **2.1 Allowed tag Values**

There are exactly four permitted values for the tag column in public.sessions:

| **Tag** | **Semantics** | **Grouping** | **Typical Duration** |
| --- | --- | --- | --- |
| wake_check | Morning resting session; baseline source. | Standalone (event_id=0) | 1–10 min |
| pre_sleep | Evening resting session before sleep. | Standalone (event_id=0) | 1–10 min |
| sleep | Overnight recording in fixed-length intervals. | Grouped (event_id>0) | N×(5–10 min) |
| experiment | Protocolized or ad-hoc experimental sessions. | Standalone (event_id=0) | Variable |

Any other tag name is **invalid** and will be rejected by DB constraints.

---

### **2.2 Allowed subtag Values and Rules**

subtag is **always programmatically assigned** by the client.

It must conform to the following patterns (enforced via DB CHECK constraints):

| **Tag** | **Allowed** subtag **patterns** | **Purpose** |
| --- | --- | --- |
| wake_check | wake_check_single | paired_day_pre | Baseline mode vs day-load paired pre-session |
| pre_sleep | pre_sleep_single | paired_day_post | Baseline mode vs day-load paired post-session |
| sleep | sleep_interval_[1-9][0-9]* | Interval index within a sleep event |
| experiment | experiment_single | protocol_[a-z0-9_]+ | Protocol bookkeeping (free list, but prefixed) |

---

### **2.3 event_id Assignment Rules**

- **Non-sleep sessions:** event_id = 0 (mandatory)
- **Sleep sessions:** event_id > 0 (all intervals from the same night share the same id)
- event_id is allocated **once at start of a sleep event** via:

```
SELECT fn_allocate_sleep_event_id(<user_id>);
```

- 
- DB constraints enforce:
    - Sleep → event_id > 0
    - Non-sleep → event_id = 0

---

## **3. iOS Recording Workflow**

### **3.1 Phases**

1. **Recording Configuration Card**
    - User selects:
        - **Tag** (from canonical list)
        - **Duration (mins)** via slider
    - Client prepares:
        - tag
        - duration_minutes
        - Placeholder for subtag and event_id (filled on start)
2. **Recording Session Card**
    - UI adjusts start button behavior:
        - **Non-sleep:** “Start to Record”
        - **Sleep:** “Start to Auto-Record”

---

### **3.2 Tag-Specific Start Logic**

| **Tag** | **UI Start Behavior** | **Subtag Rule** | **Event ID Rule** |
| --- | --- | --- | --- |
| wake_check | Start to Record | paired_day_pre if day-load active, else _single | Always 0 |
| pre_sleep | Start to Record | paired_day_post if day-load active, else _single | Always 0 |
| experiment | Start to Record | experiment_single or chosen protocol subtag | Always 0 |
| sleep | Start to Auto-Record | sleep_interval_k (increment per interval) | Allocated once/night |

---

### **3.3 Session Creation (Client-Side)**

**Non-Sleep:**

1. On “Start to Record”:
    - Lock config UI until stop
    - Assign subtag and event_id per rules
    - Record for duration_minutes
2. On finish:
    - Create **one session object**
    - Push to Queue Card

**Sleep (Auto-Record):**

1. On “Start to Auto-Record”:
    - Lock config UI
    - Call fn_allocate_sleep_event_id(user_id)
    - Start interval counter k=1
2. On each interval end:
    - Create session:
        - subtag = sleep_interval_k
        - event_id = current_event_id
    - Push to Queue Card
    - Increment k
3. On stop:
    - End loop

---

### **3.4 Queue Card Behavior**

- Holds unsent sessions (network retries allowed).
- Payload example:

```
{
  "tag": "wake_check",
  "subtag": "wake_check_single",
  "event_id": 0,
  "duration_minutes": 5,
  "recorded_at": "2025-08-08T07:30:00Z",
  "rr_intervals": [...],
  "rr_count": 300
}
```

- Flushes automatically or on user request.

---

## **4. Supabase Database Integration**

### **4.1 Relevant Tables**

- **profiles** — minimal user profile, linked to auth.users.
- **sessions** — primary store for all Lumenis session data.

---

### **4.2 sessions Columns (Core)**

| **Column** | **Type** | **Purpose** |
| --- | --- | --- |
| session_id | UUID | Primary key |
| user_id | UUID | References auth.users |
| tag | TEXT | Canonical tag |
| subtag | TEXT | Canonical subtag |
| event_id | INTEGER | Group ID for sleep, else 0 |
| recorded_at | TIMESTAMPTZ | UTC timestamp |
| duration_minutes | INTEGER | Duration of recording |
| rr_intervals | DOUBLE PRECISION[] | Raw RR interval data |
| Metrics | DOUBLE PRECISION cols | RMSSD, SDNN, SD2/SD1, etc. |

---

### **4.3 Database Enforcement**

- CHECK constraints for:
    - Valid tag
    - Valid subtag pattern for given tag
    - event_id matches tag rules
    - RR data consistency (rr_count matches array length)
- Partial indexes for:
    - Sleep event queries
    - Paired day-load matching
    - Unique sleep interval per event
    - Deduplication of wake/pre-sleep sessions

---

### **4.4 Analytics Functions**

Supabase has five built-in SQL functions for plot-ready data:

| **Function Name** | **Scenario** | **Key Filters** |
| --- | --- | --- |
| fn_baseline_points | Baseline model | wake_check |
| fn_micro_sleep_points | Micro sleep intervals | Latest sleep event |
| fn_macro_sleep_points | Macro sleep events | Aggregated sleep events |
| fn_day_load_points | Day-load paired model | Wake/pre-sleep same day |
| fn_experiment_points | Experiment trends | Protocol filtering optional |

---

## **5. API Integration**

### **5.1 Recording API**

- Endpoint: POST /api/v1/sessions
- Body: same as Queue Card JSON
- Backend:
    - Validates tag/subtag/event_id via DB
    - Inserts directly into public.sessions

### **5.2 Event ID Allocation**

- Endpoint: POST /api/v1/sleep/allocate-event-id
- Calls:

```
SELECT fn_allocate_sleep_event_id('<user_id>');
```

### **5.3 Analytics Endpoints**

Each function in §4.4 maps to an API endpoint returning JSON arrays for direct plotting.

---

## **6. Compliance Notes**

- **No user input** for subtag or event_id.
- **UTC** timestamps required.
- All RLS policies enforce **user-only access**.
- Schema is locked — changes require full review.

---

## **7. Summary Table**

| **Tag** | **Subtag Examples** | **Event ID Rule** | **Recording Mode** | **Analytics Usage** |
| --- | --- | --- | --- | --- |
| wake_check | wake_check_single, paired_day_pre | 0 | Single interval | Baseline, Day-load |
| pre_sleep | pre_sleep_single, paired_day_post | 0 | Single interval | Day-load |
| sleep | sleep_interval_1..N | >0 | Auto-record intervals | Micro, Macro sleep |
| experiment | experiment_single, protocol_* | 0 | Single interval | Experiment trends |

---

If you implement exactly as specified, **every session created by the iOS app will insert cleanly into Supabase** and feed directly into the five analytics models without transformation.