# Relational Schema for Chess.com + Social Data (v2)

## Goals
- Support player profile pages, stats dashboards, recent game feeds, head‑to‑head, Strava‑style social timelines, clubs, and notifications.
- Enable incremental ingestion with caching (ETag/Last‑Modified), resumable jobs, and safe re-runs.
- Keep Chess.com data (public schema) isolated from user-generated content (Postgres schema `social`) so we can scale or relocate each surface independently.
- Capture enough metadata to enforce GDPR/DSGVO requirements (ownership, privacy levels, erasure).

## Entities
- **Players**: Chess.com accounts (`players` table).
- **Player stats**: metrics per rules/time_class (`player_stats`, `player_tactics_stats`, `player_lessons_stats`, `player_puzzle_rush_*`).
- **Monthly archives**: normalized index with ingestion state and retry metadata (`monthly_archives`).
- **Games**: finished games with white/black participants plus PGN/FEN (`games`).
- **Ingestion telemetry**: `player_ingestion_state`, task queue `ingestion_jobs`, and `fetch_log`.
- **Social graph**: `social.app_users`, tracked players, clubs, memberships.
- **Content**: posts, post media, comments, reactions, notifications (all under `social.*`).

## Tables (high level)
- `players(id, chesscom_player_id, username, display_username, name, title, status, league, country_url, followers, joined, last_online, …)`
- `player_stats(player_id, rules, time_class, last_rating, best_rating, record_win/loss/draw, …)` unique by `(player_id, rules, time_class)`
- Optional stats add-ons: `player_tactics_stats`, `player_lessons_stats`, `player_puzzle_rush_best`, `player_puzzle_rush_daily`
- `monthly_archives(player_id, year, month, url, fetch_status, last_fetch_attempt, last_success_at, retry_count, next_retry_at, checksum, priority, …)`
- `player_ingestion_state(player_id, last_profile_fetch, next_profile_fetch, last_archives_scan, cursor, status, error, …)`
- `ingestion_jobs(job_type, player_id, scope JSONB, dedupe_key UNIQUE, status, priority, attempts, max_attempts, available_at, locked_at, completed_at)`
- `games(url, time_control, end_time, rated, time_class, rules, fen, pgn, white_player_id, black_player_id, ratings/results, eco, accuracies, …)`
- `fetch_log(url, etag, last_modified, status_code, fetched_at, error)` with indexes for retention reports
- `social.app_users(username, player_id link, privacy settings, profile metadata)`
- `social.app_user_tracked_players(app_user_id, player_id, relationship, notification_level, notes, added_at)`
- `social.clubs`, `social.club_memberships`
- `social.posts`, `social.post_media`, `social.comments`, `social.post_reactions`, `social.comment_reactions`, `social.notifications`

## Keys & Indexes
- `players.username` and `chesscom_player_id` remain globally unique.
- `player_stats` unique by `(player_id, rules, time_class)`.
- `monthly_archives` unique by `(player_id, year, month)` and `url`, plus status index on `(fetch_status, next_retry_at)` for schedulers; `last_fetch_attempt/last_success_at` default to `0` until the first games job succeeds.
- `ingestion_jobs` indexed by `(status, available_at)` plus `(player_id)` for targeted requeues; `dedupe_key` has a unique constraint so enqueueing the same work twice just bumps priority/availability.
- `games.url` unique; indexes on `end_time`, `time_class`, `white_player_id`, `black_player_id`.
- Social uniques: `social.app_users.username`, `social.app_user_tracked_players(app_user_id, player_id)`, `social.posts` indexes on `(app_user_id, created_at DESC)`, reaction uniques on `(post_id/comment_id, app_user_id, reaction)`.

## Conventions
- Store Chess.com `username` lowercased; keep `display_username` as presented.
- Timestamps are Unix epoch seconds (BIGINT) to simplify Supabase Edge usage.
- Results remain literal API codes (`win`, `timeout`, `resigned`, `agreed`, `repetition`, `stalemate`, `insufficient`, `timevsinsufficient`, `50move`, …).
- Ingestion statuses use constrained enums-in-text (documented in column comments), enabling job workers to filter statuses cheaply.
- Social schema isolates personally identifiable data and UGC for easier policy enforcement; all references cross schemas with explicit `social.*` qualifiers.

## Ingestion lifecycle
1. Upsert `players` + `player_ingestion_state` from `/player/{username}`; schedule follow-up `ingestion_jobs` (`profile`, `stats`, `archives`).
2. Fetch `/player/{username}/stats`; update `player_stats` and optional tables; update `player_ingestion_state.last_stats_fetch`.
3. Enumerate `/player/{username}/games/archives`; upsert `monthly_archives` rows (status starts `pending` with fresh `priority`).
4. For each archive job, fetch monthly games sequentially; upsert opponent players; insert/update `games` (unique on `url`); mark archive `fetch_status='succeeded'` and record `checksum`.
5. Every HTTP request logs to `fetch_log` with caching headers plus optional hash/size for later reconciliation. Scheduled cleanup can purge old rows based on `fetched_at`.

## Social schema overview
- `social.app_users` binds a Supabase auth identity to an optional Chess.com `player_id`, privacy flags, and profile metadata.
- `social.app_user_tracked_players` stores user-defined follows/friends/self + notification levels (all, mentions, mute).
- `social.clubs` + `social.club_memberships` capture group spaces and roles (member/mod/admin) to gate content.
- `social.posts` hold Strava-style updates with optional `player_snapshot` JSON payloads for cached stats; `social.post_media` references assets (images, PGNs, links).
- `social.comments`, `social.post_reactions`, `social.comment_reactions` model engagement; `social.notifications` stores “push and in-app” events for eventual mobile delivery.
- Keeping these tables under the `social` schema lets us move them to a different database/service later while the ingestion schema remains untouched.

## Example analytics (see `db/queries.sql`)
- Latest ratings per time_class for a player.
- Recent games feed (with opponent names) + friend feed using `social.app_user_tracked_players`.
- Head‑to‑head summary between two players.
- Monthly activity counts using PostgreSQL `to_char(to_timestamp())`.
- Social timeline query joining `social.posts`, reactions, comments, and tracked players.
- Club roster summaries with role counts.

## Notes
- Schema is PostgreSQL (Supabase). Full DDL lives in `db/schema_postgresql.sql` and is idempotent via `db/init_db.py`.
- Social schema intentionally lives in the same database for now but is fully namespaced (`social.*`), so we can migrate to a dedicated database or service by replicating just that schema later.
