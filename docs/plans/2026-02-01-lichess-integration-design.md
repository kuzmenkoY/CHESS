# Lichess Integration Design

## Goal

Users can log in with either Chess.com or Lichess. Each login creates a separate app identity. Users see their own platform data and a feed of followed players' stats, kept fresh via staleness-driven ingestion.

## Identity Model

Each platform login = one `app_user`. No cross-platform account linking (can be added later via a `app_user_platforms` join table without breaking changes).

### Changes to `social.app_users`

Drop the current `player_id` FK to `players`. Replace with:

```sql
platform    text NOT NULL          -- 'chesscom' | 'lichess'
platform_id text NOT NULL          -- chesscom player_id (as text) or lichess username
UNIQUE (platform, platform_id)
```

### Changes to `social.app_user_tracked_players`

Drop `tracked_player_id` FK to `players`. Replace with:

```sql
platform           text NOT NULL   -- 'chesscom' | 'lichess'
tracked_player_id  text NOT NULL   -- chesscom player_id or lichess username
```

A Chess.com user can follow a Lichess player and vice versa.

## New Tables

### `lichess_players`

```sql
CREATE TABLE IF NOT EXISTS lichess_players (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  username         text NOT NULL UNIQUE,    -- lowercased
  display_username text,
  title            text,                    -- GM, IM, etc.
  patron           boolean DEFAULT false,
  tos_violation    boolean DEFAULT false,
  disabled         boolean DEFAULT false,
  verified         boolean DEFAULT false,
  created_at       bigint,                  -- epoch ms (Lichess native)
  seen_at          bigint,                  -- epoch ms
  play_time_total  bigint,                  -- seconds
  url              text,
  bio              text,
  country          text,
  flair            text,
  ingested_at      bigint
);
```

### `lichess_player_stats`

```sql
CREATE TABLE IF NOT EXISTS lichess_player_stats (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  player_id  bigint NOT NULL REFERENCES lichess_players(id),
  perf       text NOT NULL,               -- bullet, blitz, rapid, classical, etc.
  rating     int,
  rd         int,
  prog       int,
  games      int,
  prov       boolean DEFAULT false,
  fetched_at bigint,
  UNIQUE (player_id, perf)
);
```

Lichess perf types: `bullet`, `blitz`, `rapid`, `classical`, `correspondence`, `chess960`, `crazyhouse`, `antichess`, `atomic`, `horde`, `kingOfTheHill`, `racingKings`, `threeCheck`, `ultraBullet`.

### `lichess_player_ingestion_state`

```sql
CREATE TABLE IF NOT EXISTS lichess_player_ingestion_state (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  player_id           bigint NOT NULL UNIQUE REFERENCES lichess_players(id),
  last_profile_fetch  bigint,              -- epoch ms
  status              text DEFAULT 'idle', -- idle | scheduled | running
  updated_at          bigint
);
```

### `lichess_games` (deferred, not needed for launch)

```sql
CREATE TABLE IF NOT EXISTS lichess_games (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  game_id          text NOT NULL UNIQUE,
  rated            boolean,
  variant          text,
  speed            text,
  perf             text,
  status           text,                    -- mate, resign, timeout, draw, etc.
  source           text,

  white_player_id  bigint REFERENCES lichess_players(id),
  white_rating     int,
  white_rd         int,
  black_player_id  bigint REFERENCES lichess_players(id),
  black_rating     int,
  black_rd         int,
  winner           text,                    -- white | black | NULL (draw)

  clock_initial    int,
  clock_increment  int,
  clock_total_time int,

  opening_eco      text,
  opening_name     text,

  pgn              text,
  moves            text,

  created_at       bigint,                  -- epoch ms
  last_move_at     bigint,                  -- epoch ms
  ingested_at      bigint
);

CREATE INDEX ON lichess_games (white_player_id);
CREATE INDEX ON lichess_games (black_player_id);
CREATE INDEX ON lichess_games (created_at);
CREATE INDEX ON lichess_games (speed);
```

## Ingestion

### Lichess: Single Job Type

The `/api/user/{username}` endpoint returns both profile and stats (ratings in `perfs` object). One HTTP call populates two tables.

Job type: `lichess_profile`

```
fetch /api/user/{username}
  → upsert lichess_players
  → upsert lichess_player_stats (loop over perfs keys)
  → upsert lichess_player_ingestion_state
```

### Changes to `ingestion_jobs`

Make `player_id` nullable. Lichess jobs use `scope->>'username'` instead.

```sql
-- player_id: nullable (NULL for lichess jobs, set for chesscom jobs)
-- job_type: add 'lichess_profile' to the set
-- scope: { "username": "thibault" } for lichess jobs
-- dedupe_key: still hashes (job_type, scope), works as-is
```

### Freshness-Driven Refresh

When a user opens their feed, the app checks staleness of followed players:

```
For each tracked player:
  IF (now - last_fetch) > STALENESS_THRESHOLD:
    enqueue ingestion job (dedupe prevents duplicates)

Serve cached data immediately. Fresh data on next load.
```

Thresholds (configurable via env):

| Variable | Default | Notes |
|---|---|---|
| `LICHESS_STATS_REFRESH_SECONDS` | 60 | Single API call, low cost |
| `STATS_REFRESH_SECONDS` (Chess.com) | 7200 | Can be lowered |

## User Flows

### Registration / Login

1. User opens app, chooses "Login with Chess.com" or "Login with Lichess"
2. OAuth flow completes, we get username/ID
3. Check `social.app_users` for `(platform, platform_id)`
4. Not found: create row, enqueue ingestion job, show loading state
5. Found: proceed to home screen

### View Own Stats

App reads `platform` and `platform_id` from `app_users`, queries the appropriate tables:

- `chesscom` → `players` + `player_stats`
- `lichess` → `lichess_players` + `lichess_player_stats`

UI normalizes the display (both have ratings, win/loss/draw).

### Feed

1. Fetch tracked players from `app_user_tracked_players`
2. Two queries: one for Chess.com friends, one for Lichess friends
3. Merge results in application layer, sort by freshness
4. Fire background staleness check for stale players
5. Posts (from `social.posts`) are platform-agnostic, query unchanged

## Timestamp Convention

- Chess.com: epoch **seconds** (existing convention)
- Lichess: epoch **milliseconds** (Lichess native)
- Each platform's tables store native format
- Conversion happens at application/query layer

## Future: Account Linking

To allow one user to connect both platforms later:

1. Create `social.app_user_platforms (app_user_id, platform, platform_id, linked_at)`
2. Move `platform`/`platform_id` from `app_users` into the join table
3. Social schema (`posts`, `follows`, etc.) unchanged — references `app_users.id`

No throwaway work. Current design is a natural subset of the linked design.

## Scope for Initial Implementation

**Build now:**
- `lichess_players` + `lichess_player_stats` + `lichess_player_ingestion_state` tables
- `lichess_profile` job type in ingestion worker
- `social.app_users` schema change (platform + platform_id)
- `social.app_user_tracked_players` schema change
- Staleness-driven refresh logic

**Deferred:**
- `lichess_games` table and game ingestion
- REST API endpoints
- Account linking
