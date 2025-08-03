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

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration and connection management"""
    
    def __init__(self):
        # Supabase connection details (from .env.supabase)
        self.host = os.environ.get('SUPABASE_DB_HOST', 'db.zluwfmovtmlijawhelzi.supabase.co')
        self.database = os.environ.get('SUPABASE_DB_NAME', 'postgres')
        self.user = os.environ.get('SUPABASE_DB_USER', 'postgres')
        self.password = os.environ.get('SUPABASE_DB_PASSWORD', 'Slavoj@!64Su')
        self.port = int(os.environ.get('SUPABASE_DB_PORT', '5432'))
        
        # Connection pool settings
        self.min_connections = 1
        self.max_connections = 10
        
    def get_connection_string(self) -> str:
        """Get PostgreSQL connection string"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def get_connection(self) -> psycopg2.extensions.connection:
        """Get database connection with proper error handling and IPv4 forcing"""
        try:
            # Force IPv4 connection to avoid Railway IPv6 issues
            conn = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port,
                cursor_factory=RealDictCursor,
                connect_timeout=30,
                keepalives_idle=600,
                keepalives_interval=30,
                keepalives_count=3,
                sslmode='require'
            )
            logger.info("Database connection established successfully")
            return conn
        except psycopg2.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
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
