# Schema Questions & Answers

## 1. ✅ Did I check that all fields are available from API?

**YES** - I've verified against actual API responses. See `api_field_verification.md` for details.

### Key Findings:

**✅ All core fields exist:**
- `player_id` - ✅ Stable ID (499209823)
- `username` - ✅ Lowercase
- `status`, `league`, `followers`, `joined`, `last_online` - ✅ All present
- Stats structure matches exactly
- Game structure matches exactly

**⚠️ Some fields need extraction/parsing:**
- `display_username` - Extract from `url` field (contains original case)
- `country_code` - Extract from `country` URL (e.g., "DE" from "/country/DE")
- `twitch_url` - Parse from `streaming_platforms` array
- `eco_code` - Extract from `eco` URL or parse PGN
- `start_time` - Only present for Daily Chess games (nullable)

**❌ Fields NOT in API:**
- `location` - Not available in API
- `avatar_url` - API uses `avatar` (fixed in schema)

**Schema Updated:** Fixed `avatar_url` → `avatar` and added comments mapping each field to API source.

## 2. ❓ Can we know what schema Chess.com uses internally?

**NO** - We cannot know their internal database schema. It's proprietary.

**What we CAN infer from the API:**

1. **They use stable IDs:**
   - `player_id` (integer) - Primary stable identifier
   - `uuid` (string) - Secondary identifier for games/players

2. **Data organization:**
   - Players identified by `player_id` (never changes)
   - Games organized by month/year archives
   - Stats keyed by `{rules}_{time_class}` pattern

3. **Normalization:**
   - Countries in separate endpoint (`/country/{code}`)
   - Openings referenced by URL (`/openings/...`)
   - Players referenced by URL (`/player/{username}`)

4. **Timestamps:**
   - All dates as Unix epoch seconds

**Our schema is designed to:**
- Match the API structure closely
- Use stable `player_id` for relationships
- Normalize data for efficient querying
- Support incremental updates via archives

## 3. ✅ Does user have an ID in their database?

**YES** - Users have **TWO stable identifiers:**

### Primary: `player_id` (integer)
- Example: `499209823` for YevgenChess
- **Never changes**, even if username changes
- Used for tracking across username changes
- This is what we use as `chesscom_player_id` in our schema

### Secondary: `uuid` (string)
- Example: `"3f690bc6-bc90-11f0-aeb2-2be34a696a33"`
- Also stable
- Used in some API contexts (games reference player UUIDs)

### Username (can change)
- Example: `"yevgenchess"` (lowercase)
- Can change, but `player_id` stays constant
- API documentation mentions username changes are "extremely rare"

**Our Schema Strategy:**
- ✅ Use `chesscom_player_id` (maps to API `player_id`) as primary foreign key
- ✅ Store `username` for lookups (with unique constraint)
- ✅ Store `display_username` extracted from URL (original case)
- ✅ If username changes, we can update it while keeping same `chesscom_player_id`

## Summary

✅ **All fields verified** - Schema matches API with minor extraction needed  
❌ **Can't know internal schema** - But we can infer structure from API  
✅ **Users have stable IDs** - `player_id` is the key identifier we use

The schema is ready for implementation!

