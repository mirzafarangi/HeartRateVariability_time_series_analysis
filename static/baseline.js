// Baseline Tab Visualization JavaScript
// Implements exact specifications from iOS blueprint

let baselineData = null;
let showRollingBands = false;
let syncTable = false;
let currentViewRange = null;

// Color palette (Okabe-Ito)
const COLORS = {
    fixedBaseline: '#0072B2',  // Blue
    rollingMean: '#D55E00',     // Vermillion
    sessionPoints: '#7F7F7F',   // Gray
    pointStroke: '#4D4D4D',     // Dark gray
    outliers: '#CC0000',        // Red
    bands1SD: 0.25,             // Alpha for ±1 SD
    bands2SD: 0.15              // Alpha for ±2 SD
};

// Initialize on load
window.onload = function() {
    updateBaseline();
};

function updateBaseline() {
    const m = document.getElementById('mInput').value;
    const n = document.getElementById('nInput').value;
    const maxSessions = document.getElementById('maxSessionsInput').value;
    const userId = document.querySelector('body').getAttribute('data-user-id') || '7015839c-4659-4b6c-821c-2906e710a2db';
    
    // Show loading state
    document.getElementById('plotsContainer').innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Loading baseline visualization...</p>
        </div>
    `;
    
    // Fetch data from API
    fetch(`/api/baseline?user_id=${userId}&m=${m}&n=${n}&max_sessions=${maxSessions}`)
        .then(response => response.json())
        .then(data => {
            baselineData = data;
            renderVisualization(data);
        })
        .catch(error => {
            console.error('Error fetching baseline data:', error);
            document.getElementById('plotsContainer').innerHTML = `
                <div class="loading">
                    <p style="color: #ff3b30;">Error loading baseline data. Please try again.</p>
                </div>
            `;
        });
}

function renderVisualization(data) {
    if (!data || !data.dynamic_baseline || data.dynamic_baseline.length === 0) {
        document.getElementById('plotsContainer').innerHTML = `
            <div class="loading">
                <p>No wake_check sessions found.</p>
            </div>
        `;
        return;
    }
    
    // Update KPIs
    updateKPIs(data);
    
    // Update context line
    updateContextLine(data);
    
    // Show warnings if any
    showWarnings(data.warnings);
    
    // Create plots
    createPlots(data);
    
    // Update table
    updateTable(data);
}

function updateKPIs(data) {
    const metrics = ['rmssd', 'sdnn', 'sd2_sd1', 'mean_hr'];
    const labels = {
        'rmssd': 'RMSSD',
        'sdnn': 'SDNN',
        'sd2_sd1': 'SD2/SD1',
        'mean_hr': 'Mean HR'
    };
    const units = {
        'rmssd': 'ms',
        'sdnn': 'ms',
        'sd2_sd1': '',
        'mean_hr': 'bpm'
    };
    
    let kpiHtml = '';
    const lastSession = data.dynamic_baseline[data.dynamic_baseline.length - 1];
    
    metrics.forEach(metric => {
        if (!data.metrics.includes(metric)) return;
        
        const value = lastSession.metrics[metric];
        const trends = lastSession.trends[metric];
        const fixedMean = data.fixed_baseline[metric]?.mean;
        
        let deltaFixed = '';
        if (trends && trends.delta_vs_fixed !== null) {
            const sign = trends.delta_vs_fixed >= 0 ? '+' : '';
            deltaFixed = `${sign}${trends.delta_vs_fixed.toFixed(1)} (${sign}${trends.pct_vs_fixed.toFixed(1)}%)`;
        }
        
        const direction = trends?.direction || 'stable';
        const significance = trends?.significance || '';
        
        const chipClass = metric.replace('_', '-');
        
        kpiHtml += `
            <div class="kpi-chip ${chipClass}">
                <div class="kpi-label">${labels[metric]}</div>
                <div class="kpi-value">${value?.toFixed(1) || 'N/A'} ${units[metric]}</div>
                <div class="kpi-delta">vs fixed: ${deltaFixed || 'N/A'}</div>
                <div class="kpi-direction">${direction} ${significance ? `(${significance})` : ''}</div>
            </div>
        `;
    });
    
    document.getElementById('kpiContainer').innerHTML = kpiHtml;
}

function updateContextLine(data) {
    const updated = new Date(data.updated_at).toLocaleString();
    document.getElementById('contextLine').innerHTML = 
        `Fixed m=${data.m_points_requested}, Rolling n=${data.n_points_requested} · ` +
        `Sessions: ${data.total_sessions} · Updated: ${updated}`;
}

function showWarnings(warnings) {
    if (!warnings || warnings.length === 0) {
        document.getElementById('warningsContainer').innerHTML = '';
        return;
    }
    
    let warningHtml = '<div class="warnings"><h4>Warnings:</h4><ul>';
    warnings.forEach(warning => {
        warningHtml += `<li>${warning}</li>`;
    });
    warningHtml += '</ul></div>';
    
    document.getElementById('warningsContainer').innerHTML = warningHtml;
}

function createPlots(data) {
    const metrics = ['rmssd', 'sdnn', 'sd2_sd1', 'mean_hr'];
    const metricLabels = {
        'rmssd': 'RMSSD (ms)',
        'sdnn': 'SDNN (ms)',
        'sd2_sd1': 'SD2/SD1 (ratio)',
        'mean_hr': 'Mean HR (bpm)'
    };
    
    const plotsContainer = document.getElementById('plotsContainer');
    plotsContainer.innerHTML = '';
    
    // Prepare x-axis data (session indices)
    const sessionIndices = data.dynamic_baseline.map(d => d.session_index);
    const timestamps = data.dynamic_baseline.map(d => new Date(d.timestamp));
    
    // Create subplot for each metric
    const subplots = [];
    const traces = [];
    
    metrics.forEach((metric, idx) => {
        if (!data.metrics.includes(metric)) return;
        
        const yData = data.dynamic_baseline.map(d => d.metrics[metric]);
        const rollingMeans = data.dynamic_baseline.map(d => d.rolling_stats[metric]?.mean);
        const fixedMean = data.fixed_baseline[metric]?.mean;
        const fixedStats = data.fixed_baseline[metric];
        
        // Determine subplot position
        const row = idx + 1;
        const isBottomPlot = idx === metrics.length - 1;
        
        // Session points trace
        traces.push({
            x: sessionIndices,
            y: yData,
            type: 'scatter',
            mode: 'markers',
            name: `${metricLabels[metric]} Sessions`,
            marker: {
                color: COLORS.sessionPoints,
                size: 8,
                line: {
                    color: COLORS.pointStroke,
                    width: 1
                }
            },
            hovertemplate: 
                '<b>Session %{x}</b><br>' +
                `${metricLabels[metric]}: %{y:.1f}<br>` +
                '<extra></extra>',
            xaxis: `x${idx > 0 ? idx + 1 : ''}`,
            yaxis: `y${idx > 0 ? idx + 1 : ''}`,
            showlegend: false
        });
        
        // Fixed baseline mean line
        if (fixedMean !== null && fixedMean !== undefined) {
            traces.push({
                x: sessionIndices,
                y: Array(sessionIndices.length).fill(fixedMean),
                type: 'scatter',
                mode: 'lines',
                name: 'Fixed baseline',
                line: {
                    color: COLORS.fixedBaseline,
                    width: 2
                },
                hoverinfo: 'skip',
                xaxis: `x${idx > 0 ? idx + 1 : ''}`,
                yaxis: `y${idx > 0 ? idx + 1 : ''}`,
                showlegend: false
            });
        }
        
        // Rolling mean line
        traces.push({
            x: sessionIndices,
            y: rollingMeans,
            type: 'scatter',
            mode: 'lines',
            name: 'Rolling mean',
            line: {
                color: COLORS.rollingMean,
                width: 2,
                dash: 'dash'
            },
            hoverinfo: 'skip',
            xaxis: `x${idx > 0 ? idx + 1 : ''}`,
            yaxis: `y${idx > 0 ? idx + 1 : ''}`,
            showlegend: false
        });
        
        // Fixed bands (if sufficient data)
        if (fixedStats && fixedStats.count >= 5 && !showRollingBands) {
            // ±2 SD band
            const lower2SD = Math.max(0, fixedStats.mean_minus_2sd || 0);
            const upper2SD = fixedStats.mean_plus_2sd;
            
            traces.push({
                x: sessionIndices.concat([...sessionIndices].reverse()),
                y: Array(sessionIndices.length).fill(upper2SD)
                    .concat(Array(sessionIndices.length).fill(lower2SD)),
                type: 'scatter',
                mode: 'none',
                fill: 'toself',
                fillcolor: `rgba(0, 114, 178, ${COLORS.bands2SD})`,
                hoverinfo: 'skip',
                xaxis: `x${idx > 0 ? idx + 1 : ''}`,
                yaxis: `y${idx > 0 ? idx + 1 : ''}`,
                showlegend: false
            });
            
            // ±1 SD band
            const lower1SD = Math.max(0, fixedStats.mean_minus_1sd || 0);
            const upper1SD = fixedStats.mean_plus_1sd;
            
            traces.push({
                x: sessionIndices.concat([...sessionIndices].reverse()),
                y: Array(sessionIndices.length).fill(upper1SD)
                    .concat(Array(sessionIndices.length).fill(lower1SD)),
                type: 'scatter',
                mode: 'none',
                fill: 'toself',
                fillcolor: `rgba(0, 114, 178, ${COLORS.bands1SD})`,
                hoverinfo: 'skip',
                xaxis: `x${idx > 0 ? idx + 1 : ''}`,
                yaxis: `y${idx > 0 ? idx + 1 : ''}`,
                showlegend: false
            });
        }
        
        // Rolling bands (if enabled)
        if (showRollingBands) {
            // Build rolling band arrays
            const upper2SD = [];
            const lower2SD = [];
            const upper1SD = [];
            const lower1SD = [];
            
            data.dynamic_baseline.forEach(session => {
                const stats = session.rolling_stats[metric];
                if (stats) {
                    upper2SD.push(stats.mean_plus_2sd);
                    lower2SD.push(Math.max(0, stats.mean_minus_2sd || 0));
                    upper1SD.push(stats.mean_plus_1sd);
                    lower1SD.push(Math.max(0, stats.mean_minus_1sd || 0));
                } else {
                    upper2SD.push(null);
                    lower2SD.push(null);
                    upper1SD.push(null);
                    lower1SD.push(null);
                }
            });
            
            // ±2 SD rolling band
            traces.push({
                x: sessionIndices.concat([...sessionIndices].reverse()),
                y: upper2SD.concat([...lower2SD].reverse()),
                type: 'scatter',
                mode: 'none',
                fill: 'toself',
                fillcolor: `rgba(213, 94, 0, ${COLORS.bands2SD})`,
                hoverinfo: 'skip',
                xaxis: `x${idx > 0 ? idx + 1 : ''}`,
                yaxis: `y${idx > 0 ? idx + 1 : ''}`,
                showlegend: false
            });
            
            // ±1 SD rolling band
            traces.push({
                x: sessionIndices.concat([...sessionIndices].reverse()),
                y: upper1SD.concat([...lower1SD].reverse()),
                type: 'scatter',
                mode: 'none',
                fill: 'toself',
                fillcolor: `rgba(213, 94, 0, ${COLORS.bands1SD})`,
                hoverinfo: 'skip',
                xaxis: `x${idx > 0 ? idx + 1 : ''}`,
                yaxis: `y${idx > 0 ? idx + 1 : ''}`,
                showlegend: false
            });
        }
        
        // Add subplot specification
        subplots.push([`x${idx > 0 ? idx + 1 : ''}y${idx > 0 ? idx + 1 : ''}`]);
    });
    
    // Create layout with subplots
    const layout = {
        grid: {
            rows: metrics.length,
            columns: 1,
            pattern: 'independent',
            roworder: 'top to bottom'
        },
        height: 200 * metrics.length,
        margin: { t: 80, r: 50, b: 60, l: 80 },
        paper_bgcolor: 'white',
        plot_bgcolor: 'white',
        hovermode: 'x unified',
        dragmode: 'pan'
    };
    
    // Configure each subplot's axes
    metrics.forEach((metric, idx) => {
        const isBottomPlot = idx === metrics.length - 1;
        const xaxisKey = idx === 0 ? 'xaxis' : `xaxis${idx + 1}`;
        const yaxisKey = idx === 0 ? 'yaxis' : `yaxis${idx + 1}`;
        
        // X-axis configuration
        layout[xaxisKey] = {
            title: isBottomPlot ? 'Session Index' : '',
            showticklabels: isBottomPlot,
            showgrid: true,
            gridcolor: '#e5e5ea',
            zeroline: false,
            fixedrange: false
        };
        
        // Add secondary x-axis for dates (top of bottom plot)
        if (isBottomPlot) {
            layout[`${xaxisKey}2`] = {
                overlaying: xaxisKey,
                side: 'top',
                showgrid: false,
                tickmode: 'auto',
                nticks: 5,
                tickformat: '%Y-%m-%d',
                tickvals: sessionIndices.filter((_, i) => i % Math.ceil(sessionIndices.length / 5) === 0),
                ticktext: timestamps.filter((_, i) => i % Math.ceil(timestamps.length / 5) === 0)
                    .map(d => d.toISOString().split('T')[0])
            };
        }
        
        // Y-axis configuration
        layout[yaxisKey] = {
            title: metricLabels[metric],
            showgrid: true,
            gridcolor: '#e5e5ea',
            zeroline: false,
            fixedrange: false
        };
        
        // Set domain for subplot
        const domain = [
            1 - (idx + 1) / metrics.length + 0.02,
            1 - idx / metrics.length - 0.02
        ];
        layout[yaxisKey].domain = domain;
    });
    
    // Create the plot
    const config = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'],
        toImageButtonOptions: {
            format: 'png',
            filename: 'baseline_analysis',
            height: 800,
            width: 1200,
            scale: 2
        }
    };
    
    // Create plot div
    const plotDiv = document.createElement('div');
    plotDiv.id = 'baselinePlot';
    plotsContainer.appendChild(plotDiv);
    
    Plotly.newPlot('baselinePlot', traces, layout, config);
    
    // Add event listener for range changes
    plotDiv.on('plotly_relayout', function(eventData) {
        if (eventData['xaxis.range[0]'] !== undefined) {
            currentViewRange = [
                eventData['xaxis.range[0]'],
                eventData['xaxis.range[1]']
            ];
            if (syncTable) {
                updateTable(baselineData);
            }
        }
    });
}

function updateTable(data) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';
    
    let sessions = data.dynamic_baseline;
    
    // Filter by view range if sync is enabled
    if (syncTable && currentViewRange) {
        sessions = sessions.filter(s => 
            s.session_index >= currentViewRange[0] && 
            s.session_index <= currentViewRange[1]
        );
    }
    
    sessions.forEach(session => {
        const row = document.createElement('tr');
        const timestamp = new Date(session.timestamp);
        
        row.innerHTML = `
            <td>${session.session_index}</td>
            <td>${timestamp.toLocaleString()}</td>
            <td>${session.duration_minutes} min</td>
            <td>${formatMetricValue(session.metrics.rmssd, 1)} ms</td>
            <td>${formatMetricValue(session.metrics.sdnn, 1)} ms</td>
            <td>${formatMetricValue(session.metrics.sd2_sd1, 2)}</td>
            <td>${formatMetricValue(session.metrics.mean_hr, 0)} bpm</td>
            <td>${formatMetricValue(session.rolling_stats.rmssd?.mean, 1)} ms</td>
            <td>${formatMetricValue(session.rolling_stats.sdnn?.mean, 1)} ms</td>
            <td>${session.tags.join(', ')}</td>
        `;
        
        tbody.appendChild(row);
    });
}

function formatMetricValue(value, decimals) {
    if (value === null || value === undefined) return 'N/A';
    return value.toFixed(decimals);
}

function toggleRollingBands() {
    showRollingBands = !showRollingBands;
    const toggle = document.getElementById('rollingBandsToggle');
    toggle.classList.toggle('active');
    
    // Re-render plots with new band setting
    if (baselineData) {
        createPlots(baselineData);
    }
}

function toggleTableSync() {
    syncTable = !syncTable;
    const toggle = document.getElementById('syncTableToggle');
    toggle.classList.toggle('active');
    
    // Update table if data exists
    if (baselineData) {
        updateTable(baselineData);
    }
}
