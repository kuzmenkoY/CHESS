# Supabase Database Setup

## Prerequisites

1. **Supabase Project**: Create a project at https://supabase.com
2. **Database Credentials**: Get connection details from Supabase Dashboard > Settings > Database

## Environment Variables

Create a `.env` file in the project root with one of these options:

### Option 1: Connection String (Recommended)
```bash
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
```

### Option 2: Individual Components
```bash
SUPABASE_HOST=db.[YOUR-PROJECT-REF].supabase.co
SUPABASE_PORT=5432
SUPABASE_DB_NAME=postgres
SUPABASE_USER=postgres
SUPABASE_PASSWORD=[YOUR-PASSWORD]
```

## Installation

```bash
pip install -r requirements.txt
```

## Initialize Database

Run the initialization script to create all tables:

```bash
python db/init_db.py
```

Or test the connection first:

```bash
python db/db_connection.py
```

## Getting Your Supabase Credentials

1. Go to https://supabase.com/dashboard
2. Select your project
3. Go to **Settings** > **Database**
4. Find **Connection string** section
5. Copy the **URI** format (or use individual components)

**Important**: Replace `[YOUR-PASSWORD]` with your actual database password (shown when you first create the project, or reset it in Settings > Database).

## Schema Files

- `db/schema_postgresql.sql` - PostgreSQL schema (for Supabase)
- `db/schema.sql` - Original SQLite schema (for reference)

## Next Steps

After initialization, you can:
1. Run the ingestion script to populate data
2. Use the queries in `db/queries.sql` (may need PostgreSQL syntax adjustments)

