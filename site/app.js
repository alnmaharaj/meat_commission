'use strict';

// ── State ─────────────────────────────────────────────────────────────────
const STATE = { season: null, competition: 'both' };
let db = null;
let sortState = { col: 'goal_contributions', asc: false };
const charts = {};
let activePlayerCard = null;
let activeMatchKey = null;
let analysisLoaded = false;

// ── DB ────────────────────────────────────────────────────────────────────
async function initDb() {
  const SQL = await initSqlJs({
    locateFile: f => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}`
  });
  const resp = await fetch('clubstats.db');
  if (!resp.ok) throw new Error(`Could not fetch database (HTTP ${resp.status})`);
  db = new SQL.Database(new Uint8Array(await resp.arrayBuffer()));
}

function query(sql, params = []) {
  const stmt = db.prepare(sql);
  stmt.bind(params);
  const rows = [];
  while (stmt.step()) rows.push(stmt.getAsObject());
  stmt.free();
  return rows;
}

// ── Filter helpers ────────────────────────────────────────────────────────
// Returns WHERE clauses and params for current season/competition state.
// tableAlias: 'm' for queries that join dim_match, null for v_team_match (columns exposed directly).
function buildFilters(tableAlias) {
  const p = tableAlias ? `${tableAlias}.` : '';
  const clauses = [], params = [];
  if (STATE.season !== null)          { clauses.push(`${p}season_id = ?`);    params.push(STATE.season); }
  if (STATE.competition !== 'both')   { clauses.push(`${p}competition = ?`);  params.push(STATE.competition); }
  return { clauses, params };
}

// ── Freshness ─────────────────────────────────────────────────────────────
function loadFreshness() {
  const rows = query('SELECT MAX(match_timestamp) AS ts FROM dim_match');
  if (!rows.length || !rows[0].ts) return;
  const date = new Date(rows[0].ts * 1000).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  const text = `Data through ${date}`;
  document.getElementById('freshness-stamp').textContent = text;
  document.getElementById('freshness-footer').textContent = text;
}

// ── Season options ────────────────────────────────────────────────────────
function loadSeasonOptions() {
  const rows = query('SELECT DISTINCT season_id FROM dim_match ORDER BY season_id DESC');
  const sel = document.getElementById('season-select');
  let html = '<option value="">All seasons</option>';
  for (const r of rows) html += `<option value="${r.season_id}">Season ${r.season_id}</option>`;
  sel.innerHTML = html;
  if (rows.length) {
    STATE.season = rows[0].season_id;
    sel.value = rows[0].season_id;
  }
}

// ── Leaderboard ───────────────────────────────────────────────────────────
function loadLeaderboard() {
  const { clauses, params } = buildFilters('m');
  const where = ['f.club_id = 127516', ...clauses].join(' AND ');
  const rows = query(`
    SELECT dp.player_name,
           SUM(f.goals)              AS goals,
           SUM(f.assists)            AS assists,
           SUM(f.goals + f.assists)  AS goal_contributions,
           COUNT(*)                  AS games,
           ROUND(AVG(f.rating), 2)   AS avg_rating
    FROM fact_player_match f
    JOIN dim_player dp ON dp.player_key = f.player_key
    JOIN dim_match  m  ON m.match_key   = f.match_key
    WHERE ${where}
    GROUP BY dp.player_name
  `, params);
  renderLeaderboard(rows);
}

function renderLeaderboard(rows) {
  rows.sort((a, b) => {
    const va = a[sortState.col], vb = b[sortState.col];
    if (typeof va === 'string') return sortState.asc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortState.asc ? va - vb : vb - va;
  });

  const cols = [
    { key: 'player_name',        label: 'Player', },
    { key: 'games',              label: 'GP' },
    { key: 'goals',              label: 'G' },
    { key: 'assists',            label: 'A' },
    { key: 'goal_contributions', label: 'G+A' },
    { key: 'avg_rating',         label: 'Rating' },
  ];

  let html = '<table class="data-table" id="leaderboard-table"><thead><tr>';
  for (const c of cols) {
    const active = sortState.col === c.key ? 'active' : '';
    const arrow  = sortState.col === c.key ? (sortState.asc ? ' ▲' : ' ▼') : '';
    html += `<th class="sortable ${active}" data-col="${c.key}">${c.label}${arrow}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const r of rows) {
    html += `<tr class="leaderboard-row" data-player="${esc(r.player_name)}">
      <td data-label="Player">${esc(r.player_name)}</td>
      <td data-label="GP">${r.games}</td>
      <td data-label="G">${r.goals}</td>
      <td data-label="A">${r.assists}</td>
      <td data-label="G+A">${r.goal_contributions}</td>
      <td data-label="Rating">${r.avg_rating ?? '—'}</td>
    </tr>`;
  }
  html += '</tbody></table>';

  const container = document.getElementById('leaderboard-container');
  container.innerHTML = html;

  container.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      sortState.asc = sortState.col === col ? !sortState.asc : col === 'player_name';
      sortState.col = col;
      loadLeaderboard();
    });
  });

  container.querySelectorAll('.leaderboard-row').forEach(tr => {
    tr.addEventListener('click', () => {
      const name = tr.dataset.player;
      if (activePlayerCard === name) {
        activePlayerCard = null;
        document.getElementById('player-card').classList.add('hidden');
      } else {
        activePlayerCard = name;
        loadPlayerCard(name);
      }
    });
  });
}

