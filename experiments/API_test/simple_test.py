"""
Simple Chess.com API Test
Get latest stats and download the most recent game for a user.
"""

import requests
import json
import os
from datetime import datetime

BASE_URL = "https://api.chess.com/pub"

# Headers required by Chess.com API
HEADERS = {
    "User-Agent": "ChessAPI/1.0 (Python Script)"
}

def get_latest_stats(username):
    """Get the latest stats for a user."""
    print(f"\n{'='*80}")
    print(f"LATEST STATS FOR: {username}")
    print('='*80)
    
    try:
        response = requests.get(f"{BASE_URL}/player/{username}/stats", headers=HEADERS, timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print("\n--- CURRENT RATINGS ---")
            
            # Display ratings in a readable format
            if 'chess_rapid' in stats:
                rapid = stats['chess_rapid']
                print(f"Rapid: {rapid.get('last', {}).get('rating', 'N/A')}")
            
            if 'chess_blitz' in stats:
                blitz = stats['chess_blitz']
                print(f"Blitz: {blitz.get('last', {}).get('rating', 'N/A')}")
            
            if 'chess_bullet' in stats:
                bullet = stats['chess_bullet']
                print(f"Bullet: {bullet.get('last', {}).get('rating', 'N/A')}")
            
            if 'chess_daily' in stats:
                daily = stats['chess_daily']
                print(f"Daily: {daily.get('last', {}).get('rating', 'N/A')}")
            
            print("\n--- FULL STATS JSON ---")
            print(json.dumps(stats, indent=2))
            
            return stats
        else:
            print(f"Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def download_latest_game(username):
    """Download the most recent game for a user."""
    print(f"\n{'='*80}")
    print(f"DOWNLOADING LATEST GAME FOR: {username}")
    print('='*80)
    
    try:
        # Get list of archives
        response = requests.get(f"{BASE_URL}/player/{username}/games/archives", headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"Error fetching archives: {response.status_code}")
            return None
        
        archives = response.json()
        
        if 'archives' not in archives or not archives['archives']:
            print("No game archives found.")
            return None
        
        # Get the most recent archive (last in the list)
        latest_archive_url = archives['archives'][-1]
        print(f"\nFetching latest archive: {latest_archive_url}")
        
        # Get games from the latest archive
        games_response = requests.get(latest_archive_url, headers=HEADERS, timeout=10)
        if games_response.status_code != 200:
            print(f"Error fetching games: {games_response.status_code}")
            return None
        
        games_data = games_response.json()
        
        if 'games' not in games_data or not games_data['games']:
            print("No games found in latest archive.")
            return None
        
        # Get the most recent game (last in the list)
        latest_game = games_data['games'][-1]
        
        # Display game info
        white = latest_game.get('white', {}).get('username', '?')
        black = latest_game.get('black', {}).get('username', '?')
        white_result = latest_game.get('white', {}).get('result', '?')
        end_time = latest_game.get('end_time', '?')
        time_control = latest_game.get('time_control', '?')
        time_class = latest_game.get('time_class', '?')
        
        print("\n--- LATEST GAME INFO ---")
        print(f"White: {white}")
        print(f"Black: {black}")
        print(f"Result: {white_result}")
        print(f"Time Control: {time_control}")
        print(f"Time Class: {time_class}")
        print(f"End Time: {end_time}")
        
        # Save game data to files
        output_dir = "downloaded_games"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = os.path.join(output_dir, f"{username}_latest_game_{timestamp}.json")
        pgn_filename = os.path.join(output_dir, f"{username}_latest_game_{timestamp}.pgn")
        
        # Save JSON
        with open(json_filename, 'w') as f:
            json.dump(latest_game, f, indent=2)
        print(f"\n✓ Saved game data to: {json_filename}")
        
        # Save PGN if available
        if 'pgn' in latest_game:
            with open(pgn_filename, 'w') as f:
                f.write(latest_game['pgn'])
            print(f"✓ Saved PGN to: {pgn_filename}")
            
            print("\n--- PGN PREVIEW ---")
            print(latest_game['pgn'][:500] + "..." if len(latest_game['pgn']) > 500 else latest_game['pgn'])
        
        print("\n--- FULL GAME DATA ---")
        print(json.dumps(latest_game, indent=2))
        
        return latest_game
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    username = "yevgenchess"
    
    # Get latest stats
    stats = get_latest_stats(username)
    
    # Download latest game
    game = download_latest_game(username)

