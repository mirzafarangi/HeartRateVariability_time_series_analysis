#!/usr/bin/env python3
"""
Deploy HRV Plots Table Schema to Production Database
Creates the missing hrv_plots table and associated functions
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from database_config import DatabaseConfig

def deploy_hrv_plots_schema():
    """Deploy the hrv_plots table schema to production database"""
    
    # SQL to create the hrv_plots table and functions
    schema_sql = """
    -- Create hrv_plots table for persistent plot storage
    CREATE TABLE IF NOT EXISTS public.hrv_plots (
        plot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        tag VARCHAR(50) NOT NULL,
        metric VARCHAR(20) NOT NULL,
        plot_image_base64 TEXT NOT NULL,
        plot_metadata JSONB,
        data_points_count INTEGER DEFAULT 0,
        date_range_start TIMESTAMP WITH TIME ZONE,
        date_range_end TIMESTAMP WITH TIME ZONE,
        stat_mean NUMERIC(10,3),
        stat_std NUMERIC(10,3),
        stat_min NUMERIC(10,3),
        stat_max NUMERIC(10,3),
        stat_p10 NUMERIC(10,3),
        stat_p90 NUMERIC(10,3),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        UNIQUE(user_id, tag, metric)
    );

    -- Enable RLS on hrv_plots table
    ALTER TABLE public.hrv_plots ENABLE ROW LEVEL SECURITY;

    -- Create RLS policy for hrv_plots
    DROP POLICY IF EXISTS "Users can manage their own plots" ON public.hrv_plots;
    CREATE POLICY "Users can manage their own plots" ON public.hrv_plots
        FOR ALL USING (auth.uid() = user_id);

    -- Helper function to get user plots
    CREATE OR REPLACE FUNCTION get_user_hrv_plots(p_user_id UUID)
    RETURNS TABLE(
        plot_id UUID,
        tag VARCHAR(50),
        metric VARCHAR(20),
        plot_image_base64 TEXT,
        plot_metadata JSONB,
        data_points_count INTEGER,
        date_range_start TIMESTAMP WITH TIME ZONE,
        date_range_end TIMESTAMP WITH TIME ZONE,
        stat_mean NUMERIC(10,3),
        stat_std NUMERIC(10,3),
        stat_min NUMERIC(10,3),
        stat_max NUMERIC(10,3),
        stat_p10 NUMERIC(10,3),
        stat_p90 NUMERIC(10,3),
        updated_at TIMESTAMP WITH TIME ZONE
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT 
            hp.plot_id,
            hp.tag,
            hp.metric,
            hp.plot_image_base64,
            hp.plot_metadata,
            hp.data_points_count,
            hp.date_range_start,
            hp.date_range_end,
            hp.stat_mean,
            hp.stat_std,
            hp.stat_min,
            hp.stat_max,
            hp.stat_p10,
            hp.stat_p90,
            hp.updated_at
        FROM public.hrv_plots hp
        WHERE hp.user_id = p_user_id
        ORDER BY hp.tag, hp.metric;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;

    -- Helper function to upsert (insert or update) a plot
    CREATE OR REPLACE FUNCTION upsert_hrv_plot(
        p_user_id UUID,
        p_tag VARCHAR(50),
        p_metric VARCHAR(20),
        p_plot_image_base64 TEXT,
        p_plot_metadata JSONB,
        p_data_points_count INTEGER,
        p_date_range_start TIMESTAMP WITH TIME ZONE,
        p_date_range_end TIMESTAMP WITH TIME ZONE,
        p_stat_mean NUMERIC(10,3),
        p_stat_std NUMERIC(10,3),
        p_stat_min NUMERIC(10,3),
        p_stat_max NUMERIC(10,3),
        p_stat_p10 NUMERIC(10,3),
        p_stat_p90 NUMERIC(10,3)
    )
    RETURNS UUID AS $$
    DECLARE
        result_plot_id UUID;
    BEGIN
        INSERT INTO public.hrv_plots (
            user_id, tag, metric, plot_image_base64, plot_metadata,
            data_points_count, date_range_start, date_range_end,
            stat_mean, stat_std, stat_min, stat_max, stat_p10, stat_p90
        ) VALUES (
            p_user_id, p_tag, p_metric, p_plot_image_base64, p_plot_metadata,
            p_data_points_count, p_date_range_start, p_date_range_end,
            p_stat_mean, p_stat_std, p_stat_min, p_stat_max, p_stat_p10, p_stat_p90
        )
        ON CONFLICT (user_id, tag, metric)
        DO UPDATE SET
            plot_image_base64 = EXCLUDED.plot_image_base64,
            plot_metadata = EXCLUDED.plot_metadata,
            data_points_count = EXCLUDED.data_points_count,
            date_range_start = EXCLUDED.date_range_start,
            date_range_end = EXCLUDED.date_range_end,
            stat_mean = EXCLUDED.stat_mean,
            stat_std = EXCLUDED.stat_std,
            stat_min = EXCLUDED.stat_min,
            stat_max = EXCLUDED.stat_max,
            stat_p10 = EXCLUDED.stat_p10,
            stat_p90 = EXCLUDED.stat_p90,
            updated_at = NOW()
        RETURNING plot_id INTO result_plot_id;
        
        RETURN result_plot_id;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;

    -- Grant necessary permissions
    GRANT SELECT, INSERT, UPDATE, DELETE ON public.hrv_plots TO authenticated;
    GRANT EXECUTE ON FUNCTION get_user_hrv_plots(UUID) TO authenticated;
    GRANT EXECUTE ON FUNCTION upsert_hrv_plot(UUID, VARCHAR, VARCHAR, TEXT, JSONB, INTEGER, TIMESTAMP WITH TIME ZONE, TIMESTAMP WITH TIME ZONE, NUMERIC, NUMERIC, NUMERIC, NUMERIC, NUMERIC, NUMERIC) TO authenticated;
    """
    
    try:
        # Initialize database configuration
        db_config = DatabaseConfig()
        
        # Connect to database
        conn = psycopg2.connect(
            host=db_config.host,
            database=db_config.database,
            user=db_config.user,
            password=db_config.password,
            port=db_config.port,
            cursor_factory=RealDictCursor
        )
        
        cur = conn.cursor()
        
        print("🚀 Deploying HRV plots table schema...")
        
        # Execute schema deployment
        cur.execute(schema_sql)
        conn.commit()
        
        # Verify table was created
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'hrv_plots' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        print(f"✅ HRV plots table created successfully with {len(columns)} columns:")
        for col in columns:
            print(f"   - {col['column_name']}: {col['data_type']}")
        
        # Test the upsert function
        print("\n🧪 Testing upsert function...")
        test_user_id = '7015839c-4659-4b6c-821c-2906e710a2db'
        cur.execute("""
            SELECT upsert_hrv_plot(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            test_user_id, 'test', 'rmssd', 'test_plot_data', '{"test": true}',
            1, None, None, 50.0, 10.0, 30.0, 70.0, 40.0, 60.0
        ))
        test_plot_id = cur.fetchone()[0]
        conn.commit()
        
        print(f"✅ Upsert function test successful - plot_id: {test_plot_id}")
        
        # Clean up test data
        cur.execute("DELETE FROM public.hrv_plots WHERE user_id = %s AND tag = 'test'", (test_user_id,))
        conn.commit()
        
        print("🎉 HRV plots table schema deployment completed successfully!")
        
    except Exception as e:
        print(f"❌ Schema deployment failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    deploy_hrv_plots_schema()
