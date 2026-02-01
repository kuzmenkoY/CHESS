"""
Chess.com ingestion worker.

The worker pulls jobs from `ingestion_jobs`, calls the public Chess.com API, and
persists results into Supabase/PostgreSQL.  Job types:
  - profile: refreshes /player/{username}
  - stats: refreshes /player/{username}/stats
  - archives: refreshes /player/{username}/games/archives
  - games: fetches an archive URL and stores finished games

Usage examples:
    # enqueue seed jobs for one or more usernames
    python ingestion/worker.py enqueue --username YevgenChess

    # process a single job (useful for cron)
    python ingestion/worker.py run --once

    # run continuously with polling
    python ingestion/worker.py run --loop
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, Iterable, Optional, Tuple

import requests

from db.db_connection import get_db_connection

BASE_URL = os.getenv("CHESS_API_BASE_URL", "https://api.chess.com/pub")
USER_AGENT = os.getenv("CHESS_API_USER_AGENT", "ChessPipeline/0.1 (contact@example.com)")
REQUEST_TIMEOUT = int(os.getenv("CHESS_API_TIMEOUT", "15"))
PROFILE_REFRESH_SECONDS = int(os.getenv("PROFILE_REFRESH_SECONDS", str(6 * 3600)))
STATS_REFRESH_SECONDS = int(os.getenv("STATS_REFRESH_SECONDS", str(2 * 3600)))
ARCHIVE_REFRESH_SECONDS = int(os.getenv("ARCHIVE_REFRESH_SECONDS", str(12 * 3600)))
ARCHIVE_MONTH_LIMIT = int(os.getenv("ARCHIVE_MONTH_LIMIT", "12"))  # 0 = unlimited
JOB_POLL_INTERVAL = int(os.getenv("INGESTION_POLL_SECONDS", "5"))
MAX_ARCHIVE_JOB_PRIORITY = int(os.getenv("ARCHIVE_JOB_PRIORITY", "5"))

LICHESS_BASE_URL = os.getenv("LICHESS_API_BASE_URL", "https://lichess.org/api")
LICHESS_USER_AGENT = os.getenv("LICHESS_API_USER_AGENT", "ChessPipeline/0.1 (contact@example.com)")
LICHESS_REQUEST_TIMEOUT = int(os.getenv("LICHESS_API_TIMEOUT", "15"))
LICHESS_PROFILE_REFRESH_SECONDS = int(os.getenv("LICHESS_PROFILE_REFRESH_SECONDS", "60"))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("ingestion.worker")


def utc_now_seconds() -> int:
    return int(time.time())


def utc_now_ms() -> int:
    return int(time.time() * 1000)


def lower_username(username: Optional[str]) -> Optional[str]:
    return username.lower() if isinstance(username, str) else None


class ChessAPIClient:
    """Lightweight wrapper around requests.Session."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }
        )

    def fetch_json(
        self, url: str, extra_headers: Optional[Dict[str, str]] = None
    ) -> Tuple[int, Optional[Dict[str, Any]], Dict[str, str]]:
        headers = extra_headers or {}
        try:
            response = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            LOGGER.error("Request failed for %s: %s", url, exc)
            raise

        data: Optional[Dict[str, Any]] = None
        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                LOGGER.error("Invalid JSON from %s", url)
                raise

        return response.status_code, data, response.headers

    def fetch_profile(self, username: str) -> Dict[str, Any]:
        url = f"{BASE_URL}/player/{username}"
        status, data, headers = self.fetch_json(url)
        log_fetch(url, status, headers if headers else {})
        if status == 200 and data:
            return data
        raise ValueError(f"Profile fetch failed for {username}: HTTP {status}")

    def fetch_stats(self, username: str) -> Dict[str, Any]:
        url = f"{BASE_URL}/player/{username}/stats"
        status, data, headers = self.fetch_json(url)
        log_fetch(url, status, headers if headers else {})
        if status == 200 and data:
            return data
        raise ValueError(f"Stats fetch failed for {username}: HTTP {status}")

    def fetch_archives(self, username: str) -> Iterable[str]:
        url = f"{BASE_URL}/player/{username}/games/archives"
        status, data, headers = self.fetch_json(url)
        log_fetch(url, status, headers if headers else {})
        if status == 200 and data and "archives" in data:
            return data["archives"]
        raise ValueError(f"Archives fetch failed for {username}: HTTP {status}")

    def fetch_archive_games(self, archive_url: str) -> Dict[str, Any]:
        status, data, headers = self.fetch_json(archive_url)
        log_fetch(archive_url, status, headers if headers else {})
        if status == 200 and data:
            return data
        raise ValueError(f"Archive fetch failed: {archive_url} HTTP {status}")


