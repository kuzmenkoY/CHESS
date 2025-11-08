# Task Completion Checklist
- Ensure `.env` has Supabase credentials (`DATABASE_URL` or individual components) before running scripts.
- After schema changes, re-run `python db/init_db.py` (idempotent) and confirm success output.
- For feature work touching Chess.com API, validate headers/rate-limiting behavior; `experiments/API_test/simple_test.py` is the quick regression script.
- When data model or queries change, update both `db/schema_postgresql.sql` and relevant docs under `docs/`, plus add/adjust queries in `db/queries.sql` if needed.
- No automated tests yet; rely on command outputs/logs and, if possible, manual Supabase inspection.