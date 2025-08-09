#!/usr/bin/env python3
"""
HRV Brain Canonical API v5.3.1
Production-ready Flask API fully compatible with DB v4.1

Version: 5.3.1 PRODUCTION
Compatible with: db_schema_v4.1.sql (Final Production Schema)

Key changes in v5.3.1:
- Returns event_id on duplicate session uploads (important for retries)
- Analytics functions use p_window parameter (backward compatible with points/events)
- Expanded metric allow-lists to include all 9 metrics
- Added /api/v1/sessions endpoint alias for spec compliance
- Better error mapping for trigger constraints
- Documentation for multi-device safety

IMPORTANT NOTES:
- Idempotency is in-memory only (use Redis for production deployments)
- Service role DB credentials required (bypasses RLS in Supabase)
"""

import os
import re
import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
import hashlib
import json
from typing import Dict, List, Optional, Tuple, Any
from session_validator import session_validator
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

# Load environment variables early
from dotenv import load_dotenv
load_dotenv('.env.railway')

# Import local modules
from database_config import DatabaseConfig
from hrv_metrics import calculate_hrv_metrics

# =====================================================
# CONFIGURATION
# =====================================================

# API Version
API_VERSION = "5.3.1"

# Configure structured logging
logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure CORS - restrict in production
cors_origins = os.environ.get('CORS_ORIGINS', '*')
if cors_origins != '*':
    cors_origins = cors_origins.split(',')
CORS(app, origins=cors_origins)

# Database configuration
db_config = DatabaseConfig()

# =====================================================
# CANONICAL TAG SYSTEM CONSTANTS
# =====================================================

CANONICAL_TAGS = {
    'wake_check', 'pre_sleep', 'sleep', 'experiment'
}

# Strict subtag patterns per canonical specification (WITH PREFIXES)
SUBTAG_PATTERNS = {
    'wake_check': r'^wake_check_(single|paired_day_pre)$',
    'pre_sleep': r'^pre_sleep_(single|paired_day_post)$',
    'sleep': r'^sleep_interval_[1-9][0-9]*$',
    'experiment': r'^experiment_(single|protocol_[a-z0-9_]+)$'
}

# Event ID rules (trigger-based allocation)
EVENT_ID_RULES = {
    'wake_check': lambda eid: eid == 0,
    'pre_sleep': lambda eid: eid == 0,
    'sleep': lambda eid: eid >= 0,  # Allow 0 (trigger assigns) or >0 (explicit)
    'experiment': lambda eid: eid == 0
}

# EXPANDED: All 9 metrics supported by DB v4.0
VALID_METRICS = ['rmssd', 'sdnn', 'sd2_sd1', 'mean_hr', 'mean_rr', 'rr_count', 'pnn50', 'cv_rr', 'defa']

# =====================================================
# DATABASE CONNECTION POOL
# =====================================================

connection_pool = None

def initialize_connection_pool():
    """Initialize PostgreSQL connection pool"""
    global connection_pool
    try:
        connection_pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            host=db_config.host,
            port=db_config.port,
            database=db_config.database,
            user=db_config.user,
            password=db_config.password,
            options='-c search_path=public'
        )
        logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise

def get_db_connection():
    """Get a connection from the pool"""
    if not connection_pool:
        initialize_connection_pool()
    conn = connection_pool.getconn()
    # Ensure autocommit is off so we can control transactions
    conn.autocommit = False
    return conn

def return_db_connection(conn):
    """Return a connection to the pool"""
    if connection_pool and conn:
        connection_pool.putconn(conn)

# Initialize pool on startup
initialize_connection_pool()

# =====================================================
# IDEMPOTENCY STORE (In-Memory for Development)
# =====================================================

# NOTE: In production, use Redis with TTL for distributed systems
idempotency_store = defaultdict(dict)
IDEMPOTENCY_TTL = 86400  # 24 hours in seconds

def check_idempotency(user_id: str, key: str) -> Optional[Dict]:
    """Check if request with idempotency key was already processed"""
    if key in idempotency_store[user_id]:
        stored = idempotency_store[user_id][key]
        if time.time() - stored['timestamp'] < IDEMPOTENCY_TTL:
            return stored['response']
        else:
            del idempotency_store[user_id][key]
    return None

def store_idempotency(user_id: str, key: str, response: Dict):
    """Store idempotency key with response"""
    idempotency_store[user_id][key] = {
        'timestamp': time.time(),
        'response': response
    }