// ── Results strip ─────────────────────────────────────────────────────────
function loadResults() {
  const { clauses, params } = buildFilters('vtm');
  const where = ['vtm.club_id = 127516', ...clauses].join(' AND ');
  const rows = query(`
    SELECT vtm.match_key, m.match_timestamp, vtm.competition,
           vtm.goals_for, vtm.goals_conceded,
           vtm.is_win, vtm.is_loss, vtm.is_tie,
           dc.club_name AS opp_name
    FROM v_team_match vtm
    JOIN dim_match m  ON m.match_key  = vtm.match_key
    JOIN dim_club  dc ON dc.club_id   = vtm.opp_club_id
    WHERE ${where}
    ORDER BY m.match_timestamp DESC
    LIMIT 10
  `, params);
  renderResults(rows);
}

function renderResults(rows) {
  const container = document.getElementById('results-container');
  if (!rows.length) { container.innerHTML = '<p class="empty">No matches found.</p>'; return; }

  let html = '<div class="results-strip">';
  for (const r of rows) {
    const date = new Date(r.match_timestamp * 1000)
      .toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const outcome = r.is_win ? 'W' : r.is_loss ? 'L' : 'D';
    const cls     = r.is_win ? 'win' : r.is_loss ? 'loss' : 'draw';
    html += `<div class="result-card" data-match-key="${esc(r.match_key)}">
      <span class="result-badge ${cls}">${outcome}</span>
      <span class="result-score">${r.goals_for}–${r.goals_conceded}</span>
      <span class="result-opp">${esc(r.opp_name)}</span>
      <span class="result-meta">${date} · ${r.competition}</span>
    </div>`;
  }
  html += '</div>';
  container.innerHTML = html;

  container.querySelectorAll('.result-card').forEach(card => {
    card.addEventListener('click', () => {
      const key = card.dataset.matchKey;
      if (activeMatchKey === key) {
        activeMatchKey = null;
        container.querySelectorAll('.result-card').forEach(c => c.classList.remove('selected'));
        document.getElementById('match-detail').classList.add('hidden');
      } else {
        activeMatchKey = key;
        container.querySelectorAll('.result-card').forEach(c => c.classList.remove('selected'));
        card.classList.add('selected');
        loadMatchDetail(key);
      }
    });
  });
}

// ── Match detail ──────────────────────────────────────────────────────────
function loadMatchDetail(matchKey) {
  const teamRows = query(`
    SELECT vtm.goals_for, vtm.goals_conceded, vtm.shots_for, vtm.shots_against,
           vtm.has_user_gk, vtm.num_human_players,
           vtm.is_win, vtm.is_loss, vtm.is_tie,
           dc.club_name AS opp_name, m.match_timestamp, m.competition
    FROM v_team_match vtm
    JOIN dim_club  dc ON dc.club_id  = vtm.opp_club_id
    JOIN dim_match m  ON m.match_key = vtm.match_key
    WHERE vtm.match_key = ? AND vtm.club_id = 127516
  `, [matchKey]);

  const playerRows = query(`
    SELECT dp.player_name, f.position, da.archetype_name,
           f.goals, f.assists, f.rating,
           f.shots, f.passes_made, f.pass_attempts,
           f.tackles_made, f.saves, f.man_of_match
    FROM fact_player_match f
    JOIN dim_player    dp ON dp.player_key   = f.player_key
    LEFT JOIN dim_archetype da ON da.archetype_id = f.archetype_id
    WHERE f.match_key = ? AND f.club_id = 127516
    ORDER BY f.man_of_match DESC, COALESCE(f.rating, 0) DESC
  `, [matchKey]);

  renderMatchDetail(teamRows[0], playerRows);
}

const POS_LABEL = { goalkeeper: 'GK', attacker: 'ATT', midfielder: 'MID', defender: 'DEF' };

