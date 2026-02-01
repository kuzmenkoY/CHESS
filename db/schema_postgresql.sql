-- Converted from SQLite schema

-- Enable UUID extension (useful for future)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Logical separation for social/user-generated content
CREATE SCHEMA IF NOT EXISTS social;

-- Core players
CREATE TABLE IF NOT EXISTS players (
  id BIGSERIAL PRIMARY KEY,
  chesscom_player_id BIGINT UNIQUE NOT NULL,  -- API: player_id (stable, never changes)
  username VARCHAR(255) NOT NULL UNIQUE,       -- API: username (lowercased)
  display_username VARCHAR(255),              -- extracted from API: url field
  name VARCHAR(255),                          -- API: name (optional, may be NULL)
  title VARCHAR(10),                          -- API: title (optional, only for titled players: GM, IM, etc.)
  status VARCHAR(50),                         -- API: status (basic, premium, etc.)
  league VARCHAR(50),                         -- API: league (Wood, Champion, etc.)
  country_url TEXT,                           -- API: country (full URL)
  country_code VARCHAR(2),                    -- extracted from country_url (e.g., "DE")
  avatar TEXT,                                -- API: avatar (optional URL)
  twitch_url TEXT,                           -- extracted from streaming_platforms array
  followers INTEGER DEFAULT 0,                -- API: followers
  joined BIGINT,                              -- API: joined (epoch seconds)
  last_online BIGINT,                        -- API: last_online (epoch seconds)
  is_streamer BOOLEAN NOT NULL DEFAULT FALSE, -- API: is_streamer (boolean)
  verified BOOLEAN NOT NULL DEFAULT FALSE,   -- API: verified (boolean)
  created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  updated_at BIGINT
);

CREATE INDEX IF NOT EXISTS idx_players_username ON players(username);
CREATE INDEX IF NOT EXISTS idx_players_chesscom_id ON players(chesscom_player_id);

-- Optional country catalog (populate lazily)
CREATE TABLE IF NOT EXISTS countries (
  code VARCHAR(2) PRIMARY KEY,
  name VARCHAR(255)
);

-- Per rules/time_class stats (bullet/blitz/rapid/daily, chess/chess960)
CREATE TABLE IF NOT EXISTS player_stats (
  id BIGSERIAL PRIMARY KEY,
  player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  rules VARCHAR(50) NOT NULL,                 -- e.g., 'chess', 'chess960'
  time_class VARCHAR(20) NOT NULL,           -- 'bullet','blitz','rapid','daily'
  last_rating INTEGER,
  last_rating_date BIGINT,
  last_rd INTEGER,
  best_rating INTEGER,
  best_date BIGINT,
  best_game_url TEXT,
  record_win INTEGER DEFAULT 0,
  record_loss INTEGER DEFAULT 0,
  record_draw INTEGER DEFAULT 0,
  time_per_move INTEGER,
  timeout_percent DOUBLE PRECISION,
  created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  updated_at BIGINT,
  UNIQUE(player_id, rules, time_class)
);

CREATE INDEX IF NOT EXISTS idx_player_stats_player ON player_stats(player_id);

-- Tactics
CREATE TABLE IF NOT EXISTS player_tactics_stats (
  player_id BIGINT PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  highest_rating INTEGER,
  highest_date BIGINT,
  lowest_rating INTEGER,
  lowest_date BIGINT,
  updated_at BIGINT
);

-- Lessons
CREATE TABLE IF NOT EXISTS player_lessons_stats (
  player_id BIGINT PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  highest_rating INTEGER,
  highest_date BIGINT,
  lowest_rating INTEGER,
  lowest_date BIGINT,
  updated_at BIGINT
);

-- Puzzle Rush
CREATE TABLE IF NOT EXISTS player_puzzle_rush_best (
  player_id BIGINT PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  total_attempts INTEGER,
  score INTEGER,
  updated_at BIGINT
);

CREATE TABLE IF NOT EXISTS player_puzzle_rush_daily (
  player_id BIGINT PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  total_attempts INTEGER,
  score INTEGER,
  updated_at BIGINT
);

-- Monthly archive index for incremental ingestion
CREATE TABLE IF NOT EXISTS monthly_archives (
  id BIGSERIAL PRIMARY KEY,
  player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL CHECK (month >= 1 AND month <= 12),
  url TEXT NOT NULL UNIQUE,
  created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  updated_at BIGINT,
  fetch_status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending|running|succeeded|failed|skipped
  last_fetch_attempt BIGINT NOT NULL DEFAULT 0,
  last_success_at BIGINT NOT NULL DEFAULT 0,
  next_retry_at BIGINT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  priority SMALLINT NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 9),
  checksum TEXT,
  UNIQUE(player_id, year, month)
);

