"""
Simple Lichess API Test
Test fetching user data from Lichess API without authentication.
"""

import requests
import json
from datetime import datetime

BASE_URL = "https://lichess.org/api"

# Headers - User-Agent is recommended
HEADERS = {
    "User-Agent": "LichessAPI/1.0 (Python Script)"
}

def get_user_profile(username):
    """Get user profile information (public, no auth required)."""
    print(f"\n{'='*80}")
    print(f"USER PROFILE: {username}")
    print('='*80)
    
    try:
        response = requests.get(f"{BASE_URL}/user/{username}", headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            profile = response.json()
            
            print("\n--- BASIC INFO ---")
            print(f"Username: {profile.get('username', 'N/A')}")
            print(f"Title: {profile.get('title', 'No title')}")
            print(f"Online: {profile.get('online', False)}")
            print(f"Patron: {profile.get('patron', False)}")
            
            if 'perfs' in profile:
                print("\n--- RATINGS ---")
                perfs = profile['perfs']
                if 'rapid' in perfs:
                    print(f"Rapid: {perfs['rapid'].get('rating', 'N/A')}")
                if 'blitz' in perfs:
                    print(f"Blitz: {perfs['blitz'].get('rating', 'N/A')}")
                if 'bullet' in perfs:
                    print(f"Bullet: {perfs['bullet'].get('rating', 'N/A')}")
                if 'classical' in perfs:
                    print(f"Classical: {perfs['classical'].get('rating', 'N/A')}")
            
            if 'createdAt' in profile:
                created = datetime.fromtimestamp(profile['createdAt'] / 1000)
                print(f"\nAccount Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
            
            print("\n--- FULL PROFILE JSON ---")
            print(json.dumps(profile, indent=2))
            
            return profile
        elif response.status_code == 404:
            print(f"User '{username}' not found")
            return None
        else:
            print(f"Error: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_user_rating_history(username):
    """Get user rating history (public, no auth required)."""
    print(f"\n{'='*80}")
    print(f"RATING HISTORY: {username}")
    print('='*80)
    
    try:
        response = requests.get(f"{BASE_URL}/user/{username}/rating-history", headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            history = response.json()
            
            print("\n--- RATING HISTORY ---")
            for perf_type in history:
                print(f"\n{perf_type['name']}:")
                if perf_type.get('points'):
                    latest = perf_type['points'][-1] if perf_type['points'] else None
                    if latest:
                        date = datetime.fromtimestamp(latest[0] / 1000)
                        rating = latest[1]
                        print(f"  Latest: {rating} (on {date.strftime('%Y-%m-%d')})")
                        print(f"  Total points: {len(perf_type['points'])}")
            
            print("\n--- FULL RATING HISTORY JSON ---")
            print(json.dumps(history, indent=2))
            
            return history
        else:
            print(f"Error: HTTP {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_user_games(username, max_games=5):
    """Get user's recent games (public, no auth required).
    
    Note: This endpoint returns NDJSON (Newline Delimited JSON) format.
    Requires additional parameters like format=json and pgnInJson=true.
    """
    print(f"\n{'='*80}")
    print(f"RECENT GAMES: {username} (max {max_games})")
    print('='*80)
    
    try:
        # Games endpoint requires format parameter and may need pgnInJson
        url = f"{BASE_URL}/games/user/{username}?max={max_games}&format=json&pgnInJson=true"
        response = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        
        if response.status_code == 200:
            games = []
            
            print("\n--- GAMES ---")
            # NDJSON format: one JSON object per line
            for line_num, line in enumerate(response.iter_lines(), 1):
                if line:
                    try:
                        # Decode bytes to string if needed
                        if isinstance(line, bytes):
                            line = line.decode('utf-8')
                        
                        # Skip empty lines
                        line = line.strip()
                        if not line:
                            continue
                        
                        game = json.loads(line)
                        games.append(game)
                        
                        # Display game info
                        white = game.get('players', {}).get('white', {}).get('user', {}).get('name', '?')
                        black = game.get('players', {}).get('black', {}).get('user', {}).get('name', '?')
                        winner = game.get('winner', 'draw')
                        perf = game.get('perf', '?')
                        rated = game.get('rated', False)
                        
                        print(f"\nGame {len(games)}:")
                        print(f"  White: {white}")
                        print(f"  Black: {black}")
                        print(f"  Winner: {winner}")
                        print(f"  Type: {perf} ({'rated' if rated else 'casual'})")
                        print(f"  Game ID: {game.get('id', 'N/A')}")
                        
                        if len(games) >= max_games:
                            break
                    except json.JSONDecodeError as e:
                        # Debug: show first few chars of problematic line
                        line_preview = line[:50] if len(line) > 50 else line
                        print(f"Error parsing game {line_num}: {e}")
                        print(f"  Line preview: {line_preview}")
                        continue
            
            print(f"\n--- Total games retrieved: {len(games)} ---")
            if games:
                print("\n--- FIRST GAME JSON (sample) ---")
                print(json.dumps(games[0], indent=2)[:500] + "...")
            return games
        else:
            print(f"Error: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_authenticated_endpoint(token=None):
    """Test authenticated endpoint (requires personal access token).
    
    This will only work if you provide a valid token.
    """
    if not token:
        print("\n--- SKIPPING AUTHENTICATED TEST ---")
        print("No token provided. To test authenticated endpoints:")
        print("1. Create a token at: https://lichess.org/account/oauth/token/create")
        print("2. Set LICHESS_TOKEN environment variable")
        print("3. Or pass token as parameter")
        return None
    
    print(f"\n{'='*80}")
    print("AUTHENTICATED ENDPOINT TEST")
    print('='*80)
    
    try:
        headers = {
            **HEADERS,
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.get(f"{BASE_URL}/account", headers=headers, timeout=10)
        
        if response.status_code == 200:
            account = response.json()
            print("\n--- ACCOUNT INFO ---")
            print(f"Username: {account.get('username', 'N/A')}")
            print(f"Email: {account.get('email', 'N/A')}")
            print(f"Title: {account.get('title', 'No title')}")
            print("\n--- FULL ACCOUNT JSON ---")
            print(json.dumps(account, indent=2))
            return account
        else:
            print(f"Error: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    import os
    
    # Test with a well-known user (no auth needed)
    test_username = "thibault"  # Lichess founder
    
    print("="*80)
    print("LICHESS API TEST - PUBLIC ENDPOINTS")
    print("="*80)
    
    # Test 1: Get user profile
    profile = get_user_profile(test_username)
    
    # Test 2: Get rating history
    rating_history = get_user_rating_history(test_username)
    
    # Test 3: Get recent games
    games = get_user_games(test_username, max_games=3)
    
    # Test 4: Try authenticated endpoint (if token available)
    token = os.getenv("LICHESS_TOKEN")
    if token:
        test_authenticated_endpoint(token)
    else:
        test_authenticated_endpoint()
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nNote: All tests above used PUBLIC endpoints (no authentication required)")
    print("You can query any user's public data without an account!")

