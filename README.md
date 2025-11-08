# Chess.com Data Pipeline

Project to fetch, store, and analyze Chess.com player data using their public API.

## Structure

### `/db` - Database Schema & Utilities
- `schema_postgresql.sql` - PostgreSQL schema for Supabase
- `queries.sql` - Example SQL queries for analytics
- `db_connection.py` - Database connection utility
- `init_db.py` - Script to initialize database schema
- Includes both Chess.com ingestion tables and the `social.*` schema for posts, clubs, comments, reactions, and notifications.

### `/docs` - Documentation
- `chess_api_rules.md` - Essential API rules and best practices
- `db_schema.md` - Database schema overview
- `supabase_setup.md` - Supabase setup instructions

### `/experiments/API_test` - API Testing
- `simple_test.py` - Simple script to test API endpoints

## Quick Start

1. **Setup Supabase**: See `docs/supabase_setup.md`
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Initialize database**: `python db/init_db.py`
4. **Test API**: `python experiments/API_test/simple_test.py`

## Next Steps

- Build ingestion script to populate database
- Wire up the new ingestion job queue + archive status columns to keep re-runs idempotent.
- Expand analytics queries (see `db/queries.sql`) for social feeds and clubs.
- Build user interface for statistics and Strava-like timelines backed by the `social` schema.
