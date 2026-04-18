/**
 * notifications.js — Notifications page.
 */

const NOTIF_ICONS = {
  new_jobs:            '🆕',
  application_drafted: '✅',
  follow_up:           '📬',
  error:               '🚨',
  daily_digest:        '☀️',
  default:             '🔔',
};

async function loadNotifications() {
  const list = document.getElementById('notifications-list');
  const label = document.getElementById('unread-label');

  try {
    setLoading(true);
    const data = await API.get('/notifications?limit=80');
    const notifications = data.notifications || [];
    const unread = data.unread_count || 0;

    label.textContent = unread > 0
      ? `${unread} unread notification${unread > 1 ? 's' : ''}`
      : 'All caught up ✓';

    // Update sidebar badge
    const badge = document.getElementById('notif-badge');
    badge.textContent = unread > 99 ? '99+' : unread;
    badge.classList.toggle('visible', unread > 0);

    if (notifications.length === 0) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔔</div>
          <h3>No notifications yet</h3>
          <p>Configure your Telegram bot in Settings to start receiving alerts</p>
        </div>`;
      return;
    }

    list.innerHTML = notifications.map(n => `
      <div class="notif-item ${!n.is_read ? 'unread' : ''}" id="notif-${n.id}">
        <div class="notif-icon">${NOTIF_ICONS[n.type] || NOTIF_ICONS.default}</div>
        <div class="notif-body">
          <div class="notif-title">${escHtml(n.title)}</div>
          <div class="notif-msg">${escHtml(n.message)}</div>
          <div class="notif-time">${timeAgo(n.created_at)}</div>
        </div>
        ${!n.is_read ? `
          <button class="btn btn-ghost btn-sm btn-icon" onclick="markRead(${n.id})" title="Mark read">·</button>
        ` : ''}
      </div>`).join('');

  } catch (e) {
    list.innerHTML = `<div class="empty-state"><h3>Error</h3><p>${e.message}</p></div>`;
  } finally {
    setLoading(false);
  }
}

async function markRead(id) {
  try {
    await API.patch(`/notifications/${id}/read`, {});
    const el = document.getElementById(`notif-${id}`);
    if (el) el.classList.remove('unread');
    await refreshUnreadBadge();
  } catch (_) {}
}

document.getElementById('btn-mark-all-read').addEventListener('click', async () => {
  try {
    await API.post('/notifications/mark-all-read', {});
    showToast('All notifications marked as read', 'success', 2000);
    await loadNotifications();
  } catch (e) {
    showToast('Failed: ' + e.message, 'error');
  }
});
