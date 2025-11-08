# Troubleshooting

## Supabase warning: `supautils.disable_program`

Supabase recently reserved the `supautils.*` prefix. Existing projects still
have a server-side setting that tries to set `supautils.disable_program`, which
produces this warning on every new connection:

```
WARNING:  invalid configuration parameter name "supautils.disable_program", removing it
DETAIL:  "supautils" is now a reserved prefix.
```

We confirmed the local `.env` and client code do **not** specify this parameter,
and attempts to `ALTER SYSTEM/ROLE ... RESET supautils.disable_program` are
blocked by Supabase (permission denied). Until Supabase removes that server-side
setting, the warning is harmless but unavoidable. You can safely ignore it, or
file a ticket with Supabase support to clear the parameter for your project.

## Re-fetching the current month's games

Chess.com publishes one archive per month. Once an archive is marked
`fetch_status='succeeded'`, the worker skips it to avoid duplicate work. If you
want to keep the *current* month refreshed (e.g., pull the day's new games),
reset that archive row and rerun the worker:

```sql
UPDATE monthly_archives
SET fetch_status = 'pending',
    retry_count = 0,
    last_fetch_attempt = 0,
    last_success_at = 0
WHERE player_id = (SELECT id FROM players WHERE username = :username)
  AND year = EXTRACT(YEAR FROM NOW())
  AND month = EXTRACT(MONTH FROM NOW());
```

Then enqueue the username again:

```bash
ARCHIVE_MONTH_LIMIT=3 PYTHONPATH=. python ingestion/worker.py enqueue --username :username
ARCHIVE_MONTH_LIMIT=3 PYTHONPATH=. python ingestion/worker.py run --loop
```

This causes the current-month archive to be re-downloaded immediately. Future
work: automate this by scheduling follow-up jobs for the active month.
