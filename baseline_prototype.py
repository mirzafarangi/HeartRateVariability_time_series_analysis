#!/usr/bin/env python3
"""
Baseline Tab Flask Prototype - iOS Implementation Blueprint
Implements the exact specifications from the Baseline Tab report for iOS development.
"""

from flask import Flask, render_template_string, jsonify, request
import requests
import json
from datetime import datetime
import math

app = Flask(__name__)

# Configuration
API_BASE_URL = "http://localhost:5001"
DEFAULT_USER_ID = "7015839c-4659-4b6c-821c-2906e710a2db"

@app.route('/')
def index():
    """Main page with baseline visualization"""
    return render_template_string(HTML_TEMPLATE, user_id=DEFAULT_USER_ID)

@app.route('/api/baseline')
def get_baseline():
    """Proxy endpoint to fetch baseline data from API"""
    try:
        # Get parameters
        user_id = request.args.get('user_id', DEFAULT_USER_ID)
        m = request.args.get('m', 14)
        n = request.args.get('n', 7)
        max_sessions = request.args.get('max_sessions', 300)
        
        # Call the actual API
        response = requests.get(
            f"{API_BASE_URL}/api/v1/analytics/baseline",
            params={
                'user_id': user_id,
                'm': m,
                'n': n,
                'max_sessions': max_sessions,
                'metrics': 'rmssd,sdnn,sd2_sd1,mean_hr'
            }
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'Failed to fetch baseline data'}), response.status_code
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# HTML Template (will be defined in next part)
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Baseline Tab - iOS Prototype</title>
    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f7;
            color: #1d1d1f;
            line-height: 1.47;
        }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        /* Header Section */
        .header {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        
        .header h1 {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 16px;
            color: #1d1d1f;
        }
        
        /* KPI Chips */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
            margin-bottom: 16px;
        }
        
        .kpi-chip {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            padding: 16px;
            color: white;
            position: relative;
            overflow: hidden;
        }
        
        .kpi-chip.rmssd { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .kpi-chip.sdnn { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
        .kpi-chip.sd2-sd1 { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
        .kpi-chip.mean-hr { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); }
        
        .kpi-label {
            font-size: 12px;
            font-weight: 500;
            opacity: 0.9;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        
        .kpi-value {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .kpi-delta {
            font-size: 14px;
            opacity: 0.95;
        }
        
        .kpi-direction {
            font-size: 12px;
            font-weight: 500;
            margin-top: 4px;
            padding: 2px 8px;
            background: rgba(255,255,255,0.2);
            border-radius: 4px;
            display: inline-block;
        }
        
        /* Context Line */
        .context-line {
            font-size: 13px;
            color: #86868b;
            text-align: center;
        }
        
        /* Legend Card */
        .legend-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        
        .legend-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 12px;
            color: #1d1d1f;
        }
        
        .legend-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: #3e3e43;
        }
        
        .legend-symbol {
            width: 30px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        /* Controls */
        .controls {
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            display: flex;
            gap: 16px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .control-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .control-label {
            font-size: 13px;
            color: #86868b;
            font-weight: 500;
        }
        
        input[type="number"] {
            width: 60px;
            padding: 6px 8px;
            border: 1px solid #d2d2d7;
            border-radius: 6px;
            font-size: 14px;
        }
        
        button {
            padding: 8px 16px;
            background: #0071e3;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        button:hover {
            background: #0077ed;
            transform: translateY(-1px);
        }
        
        .toggle-switch {
            position: relative;
            width: 48px;
            height: 28px;
            background: #d2d2d7;
            border-radius: 14px;
            cursor: pointer;
            transition: background 0.3s;
        }
        
        .toggle-switch.active {
            background: #34c759;
        }
        
        .toggle-slider {
            position: absolute;
            top: 2px;
            left: 2px;
            width: 24px;
            height: 24px;
            background: white;
            border-radius: 12px;
            transition: transform 0.3s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .toggle-switch.active .toggle-slider {
            transform: translateX(20px);
        }
        
        /* Plots Container */
        .plots-container {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        
        .plot-wrapper {
            margin-bottom: 20px;
        }
        
        /* Stats Table */
        .table-container {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        
        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        
        .table-title {
            font-size: 18px;
            font-weight: 600;
            color: #1d1d1f;
        }
        
        .table-wrapper {
            overflow-x: auto;
            max-height: 400px;
            overflow-y: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        
        th {
            background: #f5f5f7;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #3e3e43;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #e5e5ea;
        }
        
        tr:hover {
            background: #fafafa;
        }
        
        /* Footnotes */
        .footnotes {
            background: #f5f5f7;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        
        .footnotes h3 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 12px;
            color: #1d1d1f;
        }
        
        .footnotes p {
            font-size: 13px;
            color: #86868b;
            margin-bottom: 8px;
            line-height: 1.5;
        }
        
        /* Loading State */
        .loading {
            text-align: center;
            padding: 40px;
            color: #86868b;
        }
        
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #0071e3;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 16px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* Warnings */
        .warnings {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 20px;
            color: #856404;
            font-size: 13px;
        }
        
        .warnings h4 {
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .kpi-container {
                grid-template-columns: 1fr;
            }
            
            .controls {
                flex-direction: column;
                align-items: stretch;
            }
            
            .control-group {
                justify-content: space-between;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header with KPIs -->
        <div class="header">
            <h1>Baseline Analytics</h1>
            <div class="kpi-container" id="kpiContainer">
                <!-- KPI chips will be inserted here -->
            </div>
            <div class="context-line" id="contextLine">
                Loading baseline data...
            </div>
        </div>
        
        <!-- Warnings (if any) -->
        <div id="warningsContainer"></div>
        
        <!-- Controls -->
        <div class="controls">
            <div class="control-group">
                <label class="control-label">Fixed (m):</label>
                <input type="number" id="mInput" value="14" min="1" max="30">
            </div>
            <div class="control-group">
                <label class="control-label">Rolling (n):</label>
                <input type="number" id="nInput" value="7" min="3" max="14">
            </div>
            <div class="control-group">
                <label class="control-label">Max Sessions:</label>
                <input type="number" id="maxSessionsInput" value="300" min="10" max="500">
            </div>
            <button onclick="updateBaseline()">Update</button>
            <div class="control-group">
                <label class="control-label">Show Rolling Bands:</label>
                <div class="toggle-switch" id="rollingBandsToggle" onclick="toggleRollingBands()">
                    <div class="toggle-slider"></div>
                </div>
            </div>
        </div>
        
        <!-- Global Legend -->
        <div class="legend-card">
            <div class="legend-title">Global Style Key</div>
            <div class="legend-grid">
                <div class="legend-item">
                    <div class="legend-symbol">
                        <svg width="30" height="2">
                            <line x1="0" y1="1" x2="30" y2="1" stroke="#0072B2" stroke-width="2"/>
                        </svg>
                    </div>
                    <span>Fixed baseline (m-point)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-symbol">
                        <svg width="30" height="2">
                            <line x1="0" y1="1" x2="30" y2="1" stroke="#D55E00" stroke-width="2" stroke-dasharray="5,3"/>
                        </svg>
                    </div>
                    <span>Rolling mean (n-point)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-symbol">
                        <svg width="30" height="20">
                            <rect x="0" y="5" width="30" height="10" fill="#0072B2" opacity="0.25"/>
                        </svg>
                    </div>
                    <span>±1 SD band</span>
                </div>
                <div class="legend-item">
                    <div class="legend-symbol">
                        <svg width="30" height="20">
                            <rect x="0" y="5" width="30" height="10" fill="#0072B2" opacity="0.15"/>
                        </svg>
                    </div>
                    <span>±2 SD band</span>
                </div>
                <div class="legend-item">
                    <div class="legend-symbol">
                        <svg width="30" height="20">
                            <circle cx="15" cy="10" r="4" fill="#7F7F7F" stroke="#4D4D4D" stroke-width="1"/>
                        </svg>
                    </div>
                    <span>Session points</span>
                </div>
                <div class="legend-item">
                    <div class="legend-symbol">
                        <svg width="30" height="20">
                            <rect x="12" y="7" width="6" height="6" fill="none" stroke="#CC0000" stroke-width="2" transform="rotate(45 15 10)"/>
                        </svg>
                    </div>
                    <span>Outliers (optional)</span>
                </div>
            </div>
            <div style="margin-top: 12px; font-size: 12px; color: #86868b;">
                Timescale: Session Index (equal spacing) · Real Date/Time shown on top axis
            </div>
        </div>
        
        <!-- Plots -->
        <div class="plots-container">
            <div id="plotsContainer">
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Loading baseline visualization...</p>
                </div>
            </div>
        </div>
        
        <!-- Stats Table -->
        <div class="table-container">
            <div class="table-header">
                <div class="table-title">Session Details</div>
                <div class="control-group">
                    <label class="control-label">Sync to view:</label>
                    <div class="toggle-switch" id="syncTableToggle" onclick="toggleTableSync()">
                        <div class="toggle-slider"></div>
                    </div>
                </div>
            </div>
            <div class="table-wrapper">
                <table id="statsTable">
                    <thead>
                        <tr>
                            <th>Session #</th>
                            <th>Date/Time</th>
                            <th>Duration</th>
                            <th>RMSSD</th>
                            <th>SDNN</th>
                            <th>SD2/SD1</th>
                            <th>Mean HR</th>
                            <th>Roll RMSSD</th>
                            <th>Roll SDNN</th>
                            <th>Tags</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <!-- Rows will be inserted here -->
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Footnotes -->
        <div class="footnotes">
            <h3>Methods & Notes</h3>
            <p><strong>SD Bands:</strong> Standard deviation bands shown at ±1 SD (darker) and ±2 SD (lighter) from the mean.</p>
            <p><strong>Median-based SD:</strong> Calculated as MAD × 1.4826 for robust estimation.</p>
            <p><strong>Fixed Baseline:</strong> Computed from the last m valid sessions per metric (constant reference).</p>
            <p><strong>Rolling Baseline:</strong> n-point moving window updated per session (dynamic reference).</p>
            <p><strong>Insufficient Data:</strong> Bands are hidden when fewer than 5 points are available for fixed baseline.</p>
            <p><strong>Non-negative Metrics:</strong> Display bands are clamped at 0 for RMSSD, SDNN, and Mean HR.</p>
            <p><strong>Significance:</strong> |z| > 2 (significant), |z| > 1 (notable), |z| < 1 (not significant).</p>
        </div>
    </div>
    
    <script src="/static/baseline.js"></script>
</body>
</html>'''

if __name__ == '__main__':
    app.run(debug=True, port=5002)
