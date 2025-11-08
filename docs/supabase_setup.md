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

- `db/schema_postgresql.sql` - PostgreSQL schema (kept Supabase-friendly and idempotent)
- `docs/db_schema.md` - human-readable overview and update history

## Running the ingestion worker

1. Set a descriptive User-Agent in `.env` so Chess.com can reach you if needed:
   ```bash
   CHESS_API_USER_AGENT="ChessStrava/0.1 (contact@example.com)"
   ```
2. Enqueue seed jobs for one or more usernames:
   ```bash
   python ingestion/worker.py enqueue --username YevgenChess --username hikaru
   ```
3. Run the worker once (cron-friendly) or as a long-lived process:
   ```bash
   # single job
   python ingestion/worker.py run --once

   # continuous poller
   python ingestion/worker.py run --loop
   ```
   The worker pulls rows from `ingestion_jobs`, refreshes Chess.com data, and fan-outs archive/game jobs automatically.

## Recommended Supabase RLS policies

Enable Row Level Security and create policies that keep Chess.com data public while locking down social content:

- `players`, `player_stats`, `monthly_archives`, `games`, etc.: read-only for anonymous role (`USING true WITH CHECK false`) so the iOS app can fetch stats without auth.
- `social.app_users`: allow users to read/update only their own row (`auth.uid() = user_id_column`). Require authenticated role for inserts/updates.
- `social.app_user_tracked_players`, `social.posts`, `social.comments`, reactions, clubs, notifications: allow `SELECT` where the viewer is the owner, target user, or share target; allow `INSERT/UPDATE/DELETE` only when `auth.uid()` matches the record owner or club admin. Start simple (owner-only) and broaden later.
- Create helper Postgres functions to map Supabase `auth.uid()` to `social.app_users.id`.

Document policies in Supabase so mobile + backend engineers know how data flows. Always run `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;` before adding policies.

## Next Steps

After initialization, you can:
1. Run the ingestion worker (above) to start filling the tables.
2. Use the queries in `db/queries.sql` for analytics/social feeds or as a template for Supabase stored procedures.
