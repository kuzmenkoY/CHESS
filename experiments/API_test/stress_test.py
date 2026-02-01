#!/usr/bin/env python3
"""
Stress test Chess.com player stats and latest-game endpoints.
Supports multi-user runs with configurable concurrency, CSV input, and CSV
logging so we can see how quickly responses change and when throttling happens.
User-Agent comes from CHESS_USER_AGENT env (Chess.com requires a contact string).
"""

import argparse
import csv
import hashlib
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

BASE_URL = "https://api.chess.com/pub"
USER_AGENT = "CHESS-Data/1.0 (contact@example.com)"
HEADERS = {"User-Agent": USER_AGENT}


class SessionPool:
    """
    Simple session pool to reuse TLS connections and reduce handshake churn.
    Each checkout gives exclusive use of a Session; pool size should be
    <= concurrency to avoid waiting.
    """

    def __init__(self, size: int, max_connections: int):
        self._queue: "Queue[requests.Session]" = Queue()
        adapter = HTTPAdapter(pool_connections=max_connections, pool_maxsize=max_connections)
        for _ in range(size):
            s = requests.Session()
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            self._queue.put(s)

    @contextmanager
    def get(self) -> requests.Session:
        sess = self._queue.get()
        try:
            yield sess
        finally:
            self._queue.put(sess)


def timed_get(
    url: str,
    session: Optional[requests.Session],
    timeout: float,
) -> Tuple[requests.Response, float]:
    """Perform a GET with timing (ms)."""
    start = time.perf_counter()
    client = session or requests
    response = client.get(url, headers=HEADERS, timeout=timeout)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return response, round(elapsed_ms, 1)


def hash_json(payload: Any) -> Optional[str]:
    try:
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    except Exception:
        return None


def format_ts(ts: Optional[int]) -> str:
    if not ts:
        return "?"
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def fetch_latest_game(
    username: str,
    session: Optional[requests.Session],
    timeout: float,
) -> Tuple[Optional[Dict[str, Any]], float, str, Optional[str], int]:
    """
    Fetch most recent game via archives endpoint.
    Returns (game_payload, elapsed_ms_total, archive_url, retry_after).
    """
    archive_url = f"{BASE_URL}/player/{username}/games/archives"
    archive_resp, archive_ms = timed_get(archive_url, session=session, timeout=timeout)
    retry_after = archive_resp.headers.get("Retry-After")
    if archive_resp.status_code != 200:
        return None, archive_ms, archive_url, retry_after, archive_resp.status_code

    archives = archive_resp.json().get("archives") or []
    if not archives:
        return None, archive_ms, archive_url, retry_after, 200

    latest_archive_url = archives[-1]
    games_resp, games_ms = timed_get(latest_archive_url, session=session, timeout=timeout)
    retry_after = retry_after or games_resp.headers.get("Retry-After")
    if games_resp.status_code != 200:
        return None, archive_ms + games_ms, latest_archive_url, retry_after, games_resp.status_code

    games = games_resp.json().get("games") or []
    if not games:
        return None, archive_ms + games_ms, latest_archive_url, retry_after, 200

    return games[-1], archive_ms + games_ms, latest_archive_url, retry_after, 200


def run_stats_once(
    username: str,
    iteration: int,
    prev_hash: Optional[str],
    session: Optional[requests.Session],
    timeout: float,
) -> Tuple[Dict[str, Any], Optional[str]]:
    url = f"{BASE_URL}/player/{username}/stats"
    resp, elapsed_ms = timed_get(url, session=session, timeout=timeout)
    retry_after = resp.headers.get("Retry-After")
    entry: Dict[str, Any] = {
        "endpoint": "stats",
        "iteration": iteration,
        "status": resp.status_code,
        "elapsed_ms": elapsed_ms,
        "etag": resp.headers.get("ETag"),
        "last_modified": resp.headers.get("Last-Modified"),
        "retry_after": retry_after,
    }

    if resp.status_code == 200:
        payload = resp.json()
        payload_hash = hash_json(payload)
        entry["hash"] = payload_hash
        entry["changed"] = payload_hash is not None and payload_hash != prev_hash
        entry["blitz_rating"] = (
            payload.get("chess_blitz", {})
            .get("last", {})
            .get("rating")
        )
        prev_hash = payload_hash or prev_hash
    else:
        entry["error"] = resp.text[:300]

    return entry, prev_hash


