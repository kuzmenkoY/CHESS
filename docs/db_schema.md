# Relational Schema for Chess.com Data (v1)

## Goals
- Support user profile pages, stats dashboards, recent game feeds, head‑to‑head, and friend/follow timelines.
- Enable incremental ingestion with caching (ETag/Last‑Modified) and safe re-runs.
- Keep core minimal; extend later (clubs, tournaments) without breaking.

## Entities
- Players: Chess.com accounts (stable `player_id`, username).
- Player stats: per rules/time_class (bullet/blitz/rapid/daily).
- Monthly archives: normalized index of archive URLs per player/month.
- Games: finished games with white/black participants and PGN/FEN.
- Fetch log: caching and diagnostics per requested URL.
- App tracking: local app user and which players they track (self/friend/follow).

## Tables (high level)
- `players(id, chesscom_player_id, username, display_username, name, title, status, league, country_url, followers, joined, last_online, …)`
- `player_stats(player_id, rules, time_class, last_rating, best_rating, record_win/loss/draw, …)` unique by `(player_id, rules, time_class)`
- `player_tactics_stats`, `player_lessons_stats`, `player_puzzle_rush_best`, `player_puzzle_rush_daily` (optional, present when API has data)
- `monthly_archives(player_id, year, month, url)`
- `games(url, time_control, end_time, rated, time_class, rules, fen, pgn, white_player_id, white_rating, white_result, black_player_id, black_rating, black_result, eco_url, accuracies, …)`
- `fetch_log(url, etag, last_modified, status_code, fetched_at, error)`
- `app_users(username)`, `app_user_tracked_players(app_user_id, player_id, relationship)`

## Keys & Indexes
- `players.username` unique (lowercased), `chesscom_player_id` unique.
- `player_stats` unique by `(player_id, rules, time_class)`.
- `monthly_archives` unique by `(player_id, year, month)` and by `url`.
- `games.url` unique; indexes on `end_time`, `time_class`, `white_player_id`, `black_player_id`.
- `app_user_tracked_players` unique by `(app_user_id, player_id)`.

## Conventions
- Store `username` lowercased; keep `display_username` as seen on Chess.com.
- Results are literal API codes (`win`, `timeout`, `resigned`, `agreed`, `repetition`, `stalemate`, `insufficient`, `timevsinsufficient`, `50move`, …).
- Timestamps are epoch seconds.
- Use soft‑nullable columns for optional API fields (e.g., accuracies).

## Ingestion outline
1. Upsert `players` from `/player/{username}`.
2. Upsert `player_stats` (+ tactics/lessons/puzzle_rush if present) from `/player/{username}/stats`.
3. Get archive URLs from `/player/{username}/games/archives`; upsert `monthly_archives`.
4. For each archive URL, fetch games; upsert `players` for any opponent not seen; upsert `games` with foreign keys to white/black and archive.
5. Log `ETag`/`Last-Modified` in `fetch_log`; send conditional requests on subsequent runs.

## Example analytics (see `db/queries.sql`)
- Latest ratings per time_class for a player.
- Recent games feed (with opponent names).
- Head‑to‑head summary between two players.
- Friend feed for an app user (tracked players).
- Monthly activity counts.

## Notes
- v1 targets SQLite for local exploration. Porting to Postgres is straightforward (replace `INTEGER` booleans with `BOOLEAN`, default expressions).
- Clubs, matches, tournaments can be added later with separate tables referencing `players`.