class LichessAPIClient:
    """Lightweight wrapper for Lichess public API."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": LICHESS_USER_AGENT,
                "Accept": "application/json",
            }
        )

    def fetch_user(self, username: str) -> Dict[str, Any]:
        """Fetch profile + stats in one call. Returns the full JSON response."""
        url = f"{LICHESS_BASE_URL}/user/{username}"
        try:
            response = self.session.get(url, timeout=LICHESS_REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            LOGGER.error("Lichess request failed for %s: %s", url, exc)
            raise

        log_fetch(url, response.status_code, dict(response.headers))

        if response.status_code == 200:
            return response.json()
        raise ValueError(f"Lichess profile fetch failed for {username}: HTTP {response.status_code}")


def log_fetch(
    url: str,
    status_code: int,
    headers: Dict[str, str],
    error: Optional[str] = None,
) -> None:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fetch_log (url, etag, last_modified, status_code, fetched_at, error)
            VALUES (%s, %s, %s, %s, EXTRACT(EPOCH FROM NOW())::BIGINT, %s)
            """,
            (
                url,
                headers.get("ETag"),
                headers.get("Last-Modified"),
                status_code,
                error,
            ),
        )


def upsert_player(conn, profile: Dict[str, Any]) -> int:
    username = lower_username(profile.get("username"))
    chesscom_player_id = profile.get("player_id")
    if not username or not chesscom_player_id:
        raise ValueError("Profile missing username or player_id")

    country_url = profile.get("country")
    country_code = None
    if isinstance(country_url, str) and "/" in country_url:
        country_code = country_url.rsplit("/", 1)[-1]
        if country_code:
            country_code = country_code.upper()

    twitch_url = None
    streaming_platforms = profile.get("streaming_platforms") or []
    if isinstance(streaming_platforms, list):
        for item in streaming_platforms:
            if isinstance(item, dict) and item.get("platform", "").lower() == "twitch":
                twitch_url = item.get("url")
                break

    now_ts = utc_now_seconds()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO players (
                chesscom_player_id, username, display_username, name, title, status, league,
                country_url, country_code, avatar, twitch_url, followers, joined, last_online,
                is_streamer, verified, created_at, updated_at
            )
            VALUES (
                %(player_id)s, %(username)s, %(display_username)s, %(name)s, %(title)s,
                %(status)s, %(league)s, %(country_url)s, %(country_code)s, %(avatar)s,
                %(twitch_url)s, %(followers)s, %(joined)s, %(last_online)s,
                %(is_streamer)s, %(verified)s, COALESCE(%(created_at)s, %(now)s), %(now)s
            )
            ON CONFLICT (chesscom_player_id) DO UPDATE SET
                username = EXCLUDED.username,
                display_username = COALESCE(EXCLUDED.display_username, players.display_username),
                name = EXCLUDED.name,
                title = EXCLUDED.title,
                status = EXCLUDED.status,
                league = EXCLUDED.league,
                country_url = EXCLUDED.country_url,
                country_code = EXCLUDED.country_code,
                avatar = COALESCE(EXCLUDED.avatar, players.avatar),
                twitch_url = COALESCE(EXCLUDED.twitch_url, players.twitch_url),
                followers = EXCLUDED.followers,
                joined = COALESCE(EXCLUDED.joined, players.joined),
                last_online = EXCLUDED.last_online,
                is_streamer = EXCLUDED.is_streamer,
                verified = EXCLUDED.verified,
                updated_at = EXCLUDED.updated_at
            RETURNING id
            """,
            {
                "player_id": chesscom_player_id,
                "username": username,
                "display_username": profile.get("username"),
                "name": profile.get("name"),
                "title": profile.get("title"),
                "status": profile.get("status"),
                "league": profile.get("league"),
                "country_url": country_url,
                "country_code": country_code,
                "avatar": profile.get("avatar"),
                "twitch_url": twitch_url or profile.get("twitch_url"),
                "followers": profile.get("followers"),
                "joined": profile.get("joined"),
                "last_online": profile.get("last_online"),
                "is_streamer": profile.get("is_streamer", False),
                "verified": profile.get("verified", False),
                "created_at": profile.get("created_at"),
                "now": now_ts,
            },
        )
        player_id = cur.fetchone()["id"]

    return player_id


def upsert_player_ingestion_state(
    conn,
    player_id: int,
    *,
    profile_touch: bool = False,
    stats_touch: bool = False,
    archives_touch: bool = False,
    status: str = "idle",
    error: Optional[str] = None,
) -> None:
    now_ts = utc_now_seconds()
    updates = {
        "last_profile_fetch": now_ts if profile_touch else None,
        "next_profile_fetch": now_ts + PROFILE_REFRESH_SECONDS if profile_touch else None,
        "last_stats_fetch": now_ts if stats_touch else None,
        "next_stats_fetch": now_ts + STATS_REFRESH_SECONDS if stats_touch else None,
        "last_archives_scan": now_ts if archives_touch else None,
        "next_archives_scan": now_ts + ARCHIVE_REFRESH_SECONDS if archives_touch else None,
        "status": status,
        "error": error,
        "player_id": player_id,
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO player_ingestion_state (
                player_id, last_profile_fetch, next_profile_fetch,
                last_stats_fetch, next_stats_fetch,
                last_archives_scan, next_archives_scan, status, error, updated_at
            )
            VALUES (
                %(player_id)s, %(last_profile_fetch)s, %(next_profile_fetch)s,
                %(last_stats_fetch)s, %(next_stats_fetch)s,
                %(last_archives_scan)s, %(next_archives_scan)s,
                %(status)s, %(error)s, %(now)s
            )
            ON CONFLICT (player_id) DO UPDATE SET
                last_profile_fetch = COALESCE(EXCLUDED.last_profile_fetch, player_ingestion_state.last_profile_fetch),
                next_profile_fetch = COALESCE(EXCLUDED.next_profile_fetch, player_ingestion_state.next_profile_fetch),
                last_stats_fetch = COALESCE(EXCLUDED.last_stats_fetch, player_ingestion_state.last_stats_fetch),
                next_stats_fetch = COALESCE(EXCLUDED.next_stats_fetch, player_ingestion_state.next_stats_fetch),
                last_archives_scan = COALESCE(EXCLUDED.last_archives_scan, player_ingestion_state.last_archives_scan),
                next_archives_scan = COALESCE(EXCLUDED.next_archives_scan, player_ingestion_state.next_archives_scan),
                status = EXCLUDED.status,
                error = EXCLUDED.error,
                updated_at = EXCLUDED.updated_at
            """,
            {**updates, "now": now_ts},
        )