# =====================================================
# VALIDATION FUNCTIONS
# =====================================================

def validate_uuid(value: str) -> Tuple[bool, Optional[str]]:
    """Validate UUID format"""
    try:
        # Accept with or without hyphens
        clean_uuid = value.replace('-', '')
        if len(clean_uuid) != 32:
            return False, "Invalid UUID format"
        int(clean_uuid, 16)  # Check if valid hex
        return True, None
    except (ValueError, AttributeError):
        return False, "Invalid UUID format"

def validate_tag(tag: str) -> Tuple[bool, Optional[str]]:
    """Validate canonical tag"""
    if tag not in CANONICAL_TAGS:
        return False, f"Invalid tag. Must be one of: {', '.join(sorted(CANONICAL_TAGS))}"
    return True, None

def validate_subtag(tag: str, subtag: str) -> Tuple[bool, Optional[str]]:
    """Validate subtag against canonical patterns (WITH PREFIXES)"""
    pattern = SUBTAG_PATTERNS.get(tag)
    if not pattern:
        return False, f"No subtag pattern defined for tag '{tag}'"
    
    if not re.match(pattern, subtag):
        return False, f"Invalid subtag for {tag}. Must match pattern: {pattern}"
    
    return True, None

def validate_event_id(tag: str, event_id: int) -> Tuple[bool, Optional[str]]:
    """Validate event_id based on tag rules
    
    For trigger-based allocation:
    - Sleep sessions can have event_id=0 (DB will auto-assign) or event_id>0 (explicit)
    - Non-sleep sessions must have event_id=0
    
    MULTI-DEVICE SAFETY:
    - For sleep_interval_1: Send event_id=0, read returned event_id
    - For sleep_interval_2+: Send the explicit event_id from interval_1
    """
    if tag == 'sleep':
        # Sleep: allow 0 (DB assigns) or >0 (explicit attach/backfill)
        if event_id < 0:
            return False, "Sleep sessions must have event_id >= 0 (use 0 for auto-assignment)"
    else:
        # Non-sleep: must be 0
        if event_id != 0:
            return False, f"{tag} sessions must have event_id = 0"
    
    return True, None

