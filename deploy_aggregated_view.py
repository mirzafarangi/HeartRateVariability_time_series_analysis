#!/usr/bin/env python3
"""
Deploy Aggregated Sleep Events View
Version: 1.0.0
Date: 2025-08-07
Purpose: Deploy the aggregated_sleep_events view to production database
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables from .env.railway"""
    try:
        from dotenv import load_dotenv
        load_dotenv('.env.railway')
        logger.info("✅ Environment variables loaded from .env.railway")
        
        # Validate required variables
        required_vars = ['SUPABASE_DB_HOST', 'SUPABASE_DB_PASSWORD']
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {missing_vars}")
            return False
            
        logger.info(f"✅ Database host: {os.environ.get('SUPABASE_DB_HOST')}")
        logger.info(f"✅ Database port: {os.environ.get('SUPABASE_DB_PORT', '5432')}")
        return True
        
    except ImportError:
        logger.error("❌ python-dotenv not installed. Install with: pip install python-dotenv")
        return False
    except Exception as e:
        logger.error(f"❌ Error loading environment: {str(e)}")
        return False

def get_database_connection():
    """Get database connection using environment variables"""
    try:
        # Get connection parameters from environment
        host = os.environ.get('SUPABASE_DB_HOST')
        database = os.environ.get('SUPABASE_DB_NAME', 'postgres')
        user = os.environ.get('SUPABASE_DB_USER', 'postgres')
        password = os.environ.get('SUPABASE_DB_PASSWORD')
        port = int(os.environ.get('SUPABASE_DB_PORT', '5432'))
        
        logger.info(f"🔌 Connecting to database: {host}:{port}/{database}")
        
        # Create connection
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            port=port,
            cursor_factory=RealDictCursor,
            connect_timeout=10
        )
        
        logger.info("✅ Database connection established")
        return conn
        
    except Exception as e:
        logger.error(f"❌ Database connection failed: {str(e)}")
        return None

def deploy_aggregated_view():
    """Deploy the aggregated_sleep_events view"""
    try:
        # Load environment variables
        if not load_environment():
            return False
        
        # Get database connection
        conn = get_database_connection()
        if not conn:
            return False
        
        try:
            # Read the SQL script
            script_path = 'add_aggregated_view.sql'
            if not os.path.exists(script_path):
                logger.error(f"❌ SQL script not found: {script_path}")
                return False
            
            with open(script_path, 'r') as f:
                sql_script = f.read()
            
            logger.info(f"📄 Read SQL script: {len(sql_script)} characters")
            
            # Execute the script
            with conn.cursor() as cursor:
                logger.info("🚀 Executing aggregated_sleep_events view creation...")
                cursor.execute(sql_script)
                conn.commit()
                
                # Verify the view was created
                cursor.execute("""
                    SELECT COUNT(*) as view_exists 
                    FROM information_schema.views 
                    WHERE table_name = 'aggregated_sleep_events'
                """)
                
                result = cursor.fetchone()
                if result and result['view_exists'] > 0:
                    logger.info("✅ aggregated_sleep_events view created successfully")
                    
                    # Test the view with a sample query
                    cursor.execute("SELECT COUNT(*) as total_events FROM aggregated_sleep_events")
                    test_result = cursor.fetchone()
                    logger.info(f"✅ View test query successful: {test_result['total_events']} events found")
                    
                    return True
                else:
                    logger.error("❌ View creation verification failed")
                    return False
                    
        finally:
            conn.close()
            logger.info("🔌 Database connection closed")
            
    except Exception as e:
        logger.error(f"❌ Deployment failed: {str(e)}")
        return False

def main():
    """Main deployment function"""
    logger.info("🚀 Starting aggregated_sleep_events view deployment")
    
    success = deploy_aggregated_view()
    
    if success:
        logger.info("✅ Deployment completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Deployment failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