def upsert_player_stats(conn, player_id: int, stats_payload: Dict[str, Any]) -> None:
    now_ts = utc_now_seconds()
    for key, payload in stats_payload.items():
        if not key.startswith("chess"):
            continue

        time_class = key.split("_")[-1]
        rules = "chess960" if "960" in key else "chess"
        last = payload.get("last") or {}
        best = payload.get("best") or {}
        record = payload.get("record") or {}
        cur_payload = {
            "player_id": player_id,
            "rules": rules,
            "time_class": time_class,
            "last_rating": last.get("rating"),
            "last_rating_date": last.get("date"),
            "last_rd": last.get("rd"),
            "best_rating": best.get("rating"),
            "best_date": best.get("date"),
            "best_game_url": best.get("game"),
            "record_win": record.get("win"),
            "record_loss": record.get("loss"),
            "record_draw": record.get("draw"),
            "time_per_move": payload.get("time_per_move"),
            "timeout_percent": payload.get("timeout_percent"),
            "now": now_ts,
        }
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO player_stats (
                    player_id, rules, time_class,
                    last_rating, last_rating_date, last_rd,
                    best_rating, best_date, best_game_url,
                    record_win, record_loss, record_draw,
                    time_per_move, timeout_percent, created_at, updated_at
                )
                VALUES (
                    %(player_id)s, %(rules)s, %(time_class)s,
                    %(last_rating)s, %(last_rating_date)s, %(last_rd)s,
                    %(best_rating)s, %(best_date)s, %(best_game_url)s,
                    %(record_win)s, %(record_loss)s, %(record_draw)s,
                    %(time_per_move)s, %(timeout_percent)s, %(now)s, %(now)s
                )
                ON CONFLICT (player_id, rules, time_class) DO UPDATE SET
                    last_rating = EXCLUDED.last_rating,
                    last_rating_date = EXCLUDED.last_rating_date,
                    last_rd = EXCLUDED.last_rd,
                    best_rating = EXCLUDED.best_rating,
                    best_date = EXCLUDED.best_date,
                    best_game_url = EXCLUDED.best_game_url,
                    record_win = EXCLUDED.record_win,
                    record_loss = EXCLUDED.record_loss,
                    record_draw = EXCLUDED.record_draw,
                    time_per_move = EXCLUDED.time_per_move,
                    timeout_percent = EXCLUDED.timeout_percent,
                    updated_at = EXCLUDED.updated_at
                """,
                cur_payload,
            )

    tactics = stats_payload.get("tactics")
    if tactics:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO player_tactics_stats (
                    player_id, highest_rating, highest_date, lowest_rating, lowest_date, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id) DO UPDATE SET
                    highest_rating = EXCLUDED.highest_rating,
                    highest_date = EXCLUDED.highest_date,
                    lowest_rating = EXCLUDED.lowest_rating,
                    lowest_date = EXCLUDED.lowest_date,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    player_id,
                    (tactics.get("highest") or {}).get("rating"),
                    (tactics.get("highest") or {}).get("date"),
                    (tactics.get("lowest") or {}).get("rating"),
                    (tactics.get("lowest") or {}).get("date"),
                    now_ts,
                ),
            )

    lessons = stats_payload.get("lessons")
    if lessons:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO player_lessons_stats (
                    player_id, highest_rating, highest_date, lowest_rating, lowest_date, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (player_id) DO UPDATE SET
                    highest_rating = EXCLUDED.highest_rating,
                    highest_date = EXCLUDED.highest_date,
                    lowest_rating = EXCLUDED.lowest_rating,
                    lowest_date = EXCLUDED.lowest_date,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    player_id,
                    (lessons.get("highest") or {}).get("rating"),
                    (lessons.get("highest") or {}).get("date"),
                    (lessons.get("lowest") or {}).get("rating"),
                    (lessons.get("lowest") or {}).get("date"),
                    now_ts,
                ),
            )

    puzzle_rush = stats_payload.get("puzzle_rush")
    if puzzle_rush:
        best = puzzle_rush.get("best") or {}
        daily = puzzle_rush.get("daily") or {}
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO player_puzzle_rush_best (
                    player_id, total_attempts, score, updated_at
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (player_id) DO UPDATE SET
                    total_attempts = EXCLUDED.total_attempts,
                    score = EXCLUDED.score,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    player_id,
                    best.get("total_attempts"),
                    best.get("score"),
                    now_ts,
                ),
            )
            cur.execute(
                """
                INSERT INTO player_puzzle_rush_daily (
                    player_id, total_attempts, score, updated_at
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (player_id) DO UPDATE SET
                    total_attempts = EXCLUDED.total_attempts,
                    score = EXCLUDED.score,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    player_id,
                    daily.get("total_attempts"),
                    daily.get("score"),
                    now_ts,
                ),
            )


