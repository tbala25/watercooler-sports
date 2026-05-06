'use strict';

// ── Data file paths ───────────────────────────────────────────
const DATA_FILES = {
  leagueScores:    '../data/daily/league_scores.json',
  nonLeagueScores: '../data/daily/non_league_scores.json',
  standingsEast:   '../data/daily/standings_east.json',
  standingsWest:   '../data/daily/standings_west.json',
  topEarners:      '../data/daily/top_earners.json',
  youngPlayers:    '../data/daily/young_players.json',
  meta:            '../data/daily/meta.json',
};

// ── Helpers ───────────────────────────────────────────────────
function el(tag, className, textContent) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (textContent != null) e.textContent = textContent;
  return e;
}

function td(className, text) {
  const cell = el('td', className, text);
  return cell;
}

function unavailable(targetId, message) {
  const target = document.getElementById(targetId);
  if (!target) return;
  const tr = el('tr');
  const cell = el('td', 'data-unavailable', message || 'Data unavailable');
  cell.colSpan = target.closest('table')?.querySelector('thead tr')?.children.length || 1;
  tr.appendChild(cell);
  target.appendChild(tr);
}

function formatKickoff(utcStr) {
  if (!utcStr) return '';
  try {
    const d = new Date(utcStr);
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    let hours = d.getHours();
    const ampm = hours >= 12 ? 'p' : 'a';
    hours = hours % 12 || 12;
    const mins = d.getMinutes();
    const minStr = mins > 0 ? `:${mins.toString().padStart(2, '0')}` : '';
    return `${days[d.getDay()]} ${hours}${minStr}${ampm}`;
  } catch {
    return '';
  }
}

function formatXg(home, away) {
  if (home == null || away == null) return '';
  return `${Number(home).toFixed(1)}\u2013${Number(away).toFixed(1)}`;
}

function formatStat(home, away) {
  if (home == null || away == null) return '';
  return `${home}\u2013${away}`;
}

function formatGd(val) {
  if (val == null) return '';
  const num = Number(val);
  if (num > 0) return `+${num}`;
  return String(num);
}

function formatXgd(val) {
  if (val == null) return '';
  const num = Number(val);
  if (num > 0) return `+${num.toFixed(1)}`;
  return num.toFixed(1);
}

// ── Fetch all data ────────────────────────────────────────────
async function fetchAllData() {
  const entries = Object.entries(DATA_FILES);
  const results = await Promise.allSettled(
    entries.map(([, url]) => fetch(url).then(r => {
      if (!r.ok) throw new Error(`${r.status}`);
      return r.json();
    }))
  );

  const data = {};
  entries.forEach(([key], i) => {
    data[key] = results[i].status === 'fulfilled' ? results[i].value : null;
  });
  return data;
}

// ── Render: Masthead ──────────────────────────────────────────
function renderMasthead(meta) {
  const dateEl = document.getElementById('mast-date');
  const dotsEl = document.getElementById('source-dots');
  const footerEl = document.getElementById('footer-sources');

  if (!meta) {
    dateEl.textContent = new Date().toLocaleDateString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
    return;
  }

  // Date display
  const updateTime = meta.last_updated_et || meta.last_updated;
  if (updateTime) {
    const d = new Date(updateTime);
    const dateStr = d.toLocaleDateString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
    const matchday = meta.current_matchday
      ? `Matchday ${meta.current_matchday}`
      : '';
    dateEl.innerHTML = `${dateStr}${matchday ? ' &nbsp;&middot;&nbsp; ' + matchday : ''}`;
  }

  // Source status dots
  const sourceNames = { capology: 'Capology', fotmob: 'FotMob', transfermarkt: 'TM', sofascore: 'SofaScore' };
  dotsEl.innerHTML = '';
  for (const [key, label] of Object.entries(sourceNames)) {
    const src = meta.sources?.[key];
    const status = src?.status === 'ok' ? 'ok' : 'err';
    const ariaLabel = `${label}: ${status === 'ok' ? 'data current' : 'data unavailable'}`;
    const dot = el('span', `dot ${status}`, label);
    dot.setAttribute('aria-label', ariaLabel);
    dotsEl.appendChild(dot);
  }

  // Footer update time
  if (updateTime && footerEl) {
    try {
      const d = new Date(updateTime);
      const timeStr = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true, timeZoneName: 'short' });
      footerEl.textContent = `Capology \u00b7 FotMob \u00b7 Transfermarkt \u00b7 SofaScore \u00b7 Updated ${timeStr}`;
    } catch { /* keep default */ }
  }
}

