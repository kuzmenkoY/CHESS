PRAGMA foreign_keys = ON;

-- Core players
CREATE TABLE IF NOT EXISTS players (
  id INTEGER PRIMARY KEY,
  chesscom_player_id INTEGER UNIQUE,        -- API: player_id (stable, never changes)
  username TEXT NOT NULL UNIQUE,            -- API: username (lowercased)
  display_username TEXT,                    -- extracted from API: url field
  name TEXT,                                 -- API: name (optional, may be NULL)
  title TEXT,                                -- API: title (optional, only for titled players)
  status TEXT,                               -- API: status (basic, premium, etc.)
  league TEXT,                               -- API: league (Wood, Champion, etc.)
  country_url TEXT,                          -- API: country (full URL)
  country_code TEXT,                         -- extracted from country_url (e.g., "DE")
  avatar TEXT,                               -- API: avatar (optional URL, not avatar_url)
  twitch_url TEXT,                           -- extracted from streaming_platforms array
  followers INTEGER,                         -- API: followers
  joined INTEGER,                            -- API: joined (epoch seconds)
  last_online INTEGER,                       -- API: last_online (epoch seconds)
  is_streamer INTEGER NOT NULL DEFAULT 0,   -- API: is_streamer (boolean)
  verified INTEGER NOT NULL DEFAULT 0,      -- API: verified (boolean)
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
  updated_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_players_username ON players(username);

-- Optional country catalog (populate lazily)
CREATE TABLE IF NOT EXISTS countries (
  code TEXT PRIMARY KEY,
  name TEXT
);

-- Per rules/time_class stats (bullet/blitz/rapid/daily, chess/chess960)
CREATE TABLE IF NOT EXISTS player_stats (
  id INTEGER PRIMARY KEY,
  player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  rules TEXT NOT NULL,                      -- e.g., 'chess', 'chess960'
  time_class TEXT NOT NULL,                 -- 'bullet','blitz','rapid','daily'
  last_rating INTEGER,
  last_rating_date INTEGER,
  last_rd INTEGER,
  best_rating INTEGER,
  best_date INTEGER,
  best_game_url TEXT,
  record_win INTEGER,
  record_loss INTEGER,
  record_draw INTEGER,
  time_per_move INTEGER,
  timeout_percent REAL,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
  updated_at INTEGER,
  UNIQUE(player_id, rules, time_class)
);

-- Tactics
CREATE TABLE IF NOT EXISTS player_tactics_stats (
  player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  highest_rating INTEGER,
  highest_date INTEGER,
  lowest_rating INTEGER,
  lowest_date INTEGER,
  updated_at INTEGER
);

-- Lessons
CREATE TABLE IF NOT EXISTS player_lessons_stats (
  player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  highest_rating INTEGER,
  highest_date INTEGER,
  lowest_rating INTEGER,
  lowest_date INTEGER,
  updated_at INTEGER
);

-- Puzzle Rush
CREATE TABLE IF NOT EXISTS player_puzzle_rush_best (
  player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  total_attempts INTEGER,
  score INTEGER,
  updated_at INTEGER
);
CREATE TABLE IF NOT EXISTS player_puzzle_rush_daily (
  player_id INTEGER PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
  total_attempts INTEGER,
  score INTEGER,
  updated_at INTEGER
);

-- Monthly archive index for incremental ingestion
CREATE TABLE IF NOT EXISTS monthly_archives (
  id INTEGER PRIMARY KEY,
  player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  url TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
  UNIQUE(player_id, year, month)
);

-- Games (finished)
CREATE TABLE IF NOT EXISTS games (
  id INTEGER PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,                 -- API: url
  pgn TEXT,                                 -- API: pgn
  time_control TEXT,                        -- API: time_control
  start_time INTEGER,                      -- API: start_time (only for daily games, nullable)
  end_time INTEGER,                         -- API: end_time (epoch seconds)
  rated INTEGER,                            -- API: rated (boolean, stored as 0/1)
  time_class TEXT,                          -- API: time_class (bullet/blitz/rapid/daily)
  rules TEXT,                               -- API: rules (chess/chess960/etc)
  eco_url TEXT,                             -- API: eco (full URL)
  eco_code TEXT,                            -- extracted from eco_url or parsed from PGN
  fen TEXT,                                 -- API: fen (final position)
  initial_setup TEXT,                       -- API: initial_setup (starting FEN)
  tcn TEXT,                                 -- API: tcn
  white_accuracy REAL,                      -- API: accuracies.white
  black_accuracy REAL,                      -- API: accuracies.black
  white_player_id INTEGER REFERENCES players(id),
  white_rating INTEGER,                      -- API: white.rating
  white_result TEXT,                         -- API: white.result
  white_uuid TEXT,                          -- API: white.uuid
  black_player_id INTEGER REFERENCES players(id),
  black_rating INTEGER,                     -- API: black.rating
  black_result TEXT,                         -- API: black.result
  black_uuid TEXT,                          -- API: black.uuid
  archive_id INTEGER REFERENCES monthly_archives(id),
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);
CREATE INDEX IF NOT EXISTS idx_games_end_time ON games(end_time);
CREATE INDEX IF NOT EXISTS idx_games_white_player ON games(white_player_id);
CREATE INDEX IF NOT EXISTS idx_games_black_player ON games(black_player_id);
CREATE INDEX IF NOT EXISTS idx_games_time_class ON games(time_class);

-- Fetch/caching diagnostics (ETag, Last-Modified)
CREATE TABLE IF NOT EXISTS fetch_log (
  id INTEGER PRIMARY KEY,
  url TEXT NOT NULL,
  etag TEXT,
  last_modified TEXT,
  status_code INTEGER,
  fetched_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_fetch_log_url ON fetch_log(url);
CREATE INDEX IF NOT EXISTS idx_fetch_log_time ON fetch_log(fetched_at);

-- Local app tracking: who we track (self/friends/follows)
CREATE TABLE IF NOT EXISTS app_users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
);
CREATE TABLE IF NOT EXISTS app_user_tracked_players (
  id INTEGER PRIMARY KEY,
  app_user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
  player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
  relationship TEXT NOT NULL DEFAULT 'follow', -- self|friend|follow
  added_at INTEGER NOT NULL DEFAULT (strftime('%s','now')),
  UNIQUE(app_user_id, player_id)
);