def upsert_lichess_player(conn, data: Dict[str, Any]) -> int:
    username = data.get("id", "").lower()
    if not username:
        raise ValueError("Lichess profile missing 'id' field")

    play_time = data.get("playTime") or {}
    now_ms = utc_now_ms()

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO lichess_players (
                username, display_username, title, patron,
                tos_violation, disabled, verified,
                created_at, seen_at, play_time_total,
                url, bio, country, flair, ingested_at
            )
            VALUES (
                %(username)s, %(display_username)s, %(title)s, %(patron)s,
                %(tos_violation)s, %(disabled)s, %(verified)s,
                %(created_at)s, %(seen_at)s, %(play_time_total)s,
                %(url)s, %(bio)s, %(country)s, %(flair)s, %(now_ms)s
            )
            ON CONFLICT (username) DO UPDATE SET
                display_username = EXCLUDED.display_username,
                title = EXCLUDED.title,
                patron = EXCLUDED.patron,
                tos_violation = EXCLUDED.tos_violation,
                disabled = EXCLUDED.disabled,
                verified = EXCLUDED.verified,
                seen_at = EXCLUDED.seen_at,
                play_time_total = EXCLUDED.play_time_total,
                url = EXCLUDED.url,
                bio = EXCLUDED.bio,
                country = EXCLUDED.country,
                flair = EXCLUDED.flair,
                ingested_at = EXCLUDED.ingested_at
            RETURNING id
            """,
            {
                "username": username,
                "display_username": data.get("username"),
                "title": data.get("title"),
                "patron": data.get("patron", False),
                "tos_violation": data.get("tosViolation", False),
                "disabled": data.get("disabled", False),
                "verified": data.get("verified", False),
                "created_at": data.get("createdAt"),
                "seen_at": data.get("seenAt"),
                "play_time_total": play_time.get("total"),
                "url": data.get("url"),
                "bio": data.get("profile", {}).get("bio") if isinstance(data.get("profile"), dict) else None,
                "country": data.get("profile", {}).get("country") if isinstance(data.get("profile"), dict) else None,
                "flair": data.get("flair"),
                "now_ms": now_ms,
            },
        )
        return cur.fetchone()["id"]


def upsert_lichess_player_stats(conn, player_id: int, perfs: Dict[str, Any]) -> None:
    now_ms = utc_now_ms()
    for perf_name, perf_data in perfs.items():
        if not isinstance(perf_data, dict) or "rating" not in perf_data:
            continue
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lichess_player_stats (
                    player_id, perf, rating, rd, prog, games, prov, fetched_at
                )
                VALUES (%(player_id)s, %(perf)s, %(rating)s, %(rd)s, %(prog)s, %(games)s, %(prov)s, %(fetched_at)s)
                ON CONFLICT (player_id, perf) DO UPDATE SET
                    rating = EXCLUDED.rating,
                    rd = EXCLUDED.rd,
                    prog = EXCLUDED.prog,
                    games = EXCLUDED.games,
                    prov = EXCLUDED.prov,
                    fetched_at = EXCLUDED.fetched_at
                """,
                {
                    "player_id": player_id,
                    "perf": perf_name,
                    "rating": perf_data.get("rating"),
                    "rd": perf_data.get("rd"),
                    "prog": perf_data.get("prog"),
                    "games": perf_data.get("games"),
                    "prov": perf_data.get("prov", False),
                    "fetched_at": now_ms,
                },
            )


