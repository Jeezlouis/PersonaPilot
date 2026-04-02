/**
 * tracker.js — Kanban application tracker.
 */

const KANBAN_COLUMNS = [
  { status: 'drafted',        label: 'Drafted',       emoji: '📝' },
  { status: 'pending_review', label: 'In Review',     emoji: '👁' },
  { status: 'approved',       label: 'Approved',      emoji: '✅' },
  { status: 'sent',           label: 'Sent',          emoji: '📤' },
  { status: 'replied',        label: 'Replied',       emoji: '💬' },
  { status: 'interview',      label: 'Interview',     emoji: '🎯' },
  { status: 'offer',          label: 'Offer',         emoji: '🎉' },
  { status: 'rejected',       label: 'Rejected',      emoji: '❌' },
];

async function loadKanban() {
  const board = document.getElementById('kanban-board');
  board.innerHTML = KANBAN_COLUMNS.map(col => `
    <div class="kanban-col" data-status="${col.status}">
      <div class="kanban-col-header">
        <span class="kanban-col-title">${col.emoji} ${col.label}</span>
        <span class="kanban-col-count" id="kanban-count-${col.status}">0</span>
      </div>
      <div class="kanban-items" id="kanban-${col.status}">
        <div class="text-xs text-muted" style="padding:8px;">Loading...</div>
      </div>
    </div>`).join('');

  try {
    const data = await API.get('/applications/kanban');

    for (const col of KANBAN_COLUMNS) {
      const items = data[col.status] || [];
      const container = document.getElementById(`kanban-${col.status}`);
      const countEl   = document.getElementById(`kanban-count-${col.status}`);

      countEl.textContent = items.length;

      if (items.length === 0) {
        container.innerHTML = `<div class="text-xs text-muted" style="padding:8px;text-align:center;">Empty</div>`;
      } else {
        container.innerHTML = items.map(app => renderKanbanItem(app)).join('');
      }
    }
  } catch (e) {
    showToast('Failed to load tracker: ' + e.message, 'error');
    board.innerHTML = `<div class="empty-state"><h3>Error loading tracker</h3><p>${e.message}</p></div>`;
  }
}

function renderKanbanItem(app) {
  const job = app.job || {};
  const nextStatuses = getNextStatuses(app.status);
  return `
    <div class="kanban-item" onclick="openAppDetail(${app.id})">
      <div class="kanban-item-title">${escHtml(job.title || 'Unknown')}</div>
      <div class="kanban-item-company">${escHtml(job.company || '—')}</div>
      <div style="display:flex;gap:4px;margin-top:6px;flex-wrap:wrap;">
        ${categoryBadge(job.role_category)}
        ${job.match_score ? `<span class="text-xs" style="color:var(--text-muted)">${Math.round(job.match_score)}%</span>` : ''}
      </div>
      ${nextStatuses.length ? `
        <div style="display:flex;gap:4px;margin-top:8px;flex-wrap:wrap;" onclick="event.stopPropagation()">
          ${nextStatuses.map(s => `
            <button class="btn btn-ghost btn-sm" style="font-size:10px;padding:3px 6px;"
              onclick="moveApp(${app.id},'${s.status}')">
              ${s.emoji} ${s.label}
            </button>`).join('')}
        </div>` : ''}
    </div>`;
}

function getNextStatuses(current) {
  const flow = {
    drafted:        [{ status: 'pending_review', label: 'Review', emoji: '👁' }],
    pending_review: [{ status: 'approved', label: 'Approve', emoji: '✅' }, { status: 'rejected', label: 'Reject', emoji: '❌' }],
    approved:       [{ status: 'sent', label: 'Mark Sent', emoji: '📤' }],
    sent:           [{ status: 'replied', label: 'Got Reply', emoji: '💬' }, { status: 'rejected', label: 'No Reply', emoji: '❌' }],
    replied:        [{ status: 'interview', label: 'Interview!', emoji: '🎯' }, { status: 'rejected', label: 'Rejected', emoji: '❌' }],
    interview:      [{ status: 'offer', label: 'Got Offer!', emoji: '🎉' }, { status: 'rejected', label: 'No Offer', emoji: '❌' }],
    offer:          [],
    rejected:       [],
  };
  return flow[current] || [];
}

async function moveApp(appId, newStatus) {
  try {
    await API.patch(`/applications/${appId}`, { status: newStatus });
    showToast(`Moved to ${newStatus.replace('_', ' ')}`, 'success', 2000);
    await loadKanban();
  } catch (e) {
    showToast('Update failed: ' + e.message, 'error');
  }
}

async function openAppDetail(appId) {
  try {
    const app = await API.get(`/applications/${appId}`);
    const job = app.job || {};
    // Open job detail modal if we have a job_id
    if (app.job_id) {
      closeModal('modal-job');
      await openJobDetail(app.job_id);
    }
  } catch (e) {
    showToast('Could not load application: ' + e.message, 'error');
  }
}

document.getElementById('btn-refresh-kanban').addEventListener('click', () => {
  loadKanban();
  showToast('Tracker refreshed', 'info', 1500);
});
