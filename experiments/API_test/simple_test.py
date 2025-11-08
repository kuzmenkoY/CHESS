"""
Simple Chess.com API Test
A simple script to get basic user information and stats.
"""

import requests
import json

BASE_URL = "https://api.chess.com/pub"

# Headers required by Chess.com API
HEADERS = {
    "User-Agent": "ChessAPI/1.0 (Python Script)"
}

def get_user_info(username):
    """Get all available info for a user."""
    print(f"\n{'='*80}")
    print(f"USER: {username}")
    print('='*80)
    
    # 1. Profile
    print("\n--- PROFILE ---")
    try:
        response = requests.get(f"{BASE_URL}/player/{username}", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            profile = response.json()
            print(json.dumps(profile, indent=2))
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 2. Stats
    print("\n--- STATS ---")
    try:
        response = requests.get(f"{BASE_URL}/player/{username}/stats", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print(json.dumps(stats, indent=2))
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    
    # 3. Game Archives
    print("\n--- GAME ARCHIVES ---")
    try:
        response = requests.get(f"{BASE_URL}/player/{username}/games/archives", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            archives = response.json()
            print(json.dumps(archives, indent=2))
            
            # Get games from each archive
            if 'archives' in archives:
                print(f"\n--- GAMES FROM ARCHIVES ({len(archives['archives'])} archives) ---")
                for archive_url in archives['archives']:
                    print(f"\nFetching: {archive_url}")
                    try:
                        games_response = requests.get(archive_url, headers=HEADERS, timeout=10)
                        if games_response.status_code == 200:
                            games_data = games_response.json()
                            if 'games' in games_data:
                                print(f"  Found {len(games_data['games'])} games")
                                for i, game in enumerate(games_data['games'], 1):
                                    white = game.get('white', {}).get('username', '?')
                                    black = game.get('black', {}).get('username', '?')
                                    result = game.get('white', {}).get('result', '?')
                                    print(f"\n  Game {i}: {white} vs {black} - Result: {result}")
                                    
                                    # Print complete game data
                                    print(f"\n  --- COMPLETE GAME DATA {i} ---")
                                    print(json.dumps(game, indent=4))
                                    
                                    # Also print PGN separately for readability
                                    if 'pgn' in game:
                                        print(f"\n  --- PGN FOR GAME {i} ---")
                                        print(game['pgn'])
                        else:
                            print(f"  Error: {games_response.status_code}")
                    except Exception as e:
                        print(f"  Error fetching games: {e}")
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test with YevgenChess
    get_user_info("YevgenChess")
    
    # # Test with nipunjani
    # get_user_info("nipunjani")

