# HRV Plots Schema Deployment Guide

## Overview
This guide deploys the new `hrv_plots` table for persistent HRV plot storage to your Supabase database.

## Prerequisites
- Access to Supabase dashboard
- Project: `atriom_hrv_db`
- Database connection established

## Deployment Steps

### Step 1: Access Supabase SQL Editor
1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Select your project: `atriom_hrv_db`
3. Navigate to **SQL Editor** in the left sidebar

### Step 2: Execute Schema Creation
Copy and paste the entire contents of `hrv_plots_schema.sql` into the SQL Editor and execute it.

**Key components being created:**
- `public.hrv_plots` table with proper constraints and indexes
- Row Level Security (RLS) policies
- Helper functions: `get_user_hrv_plots()`, `upsert_hrv_plot()`
- Automatic timestamp triggers
- Proper permissions for authenticated users

### Step 3: Verify Deployment
After execution, verify the following:

```sql
-- Check table exists
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_name = 'hrv_plots';

-- Check RLS is enabled
SELECT tablename, rowsecurity FROM pg_tables 
WHERE schemaname = 'public' AND tablename = 'hrv_plots';

-- Check functions exist
SELECT routine_name FROM information_schema.routines 
WHERE routine_schema = 'public' 
AND routine_name IN ('get_user_hrv_plots', 'upsert_hrv_plot');
```

### Step 4: Test API Integration
After schema deployment, test the API endpoints:

```bash
# Test plot refresh (should now work)
curl -X POST "https://hrv-brain-api-production.up.railway.app/api/v1/plots/refresh/7015839c-4659-4b6c-821c-2906e710a2db/rest"

# Test plot retrieval
curl "https://hrv-brain-api-production.up.railway.app/api/v1/plots/hrv-trend?user_id=7015839c-4659-4b6c-821c-2906e710a2db&metric=rmssd&tag=rest"

# Test user plots
curl "https://hrv-brain-api-production.up.railway.app/api/v1/plots/user/7015839c-4659-4b6c-821c-2906e710a2db"
```

## Expected Results

### After Successful Deployment:
1. **API Plot Refresh**: Returns success with refresh results for all 9 HRV metrics
2. **iOS Analysis Tab**: Loads plots directly from database (fast, cached)
3. **Auto-Refresh**: New session uploads automatically update plots
4. **Persistent Storage**: Plots are stored once and retrieved quickly

### Architecture Benefits:
- ✅ **Fast Plot Loading**: No real-time generation, instant retrieval from DB
- ✅ **Scalable Storage**: One plot per user-tag-metric combination
- ✅ **Auto-Sync**: Plots update when sessions are added/deleted
- ✅ **Scientific Quality**: Full SD bands, rolling averages, percentiles
- ✅ **Clean iOS Integration**: Direct DB access like Sessions tab

## Troubleshooting

### If API returns "Internal server error":
- Verify `hrv_plots` table exists in Supabase
- Check RLS policies are properly configured
- Ensure helper functions are created successfully

### If iOS app shows "No plots available":
- Record some HRV sessions first
- Call plot refresh API manually
- Check user authentication in iOS app

### If plots are not updating:
- Verify auto-refresh logic in session upload endpoint
- Check plot refresh API endpoint functionality
- Ensure proper user ID format (UUID)

## Next Steps After Deployment
1. Deploy schema using this guide
2. Test API endpoints with recorded session data
3. Test iOS Analysis tab with new DB-backed components
4. Verify end-to-end functionality: Record → Auto-refresh → View plots
