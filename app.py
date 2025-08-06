"""
HRV Brain API - Clean Fresh Start Edition
Version: 4.0.0 Fresh Start
Source: schema.md (Golden Reference)

Minimal, clean API with only core session processing functionality.
Implements exact unified schema and all 9 HRV metrics from schema.md.
NO PLOT GENERATION - Pure session processing and database operations only.
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
from session_validator import validate_session_enhanced, ValidationResult

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
            maxconn=10,
            host=db_config.host,
            database=db_config.database,
            user=db_config.user,
            password=db_config.password,
            port=db_config.port
        )
        logger.info("✅ Database connection pool initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize connection pool: {str(e)}")
        raise

def get_db_connection():
    """Get database connection from pool"""
    return connection_pool.getconn()

def return_db_connection(conn):
    """Return database connection to pool"""
    connection_pool.putconn(conn)

# =====================================================
# VALIDATION FUNCTIONS
# =====================================================

def validate_session_data(data: Dict) -> Dict:
    """
    Legacy validation function for backward compatibility
    Uses the new modular validation system internally
    
    Args:
        data: Session data dictionary
        
    Returns:
        Dictionary of validation errors (empty if valid)
    """
    result = validate_session_enhanced(data)
    
    # Convert to legacy format
    errors = {}
    for error in result.errors:
        errors[error.field] = error.message
    
    return errors

def validate_user_id(user_id: str) -> bool:
    """Validate Supabase user ID format - more flexible than strict UUID"""
    if not isinstance(user_id, str):
        return False
    
    # Supabase user IDs can be various formats
    # Allow alphanumeric strings with some special characters
    if len(user_id) < 10 or len(user_id) > 50:
        return False
    
    # Basic format check - allow letters, numbers, hyphens, underscores
    import re
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', user_id))

def validate_uuid(uuid_string: str) -> bool:
    """Validate strict UUID format for session IDs"""
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
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '4.0.0'
    })

@app.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """Detailed health check with database connectivity"""
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT 1')
                db_status = 'connected'
        finally:
            return_db_connection(conn)
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy' if db_status == 'connected' else 'degraded',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '4.0.0',
        'database': db_status,
        'components': {
            'api': 'healthy',
            'database': db_status
        }
    })

@app.route('/api/v1/sessions/upload', methods=['POST'])
def upload_session():
    """
    Upload and process HRV session
    Implements exact unified schema from schema.md
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Enhanced validation with detailed error reporting
        validation_result = validate_session_enhanced(data)
        
        if not validation_result.is_valid():
            logger.warning(f"Session validation failed: {validation_result.to_dict()}")
            return jsonify({
                'error': 'Validation failed',
                'details': validation_result.to_dict(),
                'message': 'Please check the data format and try again'
            }), 400
        
        # Log warnings if any
        if validation_result.warnings:
            logger.info(f"Session validation warnings: {[w.message for w in validation_result.warnings]}")
        
        # Extract cleaned/validated data
        cleaned_data = validation_result.cleaned_data
        user_id = cleaned_data['user_id']
        session_id = cleaned_data['session_id']
        tag = cleaned_data['tag']
        subtag = cleaned_data.get('subtag')
        event_id = cleaned_data.get('event_id')
        rr_intervals = cleaned_data['rr_intervals']
        recorded_at = data.get('recorded_at', datetime.now(timezone.utc).isoformat())
        
        # Calculate HRV metrics
        hrv_metrics = calculate_hrv_metrics(rr_intervals)
        
        # Store in database
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO sessions (
                        session_id, user_id, tag, subtag, event_id,
                        recorded_at, status,
                        mean_hr, mean_rr, count_rr, rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1,
                        rr_intervals
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s
                    )
                """, (
                    session_id, user_id, tag, subtag, event_id,
                    recorded_at, 'completed',
                    hrv_metrics['mean_hr'], hrv_metrics['mean_rr'], hrv_metrics['count_rr'],
                    hrv_metrics['rmssd'], hrv_metrics['sdnn'], hrv_metrics['pnn50'],
                    hrv_metrics['cv_rr'], hrv_metrics['defa'], hrv_metrics['sd2_sd1'],
                    json.dumps(rr_intervals)
                ))
                conn.commit()
        finally:
            return_db_connection(conn)
        
        logger.info(f"✅ Session {session_id} processed and stored successfully")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': 'completed',
            'hrv_metrics': hrv_metrics,
            'processed_at': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ Error processing session: {str(e)}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@app.route('/api/v1/sessions/status/<session_id>', methods=['GET'])
def get_session_status(session_id: str):
    """Get processing status of a specific session"""
    try:
        if not validate_uuid(session_id):
            return jsonify({'error': 'Invalid session_id format'}), 400
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT session_id, status, recorded_at, 
                           mean_hr, mean_rr, count_rr, rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1
                    FROM sessions 
                    WHERE session_id = %s
                """, (session_id,))
                
                session = cursor.fetchone()
        finally:
            return_db_connection(conn)
        
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        return jsonify({
            'session_id': session['session_id'],
            'status': session['status'],
            'recorded_at': session['recorded_at'].isoformat() if session['recorded_at'] else None,
            'hrv_metrics': {
                'mean_hr': session['mean_hr'],
                'mean_rr': session['mean_rr'],
                'count_rr': session['count_rr'],
                'rmssd': session['rmssd'],
                'sdnn': session['sdnn'],
                'pnn50': session['pnn50'],
                'cv_rr': session['cv_rr'],
                'defa': session['defa'],
                'sd2_sd1': session['sd2_sd1']
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting session status: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/sessions/processed/<user_id>', methods=['GET'])
def get_processed_sessions(user_id: str):
    """Get all processed sessions for a user"""
    try:
        if not validate_user_id(user_id):
            return jsonify({'error': 'Invalid user_id format'}), 400
        
        # Get pagination parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        tag_filter = request.args.get('tag')
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Build query with optional tag filter
                base_query = """
                    SELECT session_id, tag, subtag, event_id, status,
                           recorded_at, mean_hr, mean_rr, count_rr, 
                           rmssd, sdnn, pnn50, cv_rr, defa, sd2_sd1
                    FROM sessions 
                    WHERE user_id = %s AND status = 'completed'
                """
                count_query = "SELECT COUNT(*) FROM sessions WHERE user_id = %s AND status = 'completed'"
                
                params = [user_id]
                if tag_filter:
                    base_query += " AND tag = %s"
                    count_query += " AND tag = %s"
                    params.append(tag_filter)
                
                base_query += " ORDER BY recorded_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                # Get sessions
                cursor.execute(base_query, params)
                sessions = cursor.fetchall()
                
                # Get total count
                cursor.execute(count_query, params[:-2])  # Exclude limit/offset
                total_count = cursor.fetchone()['count']
        finally:
            return_db_connection(conn)
        
        # Format response
        formatted_sessions = []
        for session in sessions:
            formatted_sessions.append({
                'session_id': session['session_id'],
                'tag': session['tag'],
                'subtag': session['subtag'],
                'event_id': session['event_id'],
                'status': session['status'],
                'recorded_at': session['recorded_at'].isoformat() if session['recorded_at'] else None,
                'hrv_metrics': {
                    'mean_hr': session['mean_hr'],
                    'mean_rr': session['mean_rr'],
                    'count_rr': session['count_rr'],
                    'rmssd': session['rmssd'],
                    'sdnn': session['sdnn'],
                    'pnn50': session['pnn50'],
                    'cv_rr': session['cv_rr'],
                    'defa': session['defa'],
                    'sd2_sd1': session['sd2_sd1']
                }
            })
        
        return jsonify({
            'sessions': formatted_sessions,
            'total_count': total_count,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting processed sessions: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/sessions/statistics/<user_id>', methods=['GET'])
def get_session_statistics(user_id: str):
    """Get session statistics for a user"""
    try:
        if not validate_user_id(user_id):
            return jsonify({'error': 'Invalid user_id format'}), 400
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get statistics by tag
                cursor.execute("""
                    SELECT tag, COUNT(*) as count
                    FROM sessions 
                    WHERE user_id = %s AND status = 'completed'
                    GROUP BY tag
                """, (user_id,))
                
                tag_stats = cursor.fetchall()
                
                # Get total count
                cursor.execute("""
                    SELECT COUNT(*) as total_count
                    FROM sessions 
                    WHERE user_id = %s AND status = 'completed'
                """, (user_id,))
                
                total = cursor.fetchone()
        finally:
            return_db_connection(conn)
        
        # Format response
        processed_by_tag = {}
        for stat in tag_stats:
            processed_by_tag[stat['tag']] = stat['count']
        
        return jsonify({
            'processed_total': total['total_count'],
            'processed_by_tag': processed_by_tag,
            'raw_total': total['total_count'],  # Same as processed in unified schema
            'raw_by_tag': processed_by_tag,    # Same as processed in unified schema
            'sleep_events': len([tag for tag in processed_by_tag.keys() if tag == 'sleep'])
        })
        
    except Exception as e:
        logger.error(f"❌ Error getting session statistics: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/v1/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """Delete a session"""
    try:
        if not validate_uuid(session_id):
            return jsonify({'error': 'Invalid session_id format'}), 400
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
                deleted_count = cursor.rowcount
                conn.commit()
        finally:
            return_db_connection(conn)
        
        if deleted_count == 0:
            return jsonify({'error': 'Session not found'}), 404
        
        logger.info(f"✅ Session {session_id} deleted successfully")
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Session deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"❌ Error deleting session: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# =====================================================
# ERROR HANDLERS
# =====================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

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
    """Load environment variables from .env.railway"""
    from dotenv import load_dotenv
    load_dotenv('.env.railway')
    logger.info("✅ Environment variables loaded")

if __name__ == '__main__':
    # Load environment variables
    load_environment()
    
    # Initialize connection pool
    initialize_connection_pool()
    
    # Start the application
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🚀 Starting HRV Brain API v4.0.0 on port {port}")
    logger.info(f"🔧 Debug mode: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