def upsert_lichess_ingestion_state(
    conn,
    player_id: int,
    *,
    profile_touch: bool = False,
    status: str = "idle",
    error: Optional[str] = None,
) -> None:
    now_ms = utc_now_ms()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO lichess_player_ingestion_state (
                player_id, last_profile_fetch, status, error, updated_at
            )
            VALUES (%(player_id)s, %(last_profile_fetch)s, %(status)s, %(error)s, %(now_ms)s)
            ON CONFLICT (player_id) DO UPDATE SET
                last_profile_fetch = COALESCE(EXCLUDED.last_profile_fetch, lichess_player_ingestion_state.last_profile_fetch),
                status = EXCLUDED.status,
                error = EXCLUDED.error,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "player_id": player_id,
                "last_profile_fetch": now_ms if profile_touch else None,
                "status": status,
                "error": error,
                "now_ms": now_ms,
            },
        )


def build_dedupe_key(job_type: str, player_id: Optional[int], scope: Dict[str, Any]) -> str:
    payload = json.dumps({"player_id": player_id, "scope": scope}, sort_keys=True)
    fingerprint = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return f"{job_type}:{fingerprint}"


def enqueue_job(
    job_type: str,
    *,
    player_id: Optional[int],
    scope: Dict[str, Any],
    priority: int = 5,
    delay_seconds: int = 0,
    max_attempts: int = 5,
) -> Optional[int]:
    dedupe_key = build_dedupe_key(job_type, player_id, scope)
    available_at = utc_now_seconds() + max(delay_seconds, 0)
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingestion_jobs (
                player_id, job_type, scope, dedupe_key, status,
                priority, attempts, max_attempts, available_at
            )
            VALUES (%s, %s, %s::jsonb, %s, 'queued', %s, 0, %s, %s)
            ON CONFLICT (dedupe_key) DO UPDATE SET
                status = CASE
                    WHEN ingestion_jobs.status IN ('succeeded', 'cancelled') THEN ingestion_jobs.status
                    ELSE 'queued' END,
                priority = LEAST(ingestion_jobs.priority, EXCLUDED.priority),
                available_at = LEAST(ingestion_jobs.available_at, EXCLUDED.available_at),
                max_attempts = GREATEST(ingestion_jobs.max_attempts, EXCLUDED.max_attempts)
            RETURNING id
            """,
            (
                player_id,
                job_type,
                json.dumps(scope),
                dedupe_key,
                priority,
                max_attempts,
                available_at,
            ),
        )
        row = cur.fetchone()
        return row["id"] if row else None


def enqueue_seed_jobs(username: str) -> None:
    username = lower_username(username)
    LOGGER.info("Enqueuing seed jobs for %s", username)
    enqueue_job("profile", player_id=None, scope={"username": username}, priority=1)
    enqueue_job("stats", player_id=None, scope={"username": username}, priority=2, delay_seconds=15)
    enqueue_job("archives", player_id=None, scope={"username": username}, priority=3, delay_seconds=30)


def fetch_player_id_by_username(username: str) -> Optional[int]:
    username = lower_username(username)
    if not username:
        return None
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM players WHERE username = %s", (username,))
        row = cur.fetchone()
        return row["id"] if row else None


def fetch_username_by_player_id(player_id: int) -> Optional[str]:
    with get_db_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT username FROM players WHERE id = %s", (player_id,))
        row = cur.fetchone()
        return row["username"] if row else None


def ensure_player(
    username: str,
    api_client: ChessAPIClient,
) -> Optional[int]:
    username = lower_username(username)
    if not username:
        return None
    player_id = fetch_player_id_by_username(username)
    if player_id:
        return player_id

    LOGGER.info("Player %s missing locally; fetching profile lazily", username)
    profile = api_client.fetch_profile(username)
    with get_db_connection() as conn:
        player_id = upsert_player(conn, profile)
        upsert_player_ingestion_state(conn, player_id, status="idle")
    return player_id


def upsert_monthly_archive(
    conn,
    player_id: int,
    year: int,
    month: int,
    url: str,
) -> Tuple[int, bool]:
    now_ts = utc_now_seconds()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO monthly_archives (
                player_id, year, month, url, created_at, updated_at, fetch_status, retry_count, priority
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', 0, %s)
            ON CONFLICT (player_id, year, month) DO UPDATE SET
                url = EXCLUDED.url,
                updated_at = EXCLUDED.updated_at,
                fetch_status = CASE
                    WHEN monthly_archives.fetch_status = 'succeeded' THEN monthly_archives.fetch_status
                    ELSE 'pending' END,
                retry_count = CASE
                    WHEN monthly_archives.fetch_status = 'succeeded' THEN monthly_archives.retry_count
                    ELSE 0 END,
                priority = LEAST(monthly_archives.priority, EXCLUDED.priority)
            RETURNING id, (xmax = 0) AS inserted
            """,
            (player_id, year, month, url, now_ts, now_ts, MAX_ARCHIVE_JOB_PRIORITY),
        )
        row = cur.fetchone()
        archive_id = row["id"]
        inserted = row["inserted"]
        return archive_id, inserted


