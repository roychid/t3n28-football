// ─────────────────────────────────────────────────────────────
//  api.js — t3n28-football
//  All backend communication. Replaces firebase.js + api-cache.js
//  Set API_BASE to your Render URL after deploying.
// ─────────────────────────────────────────────────────────────

const API_BASE = 'https://t3n28-football-api.onrender.com'; // ← update after deploy

// ── Token storage ─────────────────────────────────────────────
const Auth = {
  getToken:  ()      => localStorage.getItem('t3n28_token'),
  setToken:  (t)     => localStorage.setItem('t3n28_token', t),
  getUser:   ()      => { try { return JSON.parse(localStorage.getItem('t3n28_user')); } catch { return null; } },
  setUser:   (u)     => localStorage.setItem('t3n28_user', JSON.stringify(u)),
  clear:     ()      => { localStorage.removeItem('t3n28_token'); localStorage.removeItem('t3n28_user'); },
  isLoggedIn:()      => !!localStorage.getItem('t3n28_token'),
  getTier:   ()      => Auth.getUser()?.tier || 'free',
  isAdmin:   ()      => Auth.getUser()?.is_admin === true,
};

// ── HTTP helpers ───────────────────────────────────────────────
async function _req(method, path, body = null, auth = true) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = Auth.getToken();
    if (token) headers['Authorization'] = 'Bearer ' + token;
  }
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const r = await fetch(API_BASE + path, opts);

  if (r.status === 401) {
    Auth.clear();
    if (!window.location.pathname.includes('login') && !window.location.pathname.includes('register')) {
      window.location.href = 'login.html';
    }
    throw new Error('Session expired — please log in again');
  }

  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || `Error ${r.status}`);
  return data;
}

const api = {
  get:    (path)       => _req('GET',    path),
  post:   (path, body) => _req('POST',   path, body),
  delete: (path)       => _req('DELETE', path),
};

// ── Auth calls ────────────────────────────────────────────────
async function authRegister(email, password, name, whatsapp, interestedTier) {
  const data = await _req('POST', '/auth/register', {
    email, password, name, whatsapp: whatsapp || '', interested_tier: interestedTier || 'free'
  }, false);
  _saveSession(data);
  return data;
}

async function authLogin(email, password) {
  const data = await _req('POST', '/auth/login', { email, password }, false);
  _saveSession(data);
  return data;
}

async function authLogout() {
  Auth.clear();
  window.location.href = 'login.html';
}

async function refreshMe() {
  const data = await api.get('/auth/me');
  Auth.setUser(data);
  return data;
}

function _saveSession(data) {
  Auth.setToken(data.token);
  Auth.setUser(data);
}

// ── Football API (proxied through backend) ────────────────────
async function footballGet(endpoint) {
  // endpoint like: /fixtures?live=all
  const path = '/football' + endpoint;
  const data = await api.get(path);

  // Show usage warning if near/over limit
  if (data.warn || data.over_limit) {
    _showUsageWarning(data.usage, data.over_limit);
  }

  // Update topbar pill
  _updateUsagePill(data.usage);

  return data.data; // return the actual football API response
}

// ── Usage UI ──────────────────────────────────────────────────
function _updateUsagePill(usage) {
  if (!usage) return;
  const el    = document.getElementById('usage-pill');
  if (!el) return;
  const { count, limit } = usage;
  const pct   = count / limit;
  const color = pct >= 1 ? 'var(--red)' : pct >= 0.8 ? 'var(--yellow)' : 'var(--muted)';
  el.innerHTML = `<span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:${color};" title="API requests used today">${count}/${limit} req</span>`;
}

function _showUsageWarning(usage, isOver) {
  const old = document.getElementById('usage-warn-banner');
  if (old) old.remove();

  const { count, limit } = usage;
  const remaining = Math.max(0, limit - count);
  const color = isOver ? 'var(--red)' : 'var(--yellow)';
  const tier  = Auth.getTier();

  const b = document.createElement('div');
  b.id    = 'usage-warn-banner';
  b.style.cssText = `position:fixed;bottom:72px;right:20px;background:var(--surface);
    border:1px solid ${color};border-radius:8px;padding:12px 16px;z-index:9997;
    max-width:310px;box-shadow:0 4px 20px #0007;font-size:12px;`;
  b.innerHTML = isOver
    ? `<div style="display:flex;gap:10px;align-items:flex-start;">
        <span style="font-size:18px;">🚫</span>
        <div>
          <div style="font-weight:700;color:var(--red);margin-bottom:3px;">Daily limit reached (${limit} requests)</div>
          <div style="color:var(--muted);line-height:1.5;">Showing cached data. Resets midnight UTC.</div>
          <div style="margin-top:8px;display:flex;gap:6px;">
            <a href="pricing.html" class="btn btn-primary btn-sm">Upgrade →</a>
            <button onclick="document.getElementById('usage-warn-banner').remove()" class="btn btn-secondary btn-sm">✕</button>
          </div>
        </div>
      </div>`
    : `<div style="display:flex;gap:10px;align-items:flex-start;">
        <span style="font-size:18px;">⚠️</span>
        <div>
          <div style="font-weight:700;color:var(--yellow);margin-bottom:3px;">Only ${remaining} requests left today</div>
          <div style="color:var(--muted);line-height:1.5;">${count} of ${limit} used on ${tier} plan.</div>
          <div style="margin-top:8px;display:flex;gap:6px;">
            <a href="pricing.html" class="btn btn-sm" style="background:var(--yellow);color:#000;">Upgrade →</a>
            <button onclick="document.getElementById('usage-warn-banner').remove()" class="btn btn-secondary btn-sm">✕</button>
          </div>
        </div>
      </div>`;
  document.body.appendChild(b);
  if (!isOver) setTimeout(() => b && b.remove(), 8000);
}