function renderMatchDetail(team, players) {
  const panel = document.getElementById('match-detail');
  if (!team) { panel.classList.add('hidden'); return; }

  const date    = new Date(team.match_timestamp * 1000)
    .toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  const outcome = team.is_win ? 'W' : team.is_loss ? 'L' : 'D';
  const cls     = team.is_win ? 'win' : team.is_loss ? 'loss' : 'draw';
  const hasGK   = players.some(p => p.position === 'goalkeeper');

  let html = `
    <div class="match-detail-inner">
      <div class="match-detail-header">
        <div class="match-detail-title">
          <span class="result-badge ${cls}">${outcome}</span>
          <span class="match-score">${team.goals_for}–${team.goals_conceded}</span>
          <span class="match-opp">vs. ${esc(team.opp_name)}</span>
        </div>
        <div class="match-detail-meta">${date} · ${team.competition}</div>
        <button class="close-btn" id="close-match-detail" aria-label="Close">✕</button>
      </div>

      <div class="match-team-stats">
        <div class="team-stat"><span class="ts-val">${team.shots_for}</span><span class="ts-lbl">Our Shots</span></div>
        <div class="team-stat"><span class="ts-val">${team.shots_against}</span><span class="ts-lbl">Opp Shots</span></div>
        <div class="team-stat"><span class="ts-val">${team.num_human_players}</span><span class="ts-lbl">Players</span></div>
        <div class="team-stat"><span class="ts-val">${team.has_user_gk ? 'User' : 'CPU'}</span><span class="ts-lbl">GK</span></div>
      </div>

      <table class="data-table match-player-table">
        <thead><tr>
          <th>Player</th>
          <th>Pos</th>
          <th>G</th>
          <th>A</th>
          <th>Rating</th>
          <th>Shots</th>
          <th>Pass%</th>
          <th>Tackles</th>
          ${hasGK ? '<th>Saves</th>' : ''}
        </tr></thead>
        <tbody>`;

  for (const p of players) {
    const pos     = POS_LABEL[p.position] ?? (p.position ?? '—');
    const passAcc = p.pass_attempts > 0 ? Math.round(p.passes_made / p.pass_attempts * 100) + '%' : '—';
    const mom     = p.man_of_match ? ' ★' : '';
    html += `<tr class="${p.man_of_match ? 'highlight' : ''}">
      <td data-label="Player">${esc(p.player_name)}${mom}</td>
      <td data-label="Pos">${pos}</td>
      <td data-label="G">${p.goals}</td>
      <td data-label="A">${p.assists}</td>
      <td data-label="Rating">${p.rating ?? '—'}</td>
      <td data-label="Shots">${p.shots}</td>
      <td data-label="Pass%">${passAcc}</td>
      <td data-label="Tackles">${p.tackles_made}</td>
      ${hasGK ? `<td data-label="Saves">${p.saves ?? 0}</td>` : ''}
    </tr>`;
  }

  html += '</tbody></table></div>';
  panel.innerHTML = html;
  panel.classList.remove('hidden');

  document.getElementById('close-match-detail').addEventListener('click', () => {
    activeMatchKey = null;
    document.querySelectorAll('.result-card').forEach(c => c.classList.remove('selected'));
    panel.classList.add('hidden');
  });
}

// ── Player card ───────────────────────────────────────────────────────────
function loadPlayerCard(name) {
  const { clauses, params } = buildFilters('m');
  const where = ['f.club_id = 127516', 'dp.player_name = ?', ...clauses].join(' AND ');
  const rows = query(`
    SELECT m.match_timestamp, f.goals, f.assists, f.rating,
           f.passes_made, f.pass_attempts,
           f.tackles_made, f.tackle_attempts,
           f.shots, f.saves, f.position, f.man_of_match
    FROM fact_player_match f
    JOIN dim_player dp ON dp.player_key = f.player_key
    JOIN dim_match  m  ON m.match_key   = f.match_key
    WHERE ${where}
    ORDER BY m.match_timestamp ASC
  `, [name, ...params]);
  renderPlayerCard(name, rows);
}

function renderPlayerCard(name, rows) {
  const card = document.getElementById('player-card');
  if (!rows.length) { card.classList.add('hidden'); return; }

  const games    = rows.length;
  const goals    = rows.reduce((s, r) => s + (r.goals   || 0), 0);
  const assists  = rows.reduce((s, r) => s + (r.assists  || 0), 0);
  const avgRat   = (rows.reduce((s, r) => s + (r.rating  || 0), 0) / games).toFixed(2);
  const pAtt     = rows.reduce((s, r) => s + (r.pass_attempts || 0), 0);
  const pMade    = rows.reduce((s, r) => s + (r.passes_made   || 0), 0);
  const passAcc  = pAtt > 0 ? Math.round(pMade / pAtt * 100) : '—';
  const saves    = rows.reduce((s, r) => s + (r.saves || 0), 0);
  const mom      = rows.reduce((s, r) => s + (r.man_of_match || 0), 0);
  const isGK     = rows.some(r => r.position === 'goalkeeper');

  card.classList.remove('hidden');
  card.innerHTML = `
    <div class="player-card-inner">
      <div class="player-card-header">
        <h3>${esc(name)}</h3>
        <button class="close-btn" id="close-player-card" aria-label="Close">✕</button>
      </div>
      <div class="stat-tiles">
        <div class="stat-tile"><span class="stat-val">${goals}</span><span class="stat-lbl">Goals</span></div>
        <div class="stat-tile"><span class="stat-val">${assists}</span><span class="stat-lbl">Assists</span></div>
        <div class="stat-tile"><span class="stat-val">${avgRat}</span><span class="stat-lbl">Avg Rating</span></div>
        <div class="stat-tile"><span class="stat-val">${passAcc}${typeof passAcc === 'number' ? '%' : ''}</span><span class="stat-lbl">Pass Acc</span></div>
        ${isGK ? `<div class="stat-tile"><span class="stat-val">${saves}</span><span class="stat-lbl">Saves</span></div>` : ''}
        <div class="stat-tile"><span class="stat-val">${mom}</span><span class="stat-lbl">MOTM</span></div>
        <div class="stat-tile"><span class="stat-val">${games}</span><span class="stat-lbl">Games</span></div>
      </div>
      <div class="chart-container" style="height:140px">
        <canvas id="chart-sparkline"></canvas>
      </div>
    </div>`;

  document.getElementById('close-player-card').addEventListener('click', () => {
    activePlayerCard = null;
    card.classList.add('hidden');
  });

  if (charts.sparkline) { charts.sparkline.destroy(); charts.sparkline = null; }
  charts.sparkline = new Chart(document.getElementById('chart-sparkline'), {
    type: 'line',
    data: {
      labels: rows.map((_, i) => `G${i + 1}`),
      datasets: [{
        label: 'Rating',
        data: rows.map(r => r.rating ?? null),
        borderColor: '#e74c3c',
        backgroundColor: 'rgba(231,76,60,0.1)',
        tension: 0.3,
        fill: true,
        pointRadius: 3,
        spanGaps: true,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 4, max: 10, grid: { color: '#333' }, ticks: { color: '#888' } },
        x: { grid: { color: '#333' }, ticks: { color: '#888', maxTicksLimit: 10 } }
      }
    }
  });
}

