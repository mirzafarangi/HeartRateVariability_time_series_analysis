-- HRV Plots Table Schema
-- Persistent storage for generated HRV trend analysis plots
-- Optimized for per-user, per-tag, per-metric storage

CREATE TABLE IF NOT EXISTS public.hrv_plots (
    plot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tag VARCHAR(50) NOT NULL CHECK (tag IN ('rest', 'sleep', 'experiment_paired_pre', 'experiment_paired_post', 'experiment_duration', 'breath_workout')),
    metric VARCHAR(20) NOT NULL CHECK (metric IN ('mean_hr', 'mean_rr', 'count_rr', 'rmssd', 'sdnn', 'pnn50', 'cv_rr', 'defa', 'sd2_sd1')),
    
    -- Plot data and metadata
    plot_image_base64 TEXT NOT NULL, -- Base64 encoded PNG image
    plot_metadata JSONB NOT NULL,    -- Statistics, date range, data points count
    
    -- Data summary for quick access
    data_points_count INTEGER NOT NULL DEFAULT 0,
    date_range_start TIMESTAMP WITH TIME ZONE,
    date_range_end TIMESTAMP WITH TIME ZONE,
    
    -- Statistics (extracted from plot_metadata for indexing)
    stat_mean NUMERIC(10,3),
    stat_std NUMERIC(10,3),
    stat_min NUMERIC(10,3),
    stat_max NUMERIC(10,3),
    stat_p10 NUMERIC(10,3),
    stat_p90 NUMERIC(10,3),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint: one plot per user-tag-metric combination
    UNIQUE(user_id, tag, metric)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_hrv_plots_user_id ON public.hrv_plots(user_id);
CREATE INDEX IF NOT EXISTS idx_hrv_plots_tag ON public.hrv_plots(tag);
CREATE INDEX IF NOT EXISTS idx_hrv_plots_metric ON public.hrv_plots(metric);
CREATE INDEX IF NOT EXISTS idx_hrv_plots_updated_at ON public.hrv_plots(updated_at);

-- Row Level Security (RLS) policies
ALTER TABLE public.hrv_plots ENABLE ROW LEVEL SECURITY;

-- Users can only access their own plots
CREATE POLICY "Users can view own plots" ON public.hrv_plots
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own plots" ON public.hrv_plots
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own plots" ON public.hrv_plots
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own plots" ON public.hrv_plots
    FOR DELETE USING (auth.uid() = user_id);

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_hrv_plots_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update updated_at
CREATE TRIGGER trigger_update_hrv_plots_updated_at
    BEFORE UPDATE ON public.hrv_plots
    FOR EACH ROW
    EXECUTE FUNCTION update_hrv_plots_updated_at();

-- Helper function to get all plots for a user
CREATE OR REPLACE FUNCTION get_user_hrv_plots(p_user_id UUID)
RETURNS TABLE (
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
