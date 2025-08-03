"""
Database Configuration for HRV App
Version: 3.3.4 Final
Source: schema.md (Golden Reference)
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional
import logging
import socket
import time

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration and connection management"""
    
    def __init__(self):
        # Supabase connection details (from .env.railway)
        self.host = os.environ.get('SUPABASE_DB_HOST', 'db.zluwfmovtmlijawhelzi.supabase.co')
        self.database = os.environ.get('SUPABASE_DB_NAME', 'postgres')
        self.user = os.environ.get('SUPABASE_DB_USER', 'postgres')
        self.password = os.environ.get('SUPABASE_DB_PASSWORD', 'Slavoj@!64Su')
        self.port = int(os.environ.get('SUPABASE_DB_PORT', '5432'))
        
        # Resolve to IPv4 address for Railway compatibility
        self.ipv4_host = self._resolve_to_ipv4(self.host)
        
        # Connection pool settings
        self.min_connections = 1
        self.max_connections = 10
        
    def _resolve_to_ipv4(self, hostname: str) -> str:
        """Resolve hostname to IPv4 address for Railway compatibility"""
        try:
            # Get all addresses and filter for IPv4
            addresses = socket.getaddrinfo(hostname, None, socket.AF_INET)
            if addresses:
                ipv4_addr = addresses[0][4][0]
                logger.info(f"Resolved {hostname} to IPv4: {ipv4_addr}")
                return ipv4_addr
            else:
                logger.warning(f"No IPv4 address found for {hostname}, using hostname")
                return hostname
        except Exception as e:
            logger.warning(f"Failed to resolve {hostname} to IPv4: {e}, using hostname")
            return hostname
    
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return f"postgresql://{self.user}:{self.password}@{self.ipv4_host}:{self.port}/{self.database}"
    
    def get_connection(self) -> psycopg2.extensions.connection:
        """Get database connection with Railway-optimized settings and retry logic"""
        connection_attempts = [
            # Method 1: Direct connection string (Railway-preferred)
            lambda: psycopg2.connect(
                self.get_connection_string(),
                cursor_factory=RealDictCursor,
                connect_timeout=15,
                sslmode='require'
            ),
            # Method 2: Individual parameters with IPv4 resolution
            lambda: psycopg2.connect(
                host=self.ipv4_host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port,
                cursor_factory=RealDictCursor,
                connect_timeout=15,
                sslmode='require'
            ),
            # Method 3: Original hostname as fallback
            lambda: psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port,
                cursor_factory=RealDictCursor,
                connect_timeout=15,
                sslmode='require'
            )
        ]
        
        last_error = None
        for i, connect_method in enumerate(connection_attempts, 1):
            try:
                logger.info(f"Attempting database connection (method {i}/3)...")
                conn = connect_method()
                logger.info("Database connection established successfully")
                return conn
            except psycopg2.Error as e:
                last_error = e
                logger.warning(f"Connection method {i} failed: {e}")
                if i < len(connection_attempts):
                    logger.info(f"Retrying with method {i+1}...")
                    time.sleep(1)  # Brief delay between attempts
                continue
            except Exception as e:
                last_error = e
                logger.warning(f"Connection method {i} failed with unexpected error: {e}")
                continue
        
        # All connection methods failed
        error_msg = f"All database connection methods failed. Last error: {last_error}"
        logger.error(error_msg)
        raise psycopg2.Error(error_msg)
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT version();")
            version = cur.fetchone()
            cur.close()
            conn.close()
            logger.info(f"Database connection test successful: {version}")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def execute_schema(self, schema_file_path: str) -> bool:
        """Execute schema SQL file"""
        try:
            with open(schema_file_path, 'r') as file:
                schema_sql = file.read()
            
            conn = self.get_connection()
            cur = conn.cursor()
            
            # Execute schema
            cur.execute(schema_sql)
            conn.commit()
            
            cur.close()
            conn.close()
            
            logger.info("Schema executed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Schema execution failed: {e}")
            return False

# Global database config instance
db_config = DatabaseConfig()

def get_db_connection():
    """Helper function to get database connection"""
    return db_config.get_connection()

def test_database_connection():
    """Helper function to test database connection"""
    return db_config.test_connection()