// ── GK impact ─────────────────────────────────────────────────────────────
function loadGkImpact() {
  const { clauses, params } = buildFilters(null);
  const where = ['club_id = 127516', ...clauses].join(' AND ');

  // Per-match rows for strip plot
  const gameRows = query(`
    SELECT match_key, has_user_gk, shots_against, goals_conceded,
           CASE WHEN shots_against > 0
                THEN ROUND(1.0 - CAST(goals_conceded AS FLOAT)/shots_against, 3)
                ELSE NULL END AS save_rate
    FROM v_team_match
    WHERE ${where}
  `, params);

  // Aggregates for means and stat tiles
  const aggRows = query(`
    SELECT has_user_gk,
           COUNT(*) AS games,
           ROUND(AVG(shots_against), 1) AS avg_shots,
           ROUND(AVG(goals_conceded), 1) AS avg_goals,
           ROUND(AVG(CASE WHEN shots_against > 0
                          THEN 1.0 - CAST(goals_conceded AS FLOAT)/shots_against
                          ELSE NULL END)*100, 1) AS avg_save_rate
    FROM v_team_match
    WHERE ${where}
    GROUP BY has_user_gk
  `, params);

  renderGkImpact(gameRows, aggRows);
}

function renderGkImpact(gameRows, aggRows) {
  // agg keyed by condition
  const agg = {};
  for (const r of aggRows) agg[r.has_user_gk] = r;

  // Split per-game rows by condition, add tiny x jitter for readability
  const cpuDots   = gameRows.filter(r => !r.has_user_gk).map(r => ({ x: 0 + (Math.random() - 0.5) * 0.16, y: r.shots_against }));
  const userDots  = gameRows.filter(r =>  r.has_user_gk).map(r => ({ x: 1 + (Math.random() - 0.5) * 0.16, y: r.shots_against }));
  const cpuGoals  = gameRows.filter(r => !r.has_user_gk).map(r => ({ x: 0 + (Math.random() - 0.5) * 0.16, y: r.goals_conceded }));
  const userGoals = gameRows.filter(r =>  r.has_user_gk).map(r => ({ x: 1 + (Math.random() - 0.5) * 0.16, y: r.goals_conceded }));

  // Mean diamonds
  const means = [
    { x: 0, y: agg[0]?.avg_shots  ?? null },
    { x: 1, y: agg[1]?.avg_shots  ?? null },
  ].filter(p => p.y !== null);
  const meansGoals = [
    { x: 0, y: agg[0]?.avg_goals ?? null },
    { x: 1, y: agg[1]?.avg_goals ?? null },
  ].filter(p => p.y !== null);

  if (charts.gk) { charts.gk.destroy(); charts.gk = null; }
  charts.gk = new Chart(document.getElementById('chart-gk'), {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Shots conceded/game',
          data: [...cpuDots, ...userDots],
          backgroundColor: 'rgba(41,128,185,0.45)',
          pointRadius: 5, pointHoverRadius: 7,
        },
        {
          label: 'Goals conceded/game',
          data: [...cpuGoals, ...userGoals],
          backgroundColor: 'rgba(231,76,60,0.45)',
          pointRadius: 5, pointHoverRadius: 7,
        },
        {
          label: 'Mean shots',
          data: means,
          backgroundColor: '#2980b9',
          pointStyle: 'rectRot', pointRadius: 10, pointHoverRadius: 12,
          showLine: false,
        },
        {
          label: 'Mean goals',
          data: meansGoals,
          backgroundColor: '#e74c3c',
          pointStyle: 'rectRot', pointRadius: 10, pointHoverRadius: 12,
          showLine: false,
        },
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#ccc' } },
        tooltip: {
          callbacks: {
            title: () => '',
            label: ctx => {
              const ds = ctx.dataset.label;
              const cond = ctx.parsed.x < 0.5 ? 'CPU GK' : 'User GK';
              return `${cond} — ${ds}: ${ctx.parsed.y}`;
            }
          }
        }
      },
      scales: {
        x: {
          min: -0.5, max: 1.5,
          grid: { color: '#333' },
          ticks: {
            color: '#ccc', font: { size: 13 },
            callback: v => {
              if (Math.abs(v) < 0.05) return `CPU GK (${agg[0]?.games ?? 0}g)`;
              if (Math.abs(v - 1) < 0.05) return `User GK (${agg[1]?.games ?? 0}g)`;
              return '';
            }
          }
        },
        y: { beginAtZero: true, grid: { color: '#333' }, ticks: { color: '#888' }, title: { display: true, text: 'Per game', color: '#888' } }
      }
    }
  });

  // Stat tiles below the chart
  const tilesEl = document.getElementById('gk-stat-tiles');
  if (!tilesEl) return;
  const conditions = [
    { key: 0, label: 'CPU GK' },
    { key: 1, label: 'User GK' },
  ];
  let html = '<div class="gk-tiles-row">';
  for (const { key, label } of conditions) {
    const a = agg[key];
    if (!a) continue;
    const sr = a.avg_save_rate !== null ? `${a.avg_save_rate}%` : '—';
    html += `<div class="gk-condition-tile">
      <strong>${label}</strong> <span class="games-badge">${a.games}g</span>
      <div class="gk-tile-stats">
        <span><span class="ts-val">${a.avg_shots}</span> shots/g</span>
        <span><span class="ts-val">${a.avg_goals}</span> goals/g</span>
        <span><span class="ts-val">${sr}</span> save rate</span>
      </div>
    </div>`;
  }
  html += '</div>';
  tilesEl.innerHTML = html;
}

