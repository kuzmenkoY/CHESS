# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Chess.com API exploration project written in Python. The codebase focuses on interacting with the Chess.com public API to retrieve player profiles, statistics, and game data.

## Project Structure

```
CHESS/
└── experiments/
    └── API_test/
        ├── chess_api_explorer.py  # Full-featured API explorer
        ├── simple_test.py         # Simple API test script
        └── requirements.txt       # Python dependencies
```

## Development Commands

### Setup
```bash
pip install -r experiments/API_test/requirements.txt
```

### Running Scripts
```bash
# Full API explorer (explores multiple users)
python experiments/API_test/chess_api_explorer.py

# Simple test (single user)
python experiments/API_test/simple_test.py
```

## API Architecture

### Chess.com API
- **Base URL**: `https://api.chess.com/pub`
- **Required Headers**: Must include `User-Agent` header (e.g., "ChessAPI/1.0 (Python Script)")
- **Rate Limiting**: Be mindful of API rate limits when fetching multiple archives

### Key Endpoints Used
1. `/player/{username}` - Player profile information
2. `/player/{username}/stats` - Player statistics (ratings per time control)
3. `/player/{username}/games/archives` - List of monthly game archive URLs
4. Archive URLs - Individual month's games with full PGN data

### Data Flow
1. Fetch player profile to validate user exists
2. Retrieve statistics for current ratings
3. Get list of game archive URLs (organized by month/year)
4. Iterate through each archive URL to collect all games
5. Parse game data including PGN, results, time controls

## Code Conventions

### API Interaction Pattern
- All API calls use the `HEADERS` constant with required User-Agent
- Timeout set to 10 seconds for all requests
- Exception handling wraps all API calls with informative error messages
- Type hints used for function signatures

### Error Handling
- Functions return `Optional[Dict]` or `List[Dict]`
- API errors are caught and logged but don't crash the program
- Check for expected keys in responses before accessing

### Testing Users
Current test users in scripts:
- `YevgenChess` - Primary test user
- `nipunjani` - Secondary test user
