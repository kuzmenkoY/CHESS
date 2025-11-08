"""
Database connection utility for Supabase PostgreSQL
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_db_url() -> str:
    """
    Get database connection URL from environment.
    Supports both DATABASE_URL (connection string) and individual components.
    """
    # Option 1: Full connection string (recommended)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    
    # Option 2: Individual components
    host = os.getenv("SUPABASE_HOST")
    port = os.getenv("SUPABASE_PORT", "5432")
    db_name = os.getenv("SUPABASE_DB_NAME", "postgres")
    user = os.getenv("SUPABASE_USER", "postgres")
    password = os.getenv("SUPABASE_PASSWORD")
    
    if not host or not password:
        raise ValueError(
            "Missing database credentials. Set either DATABASE_URL or "
            "SUPABASE_HOST + SUPABASE_PASSWORD in .env file"
        )
    
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM players")
    """
    conn = None
    try:
        conn = psycopg2.connect(
            get_db_url(),
            cursor_factory=RealDictCursor
        )
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def test_connection() -> bool:
    """Test database connection."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()
                print(f"✅ Connected to PostgreSQL: {version['version']}")
                return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    print("Testing database connection...")
    test_connection()