def run_game_once(
    username: str,
    iteration: int,
    prev_hash: Optional[str],
    session: Optional[requests.Session],
    timeout: float,
) -> Tuple[Dict[str, Any], Optional[str]]:
    game, elapsed_ms, archive_url, retry_after, status_code = fetch_latest_game(
        username, session=session, timeout=timeout
    )
    entry: Dict[str, Any] = {
        "endpoint": "latest_game",
        "iteration": iteration,
        "elapsed_ms": elapsed_ms,
        "archive_url": archive_url,
        "retry_after": retry_after,
        "status": status_code,
    }

    if game:
        payload_hash = hash_json(game)
        entry.update(
            {
                "hash": payload_hash,
                "changed": payload_hash is not None and payload_hash != prev_hash,
                "end_time": game.get("end_time"),
                "time_class": game.get("time_class"),
                "url": game.get("url"),
            }
        )
        prev_hash = payload_hash or prev_hash
    else:
        entry["error"] = f"non-200 from archive/games: {status_code}" if status_code and status_code != 200 else "no games found"

    return entry, prev_hash


def poll_user_once(
    username: str,
    iteration_number: int,
    stats_prev_hash: Optional[str],
    game_prev_hash: Optional[str],
    session_pool: SessionPool,
    include_stats: bool,
    include_games: bool,
    respect_retry_after: bool,
    timeout: float,
) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    records: List[Dict[str, Any]] = []
    with session_pool.get() as session:
        ts = datetime.now(timezone.utc).isoformat()

        if include_stats:
            stats_entry, stats_prev_hash = run_stats_once(
                username, iteration_number, stats_prev_hash, session, timeout
            )
            stats_entry.update({"timestamp": ts, "username": username})
            records.append(stats_entry)

            if respect_retry_after and stats_entry.get("status") == 429:
                retry_after = stats_entry.get("retry_after")
                if retry_after:
                    time.sleep(float(retry_after))

        if include_games:
            game_entry, game_prev_hash = run_game_once(
                username, iteration_number, game_prev_hash, session, timeout
            )
            game_entry.update({"timestamp": datetime.now(timezone.utc).isoformat(), "username": username})
            records.append(game_entry)

            if respect_retry_after and game_entry.get("status") == 429:
                retry_after = game_entry.get("retry_after")
                if retry_after:
                    time.sleep(float(retry_after))

    return records, stats_prev_hash, game_prev_hash


def load_usernames(csv_path: Path, column: str, limit: Optional[int]) -> List[str]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [row[column].strip() for row in reader if row.get(column)]
    if limit:
        rows = rows[:limit]
    return rows


def write_csv(output_path: Path, rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "run_id",
        "timestamp",
        "username",
        "endpoint",
        "iteration",
        "status",
        "elapsed_ms",
        "etag",
        "last_modified",
        "hash",
        "changed",
        "retry_after",
        "blitz_rating",
        "end_time",
        "time_class",
        "url",
        "archive_url",
        "error",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: List[Dict[str, Any]]) -> None:
    total = len(rows)
    status_counts: Dict[str, int] = {}
    for row in rows:
        key = str(row.get("status"))
        status_counts[key] = status_counts.get(key, 0) + 1
    print(f"\nLogged {total} requests")
    for status, count in sorted(status_counts.items()):
        print(f"  status {status}: {count}")


