DROP VIEW IF EXISTS v_team_match;
CREATE VIEW v_team_match AS
SELECT us.match_key, m.competition, m.season_id, m.date_key, m.match_hour_local,
       us.club_id, us.goals_for, us.goals_against, us.shots_for,
       us.has_user_gk, us.num_human_players, us.is_win, us.is_loss, us.is_tie,
       opp.club_id          AS opp_club_id,
       opp.shots_for        AS shots_against,
       opp.goals_for        AS goals_conceded,
       opp.has_user_gk      AS opp_has_user_gk,
       opp.num_human_players AS opp_num_human_players
FROM fact_team_match us
JOIN fact_team_match opp
  ON opp.match_key = us.match_key AND opp.club_id <> us.club_id
JOIN dim_match m ON m.match_key = us.match_key;

DROP VIEW IF EXISTS v_gk_impact;
CREATE VIEW v_gk_impact AS
SELECT has_user_gk,
       COUNT(*)              AS games,
       ROUND(AVG(shots_against),1) AS avg_shots_conceded,
       ROUND(AVG(goals_conceded),1) AS avg_goals_conceded
FROM v_team_match
WHERE club_id = 127516
GROUP BY has_user_gk;

DROP VIEW IF EXISTS v_player_leaderboard;
CREATE VIEW v_player_leaderboard AS
SELECT m.season_id, dp.player_name,
       SUM(f.goals) AS goals, SUM(f.assists) AS assists,
       SUM(f.goals + f.assists) AS goal_contributions,
       COUNT(*) AS games, ROUND(AVG(f.rating),2) AS avg_rating
FROM fact_player_match f
JOIN dim_player dp ON dp.player_key = f.player_key
JOIN dim_match m   ON m.match_key   = f.match_key
WHERE f.club_id = 127516
GROUP BY m.season_id, dp.player_name
ORDER BY goal_contributions DESC;

DROP VIEW IF EXISTS v_nvn;
CREATE VIEW v_nvn AS
SELECT num_human_players AS our_n, opp_num_human_players AS opp_n,
       COUNT(*) AS games,
       ROUND(AVG(is_win)*100,1) AS win_pct,
       ROUND(AVG(goals_for - goals_conceded),2) AS avg_goal_diff
FROM v_team_match
WHERE club_id = 127516
GROUP BY our_n, opp_n;

DROP VIEW IF EXISTS v_player_form;
CREATE VIEW v_player_form AS
SELECT dp.player_name, da.archetype_name, da.archetype_category,
       COUNT(*) AS games,
       ROUND(AVG(f.passes_made),1) AS avg_passes,
       ROUND(AVG(f.shots),1)       AS avg_shots,
       ROUND(AVG(f.tackles_made),1) AS avg_tackles
FROM fact_player_match f
JOIN dim_player dp    ON dp.player_key = f.player_key
JOIN dim_archetype da ON da.archetype_id = f.archetype_id
WHERE f.club_id = 127516 AND dp.is_current = 1
GROUP BY dp.player_name, da.archetype_name, da.archetype_category;
