// sidebar.js — injects sidebar. Load AFTER api.js
document.addEventListener('DOMContentLoaded', () => {
  const user  = Auth.getUser();
  const tier  = Auth.getTier();
  const cfg   = getTierConfig();

  const tierColors = { free:'#64748b', starter:'#3b82f6', pro:'#22c55e', premium:'#f59e0b' };
  const tc = tierColors[tier] || '#64748b';
  const tierLabel = (cfg.label || tier).toUpperCase();

  // Feature-gated nav links
  const newsLink    = `<a class="nav-link${isFeatureAllowed('football_news') ? '' : ' nav-locked'}" href="${isFeatureAllowed('football_news') ? 'news.html' : 'pricing.html'}"><span class="nav-icon">📰</span> Football News${isFeatureAllowed('football_news') ? '' : ' <span class="lock-icon">🔒</span>'}</a>`;
  const videosLink  = `<a class="nav-link${isFeatureAllowed('goal_videos') ? '' : ' nav-locked'}" href="${isFeatureAllowed('goal_videos') ? 'videos.html' : 'pricing.html'}"><span class="nav-icon">🎥</span> Goal Videos${isFeatureAllowed('goal_videos') ? '' : ' <span class="lock-icon">🔒</span>'}</a>`;
  const schedLink   = `<a class="nav-link${isFeatureAllowed('schedule') ? '' : ' nav-locked'}" href="${isFeatureAllowed('schedule') ? 'schedule.html' : 'pricing.html'}"><span class="nav-icon">📅</span> Schedule${isFeatureAllowed('schedule') ? '' : ' <span class="lock-icon">🔒</span>'}</a>`;
  const analyticsLink = `<a class="nav-link${cfg.analytics ? '' : ' nav-locked'}" href="${cfg.analytics ? 'analytics.html' : 'pricing.html'}"><span class="nav-icon">📈</span> Analytics${cfg.analytics ? '' : ' <span class="lock-icon">🔒</span>'}</a>`;
  const affiliateLink = `<a class="nav-link${cfg.affiliate === 'own' ? '' : ' nav-locked'}" href="${cfg.affiliate === 'own' ? 'affiliate.html' : 'pricing.html'}"><span class="nav-icon">🔗</span> Affiliate${cfg.affiliate === 'own' ? '' : ' <span class="lock-icon">🔒</span>'}</a>`;
  const adminLink   = Auth.isAdmin() ? `<a class="nav-link" href="admin.html"><span class="nav-icon">🛡️</span> Admin Panel</a>` : '';

  const sidebar = `
  <aside class="sidebar">
    <div class="sidebar-logo">⚽ <span>t3n28</span>-football</div>

    <div style="padding:10px 12px;border-bottom:1px solid var(--border);">
      <div style="font-size:12px;font-weight:600;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${user?.name || 'User'}</div>
      <div style="font-size:10px;color:var(--muted);margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${user?.email || ''}</div>
      <div style="margin-top:6px;">
        <span style="background:${tc}22;color:${tc};border:1px solid ${tc}44;padding:2px 8px;border-radius:4px;font-size:9px;font-weight:700;letter-spacing:1px;">${tierLabel}</span>
        ${tier !== 'premium' ? `<a href="pricing.html" style="font-size:9px;color:var(--muted);text-decoration:none;margin-left:6px;">Upgrade →</a>` : ''}
      </div>
    </div>

    <nav>
      <div class="nav-label">Main</div>
      <a class="nav-link" href="dashboard.html"><span class="nav-icon">📊</span> Dashboard</a>
      <a class="nav-link" href="live.html"><span class="nav-icon">🔴</span> Live Matches</a>
      <a class="nav-link" href="standings.html"><span class="nav-icon">📋</span> Standings</a>
      <a class="nav-link" href="messages.html"><span class="nav-icon">💬</span> Messages</a>
      ${schedLink}

      <div class="nav-label">Content</div>
      ${newsLink}
      ${videosLink}

      <div class="nav-label">Config</div>
      <a class="nav-link" href="channels.html"><span class="nav-icon">📡</span> Channels</a>
      <a class="nav-link" href="leagues.html"><span class="nav-icon">🏆</span> Leagues</a>
      ${affiliateLink}

      <div class="nav-label">Account</div>
      ${analyticsLink}
      <a class="nav-link" href="settings.html"><span class="nav-icon">⚙️</span> Settings</a>
      <a class="nav-link" href="notifications.html" style="position:relative;">
        <span class="nav-icon">🔔</span> Notifications
        <span id="notif-badge" style="display:none;position:absolute;right:8px;top:50%;transform:translateY(-50%);background:var(--red);color:#fff;border-radius:50%;width:16px;height:16px;font-size:9px;align-items:center;justify-content:center;font-weight:700;"></span>
      </a>
      ${adminLink}
    </nav>

    <div style="padding:12px 16px;border-top:1px solid var(--border);">
      <button onclick="authLogout()" style="width:100%;background:transparent;border:1px solid var(--border);color:var(--muted);border-radius:6px;padding:7px;font-size:12px;cursor:pointer;font-family:'Inter',sans-serif;" onmouseover="this.style.borderColor='var(--red)';this.style.color='var(--red)'" onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--muted)'">
        Sign Out
      </button>
    </div>

    <div class="sidebar-bottom">v2.0 · t3n28-football</div>
  </aside>`;

  document.body.insertAdjacentHTML('afterbegin', sidebar);

  // Active link
  const path = window.location.pathname.split('/').pop() || 'dashboard.html';
  document.querySelectorAll('.nav-link').forEach(l => {
    if (l.getAttribute('href') === path) l.classList.add('active');
  });

  // Notification badge
  loadNotifBadge();
});