// ── Render: League Results (Band 1 left) ──────────────────────
function renderLeagueResults(matches) {
  const body = document.getElementById('league-results-body');
  if (!body) return;
  body.innerHTML = '';

  if (!matches || !Array.isArray(matches)) {
    unavailable('league-results-body');
    return;
  }

  const ft = matches.filter(m => m.status === 'FT');
  if (ft.length === 0) {
    unavailable('league-results-body', 'No completed matches');
    return;
  }

  // Update section label with matchday
  const label = document.getElementById('league-label');
  const maxMatchday = Math.max(...ft.map(m => m.matchday || 0));
  if (label && maxMatchday > 0) {
    label.textContent = `League — Matchday ${maxMatchday} results`;
  }

  ft.forEach((m, i) => {
    const tr = el('tr');
    if ((i + 1) % 3 === 0) tr.className = 'ledger';

    const confRankHome = m.home_conf && m.home_conf_rank
      ? `${m.home_conf}${m.home_conf_rank}` : '';
    const confRankAway = m.away_conf && m.away_conf_rank
      ? `${m.away_conf}${m.away_conf_rank}` : '';

    tr.appendChild(td('hr', confRankHome));
    tr.appendChild(td('hm', m.home_abbr || ''));
    tr.appendChild(td('sc', `${m.home_score ?? ''} \u2013 ${m.away_score ?? ''}`));
    tr.appendChild(td('aw', m.away_abbr || ''));
    tr.appendChild(td('ar', confRankAway));
    tr.appendChild(td('xg', formatXg(m.home_xg, m.away_xg)));
    tr.appendChild(td('sot', formatStat(m.home_shots_on_target, m.away_shots_on_target)));
    tr.appendChild(td('ps', formatStat(m.home_possession, m.away_possession)));
    tr.appendChild(td('hl', m.highlight || ''));

    body.appendChild(tr);
  });
}

