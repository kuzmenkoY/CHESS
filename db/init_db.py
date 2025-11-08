"""
Initialize database schema on Supabase
Run this once to create all tables.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.db_connection import get_db_connection

def init_schema():
    """Create all tables from schema_postgresql.sql"""
    schema_path = Path(__file__).parent / "schema_postgresql.sql"
    
    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        return False
    
    print(f"📖 Reading schema from: {schema_path}")
    schema_sql = schema_path.read_text()
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
        print("\n✅ Database schema initialized successfully!")
        return True
    except Exception as e:
        print(f"\n❌ Failed to initialize schema: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Initializing database schema...\n")
    init_schema()
