/**
 * app.js — Core router, API client, utilities, and global state.
 */

// ─── API Base ───────────────────────────────────────────────
const API = {
  base: '/api',

  async get(path) {
    const res = await fetch(`${this.base}${path}`);
    if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
    return res.json();
  },

  async post(path, body) {
    const res = await fetch(`${this.base}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `POST ${path} → ${res.status}`);
    }
    return res.json();
  },

  async postForm(path, formData) {
    const res = await fetch(`${this.base}${path}`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `POST ${path} → ${res.status}`);
    }
    return res.json();
  },

  async patch(path, body) {
    const res = await fetch(`${this.base}${path}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `PATCH ${path} → ${res.status}`);
    }
    return res.json();
  },

  async put(path, body) {
    const res = await fetch(`${this.base}${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`PUT ${path} → ${res.status}`);
    return res.json();
  },

  async del(path) {
    const res = await fetch(`${this.base}${path}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`);
    return res.json();
  },
};

// ─── Toast System ───────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ─── Loading Spinner ────────────────────────────────────────
function setLoading(on) {
  document.getElementById('global-spinner').classList.toggle('hidden', !on);
}

// ─── Router ─────────────────────────────────────────────────
const pages = ['dashboard', 'jobs', 'tracker', 'notifications', 'settings'];
const pageTitles = {
  dashboard: '📊 Dashboard',
  jobs: '💼 Jobs',
  tracker: '📋 Application Tracker',
  notifications: '🔔 Notifications',
  settings: '⚙️ Settings',
};

function navigateTo(page) {
  if (!pages.includes(page)) return;

  // Update nav
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.page === page);
  });

  // Update pages
  document.querySelectorAll('.page').forEach(el => {
    el.classList.toggle('active', el.id === `page-${page}`);
  });

  // Update title
  document.getElementById('page-title').textContent = pageTitles[page] || page;

  // Close sidebar on mobile
  document.getElementById('sidebar').classList.remove('open');

  // Trigger page load
  switch (page) {
    case 'dashboard':    loadDashboard(); break;
    case 'jobs':         loadJobs(); break;
    case 'tracker':      loadKanban(); break;
    case 'notifications': loadNotifications(); break;
    case 'settings':     loadSettings(); break;
  }
}

// ─── Modals ─────────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
}
function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}
// Close modal on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeModal(overlay.id);
  });
});

// ─── Score Ring ─────────────────────────────────────────────
function scoreRing(score) {
  const cls = score >= 80 ? 'high' : score >= 60 ? 'medium' : 'low';
  return `<div class="score-ring ${cls}">${Math.round(score)}</div>`;
}

// ─── Badge helpers ───────────────────────────────────────────
function jobTypeBadge(type) {
  const t = (type || 'onsite').toLowerCase();
  return `<span class="badge badge-${t}">${t}</span>`;
}
function categoryBadge(cat) {
  const c = (cat || 'other').toLowerCase();
  const labels = { frontend: 'Frontend', backend: 'Backend', fullstack: 'Full Stack', ai: 'AI/ML', devops: 'DevOps', other: 'Other' };
  return `<span class="badge badge-${c}">${labels[c] || c}</span>`;
}
function statusBadge(status) {
  const s = (status || 'new').toLowerCase();
  const labels = {
    new: 'New', reviewed: 'Reviewed', shortlisted: '⭐ Shortlisted',
    applied: '✅ Applied', skipped: 'Skipped',
    drafted: 'Drafted', pending_review: '👁 Review', approved: 'Approved',
    sent: '📤 Sent', replied: '💬 Replied', interview: '🎯 Interview',
    offer: '🎉 Offer', rejected: 'Rejected',
  };
  return `<span class="badge badge-${s}">${labels[s] || s}</span>`;
}

// ─── Time formatting ─────────────────────────────────────────
function timeAgo(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

function salary(min, max) {
  if (!min && !max) return '';
  const fmt = v => v >= 1000 ? `$${Math.round(v / 1000)}k` : `$${v}`;
  if (min && max) return `${fmt(min)}–${fmt(max)}`;
  return fmt(min || max);
}

// ─── Unread notification badge ───────────────────────────────
async function refreshUnreadBadge() {
  try {
    const data = await API.get('/notifications?is_read=false&limit=1');
    const count = data.unread_count || 0;
    const badge = document.getElementById('notif-badge');
    badge.textContent = count > 99 ? '99+' : count;
    badge.classList.toggle('visible', count > 0);
  } catch (_) {}
}

// ─── Wire up nav + hamburger ──────────────────────────────────
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => navigateTo(item.dataset.page));
});
document.getElementById('menu-toggle').addEventListener('click', () => {
  document.getElementById('sidebar').classList.toggle('open');
});

// "Scan Jobs Now" in sidebar + settings
async function triggerScrape() {
  try {
    setLoading(true);
    await API.post('/settings/scrape-now', {});
    showToast('Scrape started in background. Check back in a minute!', 'success');
  } catch (e) {
    showToast('Failed to trigger scrape: ' + e.message, 'error');
  } finally {
    setLoading(false);
  }
}
document.getElementById('btn-scrape-now').addEventListener('click', triggerScrape);

// ─── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  navigateTo('dashboard');
  setInterval(refreshUnreadBadge, 30000);
  refreshUnreadBadge();
});