def enqueue_archive_job(player_id: int, username: str, archive_url: str, year: int, month: int) -> None:
    scope = {
        "username": username,
        "archive_url": archive_url,
        "year": year,
        "month": month,
    }
    enqueue_job(
        "games",
        player_id=player_id,
        scope=scope,
        priority=MAX_ARCHIVE_JOB_PRIORITY,
    )


def generate_game_payload(game: Dict[str, Any], archive_id: int) -> Dict[str, Any]:
    def accuracy(side: str) -> Optional[float]:
        accuracies = game.get("accuracies") or {}
        return accuracies.get(side)

    eco_url = game.get("eco_url") or game.get("eco")
    eco_code = None
    if isinstance(eco_url, str) and "/" in eco_url:
        eco_code = eco_url.rsplit("/", 1)[-1]

    payload = {
        "url": game.get("url"),
        "pgn": game.get("pgn"),
        "time_control": game.get("time_control"),
        "start_time": game.get("start_time"),
        "end_time": game.get("end_time"),
        "rated": game.get("rated", False),
        "time_class": game.get("time_class"),
        "rules": game.get("rules"),
        "eco_url": eco_url,
        "eco_code": eco_code,
        "fen": game.get("fen"),
        "initial_setup": game.get("initial_setup"),
        "tcn": game.get("tcn"),
        "white_rating": (game.get("white") or {}).get("rating"),
        "white_result": (game.get("white") or {}).get("result"),
        "white_uuid": (game.get("white") or {}).get("uuid"),
        "black_rating": (game.get("black") or {}).get("rating"),
        "black_result": (game.get("black") or {}).get("result"),
        "black_uuid": (game.get("black") or {}).get("uuid"),
        "white_accuracy": accuracy("white"),
        "black_accuracy": accuracy("black"),
        "archive_id": archive_id,
    }
    return payload


