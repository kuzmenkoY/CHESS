# Lichess API Investigation

This folder contains documentation and test scripts for exploring the Lichess.org API.

## Overview

Lichess.org provides a comprehensive REST API for accessing chess data. The API supports both public (unauthenticated) and authenticated endpoints.

## Base URL

```
https://lichess.org/api
```

## Authentication Methods

### 1. Public Endpoints (No Authentication Required)

Many endpoints are publicly accessible without authentication:
- User profiles
- User ratings
- Public games
- Tournaments
- Puzzles
- Leaderboards

**Example:**
```python
import requests

response = requests.get("https://lichess.org/api/user/thibault")
user_data = response.json()
```

### 2. Personal API Access Tokens

For quick API access without OAuth flow, you can use Personal API Access Tokens:

**How to Generate:**
1. Log in to your Lichess account
2. Go to: https://lichess.org/account/oauth/token/create
3. Create a new token with desired scopes
4. Copy the token (you'll only see it once!)

**Usage:**
```python
import requests

headers = {
    "Authorization": f"Bearer {your_token}"
}

response = requests.get("https://lichess.org/api/account", headers=headers)
account_data = response.json()
```

**Security Notes:**
- Keep tokens secret - never commit them to public repositories
- Use environment variables or secure storage
- Tokens can perform actions within their scope limits
- Revoke compromised tokens immediately
- View/manage tokens at: https://lichess.org/account/oauth/token

### 3. OAuth 2.0 with PKCE (For User Authorization)

For allowing users of your application to authorize with Lichess:

**Key Features:**
- Supports unregistered and public clients (no client authentication required)
- Uses PKCE (Proof Key for Code Exchange) for security
- Users can log in with their Lichess account
- Grants your app access to user data based on requested scopes

**OAuth Flow:**
1. **Authorization Request**: Redirect user to Lichess authorization endpoint
2. **User Consent**: User logs in and grants permissions
3. **Authorization Code**: Lichess redirects back with code
4. **Token Exchange**: Exchange code for access token
5. **API Access**: Use access token for authenticated requests

**Resources:**
- OAuth endpoint documentation: https://lichess.org/api#tag/OAuth
- Demo app: https://github.com/lichess-org/api-demo
- Flask/Python example: Available in Lichess API docs
- NodeJS Passport strategy: Available in Lichess API docs

## Rate Limiting

- **One request at a time**: Only make one request at a time
- **429 Status**: If you receive HTTP 429, you're being rate limited
- **Best Practice**: Implement sequential requests, not parallel
- **Retry Logic**: Wait and retry after receiving 429

## Response Formats

### Standard JSON
Most endpoints return standard JSON responses.

### NDJSON (Newline Delimited JSON)
Some endpoints stream responses as NDJSON:
- One JSON object per line
- Useful for large datasets (games, tournaments)
- Example: Game exports, tournament results

**JavaScript utility function** available in Lichess API docs for reading NDJSON streams.

## Python Libraries

### 1. Berserk (Official Python Library)
- **GitHub**: https://github.com/lichess-org/berserk
- **Installation**: `pip install berserk`
- **Documentation**: Comprehensive Python wrapper for Lichess API
- **Features**: 
  - User data
  - Games
  - Tournaments
  - Puzzles
  - Bot API
  - Board API

### 2. python-chess
- General chess library that can work with Lichess data
- Useful for parsing PGN, analyzing positions

## Common Endpoints

### User Data (Public)
- `GET /api/user/{username}` - User profile
- `GET /api/user/{username}/rating-history` - Rating history
- `GET /api/user/{username}/activity` - Recent activity
- `GET /api/user/{username}/perf/{perf}` - Performance stats for time control

### Games (Public)
- `GET /api/games/user/{username}` - Export user games (NDJSON stream)
- `GET /api/game/{gameId}` - Single game (PGN format)

### Account (Authenticated)
- `GET /api/account` - Your account info
- `GET /api/account/email` - Your email
- `GET /api/account/preferences` - Your preferences

### Tournaments (Public)
- `GET /api/tournament` - Current tournaments
- `GET /api/tournament/{id}` - Tournament details
- `GET /api/tournament/{id}/results` - Tournament results

### Puzzles (Public)
- `GET /api/puzzle/daily` - Daily puzzle
- `GET /api/puzzle/activity` - Puzzle activity

## Do You Need Authorization?

### No Authorization Needed For:
- ✅ Viewing any user's public profile
- ✅ Viewing any user's public games
- ✅ Viewing ratings and statistics
- ✅ Downloading public game data
- ✅ Accessing tournaments and puzzles

### Authorization Required For:
- ❌ Accessing your own account details
- ❌ Viewing private games
- ❌ Making moves or playing games
- ❌ Accessing user preferences
- ❌ Bot operations

## Getting Started

### 1. Do You Need a Lichess Account?

**For Public Data**: No account needed! You can query any user's public data.

**For Personal Access Token**: Yes, you need an account to generate tokens.

**For OAuth Integration**: Yes, users need Lichess accounts to authorize your app.

### 2. Testing Public Endpoints

You can immediately start fetching data from any public user:

```python
import requests

# Get user profile (no auth needed)
response = requests.get("https://lichess.org/api/user/magnuscarlsen")
profile = response.json()

# Get user games (no auth needed)
response = requests.get("https://lichess.org/api/games/user/magnuscarlsen?max=5")
# Returns NDJSON stream
```

### 3. Setting Up OAuth for Your Application

If you want users to authorize with Lichess:

1. **Choose a unique client ID** (any string, no registration needed)
2. **Implement OAuth 2.0 PKCE flow**:
   - Generate code verifier and challenge
   - Redirect user to authorization endpoint
   - Handle callback with authorization code
   - Exchange code for access token
3. **Use access token** for authenticated requests

See `oauth_example.py` for a basic implementation example.

## Example Use Cases

### 1. Fetch User Profile (No Auth)
```python
import requests

username = "thibault"
response = requests.get(f"https://lichess.org/api/user/{username}")
user = response.json()
print(f"User: {user['username']}")
print(f"Title: {user.get('title', 'No title')}")
```

### 2. Download User Games (No Auth)
```python
import requests

username = "thibault"
url = f"https://lichess.org/api/games/user/{username}?max=10"
response = requests.get(url, stream=True)

for line in response.iter_lines():
    if line:
        game = json.loads(line)
        print(f"Game: {game.get('id')}")
```

### 3. Authenticated Request (With Token)
```python
import requests
import os

token = os.getenv("LICHESS_TOKEN")
headers = {"Authorization": f"Bearer {token}"}

response = requests.get("https://lichess.org/api/account", headers=headers)
account = response.json()
print(f"Logged in as: {account['username']}")
```

## Resources

- **Official API Docs**: https://lichess.org/api
- **Berserk Python Library**: https://github.com/lichess-org/berserk
- **API Demo App**: https://github.com/lichess-org/api-demo
- **OAuth Documentation**: https://lichess.org/api#tag/OAuth
- **Personal Tokens**: https://lichess.org/account/oauth/token
- **Discord Channel**: Lichess Discord for API help

## Notes

- All API requests should include appropriate User-Agent headers
- Respect rate limits (one request at a time)
- Public data is freely accessible - no authorization needed
- For user-specific actions, implement OAuth flow
- Personal tokens are convenient for testing and personal projects
- OAuth is recommended for production applications with multiple users

