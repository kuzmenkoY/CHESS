# API Field Verification & Schema Analysis

## 1. Field Availability Check

### Profile Endpoint: `/pub/player/{username}`

**Available in API:**
- ✅ `player_id` - **YES, this is the stable ID** (e.g., 499209823)
- ✅ `username` - lowercase version
- ✅ `url` - web profile URL (contains display username with original case)
- ✅ `@id` - API self-reference URL
- ✅ `followers` - integer count
- ✅ `country` - URL to country endpoint (e.g., "https://api.chess.com/pub/country/DE")
- ✅ `last_online` - timestamp
- ✅ `joined` - timestamp
- ✅ `status` - "basic", "premium", etc.
- ✅ `is_streamer` - boolean
- ✅ `verified` - boolean
- ✅ `league` - "Wood", "Champion", etc.
- ✅ `streaming_platforms` - array

**NOT in API (need to extract or omit):**
- ❌ `name` - **NOT always present** (optional, e.g., nipunjani has it, YevgenChess doesn't)
- ❌ `title` - **NOT always present** (only for titled players: GM, IM, FM, etc.)
- ❌ `avatar` - **NOT always present** (optional URL)
- ❌ `location` - **NOT in API response** (not available)
- ❌ `twitch_url` - **NOT directly** (in `streaming_platforms` array, need to parse)

**Schema Issues Found:**
- `avatar_url` - API uses `avatar` (not `avatar_url`)
- `twitch_url` - Need to extract from `streaming_platforms` array
- `country_code` - Need to extract from country URL (e.g., "DE" from "/country/DE")

### Stats Endpoint: `/pub/player/{username}/stats`

**Available in API:**
- ✅ `chess_bullet`, `chess_blitz`, `chess_rapid`, `chess_daily` - objects with:
  - `last.rating`, `last.date`, `last.rd`
  - `best.rating`, `best.date`, `best.game` (URL)
  - `record.win`, `record.loss`, `record.draw`
  - `record.time_per_move` (optional)
  - `record.timeout_percent` (optional)
- ✅ `tactics` - object with `highest.rating`, `highest.date`, `lowest.rating`, `lowest.date`
- ✅ `lessons` - same structure as tactics
- ✅ `puzzle_rush` - object with `daily` and `best` objects containing `total_attempts` and `score`
- ✅ `fide` - integer (0 if not rated)

**Schema is correct** - matches API structure

### Games Endpoint: `/pub/player/{username}/games/{YYYY}/{MM}`

**Available in API:**
- ✅ `url` - game URL
- ✅ `pgn` - full PGN string
- ✅ `time_control` - string (e.g., "60")
- ✅ `end_time` - timestamp
- ✅ `rated` - boolean
- ✅ `accuracies.white`, `accuracies.black` - floats
- ✅ `tcn` - string
- ✅ `uuid` - game UUID
- ✅ `initial_setup` - FEN string
- ✅ `fen` - final FEN
- ✅ `time_class` - "bullet", "blitz", "rapid", "daily"
- ✅ `rules` - "chess", "chess960", etc.
- ✅ `eco` - URL to opening (e.g., "https://www.chess.com/openings/Van-t-Kruijs-Opening-1...c5")
- ✅ `white.username`, `white.rating`, `white.result`, `white.@id`, `white.uuid`
- ✅ `black.username`, `black.rating`, `black.result`, `black.@id`, `black.uuid`

**NOT in API:**
- ❌ `start_time` - **Only for Daily Chess games** (not always present)
- ❌ `eco_code` - Need to extract from `eco` URL or parse PGN

**Schema Issues Found:**
- `start_time` - Should be nullable (only for daily games)
- `eco_code` - Need to parse from `eco` URL or extract from PGN

## 2. Chess.com Internal Schema

**We CANNOT know their internal schema** - it's proprietary. However, we can infer:

- They use `player_id` as a stable identifier (doesn't change when username changes)
- They use `uuid` for games and players (separate from `player_id`)
- They structure data hierarchically (stats by game type, games by month)
- They use timestamps (Unix epoch seconds)
- They normalize country data (separate endpoint)

**What we know from API:**
- Stable IDs: `player_id` (integer) and `uuid` (string)
- Usernames can change, but `player_id` stays constant
- Games are organized by month/year archives
- Stats are keyed by `{rules}_{time_class}` (e.g., "chess_bullet")

## 3. User ID in Chess.com Database

**YES - Users have stable IDs:**

1. **`player_id`** (integer) - Primary stable identifier
   - Example: `499209823` for YevgenChess
   - Never changes, even if username changes
   - Used for tracking across username changes

2. **`uuid`** (string) - Secondary identifier
   - Example: `"3f690bc6-bc90-11f0-aeb2-2be34a696a33"`
   - Also stable, used in some contexts

**Recommendation:** Use `player_id` as the primary foreign key in our schema (which we already do with `chesscom_player_id`).

## Schema Corrections Needed

1. **players table:**
   - Change `avatar_url` → `avatar` (match API)
   - Make `name`, `title` explicitly nullable
   - Extract `country_code` from `country` URL during ingestion
   - Parse `twitch_url` from `streaming_platforms` array

2. **games table:**
   - Make `start_time` nullable (only for daily games)
   - Extract `eco_code` from `eco` URL or parse PGN

3. **Add helper functions:**
   - Extract country code from country URL
   - Parse streaming platforms array
   - Extract ECO code from ECO URL

