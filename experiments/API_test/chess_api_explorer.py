"""
Chess.com API Explorer
This script explores the Chess.com API to understand available endpoints and data.
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional

BASE_URL = "https://api.chess.com/pub"

# Headers required by Chess.com API
HEADERS = {
    "User-Agent": "ChessAPI/1.0 (Python Script)"
}


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_json(data: Dict, indent: int = 2):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def get_player_profile(username: str) -> Optional[Dict]:
    """Get player profile information."""
    url = f"{BASE_URL}/player/{username}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching profile: {e}")
        return None


def get_player_stats(username: str) -> Optional[Dict]:
    """Get player statistics."""
    url = f"{BASE_URL}/player/{username}/stats"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching stats: {e}")
        return None


def get_player_game_archives(username: str) -> Optional[Dict]:
    """Get list of game archive URLs for a player."""
    url = f"{BASE_URL}/player/{username}/games/archives"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching game archives: {e}")
        return None


def get_games_from_archive(archive_url: str) -> Optional[Dict]:
    """Get games from a specific archive URL."""
    try:
        response = requests.get(archive_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching games from archive: {e}")
        return None


def get_all_player_games(username: str) -> List[Dict]:
    """Get all games for a player."""
    archives = get_player_game_archives(username)
    if not archives or 'archives' not in archives:
        return []
    
    all_games = []
    archive_urls = archives['archives']
    
    print(f"\nFound {len(archive_urls)} archive(s) to process...")
    
    for archive_url in archive_urls:
        print(f"  Fetching: {archive_url}")
        archive_data = get_games_from_archive(archive_url)
        if archive_data and 'games' in archive_data:
            all_games.extend(archive_data['games'])
    
    return all_games


def explore_user(username: str):
    """Explore all available information for a user."""
    print_section(f"EXPLORING USER: {username}")
    
    # 1. Player Profile
    print_section(f"1. PROFILE INFORMATION - {username}")
    profile = get_player_profile(username)
    if profile:
        print_json(profile)
    else:
        print(f"Could not fetch profile for {username}")
        return
    
    # 2. Player Stats
    print_section(f"2. STATISTICS - {username}")
    stats = get_player_stats(username)
    if stats:
        print_json(stats)
    else:
        print(f"Could not fetch stats for {username}")
    
    # 3. Game Archives
    print_section(f"3. GAME ARCHIVES - {username}")
    archives = get_player_game_archives(username)
    if archives:
        print_json(archives)
        print(f"\nTotal archives: {len(archives.get('archives', []))}")
    else:
        print(f"Could not fetch game archives for {username}")
    
    # 4. All Games
    print_section(f"4. ALL GAMES - {username}")
    all_games = get_all_player_games(username)
    print(f"\nTotal games found: {len(all_games)}")
    
    if all_games:
        print("\nFirst game details:")
        print_json(all_games[0] if len(all_games) > 0 else {})
        
        # Print summary of all games
        print("\n\nGames Summary:")
        print("-" * 80)
        for i, game in enumerate(all_games, 1):
            white = game.get('white', {}).get('username', 'Unknown')
            black = game.get('black', {}).get('username', 'Unknown')
            result = game.get('white', {}).get('result', '?')
            time_control = game.get('time_control', '?')
            time_class = game.get('time_class', '?')
            end_time = game.get('end_time', '?')
            
            print(f"Game {i}:")
            print(f"  White: {white}")
            print(f"  Black: {black}")
            print(f"  Result: {result}")
            print(f"  Time Control: {time_control}")
            print(f"  Time Class: {time_class}")
            print(f"  End Time: {end_time}")
            print()


def main():
    """Main function to explore multiple users."""
    users = ["YevgenChess", "nipunjani"]
    
    for user in users:
        explore_user(user)
        print("\n\n")


if __name__ == "__main__":
    main()