async function loadUsagePill() {
  try {
    const u     = await api.get('/usage/me');
    _updateUsagePill(u);
    return u;
  } catch(e) { return null; }
}

// ── Tier helpers ──────────────────────────────────────────────
const TOP15_IDS = Auth.getUser()?.top15_ids ||
  [39,140,135,78,61,2,3,88,94,144,253,45,848,4,1];

function canUseLeague(leagueId) {
  const tier = Auth.getTier();
  const user = Auth.getUser();
  const ids  = user?.top15_ids || TOP15_IDS;
  const cfg  = user?.tier_config || {};
  const lt   = cfg.league_type || 'non-top15';
  if (lt === 'all')      return true;
  if (lt === 'top15')    return ids.includes(leagueId);
  return !ids.includes(leagueId);
}

function getTierConfig() {
  return Auth.getUser()?.tier_config || {};
}

function isFeatureAllowed(feature) {
  const cfg = getTierConfig();
  return !!cfg[feature];
}

// ── localStorage DB (channels, leagues, posts, settings) ──────
const DB = {
  get:    k      => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set:    (k, v) => localStorage.setItem(k, JSON.stringify(v)),
  push:   (k, v) => { const a = DB.get(k)||[]; a.push({...v, id:Date.now()}); DB.set(k,a); return a; },
  remove: (k, id)=> { const a = (DB.get(k)||[]).filter(i=>i.id!==id); DB.set(k,a); return a; },
};

// ── Owner affiliate logic ─────────────────────────────────────
function getAffiliateLink() {
  const user = Auth.getUser();
  const cfg  = getTierConfig();
  if (cfg.affiliate === 'owner') return user?.owner_affiliate || 'https://t.me/t3n28football';
  const settings = DB.get('settings') || {};
  return settings.affiliateLink || '';
}

function applyAffiliate(text) {
  const cfg  = getTierConfig();
  if (cfg.affiliate !== 'owner') return text;
  const link = getAffiliateLink();
  if (!link) return text;
  return text + `\n\n🔗 ${link}`;
}

function applyWatermark(text) {
  const cfg = getTierConfig();
  if (!cfg.watermark) return text;
  return text + '\n\n— Powered by t3n28-football';
}

function applyAdornments(text) {
  return applyWatermark(applyAffiliate(text));
}

// ── Telegram send ─────────────────────────────────────────────
async function sendTelegram(botToken, chatId, text) {
  if (!isFeatureAllowed('telegram')) {
    throw new Error('Telegram is not available on your plan. Upgrade to Starter or higher.');
  }
  const r = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ chat_id: chatId, text: applyAdornments(text), parse_mode: 'HTML' }),
  });
  return r.json();
}

async function sendToAllChannels(text) {
  const channels = (DB.get('channels') || []).filter(c => c.type === 'telegram' && c.token && c.chatId);
  const cfg = getTierConfig();
  const max = cfg.channels || 0;
  const allowed = channels.slice(0, max);
  const results = [];
  for (const ch of allowed) {
    try {
      await sendTelegram(ch.token, ch.chatId, text);
      results.push({ channel: ch.name, ok: true });
    } catch(e) {
      results.push({ channel: ch.name, ok: false, error: e.message });
    }
  }
  return results;
}

// ── Toast & copy (shared UI helpers) ─────────────────────────
function toast(msg, type = 'success') {
  let el = document.getElementById('toast');
  if (!el) { el = document.createElement('div'); el.id='toast'; document.body.appendChild(el); }
  el.textContent = msg;
  el.style.borderColor = type === 'error' ? 'var(--red)' : 'var(--green)';
  el.style.color       = type === 'error' ? 'var(--red)' : 'var(--green)';
  el.classList.add('show');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3200);
}

function copyText(text, label = 'Copied!') {
  navigator.clipboard.writeText(text)
    .then(() => toast('📋 ' + label))
    .catch(() => {
      const ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); document.body.removeChild(ta);
      toast('📋 ' + label);
    });
}

function toggle(el) { el.classList.toggle('on'); }

// ── Guard: redirect to login if not authenticated ─────────────
function requireAuth() {
  if (!Auth.isLoggedIn()) {
    window.location.href = 'login.html';
    return false;
  }
  return true;
}

// ── Guard: redirect non-admins away from admin page ──────────
function requireAdminAuth() {
  if (!Auth.isLoggedIn()) { window.location.href = 'login.html'; return false; }
  if (!Auth.isAdmin())    { window.location.href = 'dashboard.html'; return false; }
  return true;
}

// ── Notifications badge ───────────────────────────────────────
async function loadNotifBadge() {
  try {
    const notifs = await api.get('/notifications');
    const unread = notifs.filter(n => !n.read).length;
    const badge  = document.getElementById('notif-badge');
    if (badge) {
      badge.textContent    = unread > 0 ? unread : '';
      badge.style.display  = unread > 0 ? 'flex' : 'none';
    }
  } catch(e) { /* non-fatal */ }
}