// ── Render: Non-League Results (Band 1 right) ─────────────────
function renderNonLeagueResults(matches) {
  const body = document.getElementById('non-league-results-body');
  if (!body) return;
  body.innerHTML = '';

  if (!matches || !Array.isArray(matches)) {
    unavailable('non-league-results-body');
    return;
  }

  const ft = matches.filter(m => m.status === 'FT');
  if (ft.length === 0) {
    unavailable('non-league-results-body', 'No non-league results');
    return;
  }

  // Group by competition + round
  const groups = {};
  ft.forEach(m => {
    const key = `${m.competition || 'Other'}${m.round ? ' \u00b7 ' + m.round : ''}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(m);
  });

  for (const [groupLabel, groupMatches] of Object.entries(groups)) {
    // Competition subheader
    const shTr = el('tr', 'sh');
    const shTd = el('td', null, groupLabel);
    shTd.colSpan = 3;
    shTr.appendChild(shTd);
    body.appendChild(shTr);

    groupMatches.forEach(m => {
      // Match row
      const tr = el('tr');
      tr.appendChild(td('tm', m.home_abbr || m.home_team || ''));
      tr.appendChild(td('sc', `${m.home_score ?? ''} \u2013 ${m.away_score ?? ''}`));
      tr.appendChild(td('tm', m.away_team || m.away_abbr || ''));
      body.appendChild(tr);

      // Aggregate row
      if (m.aggregate_status) {
        const agTr = el('tr');
        const agTd = td('ag', m.aggregate_status);
        agTd.colSpan = 3;
        if (m.eliminated_team) {
          agTd.style.color = 'var(--red)';
        }
        agTr.appendChild(agTd);
        body.appendChild(agTr);
      }
    });
  }
}

// ── Render: Top Earners (Band 2 left) ─────────────────────────
function renderTopEarners(earners) {
  const body = document.getElementById('top-earners-body');
  if (!body) return;
  body.innerHTML = '';

  if (!earners || !Array.isArray(earners) || earners.length === 0) {
    unavailable('top-earners-body');
    return;
  }

  earners.forEach((p, i) => {
    const tr = el('tr');

    // Classes
    const classes = [];
    if (p.zero_ga) classes.push('under');
    if ((i + 1) % 3 === 0) classes.push('ledger');
    if (classes.length) tr.className = classes.join(' ');

    // Player name with DP badge
    const nmTd = el('td');
    nmTd.className = 'nm';
    nmTd.textContent = p.player || '';
    if (p.is_designated_player) {
      const badge = el('span', 'dp-b', 'DP');
      nmTd.appendChild(badge);
    }
    tr.appendChild(nmTd);

    tr.appendChild(td('cl', p.club_abbr || ''));
    tr.appendChild(td('po', p.position || ''));

    const salTd = td('sal', p.annual_salary_display || '');
    tr.appendChild(salTd);

    tr.appendChild(td(null, String(p.gp ?? '')));
    tr.appendChild(td(null, String(p.avg_minutes ?? '')));
    tr.appendChild(td(null, (p.goals_per90 ?? '').toFixed?.(2) ?? String(p.goals_per90 ?? '')));
    tr.appendChild(td(null, (p.assists_per90 ?? '').toFixed?.(2) ?? String(p.assists_per90 ?? '')));
    tr.appendChild(td(null, (p.ga_per90 ?? '').toFixed?.(2) ?? String(p.ga_per90 ?? '')));
    tr.appendChild(td(null, (p.xgxa_per90 ?? '').toFixed?.(2) ?? String(p.xgxa_per90 ?? '')));

    body.appendChild(tr);
  });
}

// ── Render: Young Players (Band 2 right) ──────────────────────
function renderYoungPlayers(players) {
  const body = document.getElementById('young-players-body');
  if (!body) return;
  body.innerHTML = '';

  if (!players || !Array.isArray(players) || players.length === 0) {
    unavailable('young-players-body');
    return;
  }

  players.forEach((p, i) => {
    const tr = el('tr');
    if ((i + 1) % 3 === 0) tr.className = 'ledger';

    // Player name with HOT badge
    const nmTd = el('td');
    nmTd.className = 'nm';
    nmTd.textContent = p.player || '';
    if (p.hot_streak) {
      const badge = el('span', 'hot-b', 'HOT');
      nmTd.appendChild(badge);
    }
    tr.appendChild(nmTd);

    tr.appendChild(td('cl', p.club_abbr || ''));
    tr.appendChild(td('po', p.position || ''));
    tr.appendChild(td(null, String(p.age ?? '')));
    tr.appendChild(td(null, String(p.gp ?? '')));
    tr.appendChild(td(null, String(p.avg_minutes ?? '')));
    tr.appendChild(td(null, (p.goals_per90 ?? '').toFixed?.(2) ?? String(p.goals_per90 ?? '')));
    tr.appendChild(td(null, (p.assists_per90 ?? '').toFixed?.(2) ?? String(p.assists_per90 ?? '')));
    tr.appendChild(td(null, (p.ga_per90 ?? '').toFixed?.(2) ?? String(p.ga_per90 ?? '')));
    tr.appendChild(td(null, (p.xgxa_per90 ?? '').toFixed?.(2) ?? String(p.xgxa_per90 ?? '')));

    body.appendChild(tr);
  });
}

// ── Render: Standings (Band 3) ────────────────────────────────
function renderStandings(data, bodyId) {
  const body = document.getElementById(bodyId);
  if (!body) return;
  body.innerHTML = '';

  if (!data || !Array.isArray(data) || data.length === 0) {
    unavailable(bodyId);
    return;
  }

  // Show positions 1-4 and 7-10 only, separator between 4 and 7
  const top4 = data.filter(t => t.position >= 1 && t.position <= 4);
  const bubble = data.filter(t => t.position >= 7 && t.position <= 10);

  top4.forEach(t => {
    const tr = el('tr', 'po');
    tr.appendChild(td(null, String(t.position)));
    tr.appendChild(td(null, t.club_abbr || ''));
    tr.appendChild(td(null, String(t.gp ?? '')));
    tr.appendChild(td(null, String(t.points ?? '')));
    tr.appendChild(td(null, formatGd(t.goal_diff)));

    const xgdTd = td(null, formatXgd(t.xgd));
    if (t.xgd != null) {
      xgdTd.className = Number(t.xgd) >= 0 ? 'xp' : 'xn';
    }
    tr.appendChild(xgdTd);
    body.appendChild(tr);
  });

  // Separator row
  if (top4.length > 0 && bubble.length > 0) {
    const sepTr = el('tr');
    const sepTd = el('td');
    sepTd.colSpan = 6;
    const sepDiv = el('div', 'po-sep');
    sepTd.appendChild(sepDiv);
    sepTr.appendChild(sepTd);
    body.appendChild(sepTr);
  }

  bubble.forEach(t => {
    const tr = el('tr', 'bb');
    tr.appendChild(td(null, String(t.position)));
    tr.appendChild(td(null, t.club_abbr || ''));
    tr.appendChild(td(null, String(t.gp ?? '')));
    tr.appendChild(td(null, String(t.points ?? '')));
    tr.appendChild(td(null, formatGd(t.goal_diff)));

    const xgdTd = td(null, formatXgd(t.xgd));
    if (t.xgd != null) {
      xgdTd.className = Number(t.xgd) >= 0 ? 'xp' : 'xn';
    }
    tr.appendChild(xgdTd);
    body.appendChild(tr);
  });
}

// ── Render: Upcoming League (Band 4 left) ─────────────────────
function renderUpcomingLeague(matches) {
  const body = document.getElementById('upcoming-league-body');
  if (!body) return;
  body.innerHTML = '';

  if (!matches || !Array.isArray(matches)) {
    unavailable('upcoming-league-body');
    return;
  }

  const sch = matches.filter(m => m.status === 'SCH' || m.status === 'LIVE');
  if (sch.length === 0) {
    unavailable('upcoming-league-body', 'No upcoming fixtures');
    return;
  }

  // Update section label and filter to next matchday only
  const label = document.getElementById('upcoming-label');
  const matchdays = sch.filter(m => m.matchday > 0).map(m => m.matchday);
  const nextMatchday = matchdays.length > 0 ? Math.min(...matchdays) : 0;
  if (label && nextMatchday > 0) {
    label.textContent = `Upcoming — Matchday ${nextMatchday}`;
  }

  const visible = nextMatchday > 0 ? sch.filter(m => m.matchday === nextMatchday) : sch;

  visible.forEach(m => {
    const tr = el('tr');

    const confRankHome = m.home_conf && m.home_conf_rank
      ? `${m.home_conf}${m.home_conf_rank}` : '';
    const confRankAway = m.away_conf && m.away_conf_rank
      ? `${m.away_conf}${m.away_conf_rank}` : '';

    tr.appendChild(td('hr', confRankHome));
    tr.appendChild(td('hm', m.home_abbr || ''));
    tr.appendChild(td('sc', formatKickoff(m.kickoff_utc || m.kickoff_et)));
    tr.appendChild(td('aw', m.away_abbr || ''));
    tr.appendChild(td('ar', confRankAway));
    tr.appendChild(td('hl', m.matchup_headline || ''));

    body.appendChild(tr);
  });
}

// ── Render: Upcoming Non-League (Band 4 right) ────────────────
function renderUpcomingNonLeague(matches) {
  const body = document.getElementById('upcoming-non-league-body');
  if (!body) return;
  body.innerHTML = '';

  if (!matches || !Array.isArray(matches)) {
    unavailable('upcoming-non-league-body');
    return;
  }

  const sch = matches.filter(m => m.status === 'SCH' || m.status === 'LIVE');
  if (sch.length === 0) {
    unavailable('upcoming-non-league-body', 'No upcoming non-league');
    return;
  }

  sch.forEach(m => {
    const tr = el('tr');

    tr.appendChild(td('tm', m.home_abbr || m.home_team || ''));
    tr.appendChild(td('sc', formatKickoff(m.kickoff_utc || m.kickoff_et)));
    tr.appendChild(td('tm', m.away_team || m.away_abbr || ''));

    const parts = [m.competition_short, m.round];
    if (m.leg) parts.push(`Leg ${m.leg}`);
    const context = parts.filter(Boolean).join(' \u00b7 ');
    tr.appendChild(td('cx', context));

    body.appendChild(tr);
  });
}

// ── Main ──────────────────────────────────────────────────────
async function main() {
  const data = await fetchAllData();

  renderMasthead(data.meta);
  renderLeagueResults(data.leagueScores);
  renderNonLeagueResults(data.nonLeagueScores);
  renderTopEarners(data.topEarners);
  renderYoungPlayers(data.youngPlayers);
  renderStandings(data.standingsEast, 'standings-east-body');
  renderStandings(data.standingsWest, 'standings-west-body');
  renderUpcomingLeague(data.leagueScores);
  renderUpcomingNonLeague(data.nonLeagueScores);
}

document.addEventListener('DOMContentLoaded', main);