// ── n-vs-n ────────────────────────────────────────────────────────────────
function loadNvN() {
  const { clauses, params } = buildFilters(null);
  const where = ['club_id = 127516', ...clauses].join(' AND ');
  const rows = query(`
    SELECT (num_human_players - opp_num_human_players) AS diff,
           COUNT(*)                                    AS games,
           ROUND(AVG(is_win) * 100, 1)                AS win_pct,
           ROUND(AVG(goals_for - goals_conceded), 2)  AS avg_goal_diff
    FROM v_team_match
    WHERE ${where}
    GROUP BY diff
    ORDER BY diff DESC
  `, params);
  renderNvN(rows);
}

function renderNvN(rows) {
  const canvas = document.getElementById('chart-nvn');
  if (!rows.length) {
    if (canvas) canvas.style.display = 'none';
    const container = document.getElementById('nvn-container');
    container.innerHTML = '<p class="empty">No n-vs-n data yet.</p>';
    return;
  }
  if (canvas) canvas.style.display = '';

  const labels   = rows.map(r => r.diff > 0 ? `+${r.diff}` : String(r.diff));
  const winPcts  = rows.map(r => r.win_pct);
  const games    = rows.map(r => r.games);
  const goalDiff = rows.map(r => r.avg_goal_diff);

  // Color bars: 0% = red(231,76,60), 50% = grey(128,128,128), 100% = green(39,174,96)
  function winColor(pct, alpha = 0.75) {
    let r, g, b;
    if (pct >= 50) {
      const t = (pct - 50) / 50;
      r = Math.round(128 - 89 * t);
      g = Math.round(128 + 46 * t);
      b = Math.round(128 - 32 * t);
    } else {
      const t = pct / 50;
      r = Math.round(231 - 103 * t);
      g = Math.round(76  +  52 * t);
      b = Math.round(60  +  68 * t);
    }
    return `rgba(${r},${g},${b},${alpha})`;
  }
  const colors = winPcts.map(p => winColor(p));

  if (charts.nvn) { charts.nvn.destroy(); charts.nvn = null; }
  charts.nvn = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Win%',
        data: winPcts,
        backgroundColor: colors,
        borderColor: colors.map(c => c.replace('0.75', '1')),
        borderWidth: 1,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            title: (items) => {
              const idx = items[0].dataIndex;
              const d = rows[idx].diff;
              return d === 0 ? 'Even (us = them)' : d > 0 ? `Up ${d} player${d > 1 ? 's' : ''}` : `Down ${Math.abs(d)} player${Math.abs(d) > 1 ? 's' : ''}`;
            },
            label: (item) => {
              const idx = item.dataIndex;
              const gd = goalDiff[idx] >= 0 ? `+${goalDiff[idx]}` : String(goalDiff[idx]);
              return [`Win%: ${winPcts[idx]}%`, `Games: ${games[idx]}`, `Avg goal diff: ${gd}`];
            }
          }
        }
      },
      scales: {
        x: {
          min: 0, max: 100,
          grid: { color: '#333' },
          ticks: { color: '#888', callback: v => `${v}%` },
          title: { display: true, text: 'Win %', color: '#888' }
        },
        y: {
          grid: { color: '#333' },
          ticks: { color: '#ccc', font: { size: 13 } },
          title: { display: true, text: 'Us − Them', color: '#888' }
        }
      },
      animation: {
        onComplete: ({ chart }) => {
          // Print game count at end of each bar
          const ctx = chart.ctx;
          ctx.save();
          ctx.fillStyle = '#ccc';
          ctx.font = '11px sans-serif';
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          chart.data.datasets[0].data.forEach((val, i) => {
            const meta = chart.getDatasetMeta(0);
            const bar  = meta.data[i];
            if (!bar) return;
            const x = bar.x + 4;
            const y = bar.y;
            ctx.fillText(`${games[i]}g`, x, y);
          });
          ctx.restore();
        }
      }
    }
  });

  // Size chart height to number of bars (min 200px)
  canvas.parentElement.style.height = `${Math.max(200, rows.length * 44)}px`;
}

