# Supabase Edge Functions Deployment Guide

## Overview
Deploy the HRV Brain API as Supabase Edge Functions for seamless integration with your Supabase project.

## Prerequisites
- Supabase CLI installed: `npm install -g supabase`
- Supabase project created (atriom_hrv_db)
- GitHub repository connected to Supabase

## Setup Steps

### 1. Initialize Supabase in your project
```bash
cd /Users/ashkanbeheshti/Desktop/hrv-ios-api/api_hrv
supabase init
```

### 2. Link to your Supabase project
```bash
supabase link --project-ref zluwfmovtmlijawhelzi
```

### 3. Create Edge Function structure
```bash
mkdir -p supabase/functions/hrv-api
```

### 4. Convert Flask app to Edge Function
Create `supabase/functions/hrv-api/index.ts`:

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    // Initialize Supabase client
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? '',
    )

    const url = new URL(req.url)
    const path = url.pathname

    // Route handling (implement your Flask routes here)
    if (path === '/health') {
      return new Response(
        JSON.stringify({
          status: 'healthy',
          version: '3.3.4',
          timestamp: new Date().toISOString(),
          database: 'supabase-postgresql'
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      )
    }

    // Add other routes here...

    return new Response(
      JSON.stringify({ error: 'Not found' }),
      { status: 404, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )

  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    )
  }
})
```

### 5. Deploy Edge Function
```bash
supabase functions deploy hrv-api
```

### 6. Set Environment Variables
```bash
supabase secrets set SUPABASE_DB_HOST=db.zluwfmovtmlijawhelzi.supabase.co
supabase secrets set SUPABASE_DB_PASSWORD=your-password
# Add other environment variables...
```

## Advantages of Edge Functions
- ✅ Native Supabase integration
- ✅ Automatic scaling
- ✅ Built-in authentication
- ✅ Global edge deployment
- ✅ No cold starts

## Limitations
- ❌ Deno runtime (not Python)
- ❌ Limited to TypeScript/JavaScript
- ❌ Need to rewrite NumPy calculations

## Recommendation
For Python-based HRV calculations, use traditional hosting (Render/Railway) with Supabase database connection.