def validate_session_payload(data: Dict) -> Tuple[Dict, Dict]:
    """
    Validate session upload payload
    Returns: (validated_data, errors)
    """
    validated = {}
    errors = {}
    
    # Required fields (INCLUDING session_id per spec)
    required_fields = [
        'user_id', 'session_id', 'tag', 'subtag', 'event_id',
        'recorded_at', 'duration_minutes', 'rr_intervals'
    ]
    
    for field in required_fields:
        if field not in data:
            errors[field] = f"Required field '{field}' is missing"
    
    if errors:
        return {}, errors
    
    # Validate user_id
    is_valid, error = validate_uuid(data['user_id'])
    if not is_valid:
        errors['user_id'] = error
    else:
        validated['user_id'] = data['user_id']
    
    # Validate session_id
    is_valid, error = validate_uuid(data['session_id'])
    if not is_valid:
        errors['session_id'] = error
    else:
        validated['session_id'] = data['session_id']
    
    # Validate tag
    is_valid, error = validate_tag(data['tag'])
    if not is_valid:
        errors['tag'] = error
    else:
        validated['tag'] = data['tag']
    
    # Validate subtag (only if tag is valid)
    if 'tag' not in errors:
        is_valid, error = validate_subtag(data['tag'], data['subtag'])
        if not is_valid:
            errors['subtag'] = error
        else:
            validated['subtag'] = data['subtag']
    
    # Validate event_id
    try:
        event_id = int(data['event_id'])
        if 'tag' not in errors:
            is_valid, error = validate_event_id(data['tag'], event_id)
            if not is_valid:
                errors['event_id'] = error
            else:
                validated['event_id'] = event_id
    except (ValueError, TypeError):
        errors['event_id'] = "Must be an integer"
    
    # Validate recorded_at (must have timezone)
    try:
        recorded_at = datetime.fromisoformat(data['recorded_at'].replace('Z', '+00:00'))
        if recorded_at.tzinfo is None:
            errors['recorded_at'] = "Timestamp must include timezone information"
        else:
            # Convert to UTC
            validated['recorded_at'] = recorded_at.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        errors['recorded_at'] = "Invalid ISO format timestamp with timezone required"
    
    # Validate duration_minutes
    try:
        duration = int(data['duration_minutes'])
        if duration <= 0:
            errors['duration_minutes'] = "Must be greater than 0"
        else:
            validated['duration_minutes'] = duration
    except (ValueError, TypeError):
        errors['duration_minutes'] = "Must be a positive integer"
    
    # Validate rr_intervals
    if not isinstance(data.get('rr_intervals'), list):
        errors['rr_intervals'] = "Must be an array of numbers"
    elif len(data['rr_intervals']) == 0:
        errors['rr_intervals'] = "Array cannot be empty"
    else:
        try:
            # Validate each RR interval
            rr_intervals = []
            for i, rr in enumerate(data['rr_intervals']):
                rr_val = float(rr)
                if rr_val <= 0 or rr_val > 3000:
                    errors['rr_intervals'] = f"RR interval at index {i} out of range (0-3000ms)"
                    break
                rr_intervals.append(rr_val)
            
            if 'rr_intervals' not in errors:
                validated['rr_intervals'] = rr_intervals
                
                # Optional: validate rr_count if provided
                if 'rr_count' in data:
                    try:
                        rr_count = int(data['rr_count'])
                        if rr_count != len(rr_intervals):
                            errors['rr_count'] = f"Mismatch: rr_count={rr_count} but array has {len(rr_intervals)} intervals"
                        else:
                            validated['rr_count'] = rr_count
                    except (ValueError, TypeError):
                        errors['rr_count'] = "Must be an integer"
                else:
                    validated['rr_count'] = len(rr_intervals)
                    
        except (ValueError, TypeError) as e:
            errors['rr_intervals'] = f"Invalid RR interval values: {str(e)}"
    
    return validated, errors

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def call_sql_named(conn, function_name: str, params: Dict[str, Any]) -> List[Dict]:
    """
    Call a SQL function with named parameters
    This ensures parameters are passed correctly regardless of order
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        # Build the function call with named parameters
        param_list = [f"{key} := %({key})s" for key in params.keys()]
        query = f"SELECT * FROM {function_name}({', '.join(param_list)})"
        
        cursor.execute(query, params)
        return cursor.fetchall()

def get_input_fingerprint(data: Dict) -> str:
    """Generate a fingerprint of input data for logging"""
    # Create a deterministic string representation
    key_parts = [
        data.get('user_id', '')[:8],
        data.get('session_id', '')[:8],
        data.get('tag', ''),
        data.get('subtag', ''),
        str(data.get('event_id', '')),
        str(data.get('recorded_at', ''))[:19]
    ]
    fingerprint = '|'.join(key_parts)
    return hashlib.md5(fingerprint.encode()).hexdigest()[:12]

# =====================================================
# API ENDPOINTS
# =====================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check"""
    return jsonify({
        'status': 'healthy',
        'version': API_VERSION,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200

@app.route('/health/detailed', methods=['GET'])
def health_check_detailed():
    """Detailed health check with database connectivity test"""
    try:
        conn = None
        db_status = 'unknown'
        db_error = None
        
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
                result = cur.fetchone()
                db_status = 'connected' if result else 'error'
        except Exception as e:
            db_status = 'error'
            db_error = str(e)
        finally:
            if conn:
                return_db_connection(conn)
        
        return jsonify({
            'status': 'healthy',
            'version': API_VERSION,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database': {
                'status': db_status,
                'error': db_error
            },
            'features': {
                'canonical_tags': True,
                'idempotency': 'in-memory',
                'analytics': True,
                'constraints': True,
                'trigger_allocation': True,
                'db_v4_1_compatible': True,
                'duplicate_event_id_return': True  # NEW
            }
        }), 200
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({
            'status': 'error',
            'version': API_VERSION,
            'error': str(e)
        }), 500

# =====================================================
# SLEEP EVENT ID ALLOCATION
# =====================================================

@app.route('/api/v1/sleep/allocate-event-id', methods=['POST'])
def allocate_sleep_event_id():
    """
    OPTIONAL: Explicitly allocate a sleep event ID.
    
    Most clients should just send sleep sessions with event_id=0 and let
    the database trigger handle allocation automatically.
    
    This endpoint remains available for:
    - Clients that need to know the event_id before uploading
    - Special workflows requiring explicit allocation
    - Backward compatibility
    
    Returns: {"event_id": <allocated_id>}
    """
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': 'user_id is required'}), 400
        
        user_id = data['user_id']
        
        # Validate UUID
        is_valid, error = validate_uuid(user_id)
        if not is_valid:
            return jsonify({'error': error}), 400
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Call the allocator function
                cursor.execute(
                    "SELECT public.fn_allocate_sleep_event_id(%s) as event_id",
                    (user_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    return jsonify({'error': 'Failed to allocate event_id'}), 500
                
                event_id = result[0]
                conn.commit()
                
                logger.info(f"Allocated event_id {event_id} for user {user_id}")
                
                return jsonify({
                    'event_id': event_id,
                    'user_id': user_id,
                    'message': 'Event ID allocated. Note: You can also send event_id=0 to auto-allocate.'
                }), 200
                
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error allocating event_id: {str(e)}")
            return jsonify({'error': 'Failed to allocate event_id'}), 500
        finally:
            if conn:
                return_db_connection(conn)
                
    except Exception as e:
        logger.error(f"Unexpected error in allocate_sleep_event_id: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# =====================================================
# ANALYTICS ENDPOINTS (UPDATED FOR DB v4.0)
# =====================================================

@app.route('/api/v1/analytics/baseline', methods=['GET'])
def analytics_baseline():
    """Get baseline analytics points"""
    try:
        user_id = request.args.get('user_id')
        metric = request.args.get('metric', 'rmssd')
        
        # UPDATED: Support both 'window' (new) and 'points' (backward compat)
        window = request.args.get('window', type=int)
        if window is None:
            window = request.args.get('points', 100, type=int)
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        ok, err = validate_uuid(user_id)
        if not ok:
            return jsonify({'error': err}), 400
        
        # UPDATED: Validate against full metric list
        if metric not in VALID_METRICS:
            return jsonify({'error': f'Invalid metric. Must be one of: {", ".join(VALID_METRICS)}'}), 400
        
        # UPDATED: Use p_window for DB v4.0 compatibility
        params = {
            'p_user_id': user_id,
            'p_metric': metric,
            'p_window': window  # Changed from p_points
        }
        
        conn = None
        try:
            conn = get_db_connection()
            results = call_sql_named(conn, 'public.fn_baseline_points', params)
            
            # Convert datetime fields and cast decimals to float
            for row in results:
                if row.get('t'):
                    row['timestamp'] = row.pop('t').isoformat()
                if row.get('value') is not None:
                    row['value'] = float(row['value'])
                if row.get('rolling_avg') is not None:
                    row['rolling_avg'] = float(row['rolling_avg'])
                if row.get('rolling_sd') is not None:
                    row['rolling_sd'] = float(row['rolling_sd'])
            
            return jsonify({
                'status': 'success',
                'user_id': user_id,
                'metric': metric,
                'window': window,  # Return both for clarity
                'points': window,  # Backward compat
                'results': results
            }), 200
            
        except Exception as e:
            logger.error(f"Database error in baseline analytics: {str(e)}")
            return jsonify({'error': 'Analytics query failed'}), 500
        finally:
            if conn:
                return_db_connection(conn)
                
    except Exception as e:
        logger.error(f"Unexpected error in analytics_baseline: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/analytics/micro-sleep', methods=['GET'])
def analytics_micro_sleep():
    """Get micro-sleep analytics points"""
    try:
        user_id = request.args.get('user_id')
        metric = request.args.get('metric', 'rmssd')
        
        # UPDATED: Support both 'window' and 'points'
        window = request.args.get('window', type=int)
        if window is None:
            window = request.args.get('points', 30, type=int)
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        ok, err = validate_uuid(user_id)
        if not ok:
            return jsonify({'error': err}), 400
        
        # UPDATED: Full metric validation
        if metric not in VALID_METRICS:
            return jsonify({'error': f'Invalid metric. Must be one of: {", ".join(VALID_METRICS)}'}), 400
        
        # UPDATED: Use p_window
        params = {
            'p_user_id': user_id,
            'p_metric': metric,
            'p_window': window
        }
        
        conn = None
        try:
            conn = get_db_connection()
            results = call_sql_named(conn, 'public.fn_micro_sleep_points', params)
            
            # Convert datetime fields and cast decimals to float
            for row in results:
                if row.get('t'):
                    row['timestamp'] = row.pop('t').isoformat()
                for k in ('value', 'rolling_avg', 'rolling_sd'):
                    if row.get(k) is not None:
                        row[k] = float(row[k])
                if row.get('event_id') is not None:
                    row['event_id'] = int(row['event_id'])
                if row.get('interval_number') is not None:
                    row['interval_number'] = int(row['interval_number'])
            
            return jsonify({
                'status': 'success',
                'user_id': user_id,
                'metric': metric,
                'window': window,
                'points': window,  # Backward compat
                'results': results
            }), 200
            
        except Exception as e:
            logger.error(f"Database error in micro-sleep analytics: {str(e)}")
            return jsonify({'error': 'Analytics query failed'}), 500
        finally:
            if conn:
                return_db_connection(conn)
                
    except Exception as e:
        logger.error(f"Unexpected error in analytics_micro_sleep: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/analytics/macro-sleep', methods=['GET'])
def analytics_macro_sleep():
    """Get macro-sleep analytics points (aggregated by event)"""
    try:
        user_id = request.args.get('user_id')
        metric = request.args.get('metric', 'rmssd')
        
        # UPDATED: Support both 'window' and 'events'
        window = request.args.get('window', type=int)
        if window is None:
            window = request.args.get('events', 3, type=int)
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        ok, err = validate_uuid(user_id)
        if not ok:
            return jsonify({'error': err}), 400
        
        # UPDATED: Full metric validation
        if metric not in VALID_METRICS:
            return jsonify({'error': f'Invalid metric. Must be one of: {", ".join(VALID_METRICS)}'}), 400
        
        # UPDATED: Use p_window
        params = {
            'p_user_id': user_id,
            'p_metric': metric,
            'p_window': window
        }
        
        conn = None
        try:
            conn = get_db_connection()
            results = call_sql_named(conn, 'public.fn_macro_sleep_points', params)
            
            # Convert datetime fields and format results
            for row in results:
                if row.get('t'):
                    row['timestamp'] = row.pop('t').isoformat()
                if row.get('avg_value') is not None:
                    row['avg_value'] = float(row['avg_value'])
                if row.get('rolling_avg') is not None:
                    row['rolling_avg'] = float(row['rolling_avg'])
                if row.get('event_id') is not None:
                    row['event_id'] = int(row['event_id'])
            
            return jsonify({
                'status': 'success',
                'user_id': user_id,
                'metric': metric,
                'window': window,
                'events': window,  # Backward compat
                'results': results
            }), 200
            
        except Exception as e:
            logger.error(f"Database error in macro-sleep analytics: {str(e)}")
            return jsonify({'error': 'Analytics query failed'}), 500
        finally:
            if conn:
                return_db_connection(conn)
                
    except Exception as e:
        logger.error(f"Unexpected error in analytics_macro_sleep: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/analytics/day-load', methods=['GET'])
def analytics_day_load():
    """Get day-load analytics points"""
    try:
        user_id = request.args.get('user_id')
        metric = request.args.get('metric', 'rmssd')
        min_hours = request.args.get('min_hours', 12, type=int)
        max_hours = request.args.get('max_hours', 18, type=int)
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        ok, err = validate_uuid(user_id)
        if not ok:
            return jsonify({'error': err}), 400
        
        # UPDATED: Full metric validation
        if metric not in VALID_METRICS:
            return jsonify({'error': f'Invalid metric. Must be one of: {", ".join(VALID_METRICS)}'}), 400
        
        # Validate hours
        if min_hours < 0 or max_hours > 24 or min_hours >= max_hours:
            return jsonify({'error': 'Invalid hour range. Must be 0 <= min_hours < max_hours <= 24'}), 400
        
        # Build parameters for DB function (no change needed here)
        params = {
            'p_user_id': user_id,
            'p_metric': metric,
            'p_min_hours': min_hours,
            'p_max_hours': max_hours
        }
        
        conn = None
        try:
            conn = get_db_connection()
            results = call_sql_named(conn, 'public.fn_day_load_points', params)

            # Map to API fields
            for row in results:
                if row.get('day_date'):
                    row['day_date'] = row['day_date'].isoformat()
                if row.get('wake_ts'):
                    row['wake_timestamp'] = row.pop('wake_ts').isoformat()
                if row.get('pre_ts'):
                    row['pre_sleep_timestamp'] = row.pop('pre_ts').isoformat()
                for k in ('wake_value', 'pre_value', 'delta_value'):
                    if row.get(k) is not None:
                        row[k] = float(row[k])
            
            return jsonify({
                'status': 'success',
                'user_id': user_id,
                'metric': metric,
                'min_hours': min_hours,
                'max_hours': max_hours,
                'results': results
            }), 200
            
        except Exception as e:
            logger.error(f"Database error in day-load analytics: {str(e)}")
            return jsonify({'error': 'Analytics query failed'}), 500
        finally:
            if conn:
                return_db_connection(conn)
                
    except Exception as e:
        logger.error(f"Unexpected error in analytics_day_load: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/analytics/experiment', methods=['GET'])
def analytics_experiment():
    """Get experiment analytics points"""
    try:
        user_id = request.args.get('user_id')
        metric = request.args.get('metric', 'rmssd')
        protocol = request.args.get('protocol')  # Optional
        
        # UPDATED: Support both 'window' and 'points'
        window = request.args.get('window', type=int)
        if window is None:
            window = request.args.get('points', 100, type=int)
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        ok, err = validate_uuid(user_id)
        if not ok:
            return jsonify({'error': err}), 400
        
        # UPDATED: Full metric validation
        if metric not in VALID_METRICS:
            return jsonify({'error': f'Invalid metric. Must be one of: {", ".join(VALID_METRICS)}'}), 400
        
        # Map protocol to subtag pattern
        protocol_subtag = None
        if protocol:
            if protocol == 'single':
                protocol_subtag = 'experiment_single'
            elif protocol.startswith('protocol_'):
                protocol_subtag = f'experiment_{protocol}'
            else:
                protocol_subtag = f'experiment_protocol_{protocol}'
        
        # UPDATED: Use p_window
        params = {
            'p_user_id': user_id,
            'p_metric': metric,
            'p_window': window,
            'p_protocol_subtag': protocol_subtag
        }
        
        conn = None
        try:
            conn = get_db_connection()
            results = call_sql_named(conn, 'public.fn_experiment_points', params)
            
            # Convert datetime fields and cast decimals to float
            for row in results:
                if row.get('t'):
                    row['timestamp'] = row.pop('t').isoformat()
                if row.get('value') is not None:
                    row['value'] = float(row['value'])
                if row.get('rolling_avg') is not None:
                    row['rolling_avg'] = float(row['rolling_avg'])
            
            return jsonify({
                'status': 'success',
                'user_id': user_id,
                'metric': metric,
                'window': window,
                'points': window,  # Backward compat
                'protocol': protocol,
                'protocol_subtag': protocol_subtag,
                'results': results
            }), 200
            
        except Exception as e:
            logger.error(f"Database error in experiment analytics: {str(e)}")
            return jsonify({'error': 'Analytics query failed'}), 500
        finally:
            if conn:
                return_db_connection(conn)
                
    except Exception as e:
        logger.error(f"Unexpected error in analytics_experiment: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# =====================================================
# SESSION ENDPOINTS
# =====================================================

@app.route('/api/v1/sessions/upload', methods=['POST'])
def upload_session():
    """
    Upload and process a new HRV session
    
    UPDATED in v5.3.0:
    - Compatible with DB v4.0 trigger-based allocation
    - Returns assigned event_id for multi-device safety
    - Better error mapping for trigger constraints
    
    MULTI-DEVICE SAFETY:
    - For sleep_interval_1: Send event_id=0, save returned event_id
    - For sleep_interval_2+: Send the saved event_id explicitly
    """
    try:
        # Get and validate input
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Idempotency: only meaningful if we have both user_id and key
        idempotency_key = request.headers.get('Idempotency-Key')
        if idempotency_key and data.get('user_id'):
            cached = check_idempotency(data['user_id'], idempotency_key)
            if cached:
                logger.info(f"Idempotent request detected: {idempotency_key}")
                return jsonify(cached), 200
        
        # Generate input fingerprint for logging
        fingerprint = get_input_fingerprint(data)
        logger.info(f"Processing session upload: fingerprint={fingerprint}")
        
        # Validate canonical fields
        validated, errors = validate_session_payload(data)
        if errors:
            logger.warning(f"Validation failed: {errors}")
            response = {'error': 'Validation failed', 'details': errors}
            # Store validation errors for idempotency
            if idempotency_key and data.get('user_id'):
                store_idempotency(data['user_id'], idempotency_key, response)
            return jsonify(response), 400
        
        # NEW: Run modular session validator
        validation_report = session_validator.get_validation_report(validated)
        validation_result = validation_report['validation_result']
        
        if not validation_result['is_valid']:
            logger.warning(f"Session validation failed: {validation_result['errors']}")
            response = {
                'error': 'Session validation failed',
                'validation_report': validation_report,
                'message': validation_result['errors'][0] if validation_result['errors'] else 'Invalid session data'
            }
            # Store validation errors for idempotency
            if idempotency_key and data.get('user_id'):
                store_idempotency(data['user_id'], idempotency_key, response)
            return jsonify(response), 400
        
        # Extract validated fields
        user_id = validated['user_id']
        session_id = validated['session_id']
        tag = validated['tag']
        subtag = validated['subtag']
        event_id = validated['event_id']
        recorded_at = validated['recorded_at']
        duration_minutes = validated['duration_minutes']
        rr_intervals = validated['rr_intervals']
        rr_count = validated.get('rr_count', len(rr_intervals))
        
        # Calculate HRV metrics
        try:
            metrics = calculate_hrv_metrics(rr_intervals)
            
            # Ensure duration_minutes is int for DB
            duration_minutes = int(duration_minutes)
            
        except Exception as e:
            logger.error(f"HRV calculation failed: {str(e)}")
            response = {'error': f'HRV calculation failed: {str(e)}'}
            # Store HRV errors for idempotency
            if idempotency_key and user_id:
                store_idempotency(user_id, idempotency_key, response)
            return jsonify(response), 500
        
        # Insert into database
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                # Return both session_id AND event_id for multi-device safety
                insert_query = """
                    INSERT INTO sessions (
                        session_id, user_id, tag, subtag, event_id,
                        recorded_at, duration_minutes, 
                        rr_intervals, rr_count,
                        mean_hr, mean_rr, rmssd, sdnn, pnn50,
                        cv_rr, defa, sd2_sd1
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s
                    )
                    ON CONFLICT (session_id) DO NOTHING
                    RETURNING session_id, event_id
                """
                
                cursor.execute(insert_query, (
                    session_id, user_id, tag, subtag, event_id,
                    recorded_at, duration_minutes,
                    rr_intervals, rr_count,
                    metrics['mean_hr'], metrics['mean_rr'],
                    metrics['rmssd'], metrics['sdnn'], metrics['pnn50'],
                    metrics['cv_rr'], metrics['defa'], metrics['sd2_sd1']
                ))
                
                result = cursor.fetchone()
                if not result:
                    # Session already exists (conflict) - fetch the event_id for retries
                    cursor.execute(
                        "SELECT event_id FROM sessions WHERE session_id = %s",
                        (session_id,)
                    )
                    existing = cursor.fetchone()
                    existing_event_id = existing[0] if existing else None
                    
                    logger.info(f"Session {session_id} already exists with event_id={existing_event_id}")
                    response = {
                        'status': 'duplicate',
                        'session_id': session_id,
                        'event_id': existing_event_id,  # Important for sleep_interval_1 retries
                        'message': 'Session already exists'
                    }
                    status_code = 200
                else:
                    conn.commit()
                    
                    # Extract the assigned event_id (important for sleep sessions)
                    assigned_event_id = result[1]
                    
                    # Log if event_id was auto-assigned
                    if tag == 'sleep' and event_id == 0 and assigned_event_id > 0:
                        logger.info(f"Session {session_id} auto-assigned event_id={assigned_event_id}")
                    
                    logger.info(f"Session {session_id} inserted successfully with event_id={assigned_event_id}")
                    
                    response = {
                        'session_id': result['session_id'],
                        'event_id': result['event_id'],  # Return for multi-device safety
                        'message': 'Session uploaded successfully',
                        'metrics': metrics,
                        'validation_report': validation_report,  # Include validation details
                        'db_status': 'saved'  # Confirm DB save status
                    }
                    status_code = 201
                
                # Store for idempotency
                if idempotency_key:
                    store_idempotency(user_id, idempotency_key, response)
                
                return jsonify(response), status_code
                
        except psycopg2.IntegrityError as e:
            conn.rollback()
            # Map constraint violations to friendly messages
            error_msg = str(e)
            constraint_name = e.diag.constraint_name if hasattr(e.diag, 'constraint_name') else None
            
            if constraint_name == 'chk_tag_values':
                return jsonify({'error': 'Invalid tag. Must be one of: wake_check, pre_sleep, sleep, experiment'}), 400
            elif constraint_name == 'chk_subtag_by_tag':
                return jsonify({'error': 'Subtag does not match the required pattern for the tag'}), 400
            elif constraint_name == 'chk_sleep_grouping':
                return jsonify({'error': 'Invalid event_id for tag (sleep >= 0, non-sleep = 0)'}), 400
            elif constraint_name == 'chk_rr_len_matches_count':
                return jsonify({'error': 'rr_count must equal rr_intervals array length'}), 400
            elif constraint_name == 'chk_rr_count_positive':
                return jsonify({'error': 'rr_count must be greater than 0'}), 400
            elif constraint_name == 'chk_duration_positive':
                return jsonify({'error': 'duration_minutes must be greater than 0'}), 400
            elif constraint_name == 'chk_metric_ranges_soft':
                return jsonify({'error': 'One or more metrics are outside allowed ranges'}), 400
            elif constraint_name == 'sessions_pkey' or 'sessions_pkey' in error_msg:
                return jsonify({'error': 'Session ID already exists'}), 409
            elif constraint_name == 'trg_check_sleep_event_id':
                return jsonify({'error': 'Sleep session must have event_id > 0 after processing'}), 400
            elif constraint_name == 'uq_sleep_interval_per_user_event':
                return jsonify({'error': 'Duplicate sleep interval for this event'}), 409
            else:
                logger.error(f"Database constraint violation ({constraint_name}): {error_msg}")
                return jsonify({'error': 'Data constraint violation', 'constraint': constraint_name}), 400
                
        except Exception as e:
            if conn:
                conn.rollback()
            
            # UPDATED: Better error mapping for trigger messages
            error_msg = str(e)
            if "Cannot attach interval" in error_msg:
                logger.warning(f"Sleep event attachment error: {error_msg}")
                return jsonify({
                    'error': 'Cannot attach sleep interval',
                    'message': 'No existing sleep event found. Start with sleep_interval_1 or provide a valid event_id.'
                }), 400
            elif "Out-of-order interval" in error_msg:
                logger.warning(f"Out-of-order sleep interval: {error_msg}")
                return jsonify({
                    'error': 'Out-of-order sleep interval',
                    'message': 'Sleep intervals must be uploaded sequentially. Check the previous interval number.'
                }), 400
            elif "Invalid sleep subtag" in error_msg:
                return jsonify({
                    'error': 'Invalid sleep subtag',
                    'message': 'Sleep subtag must be sleep_interval_N where N >= 1'
                }), 400
            # NEW: Catch AFTER trigger error message
            elif "must have event_id > 0 after trigger" in error_msg:
                return jsonify({
                    'error': 'Trigger processing failed',
                    'message': 'Sleep session must have event_id > 0 after trigger processing'
                }), 400
            
            logger.error(f"Database error: {error_msg}")
            return jsonify({'error': 'Database operation failed'}), 500
            
        finally:
            if conn:
                return_db_connection(conn)
                
    except Exception as e:
        logger.error(f"Unexpected error in upload_session: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# ADDED: Spec-compliant endpoint alias
@app.route('/api/v1/sessions', methods=['POST'])
def upload_session_alias():
    """Alias for /api/v1/sessions/upload to match specification"""
    return upload_session()

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# =====================================================
# MAIN ENTRY POINT
# =====================================================

if __name__ == '__main__':
    import sys
    port = 5000
    # Check for --port argument
    for i, arg in enumerate(sys.argv):
        if arg == '--port' and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    
    initialize_connection_pool()
    logger.info(f"Starting HRV Brain API v{API_VERSION} on port {port}")
    logger.info(f"Debug mode: {app.debug}")
    logger.info(f"Database: {db_config.host}:{db_config.port}/{db_config.database}")
    logger.info("Canonical tag system enforced with strict validation")
    logger.info("DB v4.1 compatible - using p_window parameter for analytics")
    logger.info("Returns event_id on duplicate uploads for retry safety")
    logger.info("Multi-device safety: clients should send explicit event_id for sleep_interval_2+")
    logger.info("IMPORTANT: Idempotency is in-memory only - use Redis for production")
    app.run(host='0.0.0.0', port=port, debug=False)