// ── Wilson CI lower bound ──────────────────────────────────────────────────
function wilsonLower(wins, n, z = 1.96) {
  if (n === 0) return 0;
  const p = wins / n, z2 = z * z;
  return Math.max(0, (p + z2 / (2 * n) - z * Math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / (1 + z2 / n));
}

// ── Team comp ─────────────────────────────────────────────────────────────
function loadTeamComp() {
  const { clauses, params } = buildFilters('m');
  const where = ['f.club_id = 127516', 'dp.is_current = 1', ...clauses].join(' AND ');
  const rows = query(`
    SELECT f.match_key, dp.player_name,
           ftm.is_win, ftm.is_loss, ftm.is_tie, ftm.goals_for, ftm.goals_against
    FROM fact_player_match f
    JOIN dim_player      dp  ON dp.player_key  = f.player_key
    JOIN dim_match       m   ON m.match_key    = f.match_key
    JOIN fact_team_match ftm ON ftm.match_key  = f.match_key AND ftm.club_id = f.club_id
    WHERE ${where}
    ORDER BY f.match_key, dp.player_name
  `, params);

  const matchMap = {};
  for (const r of rows) {
    if (!matchMap[r.match_key])
      matchMap[r.match_key] = { players: [], is_win: r.is_win, is_loss: r.is_loss, is_tie: r.is_tie, goals_for: r.goals_for, goals_against: r.goals_against };
    matchMap[r.match_key].players.push(r.player_name);
  }

  const lineupMap = {};
  for (const data of Object.values(matchMap)) {
    const lineup = [...new Set(data.players)].sort().join(', ');
    if (!lineupMap[lineup]) lineupMap[lineup] = { games: 0, wins: 0, losses: 0, ties: 0, gf: 0, ga: 0 };
    lineupMap[lineup].games++;
    lineupMap[lineup].wins   += data.is_win  || 0;
    lineupMap[lineup].losses += data.is_loss || 0;
    lineupMap[lineup].ties   += data.is_tie  || 0;
    lineupMap[lineup].gf     += data.goals_for;
    lineupMap[lineup].ga     += data.goals_against;
  }

  const comps = Object.entries(lineupMap)
    .filter(([, d]) => d.games >= 3)
    .sort(([, a], [, b]) => wilsonLower(b.wins, b.games) - wilsonLower(a.wins, a.games))
    .map(([lineup, d]) => ({
      lineup,
      games:    d.games,
      wins:     d.wins,
      losses:   d.losses,
      ties:     d.ties,
      win_pct:  Math.round(d.wins / d.games * 100),
      avg_gf:   (d.gf / d.games).toFixed(1),
      avg_ga:   (d.ga / d.games).toFixed(1),
    }));

  renderTeamComp(comps);
}

function renderTeamComp(comps) {
  const container = document.getElementById('teamcomp-container');
  if (!comps.length) {
    container.innerHTML = '<p class="empty">Not enough data yet (need ≥3 games with the same lineup).</p>';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>Lineup</th><th>Record</th><th>Win% (CI-sorted)</th><th>GF/G</th><th>GA/G</th></tr></thead><tbody>';
  for (const c of comps) {
    const record = `${c.wins}W ${c.losses}L${c.ties > 0 ? ` ${c.ties}D` : ''}`;
    html += `<tr>
      <td data-label="Lineup" class="lineup-cell">${esc(c.lineup)}</td>
      <td data-label="Record">${record}</td>
      <td data-label="Win%">${c.win_pct}%</td>
      <td data-label="GF/G">${c.avg_gf}</td>
      <td data-label="GA/G">${c.avg_ga}</td>
    </tr>`;
  }
  html += '</tbody></table>';
  container.innerHTML = html;
}

// ── Per-player impact ─────────────────────────────────────────────────────
function loadPlayerImpact() {
  const { clauses, params } = buildFilters('m');
  const whereTeam   = ['ftm.club_id = 127516', ...clauses].join(' AND ');
  const wherePlayer = ['fpm.club_id = 127516', 'dp.is_current = 1', ...clauses].join(' AND ');

  const totals = query(`
    SELECT COUNT(*) AS total_games, SUM(ftm.is_win) AS total_wins
    FROM fact_team_match ftm
    JOIN dim_match m ON m.match_key = ftm.match_key
    WHERE ${whereTeam}
  `, params);
  if (!totals.length) return;
  const { total_games, total_wins } = totals[0];

  const playerRows = query(`
    SELECT dp.player_name,
           COUNT(*)           AS games_with,
           SUM(ftm.is_win)    AS wins_with
    FROM fact_player_match fpm
    JOIN dim_player      dp  ON dp.player_key = fpm.player_key
    JOIN fact_team_match ftm ON ftm.match_key = fpm.match_key AND ftm.club_id = fpm.club_id
    JOIN dim_match       m   ON m.match_key   = fpm.match_key
    WHERE ${wherePlayer}
    GROUP BY dp.player_name
  `, params);

  const impacts = playerRows
    .map(r => {
      const gw = r.games_with, ww = r.wins_with;
      const gwo = total_games - gw, wwo = total_wins - ww;
      const pctWith    = gw  > 0 ? Math.round(ww  / gw  * 100) : null;
      const pctWithout = gwo > 0 ? Math.round(wwo / gwo * 100) : null;
      return { name: r.player_name, games_with: gw, pct_with: pctWith, pct_without: pctWithout, wins_with: ww, games_without: gwo };
    })
    .filter(r => r.games_with >= 2)
    .sort((a, b) => wilsonLower(b.wins_with, b.games_with) - wilsonLower(a.wins_with, a.games_with));

  renderPlayerImpact(impacts);
}

function renderPlayerImpact(impacts) {
  const container = document.getElementById('playerimpact-container');
  if (!impacts.length) { container.innerHTML = '<p class="empty">Not enough data.</p>'; return; }
  let html = '<table class="data-table"><thead><tr><th>Player</th><th>Games</th><th>Win% with</th><th>Win% without</th><th>Diff</th></tr></thead><tbody>';
  for (const r of impacts) {
    const diff = (r.pct_with !== null && r.pct_without !== null) ? r.pct_with - r.pct_without : null;
    const diffStr  = diff === null ? '—' : (diff >= 0 ? `+${diff}` : String(diff));
    const diffCls  = diff === null ? '' : diff > 0 ? 'positive-diff' : diff < 0 ? 'negative-diff' : '';
    const withoutStr = r.pct_without !== null ? `${r.pct_without}% (${r.games_without}g)` : `— (${r.games_without}g)`;
    html += `<tr>
      <td data-label="Player">${esc(r.name)}</td>
      <td data-label="Games">${r.games_with}</td>
      <td data-label="Win% with">${r.pct_with !== null ? r.pct_with + '%' : '—'}</td>
      <td data-label="Win% without">${withoutStr}</td>
      <td data-label="Diff" class="${diffCls}">${diffStr}</td>
    </tr>`;
  }
  html += '</tbody></table>';
  container.innerHTML = html;
}

// ── Percentile rank utility ───────────────────────────────────────────────
function percentileRank(arr, val) {
  const below = arr.filter(v => v < val).length;
  return arr.length > 1 ? Math.round(below / (arr.length - 1) * 100) : 50;
}

// ── Player form ───────────────────────────────────────────────────────────
function loadPlayerForm() {
  const { clauses, params } = buildFilters('m');
  const where = ['f.club_id = 127516', 'dp.is_current = 1', ...clauses].join(' AND ');

  // Aggregate stats per player (for percentile bars)
  const aggRows = query(`
    SELECT dp.player_name, da.archetype_name, da.archetype_category,
           COUNT(*)                        AS games,
           ROUND(AVG(f.passes_made), 1)    AS avg_passes,
           ROUND(AVG(f.shots), 1)          AS avg_shots,
           ROUND(AVG(f.tackles_made), 1)   AS avg_tackles
    FROM fact_player_match f
    JOIN dim_player    dp ON dp.player_key   = f.player_key
    JOIN dim_archetype da ON da.archetype_id = f.archetype_id
    JOIN dim_match     m  ON m.match_key     = f.match_key
    WHERE ${where}
    GROUP BY dp.player_name, da.archetype_name, da.archetype_category
    ORDER BY dp.player_name, da.archetype_name
  `, params);

  // Per-game trend data for sparklines (no archetype join needed)
  const { clauses: tClauses, params: tParams } = buildFilters('m');
  const tWhere = ['f.club_id = 127516', 'dp.is_current = 1', ...tClauses].join(' AND ');
  const trendRows = query(`
    SELECT dp.player_name, m.match_timestamp,
           f.passes_made, f.shots, f.tackles_made
    FROM fact_player_match f
    JOIN dim_player dp ON dp.player_key = f.player_key
    JOIN dim_match  m  ON m.match_key   = f.match_key
    WHERE ${tWhere}
    ORDER BY dp.player_name, m.match_timestamp ASC
  `, tParams);

  renderPlayerForm(aggRows, trendRows);
}

function renderPlayerForm(aggRows, trendRows) {
  const container = document.getElementById('form-container');
  if (!aggRows.length) { container.innerHTML = '<p class="empty">No data available.</p>'; return; }

  // Destroy old form + trend charts
  for (const key of Object.keys(charts).filter(k => k.startsWith('form-') || k.startsWith('trend-'))) {
    charts[key].destroy();
    delete charts[key];
  }

  // Group agg rows by player (handles multiple archetypes)
  const playerMap = {};
  for (const r of aggRows) {
    if (!playerMap[r.player_name]) playerMap[r.player_name] = [];
    playerMap[r.player_name].push(r);
  }

  // Group trend rows by player
  const trendMap = {};
  for (const r of trendRows) {
    if (!trendMap[r.player_name]) trendMap[r.player_name] = [];
    trendMap[r.player_name].push(r);
  }

  // Build percentile arrays across all players (using primary archetype per player)
  const primaries = Object.entries(playerMap).map(([, arcs]) => arcs.reduce((a, b) => a.games >= b.games ? a : b));
  const allPasses  = primaries.map(p => p.avg_passes);
  const allShots   = primaries.map(p => p.avg_shots);
  const allTackles = primaries.map(p => p.avg_tackles);

  let html = '<div class="form-grid">';
  for (const [player, archetypes] of Object.entries(playerMap)) {
    const id = sanitizeId(player);
    const totalGames = archetypes.reduce((s, a) => s + a.games, 0);
    const arcLabel   = archetypes.map(a => `${a.archetype_name} (${a.games}g)`).join(' / ');
    html += `<div class="form-card">
      <h4>${esc(player)}<span class="games-badge">${totalGames}g</span></h4>
      <p class="archetype-label">${esc(arcLabel)}</p>
      <div class="chart-container" style="height:140px"><canvas id="chart-form-${id}"></canvas></div>
      <div class="chart-container" style="height:90px;margin-top:6px"><canvas id="chart-trend-${id}"></canvas></div>
    </div>`;
  }
  html += '</div>';
  container.innerHTML = html;

  for (const [player, archetypes] of Object.entries(playerMap)) {
    const id      = sanitizeId(player);
    const primary = archetypes.reduce((a, b) => a.games >= b.games ? a : b);

    // Percentile bars
    const pctPasses  = percentileRank(allPasses,  primary.avg_passes);
    const pctShots   = percentileRank(allShots,   primary.avg_shots);
    const pctTackles = percentileRank(allTackles, primary.avg_tackles);

    const formCtx = document.getElementById(`chart-form-${id}`);
    if (formCtx) {
      charts[`form-${player}`] = new Chart(formCtx, {
        type: 'bar',
        data: {
          labels: ['Passes', 'Shots', 'Tackles'],
          datasets: [{
            label: 'Percentile vs teammates',
            data: [pctPasses, pctShots, pctTackles],
            backgroundColor: ['#2980b9', '#e74c3c', '#27ae60']
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                afterLabel: (item) => {
                  const raws = [primary.avg_passes, primary.avg_shots, primary.avg_tackles];
                  return `Raw avg: ${raws[item.dataIndex]}/game`;
                }
              }
            }
          },
          scales: {
            y: { min: 0, max: 100, grid: { color: '#333' }, ticks: { color: '#888', callback: v => `${v}%` } },
            x: { grid: { color: '#333' }, ticks: { color: '#ccc' } }
          }
        }
      });
    }

    // Trend sparkline
    const trendCtx = document.getElementById(`chart-trend-${id}`);
    const games = trendMap[player] ?? [];
    if (trendCtx && games.length) {
      const labels = games.map((_, i) => `G${i + 1}`);
      charts[`trend-${player}`] = new Chart(trendCtx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            { label: 'Passes', data: games.map(g => g.passes_made), borderColor: '#2980b9', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2, spanGaps: true },
            { label: 'Shots',  data: games.map(g => g.shots),       borderColor: '#e74c3c', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2, spanGaps: true },
            { label: 'Tackles',data: games.map(g => g.tackles_made),borderColor: '#27ae60', backgroundColor: 'transparent', tension: 0.3, pointRadius: 2, spanGaps: true },
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: true, position: 'top', labels: { color: '#888', boxWidth: 10, font: { size: 10 }, padding: 6 } }
          },
          scales: {
            y: { beginAtZero: true, grid: { color: '#222' }, ticks: { color: '#666', font: { size: 9 } } },
            x: { grid: { display: false }, ticks: { color: '#666', font: { size: 9 }, maxTicksLimit: 8 } }
          }
        }
      });
    }
  }
}