CREATE INDEX IF NOT EXISTS idx_archives_player ON monthly_archives(player_id);
CREATE INDEX IF NOT EXISTS idx_archives_year_month ON monthly_archives(year, month);
CREATE INDEX IF NOT EXISTS idx_archives_status ON monthly_archives(fetch_status, next_retry_at);

-- Track last successful ingestion touch points per player
CREATE TABLE IF NOT EXISTS player_ingestion_state (
  player_id BIGINT PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  last_profile_fetch BIGINT,
  next_profile_fetch BIGINT,
  last_stats_fetch BIGINT,
  next_stats_fetch BIGINT,
  last_archives_scan BIGINT,
  next_archives_scan BIGINT,
  archive_cursor_year INTEGER,
  archive_cursor_month INTEGER,
  status VARCHAR(20) NOT NULL DEFAULT 'idle', -- idle|scheduled|running|blocked|error
  error TEXT,
  updated_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
);

-- Generic ingestion task queue (pull-based workers)
CREATE TABLE IF NOT EXISTS ingestion_jobs (
  id BIGSERIAL PRIMARY KEY,
  player_id BIGINT REFERENCES players(id) ON DELETE CASCADE,
  job_type VARCHAR(30) NOT NULL, -- profile|stats|archives|games
  scope JSONB,
  dedupe_key VARCHAR(255) UNIQUE,
  status VARCHAR(20) NOT NULL DEFAULT 'queued', -- queued|locked|succeeded|failed|cancelled
  priority SMALLINT NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 9),
  attempts SMALLINT NOT NULL DEFAULT 0,
  max_attempts SMALLINT NOT NULL DEFAULT 5,
  available_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  locked_at BIGINT,
  completed_at BIGINT,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs(status, available_at);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_player ON ingestion_jobs(player_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_type ON ingestion_jobs(job_type);

-- Games (finished)
CREATE TABLE IF NOT EXISTS games (
  id BIGSERIAL PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,                   -- API: url
  pgn TEXT,                                  -- API: pgn
  time_control VARCHAR(50),                  -- API: time_control
  start_time BIGINT,                         -- API: start_time (only for daily games, nullable)
  end_time BIGINT NOT NULL,                  -- API: end_time (epoch seconds)
  rated BOOLEAN NOT NULL DEFAULT TRUE,      -- API: rated (boolean)
  time_class VARCHAR(20),                   -- API: time_class (bullet/blitz/rapid/daily)
  rules VARCHAR(50),                        -- API: rules (chess/chess960/etc)
  eco_url TEXT,                             -- API: eco (full URL)
  eco_code VARCHAR(128),                     -- extracted from eco_url or parsed from PGN
  fen TEXT,                                 -- API: fen (final position)
  initial_setup TEXT,                        -- API: initial_setup (starting FEN)
  tcn TEXT,                                 -- API: tcn
  white_accuracy DOUBLE PRECISION,          -- API: accuracies.white
  black_accuracy DOUBLE PRECISION,          -- API: accuracies.black
  white_player_id BIGINT REFERENCES players(id),
  white_rating INTEGER,                     -- API: white.rating
  white_result VARCHAR(50),                 -- API: white.result
  white_uuid VARCHAR(255),                  -- API: white.uuid
  black_player_id BIGINT REFERENCES players(id),
  black_rating INTEGER,                     -- API: black.rating
  black_result VARCHAR(50),                 -- API: black.result
  black_uuid VARCHAR(255),                  -- API: black.uuid
  archive_id BIGINT REFERENCES monthly_archives(id),
  created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT
);

CREATE INDEX IF NOT EXISTS idx_games_end_time ON games(end_time);
CREATE INDEX IF NOT EXISTS idx_games_white_player ON games(white_player_id);
CREATE INDEX IF NOT EXISTS idx_games_black_player ON games(black_player_id);
CREATE INDEX IF NOT EXISTS idx_games_time_class ON games(time_class);
CREATE INDEX IF NOT EXISTS idx_games_url ON games(url);

DO $$
BEGIN
  ALTER TABLE games
    ALTER COLUMN eco_code TYPE VARCHAR(128);
EXCEPTION
  WHEN undefined_column THEN NULL;
END $$;

-- Fetch/caching diagnostics (ETag, Last-Modified)
CREATE TABLE IF NOT EXISTS fetch_log (
  id BIGSERIAL PRIMARY KEY,
  url TEXT NOT NULL,
  etag VARCHAR(255),
  last_modified VARCHAR(255),
  status_code INTEGER,
  fetched_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_fetch_log_url ON fetch_log(url);
CREATE INDEX IF NOT EXISTS idx_fetch_log_time ON fetch_log(fetched_at);
CREATE INDEX IF NOT EXISTS idx_fetch_log_url_time ON fetch_log(url, fetched_at DESC);

-- ============================================================
-- Lichess tables
-- ============================================================

CREATE TABLE IF NOT EXISTS lichess_players (
  id               BIGSERIAL PRIMARY KEY,
  username         TEXT NOT NULL UNIQUE,          -- lowercased
  display_username TEXT,
  title            VARCHAR(10),                   -- GM, IM, etc.
  patron           BOOLEAN DEFAULT FALSE,
  tos_violation    BOOLEAN DEFAULT FALSE,
  disabled         BOOLEAN DEFAULT FALSE,
  verified         BOOLEAN DEFAULT FALSE,
  created_at       BIGINT,                        -- epoch ms (Lichess native)
  seen_at          BIGINT,                        -- epoch ms
  play_time_total  BIGINT,                        -- seconds
  url              TEXT,
  bio              TEXT,
  country          TEXT,
  flair            TEXT,
  ingested_at      BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
);

CREATE INDEX IF NOT EXISTS idx_lichess_players_username ON lichess_players(username);

CREATE TABLE IF NOT EXISTS lichess_player_stats (
  id         BIGSERIAL PRIMARY KEY,
  player_id  BIGINT NOT NULL REFERENCES lichess_players(id) ON DELETE CASCADE,
  perf       TEXT NOT NULL,
  rating     INTEGER,
  rd         INTEGER,
  prog       INTEGER,
  games      INTEGER,
  prov       BOOLEAN DEFAULT FALSE,
  fetched_at BIGINT,
  UNIQUE (player_id, perf)
);

CREATE INDEX IF NOT EXISTS idx_lichess_player_stats_player ON lichess_player_stats(player_id);

CREATE TABLE IF NOT EXISTS lichess_player_ingestion_state (
  player_id           BIGINT PRIMARY KEY REFERENCES lichess_players(id) ON DELETE CASCADE,
  last_profile_fetch  BIGINT,                     -- epoch ms
  status              VARCHAR(20) NOT NULL DEFAULT 'idle',
  error               TEXT,
  updated_at          BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT
);

-- Local app tracking: who we track (self/friends/follows)
CREATE TABLE IF NOT EXISTS social.app_users (
  id BIGSERIAL PRIMARY KEY,
  username VARCHAR(255) NOT NULL UNIQUE,
  player_id BIGINT REFERENCES players(id) ON DELETE SET NULL,
  display_name VARCHAR(255),
  avatar_url TEXT,
  bio TEXT,
  privacy_level VARCHAR(20) NOT NULL DEFAULT 'public', -- public|followers|private
  allow_comments BOOLEAN NOT NULL DEFAULT TRUE,
  created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  updated_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  last_seen BIGINT
);

CREATE INDEX IF NOT EXISTS idx_app_users_player_id ON social.app_users(player_id);

CREATE TABLE IF NOT EXISTS social.app_user_tracked_players (
  id BIGSERIAL PRIMARY KEY,
  app_user_id BIGINT NOT NULL REFERENCES social.app_users(id) ON DELETE CASCADE,
  player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  relationship VARCHAR(20) NOT NULL DEFAULT 'follow', -- self|friend|follow
  notification_level VARCHAR(20) NOT NULL DEFAULT 'all', -- all|mentions|mute
  notes TEXT,
  added_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  UNIQUE(app_user_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_tracked_app_user ON social.app_user_tracked_players(app_user_id);
CREATE INDEX IF NOT EXISTS idx_tracked_player ON social.app_user_tracked_players(player_id);

-- Clubs & memberships
CREATE TABLE IF NOT EXISTS social.clubs (
  id BIGSERIAL PRIMARY KEY,
  slug VARCHAR(120) NOT NULL UNIQUE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  owner_id BIGINT REFERENCES social.app_users(id) ON DELETE SET NULL,
  visibility VARCHAR(20) NOT NULL DEFAULT 'public', -- public|private|unlisted
  created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  updated_at BIGINT
);

CREATE TABLE IF NOT EXISTS social.club_memberships (
  id BIGSERIAL PRIMARY KEY,
  club_id BIGINT NOT NULL REFERENCES social.clubs(id) ON DELETE CASCADE,
  app_user_id BIGINT NOT NULL REFERENCES social.app_users(id) ON DELETE CASCADE,
  role VARCHAR(20) NOT NULL DEFAULT 'member', -- member|admin|moderator
  status VARCHAR(20) NOT NULL DEFAULT 'active', -- active|pending|blocked
  joined_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  UNIQUE(club_id, app_user_id)
);

CREATE INDEX IF NOT EXISTS idx_club_memberships_user ON social.club_memberships(app_user_id);

-- Posts (Strava-like feed)
CREATE TABLE IF NOT EXISTS social.posts (
  id BIGSERIAL PRIMARY KEY,
  app_user_id BIGINT NOT NULL REFERENCES social.app_users(id) ON DELETE CASCADE,
  club_id BIGINT REFERENCES social.clubs(id) ON DELETE SET NULL,
  player_snapshot JSONB, -- cached stats or summary shown in the post
  content TEXT NOT NULL,
  audience VARCHAR(20) NOT NULL DEFAULT 'followers', -- public|followers|club|private
  source VARCHAR(30) NOT NULL DEFAULT 'manual', -- manual|auto_stats|system
  is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
  created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  updated_at BIGINT,
  deleted_at BIGINT
);

CREATE INDEX IF NOT EXISTS idx_posts_user ON social.posts(app_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_club ON social.posts(club_id, created_at DESC);

CREATE TABLE IF NOT EXISTS social.post_media (
  id BIGSERIAL PRIMARY KEY,
  post_id BIGINT NOT NULL REFERENCES social.posts(id) ON DELETE CASCADE,
  media_type VARCHAR(20) NOT NULL, -- image|video|pgn|link
  url TEXT NOT NULL,
  metadata JSONB,
  sort_order SMALLINT NOT NULL DEFAULT 0
);

-- Comments
CREATE TABLE IF NOT EXISTS social.comments (
  id BIGSERIAL PRIMARY KEY,
  post_id BIGINT NOT NULL REFERENCES social.posts(id) ON DELETE CASCADE,
  app_user_id BIGINT NOT NULL REFERENCES social.app_users(id) ON DELETE CASCADE,
  parent_comment_id BIGINT REFERENCES social.comments(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  updated_at BIGINT,
  deleted_at BIGINT
);

CREATE INDEX IF NOT EXISTS idx_comments_post ON social.comments(post_id, created_at);

-- Reactions (likes, emojis) on posts
CREATE TABLE IF NOT EXISTS social.post_reactions (
  id BIGSERIAL PRIMARY KEY,
  post_id BIGINT NOT NULL REFERENCES social.posts(id) ON DELETE CASCADE,
  app_user_id BIGINT NOT NULL REFERENCES social.app_users(id) ON DELETE CASCADE,
  reaction VARCHAR(30) NOT NULL DEFAULT 'like',
  reacted_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  UNIQUE(post_id, app_user_id, reaction)
);

CREATE INDEX IF NOT EXISTS idx_post_reactions_post ON social.post_reactions(post_id);

-- Reactions on comments
CREATE TABLE IF NOT EXISTS social.comment_reactions (
  id BIGSERIAL PRIMARY KEY,
  comment_id BIGINT NOT NULL REFERENCES social.comments(id) ON DELETE CASCADE,
  app_user_id BIGINT NOT NULL REFERENCES social.app_users(id) ON DELETE CASCADE,
  reaction VARCHAR(30) NOT NULL DEFAULT 'like',
  reacted_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  UNIQUE(comment_id, app_user_id, reaction)
);

-- Notification log for mobile push / in-app feed
CREATE TABLE IF NOT EXISTS social.notifications (
  id BIGSERIAL PRIMARY KEY,
  app_user_id BIGINT NOT NULL REFERENCES social.app_users(id) ON DELETE CASCADE,
  event_type VARCHAR(50) NOT NULL,
  event_payload JSONB,
  seen BOOLEAN NOT NULL DEFAULT FALSE,
  created_at BIGINT NOT NULL DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT,
  seen_at BIGINT
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON social.notifications(app_user_id, seen, created_at DESC);
