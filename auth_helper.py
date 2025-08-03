"""
HRV App Unified Authentication Helper
Version: 4.0.0 FINAL CLEAN EDITION

CRITICAL AUTHENTICATION CLARIFICATION:
- SERVER-SIDE (Railway API): Uses SERVICE_ROLE_KEY for database operations
- CLIENT-SIDE (iOS): Uses ANON_KEY + JWT tokens from user authentication
- NEVER expose SERVICE_ROLE_KEY to client-side code!
"""

import os
import jwt
import logging
from typing import Optional, Dict, Any
from supabase import create_client, Client
from flask import request

logger = logging.getLogger(__name__)

class SupabaseAuth:
    """Unified Supabase authentication handler"""
    
    def __init__(self):
        self.supabase_url = os.environ.get('SUPABASE_URL')
        self.anon_key = os.environ.get('SUPABASE_ANON_KEY')
        self.service_role_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
        
        if not all([self.supabase_url, self.anon_key, self.service_role_key]):
            raise ValueError("Missing required Supabase environment variables")
        
        # Server-side client with service role (full access)
        self.admin_client: Client = create_client(self.supabase_url, self.service_role_key)
        
        # Client-side client with anon key (for user operations)
        self.client: Client = create_client(self.supabase_url, self.anon_key)
    
    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token from iOS client"""
        try:
            # Decode JWT token (Supabase uses HS256)
            payload = jwt.decode(
                token, 
                self.anon_key, 
                algorithms=['HS256'],
                options={"verify_signature": True}
            )
            return payload
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"JWT verification error: {e}")
            return None
    
    def get_user_from_request(self) -> Optional[str]:
        """Extract user ID from Authorization header"""
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.replace('Bearer ', '')
        payload = self.verify_jwt_token(token)
        
        if payload and 'sub' in payload:
            return payload['sub']  # User ID
        
        return None
    
    def require_auth(self):
        """Decorator to require authentication"""
        def decorator(f):
            def wrapper(*args, **kwargs):
                user_id = self.get_user_from_request()
                if not user_id:
                    return {'error': 'Authentication required'}, 401
                
                # Add user_id to kwargs for the route function
                kwargs['user_id'] = user_id
                return f(*args, **kwargs)
            
            wrapper.__name__ = f.__name__
            return wrapper
        return decorator

# Global auth instance
supabase_auth = SupabaseAuth()
