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
SELECT to_char(to_timestamp(g.end_time), 'YYYY-MM') AS ym,
       COUNT(*) AS games
FROM games g, p
WHERE g.white_player_id = p.id OR g.black_player_id = p.id
GROUP BY ym
ORDER BY ym DESC;

-- Friend feed: recent games of players tracked by an app user
-- :app_username, :limit
WITH u AS (SELECT id FROM social.app_users WHERE username = :app_username),
tp AS (
  SELECT autp.player_id
  FROM social.app_user_tracked_players autp
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

-- Social: Latest posts visible to an app user (self + followed players)
-- :viewer_username, :limit
WITH viewer AS (
  SELECT id FROM social.app_users WHERE username = :viewer_username
),
followed_players AS (
  SELECT player_id
  FROM social.app_user_tracked_players autp
  JOIN viewer v ON v.id = autp.app_user_id
),
followed_users AS (
  SELECT DISTINCT au.id
  FROM social.app_users au
  LEFT JOIN followed_players fp ON fp.player_id = au.player_id
  WHERE au.id IN (SELECT id FROM viewer)
     OR fp.player_id IS NOT NULL
)
SELECT p.id,
       p.content,
       p.player_snapshot,
       p.audience,
       p.source,
       p.created_at,
       au.username,
       au.display_name,
       COALESCE(reaction_counts.reactions, 0) AS reactions,
       COALESCE(comment_counts.comments, 0) AS comments
FROM social.posts p
JOIN social.app_users au ON au.id = p.app_user_id
JOIN followed_users fu ON fu.id = p.app_user_id
LEFT JOIN (
  SELECT post_id, COUNT(*) AS reactions
  FROM social.post_reactions
  GROUP BY post_id
) AS reaction_counts ON reaction_counts.post_id = p.id
LEFT JOIN (
  SELECT post_id, COUNT(*) AS comments
  FROM social.comments
  WHERE deleted_at IS NULL
  GROUP BY post_id
) AS comment_counts ON comment_counts.post_id = p.id
WHERE p.deleted_at IS NULL
ORDER BY p.created_at DESC
LIMIT :limit;

-- Social: Club roster with follower counts
-- :club_slug
SELECT c.name,
       c.slug,
       c.description,
       c.visibility,
       au.username AS owner_username,
       COUNT(cm.id) FILTER (WHERE cm.status = 'active') AS active_members,
       COUNT(CASE WHEN cm.role = 'admin' THEN 1 END) AS admins
FROM social.clubs c
LEFT JOIN social.app_users au ON au.id = c.owner_id
LEFT JOIN social.club_memberships cm ON cm.club_id = c.id
WHERE c.slug = :club_slug
GROUP BY c.id, au.username;