// ── Tab switching ─────────────────────────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
    b.setAttribute('aria-selected', b.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-content').forEach(c =>
    c.classList.toggle('active', c.id === `tab-${tab}`)
  );
  if (tab === 'analysis' && !analysisLoaded) {
    analysisLoaded = true;
    loadGkImpact();
    loadNvN();
    loadTeamComp();
    loadPlayerImpact();
    loadPlayerForm();
  }
}

// ── Refresh all loaded dashboards ─────────────────────────────────────────
function refreshAll() {
  activeMatchKey = null;
  document.getElementById('match-detail').classList.add('hidden');
  loadLeaderboard();
  loadResults();
  if (activePlayerCard) loadPlayerCard(activePlayerCard);
  if (analysisLoaded) {
    loadGkImpact();
    loadNvN();
    loadTeamComp();
    loadPlayerImpact();
    loadPlayerForm();
  }
}

// ── Utils ─────────────────────────────────────────────────────────────────
function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function sanitizeId(str) { return str.replace(/[^a-z0-9]/gi, '_'); }

function showError(msg) {
  document.getElementById('loading-overlay').classList.add('hidden');
  document.getElementById('error-overlay').classList.remove('hidden');
  document.getElementById('error-message').textContent = msg;
}

// ── Init ──────────────────────────────────────────────────────────────────
async function init() {
  try {
    await initDb();
    loadFreshness();
    loadSeasonOptions();
    loadLeaderboard();
    loadResults();
    document.getElementById('loading-overlay').classList.add('hidden');
    document.getElementById('controls').classList.remove('hidden');
  } catch (e) {
    showError(e.message);
  }
}

// ── Event listeners ───────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn =>
  btn.addEventListener('click', () => switchTab(btn.dataset.tab))
);

document.getElementById('season-select').addEventListener('change', e => {
  STATE.season = e.target.value ? Number(e.target.value) : null;
  refreshAll();
});

document.querySelectorAll('.toggle-btn').forEach(btn =>
  btn.addEventListener('click', () => {
    document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    STATE.competition = btn.dataset.comp;
    refreshAll();
  })
);

init();