def upsert_game(conn, payload: Dict[str, Any], white_player_id: Optional[int], black_player_id: Optional[int]) -> None:
    if not payload.get("url"):
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO games (
                url, pgn, time_control, start_time, end_time, rated, time_class, rules,
                eco_url, eco_code, fen, initial_setup, tcn,
                white_accuracy, black_accuracy,
                white_player_id, white_rating, white_result, white_uuid,
                black_player_id, black_rating, black_result, black_uuid,
                archive_id, created_at
            )
            VALUES (
                %(url)s, %(pgn)s, %(time_control)s, %(start_time)s, %(end_time)s, %(rated)s, %(time_class)s, %(rules)s,
                %(eco_url)s, %(eco_code)s, %(fen)s, %(initial_setup)s, %(tcn)s,
                %(white_accuracy)s, %(black_accuracy)s,
                %(white_player_id)s, %(white_rating)s, %(white_result)s, %(white_uuid)s,
                %(black_player_id)s, %(black_rating)s, %(black_result)s, %(black_uuid)s,
                %(archive_id)s, EXTRACT(EPOCH FROM NOW())::BIGINT
            )
            ON CONFLICT (url) DO UPDATE SET
                pgn = EXCLUDED.pgn,
                time_control = EXCLUDED.time_control,
                end_time = EXCLUDED.end_time,
                rated = EXCLUDED.rated,
                time_class = EXCLUDED.time_class,
                rules = EXCLUDED.rules,
                eco_url = EXCLUDED.eco_url,
                eco_code = EXCLUDED.eco_code,
                fen = EXCLUDED.fen,
                initial_setup = EXCLUDED.initial_setup,
                tcn = EXCLUDED.tcn,
                white_accuracy = EXCLUDED.white_accuracy,
                black_accuracy = EXCLUDED.black_accuracy,
                white_player_id = COALESCE(EXCLUDED.white_player_id, games.white_player_id),
                black_player_id = COALESCE(EXCLUDED.black_player_id, games.black_player_id),
                white_rating = EXCLUDED.white_rating,
                black_rating = EXCLUDED.black_rating,
                white_result = EXCLUDED.white_result,
                black_result = EXCLUDED.black_result,
                archive_id = EXCLUDED.archive_id
            """,
            {
                **payload,
                "white_player_id": white_player_id,
                "black_player_id": black_player_id,
            },
        )


class IngestionWorker:
    def __init__(self, api_client: Optional[ChessAPIClient] = None, poll_interval: int = JOB_POLL_INTERVAL):
        self.api_client = api_client or ChessAPIClient()
        self.poll_interval = poll_interval

    def run(self, once: bool = False) -> None:
        LOGGER.info("Starting ingestion worker (once=%s)", once)
        while True:
            job = self._claim_job()
            if not job:
                if once:
                    LOGGER.info("No pending jobs; exiting")
                    return
                time.sleep(self.poll_interval)
                continue

            try:
                LOGGER.info("Processing job %s (%s)", job["id"], job["job_type"])
                self._process_job(job)
                self._mark_job_success(job["id"])
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception("Job %s failed: %s", job["id"], exc)
                self._mark_job_failure(job["id"], str(exc))

            if once:
                return

    def _claim_job(self) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM ingestion_jobs
                WHERE status = 'queued'
                  AND available_at <= EXTRACT(EPOCH FROM NOW())
                ORDER BY priority ASC, id ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """
            )
            job = cur.fetchone()
            if not job:
                return None

            cur.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'locked',
                    locked_at = EXTRACT(EPOCH FROM NOW())::BIGINT,
                    attempts = attempts + 1
                WHERE id = %s
                RETURNING *
                """,
                (job["id"],),
            )
            updated = cur.fetchone()
            return updated

    def _mark_job_success(self, job_id: int) -> None:
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'succeeded', completed_at = EXTRACT(EPOCH FROM NOW())::BIGINT
                WHERE id = %s
                """,
                (job_id,),
            )

    def _mark_job_failure(self, job_id: int, error: str) -> None:
        retry_delay = 300  # 5 minutes
        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_jobs
                SET status = CASE
                        WHEN attempts >= max_attempts THEN 'failed'
                        ELSE 'queued'
                    END,
                    available_at = CASE
                        WHEN attempts >= max_attempts THEN available_at
                        ELSE EXTRACT(EPOCH FROM NOW())::BIGINT + %s
                    END,
                    error = %s
                WHERE id = %s
                """,
                (retry_delay, error[:500], job_id),
            )

    def _process_job(self, job: Dict[str, Any]) -> None:
        job_type = job["job_type"]
        scope = job.get("scope") or {}
        if isinstance(scope, str):
            scope = json.loads(scope)
        if job_type == "profile":
            self._process_profile_job(job, scope)
        elif job_type == "stats":
            self._process_stats_job(job, scope)
        elif job_type == "archives":
            self._process_archives_job(job, scope)
        elif job_type == "games":
            self._process_games_job(job, scope)
        else:
            raise ValueError(f"Unsupported job type: {job_type}")

    def _current_username(self, job: Dict[str, Any], scope: Dict[str, Any]) -> str:
        username = lower_username(scope.get("username"))
        if username:
            return username
        player_id = job.get("player_id")
        if player_id:
            username = fetch_username_by_player_id(player_id)
        if not username:
            raise ValueError("Job missing username")
        scope["username"] = username
        return username

    def _process_profile_job(self, job: Dict[str, Any], scope: Dict[str, Any]) -> None:
        username = self._current_username(job, scope)
        LOGGER.info("Refreshing profile for %s", username)
        profile = self.api_client.fetch_profile(username)
        with get_db_connection() as conn:
            player_id = upsert_player(conn, profile)
            upsert_player_ingestion_state(conn, player_id, profile_touch=True, status="idle", error=None)
        enqueue_job("stats", player_id=job.get("player_id") or player_id, scope={"username": username}, priority=2)
        enqueue_job("archives", player_id=job.get("player_id") or player_id, scope={"username": username}, priority=3)

    def _process_stats_job(self, job: Dict[str, Any], scope: Dict[str, Any]) -> None:
        username = self._current_username(job, scope)
        LOGGER.info("Refreshing stats for %s", username)
        stats = self.api_client.fetch_stats(username)
        player_id = job.get("player_id") or fetch_player_id_by_username(username)
        if not player_id:
            profile = self.api_client.fetch_profile(username)
            with get_db_connection() as conn:
                player_id = upsert_player(conn, profile)
        with get_db_connection() as conn:
            upsert_player_stats(conn, player_id, stats)
            upsert_player_ingestion_state(conn, player_id, stats_touch=True, status="idle", error=None)

    def _process_archives_job(self, job: Dict[str, Any], scope: Dict[str, Any]) -> None:
        username = self._current_username(job, scope)
        LOGGER.info("Refreshing archives for %s", username)
        archives = list(self.api_client.fetch_archives(username))
        total_archives = len(archives)
        if ARCHIVE_MONTH_LIMIT > 0 and total_archives > ARCHIVE_MONTH_LIMIT:
            archives = archives[-ARCHIVE_MONTH_LIMIT:]
            LOGGER.info(
                "Limiting archives for %s to the most recent %s months (of %s available)",
                username,
                ARCHIVE_MONTH_LIMIT,
                total_archives,
            )
        player_id = job.get("player_id") or fetch_player_id_by_username(username)
        if not player_id:
            profile = self.api_client.fetch_profile(username)
            with get_db_connection() as conn:
                player_id = upsert_player(conn, profile)

        new_jobs = 0
        with get_db_connection() as conn:
            for archive_url in archives:
                cleaned = archive_url.rstrip("/")
                try:
                    year = int(cleaned.split("/")[-2])
                    month = int(cleaned.split("/")[-1])
                except (ValueError, IndexError):
                    LOGGER.warning("Could not parse archive path: %s", archive_url)
                    continue

                archive_id, inserted = upsert_monthly_archive(conn, player_id, year, month, archive_url)
                if inserted:
                    enqueue_archive_job(player_id, username, archive_url, year, month)
                    new_jobs += 1

            upsert_player_ingestion_state(conn, player_id, archives_touch=True, status="idle", error=None)

        LOGGER.info("Archive refresh complete (%s new archive jobs)", new_jobs)

    def _process_games_job(self, job: Dict[str, Any], scope: Dict[str, Any]) -> None:
        username = self._current_username(job, scope)
        archive_url = scope.get("archive_url")
        year = scope.get("year")
        month = scope.get("month")
        if not archive_url or year is None or month is None:
            raise ValueError("Games job missing archive scope")

        LOGGER.info("Fetching games for %s %s/%s", username, year, month)
        data = self.api_client.fetch_archive_games(archive_url)

        player_id = job.get("player_id") or fetch_player_id_by_username(username)
        if not player_id:
            player_id = ensure_player(username, self.api_client)

        with get_db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM monthly_archives
                WHERE player_id = %s AND year = %s AND month = %s
                """,
                (player_id, year, month),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Archive row missing locally")
            archive_id = row["id"]

        games = data.get("games") or []
        created = 0
        for game in games:
            white_username = lower_username((game.get("white") or {}).get("username"))
            black_username = lower_username((game.get("black") or {}).get("username"))
            white_id = ensure_player(white_username, self.api_client) if white_username else None
            black_id = ensure_player(black_username, self.api_client) if black_username else None
            payload = generate_game_payload(game, archive_id)
            with get_db_connection() as conn:
                upsert_game(conn, payload, white_id, black_id)
            created += 1

        LOGGER.info("Stored %s games for %s/%s", created, year, month)
        with get_db_connection() as conn, conn.cursor() as cur:
            now_ts = utc_now_seconds()
            cur.execute(
                """
                UPDATE monthly_archives
                SET fetch_status = 'succeeded',
                    last_fetch_attempt = %(now)s,
                    last_success_at = %(now)s,
                    retry_count = 0,
                    next_retry_at = NULL
                WHERE player_id = %(player_id)s AND year = %(year)s AND month = %(month)s
                """,
                {"now": now_ts, "player_id": player_id, "year": year, "month": month},
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chess.com ingestion worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    enqueue_parser = subparsers.add_parser("enqueue", help="enqueue seed jobs for usernames")
    enqueue_parser.add_argument("--username", action="append", required=True, help="Chess.com username(s)")

    run_parser = subparsers.add_parser("run", help="run the ingestion worker")
    run_parser.add_argument("--once", action="store_true", help="process at most one job")
    run_parser.add_argument("--loop", action="store_true", help="run until interrupted")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "enqueue":
        for username in args.username:
            enqueue_seed_jobs(username)
    elif args.command == "run":
        worker = IngestionWorker()
        once = True
        if args.loop:
            once = False
        elif args.once:
            once = True
        worker.run(once=once)
    else:
        raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
