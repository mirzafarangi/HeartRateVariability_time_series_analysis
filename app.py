"""
HRV Brain API - Supabase Edition
Version: 3.3.4 Final
Source: schema.md (Golden Reference)

Clean, production-ready API with Supabase PostgreSQL integration.
Implements exact unified schema and all 9 HRV metrics from schema.md.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union
from uuid import UUID

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from database_config import DatabaseConfig
from hrv_metrics import calculate_hrv_metrics
import jwt
from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize database configuration
db_config = DatabaseConfig()

# Global connection pool
connection_pool = None

def initialize_connection_pool():
    """Initialize PostgreSQL connection pool"""
    global connection_pool
    try:
        connection_pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=20,
            host=db_config.host,
            database=db_config.database,
            user=db_config.user,
            password=db_config.password,
            port=db_config.port,
            cursor_factory=RealDictCursor
        )
        logger.info("✅ Database connection pool initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize connection pool: {e}")
        raise

def get_db_connection():
    """Get database connection from pool"""
    if connection_pool is None:
        initialize_connection_pool()
    return connection_pool.getconn()

def return_db_connection(conn):
    """Return database connection to pool"""
    if connection_pool and conn:
        connection_pool.putconn(conn)

# =====================================================
# VALIDATION FUNCTIONS
# =====================================================

def validate_session_data(data: Dict) -> Dict[str, str]:
    """
    Validate session data against schema.md requirements
    
    Args:
        data: Session data dictionary
        
    Returns:
        Dictionary of validation errors (empty if valid)
    """
    errors = {}
    
    # Required fields from schema.md
    required_fields = [
        'session_id', 'user_id', 'tag', 'subtag', 'event_id',
        'duration_minutes', 'recorded_at', 'rr_intervals'
    ]
    
    for field in required_fields:
        if field not in data:
            errors[field] = f"Missing required field: {field}"
    
    if errors:
        return errors
    
    # Validate tag (6 allowed base tags from schema.md)
    valid_tags = ['rest', 'sleep', 'experiment_paired_pre', 'experiment_paired_post', 'experiment_duration', 'breath_workout']
    if data['tag'] not in valid_tags:
        errors['tag'] = f"Invalid tag. Must be one of: {valid_tags}"
    
    # Validate duration (1-30 minutes from schema.md)
    try:
        duration = int(data['duration_minutes'])
        if duration < 1 or duration > 30:
            errors['duration_minutes'] = "Duration must be between 1 and 30 minutes"
    except (ValueError, TypeError):
        errors['duration_minutes'] = "Duration must be a valid integer"
    
    # Validate event_id
    try:
        event_id = int(data['event_id'])
        if event_id < 0:
            errors['event_id'] = "Event ID must be non-negative"
        
        # Sleep sessions must have event_id > 0 (from schema.md)
        if data['tag'] == 'sleep' and event_id == 0:
            errors['event_id'] = "Sleep sessions must have event_id > 0 for grouping"
        
        # Non-sleep sessions must have event_id = 0 (from schema.md)
        if data['tag'] != 'sleep' and event_id != 0:
            errors['event_id'] = "Non-sleep sessions must have event_id = 0"
            
    except (ValueError, TypeError):
        errors['event_id'] = "Event ID must be a valid integer"
    
    # Validate RR intervals
    if not isinstance(data['rr_intervals'], list):
        errors['rr_intervals'] = "RR intervals must be a list"
    elif len(data['rr_intervals']) < 10:
        errors['rr_intervals'] = "Minimum 10 RR intervals required"
    else:
        # Check if all RR intervals are valid numbers
        try:
            rr_values = [float(rr) for rr in data['rr_intervals']]
            invalid_rr = [rr for rr in rr_values if rr <= 0 or rr > 3000]
            if invalid_rr:
                errors['rr_intervals'] = f"Invalid RR intervals found: {len(invalid_rr)} values out of range"
        except (ValueError, TypeError):
            errors['rr_intervals'] = "All RR intervals must be valid numbers"
    
    # Validate recorded_at timestamp
    try:
        datetime.fromisoformat(data['recorded_at'].replace('Z', '+00:00'))
    except (ValueError, TypeError):
        errors['recorded_at'] = "Invalid timestamp format. Use ISO8601 format"
    
    return errors

def validate_uuid(uuid_string: str) -> bool:
    """Validate UUID format"""
    try:
        UUID(uuid_string)
        return True
    except ValueError:
        return False

# =====================================================
# API ENDPOINTS
# =====================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': '3.3.4',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'database': 'supabase-postgresql'
    })

@app.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with database connectivity"""
    health_status = {
        'status': 'healthy',
        'version': '3.3.4',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'database': 'supabase-postgresql',
        'components': {}
    }
    
    # Test database connectivity
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT version(), NOW()")
        db_info = cur.fetchone()
        cur.close()
        return_db_connection(conn)
        
        health_status['components']['database'] = {
            'status': 'healthy',
            'version': db_info['version'].split(',')[0],
            'timestamp': db_info['now'].isoformat()
        }
    except Exception as e:
        health_status['status'] = 'degraded'
        health_status['components']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    # Test HRV metrics calculation
    try:
        test_rr = [800, 820, 810, 830, 825, 815, 835, 820, 810, 825]
        test_metrics = calculate_hrv_metrics(test_rr)
        health_status['components']['hrv_metrics'] = {
            'status': 'healthy',
            'test_metrics_count': len(test_metrics)
        }
    except Exception as e:
        health_status['status'] = 'degraded'
        health_status['components']['hrv_metrics'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    return jsonify(health_status)

@app.route('/api/v1/sessions/upload', methods=['POST'])
def upload_session():
    """
    Upload and process HRV session
    Implements exact unified schema from schema.md
    """
    try:
        # Get and validate request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate session data
        validation_errors = validate_session_data(data)
        if validation_errors:
            return jsonify({
                'error': 'Validation failed',
                'details': validation_errors
            }), 400
        
        # Validate user_id format
        if not validate_uuid(data['user_id']):
            return jsonify({'error': 'Invalid user_id format'}), 400
        
        # Calculate HRV metrics
        try:
            hrv_metrics = calculate_hrv_metrics(data['rr_intervals'])
        except Exception as e:
            logger.error(f"HRV metrics calculation failed: {e}")
            return jsonify({
                'error': 'HRV metrics calculation failed',
                'details': str(e)
            }), 400
        
        # Store session in database
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Insert session with all data (raw + processed)
            insert_query = """
                INSERT INTO public.sessions (
                    session_id, user_id, tag, subtag, event_id,
                    duration_minutes, recorded_at, rr_intervals, rr_count,
                    status, processed_at,
                    mean_hr, mean_rr, count_rr, rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            cur.execute(insert_query, (
                data['session_id'],
                data['user_id'],
                data['tag'],
                data['subtag'],
                data['event_id'],
                data['duration_minutes'],
                data['recorded_at'],
                data['rr_intervals'],  # PostgreSQL DECIMAL[] array
                len(data['rr_intervals']),
                'completed',  # Mark as completed since we processed it
                datetime.now(timezone.utc),
                hrv_metrics['mean_hr'],
                hrv_metrics['mean_rr'],
                hrv_metrics['count_rr'],
                hrv_metrics['rmssd'],
                hrv_metrics['sdnn'],
                hrv_metrics['pnn50'],
                hrv_metrics['cv_rr'],
                hrv_metrics['defa'],
                hrv_metrics['sd2_sd1']
            ))
            
            conn.commit()
            cur.close()
            
            logger.info(f"Session {data['session_id']} uploaded and processed successfully")
            
            # Return success response with metrics
            return jsonify({
                'status': 'completed',
                'session_id': data['session_id'],
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'hrv_metrics': hrv_metrics
            }), 201
            
        except psycopg2.IntegrityError as e:
            conn.rollback()
            logger.error(f"Database integrity error: {e}")
            return jsonify({
                'error': 'Session already exists or data integrity violation',
                'details': str(e)
            }), 409
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            return jsonify({
                'error': 'Database operation failed',
                'details': str(e)
            }), 500
        finally:
            return_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Upload session error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/api/v1/sessions/status/<session_id>', methods=['GET'])
def get_session_status(session_id: str):
    """Get processing status of a specific session"""
    try:
        if not validate_uuid(session_id):
            return jsonify({'error': 'Invalid session_id format'}), 400
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            query = """
                SELECT session_id, status, processed_at, 
                       mean_hr, mean_rr, count_rr, rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1
                FROM public.sessions 
                WHERE session_id = %s
            """
            
            cur.execute(query, (session_id,))
            session = cur.fetchone()
            cur.close()
            
            if not session:
                return jsonify({'error': 'Session not found'}), 404
            
            response = {
                'session_id': session['session_id'],
                'status': session['status'],
                'processed_at': session['processed_at'].isoformat() if session['processed_at'] else None
            }
            
            # Include metrics if completed
            if session['status'] == 'completed':
                response['hrv_metrics'] = {
                    'mean_hr': float(session['mean_hr']) if session['mean_hr'] else None,
                    'mean_rr': float(session['mean_rr']) if session['mean_rr'] else None,
                    'count_rr': session['count_rr'],
                    'rmssd': float(session['rmssd']) if session['rmssd'] else None,
                    'sdnn': float(session['sdnn']) if session['sdnn'] else None,
                    'pnn50': float(session['pnn50']) if session['pnn50'] else None,
                    'cv_rr': float(session['cv_rr']) if session['cv_rr'] else None,
                    'defa': float(session['defa']) if session['defa'] else None,
                    'sd2_sd1': float(session['sd2_sd1']) if session['sd2_sd1'] else None
                }
            
            return jsonify(response)
            
        finally:
            return_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Get session status error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/api/v1/sessions/processed/<user_id>', methods=['GET'])
def get_processed_sessions(user_id: str):
    """Get all processed sessions for a user"""
    try:
        if not validate_uuid(user_id):
            return jsonify({'error': 'Invalid user_id format'}), 400
        
        # Get pagination parameters
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 sessions
        offset = int(request.args.get('offset', 0))
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Get processed sessions
            query = """
                SELECT session_id, tag, subtag, event_id, duration_minutes,
                       recorded_at, processed_at,
                       mean_hr, mean_rr, count_rr, rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1
                FROM public.sessions 
                WHERE user_id = %s AND status = 'completed'
                ORDER BY recorded_at DESC
                LIMIT %s OFFSET %s
            """
            
            cur.execute(query, (user_id, limit, offset))
            sessions = cur.fetchall()
            
            # Get total count
            count_query = """
                SELECT COUNT(*) as total_count
                FROM public.sessions 
                WHERE user_id = %s AND status = 'completed'
            """
            
            cur.execute(count_query, (user_id,))
            total_count = cur.fetchone()['total_count']
            
            cur.close()
            
            # Format response
            formatted_sessions = []
            for session in sessions:
                formatted_session = {
                    'session_id': session['session_id'],
                    'tag': session['tag'],
                    'subtag': session['subtag'],
                    'event_id': session['event_id'],
                    'duration_minutes': session['duration_minutes'],
                    'recorded_at': session['recorded_at'].isoformat(),
                    'processed_at': session['processed_at'].isoformat() if session['processed_at'] else None,
                    'status': 'completed',  # Add missing status field for iOS compatibility
                    'hrv_metrics': {
                        'mean_hr': float(session['mean_hr']) if session['mean_hr'] else None,
                        'mean_rr': float(session['mean_rr']) if session['mean_rr'] else None,
                        'count_rr': session['count_rr'],
                        'rmssd': float(session['rmssd']) if session['rmssd'] else None,
                        'sdnn': float(session['sdnn']) if session['sdnn'] else None,
                        'pnn50': float(session['pnn50']) if session['pnn50'] else None,
                        'cv_rr': float(session['cv_rr']) if session['cv_rr'] else None,
                        'defa': float(session['defa']) if session['defa'] else None,
                        'sd2_sd1': float(session['sd2_sd1']) if session['sd2_sd1'] else None
                    }
                }
                formatted_sessions.append(formatted_session)
            
            return jsonify({
                'sessions': formatted_sessions,
                'total_count': total_count,
                'limit': limit,
                'offset': offset
            })
            
        finally:
            return_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Get processed sessions error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/api/v1/sessions/statistics/<user_id>', methods=['GET'])
def get_session_statistics(user_id: str):
    """Get session statistics for a user (using helper function from schema)"""
    try:
        if not validate_uuid(user_id):
            return jsonify({'error': 'Invalid user_id format'}), 400
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Use the helper function from our schema
            query = "SELECT * FROM public.get_user_session_statistics(%s)"
            cur.execute(query, (user_id,))
            stats = cur.fetchone()
            cur.close()
            
            if not stats:
                # Return empty statistics if user has no sessions
                return jsonify({
                    'raw_total': 0,
                    'processed_total': 0,
                    'raw_by_tag': {},
                    'processed_by_tag': {},
                    'sleep_events': 0
                })
            
            # Map PostgreSQL function results to expected iOS format
            total_sessions = stats['total_sessions'] or 0
            tags_summary = stats['tags_summary'] or {}
            
            return jsonify({
                'raw_total': total_sessions,
                'processed_total': total_sessions,  # All sessions are processed
                'raw_by_tag': tags_summary,
                'processed_by_tag': tags_summary,
                'sleep_events': tags_summary.get('sleep', 0)  # Count of sleep sessions
            })
            
        finally:
            return_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Get session statistics error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

@app.route('/api/v1/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """Delete a session (both raw and processed data)"""
    try:
        if not validate_uuid(session_id):
            return jsonify({'error': 'Invalid session_id format'}), 400
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Check if session exists and get user_id for authorization
            check_query = "SELECT user_id FROM public.sessions WHERE session_id = %s"
            cur.execute(check_query, (session_id,))
            session = cur.fetchone()
            
            if not session:
                return jsonify({'error': 'Session not found'}), 404
            
            # Delete session (triggers will update user session counts automatically)
            delete_query = "DELETE FROM public.sessions WHERE session_id = %s"
            cur.execute(delete_query, (session_id,))
            
            if cur.rowcount == 0:
                return jsonify({'error': 'Session not found'}), 404
            
            conn.commit()
            cur.close()
            
            logger.info(f"Session {session_id} deleted successfully")
            
            return jsonify({
                'status': 'deleted',
                'session_id': session_id
            })
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Delete session error: {e}")
            return jsonify({
                'error': 'Database operation failed',
                'details': str(e)
            }), 500
        finally:
            return_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Delete session error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500

# =====================================================
# ERROR HANDLERS
# =====================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# =====================================================
# APPLICATION INITIALIZATION
# =====================================================

def load_environment():
    """Load environment variables from .env.supabase"""
    env_file = '.env.supabase'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        logger.info("✅ Environment variables loaded from .env.supabase")

if __name__ == '__main__':
    # Load environment variables
    load_environment()
    
    # Try to initialize connection pool, but don't crash if it fails
    try:
        initialize_connection_pool()
        logger.info(f"🔗 Connected to Supabase PostgreSQL")
    except Exception as e:
        logger.warning(f"⚠️ Database connection failed during startup: {e}")
        logger.info(f"🔄 Will retry database connection on first API call")
        # Don't exit - let the app start anyway for health checks
    
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🚀 Starting HRV Brain API v3.3.4 on port {port}")
    logger.info(f"📋 Following schema.md unified data model")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