def main() -> None:
    start_wall = time.time()
    parser = argparse.ArgumentParser(
        description="Stress test Chess.com stats and latest-game endpoints (multi-user capable)."
    )
    parser.add_argument(
        "username",
        nargs="?",
        default="yevgenchess",
        help="Single username (ignored if --users-csv is provided).",
    )
    parser.add_argument(
        "--users-csv",
        type=str,
        help="Path to CSV containing usernames.",
    )
    parser.add_argument(
        "--username-column",
        type=str,
        default="username",
        help="Column name in the CSV that holds the username values.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Max users to load from CSV (for quick probes).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="How many times to hit each endpoint per user.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to sleep between iterations for the same user.",
    )
    parser.add_argument(
        "--jitter",
        type=float,
        default=0.0,
        help="Random extra seconds (0..jitter) added to --sleep.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Max concurrent users (threads).",
    )
    parser.add_argument(
        "--skip-games",
        action="store_true",
        help="Skip polling the latest game (archives) endpoint.",
    )
    parser.add_argument(
        "--games-only",
        action="store_true",
        help="Only hit latest game (archives) endpoint; skip stats.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--session-pool-size",
        type=int,
        default=50,
        help="How many Sessions to keep in the pool (<= concurrency is fine).",
    )
    parser.add_argument(
        "--session-pool-connections",
        type=int,
        default=200,
        help="Max connections per Session adapter (pool_connections/pool_maxsize).",
    )
    parser.add_argument(
        "--respect-retry-after",
        action="store_true",
        help="If 429 and Retry-After are returned, sleep accordingly.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="CSV output path. Default: experiments/API_test/logs/stress_<timestamp>.csv",
    )
    args = parser.parse_args()

    if args.users_csv:
        usernames = load_usernames(Path(args.users_csv), args.username_column, args.limit)
    else:
        usernames = [args.username]

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    default_output = Path("experiments/API_test/logs") / f"stress_{run_id}.csv"
    output_path = Path(args.output) if args.output else default_output
    if output_path.exists() and output_path.is_dir():
        output_path = output_path / f"stress_{run_id}.csv"
    elif str(output_path).endswith("/"):
        output_path = output_path / f"stress_{run_id}.csv"
    elif output_path.suffix == "":
        # Treat as directory path if no suffix and path ends with a slash-like token
        potential = output_path
        if potential.name == "" or potential.name.endswith("/"):
            output_path = potential / f"stress_{run_id}.csv"

    print("Chess.com stress test")
    print(f"Using User-Agent: {USER_AGENT}")
    print(f"Users: {len(usernames)} | iterations={args.iterations} | concurrency={args.concurrency} | timeout={args.timeout}s")
    print(f"Logging to: {output_path}")

    all_rows: List[Dict[str, Any]] = []
    stats_hashes: Dict[str, Optional[str]] = {}
    game_hashes: Dict[str, Optional[str]] = {}

    session_pool = SessionPool(
        size=max(1, args.session_pool_size),
        max_connections=max(10, args.session_pool_connections),
    )

    for iteration_number in range(1, args.iterations + 1):
        print(f"\nIteration {iteration_number}/{args.iterations}")

        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {
                executor.submit(
                    poll_user_once,
                    username,
                    iteration_number,
                    stats_hashes.get(username),
                    game_hashes.get(username),
                    session_pool,
                    not args.games_only,
                    not args.skip_games,
                    args.respect_retry_after,
                    args.timeout,
                ): username
                for username in usernames
            }
            for future in as_completed(futures):
                username = futures[future]
                try:
                    user_rows, new_stats_hash, new_game_hash = future.result()
                    stats_hashes[username] = new_stats_hash
                    game_hashes[username] = new_game_hash
                    for row in user_rows:
                        row["run_id"] = run_id
                    all_rows.extend(user_rows)
                except Exception as exc:  # pragma: no cover - defensive
                    all_rows.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "username": username,
                            "endpoint": "error",
                            "iteration": iteration_number,
                            "status": "exception",
                            "error": str(exc),
                            "run_id": run_id,
                        }
                    )

    write_csv(output_path, all_rows)
    summarize(all_rows)
    end_wall = time.time()
    wall = end_wall - start_wall
    rps = (len(all_rows) / wall) if wall > 0 else 0.0
    print(f"Total wall time: {wall:.1f}s | Requests/sec: {rps:.2f}")


if __name__ == "__main__":
    main()
