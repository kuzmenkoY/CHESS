-- Latest ratings per time_class for a player
-- :player_username (lowercased)
WITH p AS (
  SELECT id FROM players WHERE username = :player_username
)
SELECT ps.time_class,
       ps.rules,
       ps.last_rating,
       ps.last_rating_date
FROM player_stats ps
JOIN p ON ps.player_id = p.id
ORDER BY ps.rules, ps.time_class;

-- Recent games feed for a player
-- :player_username, :limit
WITH p AS (
  SELECT id FROM players WHERE username = :player_username
)
SELECT g.*,
       pw.display_username AS white_name,
       pb.display_username AS black_name
FROM games g
LEFT JOIN players pw ON pw.id = g.white_player_id
LEFT JOIN players pb ON pb.id = g.black_player_id
WHERE g.white_player_id IN (SELECT id FROM p)
   OR g.black_player_id IN (SELECT id FROM p)
ORDER BY g.end_time DESC
LIMIT :limit;

-- Head-to-head summary between two players
-- :user_a (lowercased), :user_b (lowercased)
WITH a AS (SELECT id FROM players WHERE username = :user_a),
     b AS (SELECT id FROM players WHERE username = :user_b)
SELECT
  SUM(CASE WHEN (g.white_player_id = a.id AND g.white_result = 'win') OR (g.black_player_id = a.id AND g.black_result = 'win') THEN 1 ELSE 0 END) AS a_wins,
  SUM(CASE WHEN (g.white_player_id = b.id AND g.white_result = 'win') OR (g.black_player_id = b.id AND g.black_result = 'win') THEN 1 ELSE 0 END) AS b_wins,
  SUM(CASE WHEN (g.white_result IN ('agreed','repetition','stalemate','50move','insufficient','timevsinsufficient')
            AND g.black_result IN ('agreed','repetition','stalemate','50move','insufficient','timevsinsufficient')) THEN 1 ELSE 0 END) AS draws,
  COUNT(*) AS games
FROM games g, a, b
WHERE (g.white_player_id = a.id AND g.black_player_id = b.id)
   OR (g.white_player_id = b.id AND g.black_player_id = a.id);

-- Monthly activity (games per month) for a player
-- :player_username
WITH p AS (SELECT id FROM players WHERE username = :player_username)
SELECT strftime('%Y-%m', g.end_time, 'unixepoch') AS ym,
       COUNT(*) AS games
FROM games g, p
WHERE g.white_player_id = p.id OR g.black_player_id = p.id
GROUP BY ym
ORDER BY ym DESC;

-- Friend feed: recent games of players tracked by an app user
-- :app_username, :limit
WITH u AS (SELECT id FROM app_users WHERE username = :app_username),
tp AS (
  SELECT autp.player_id
  FROM app_user_tracked_players autp
  JOIN u ON u.id = autp.app_user_id
)
SELECT g.*,
       pw.display_username AS white_name,
       pb.display_username AS black_name
FROM games g
LEFT JOIN players pw ON pw.id = g.white_player_id
LEFT JOIN players pb ON pb.id = g.black_player_id
WHERE g.white_player_id IN (SELECT player_id FROM tp)
   OR g.black_player_id IN (SELECT player_id FROM tp)
ORDER BY g.end_time DESC
LIMIT :limit;


