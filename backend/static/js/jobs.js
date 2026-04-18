/**
 * jobs.js — Jobs list + detail view + AI draft generation.
 */

let jobsState = {
  jobs: [],
  total: 0,
  page: 0,
  limit: 30,
  filters: { status: '', role_category: '', job_type: '', seniority: '', min_score: 0, search: '' },
};

// ─── Job Card renderer (shared with dashboard) ───────────────
function renderJobCard(job, onClick = true) {
  const sal = salary(job.salary_min, job.salary_max);
  return `
    <div class="job-card" ${onClick ? `onclick="openJobDetail(${job.id})"` : ''} id="job-${job.id}">
      ${scoreRing(job.match_score || 0)}
      <div class="job-card-body">
        <div class="job-card-title">${escHtml(job.title)}</div>
        <div class="job-card-company">${escHtml(job.company || 'Unknown company')}</div>
        <div class="job-card-meta">
          ${jobTypeBadge(job.job_type)}
          ${categoryBadge(job.role_category)}
          ${statusBadge(job.status)}
          ${job.contact_email ? '<span class="badge badge-accent" style="padding: 2px 6px;">📧 Outreach</span>' : ''}
          ${sal ? `<span class="text-xs text-muted">${sal}</span>` : ''}
          <span class="job-source">${job.source || ''}</span>
          <span class="text-xs text-muted">${timeAgo(job.found_at)}</span>
        </div>
      </div>
      <div class="job-card-actions">
        <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();skipJob(${job.id})">Skip</button>
        <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();openJobDetail(${job.id})">View</button>
      </div>
    </div>`;
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ─── Load jobs list ──────────────────────────────────────────
async function loadJobs(reset = true) {
  if (reset) jobsState.page = 0;

  const { filters, limit, page } = jobsState;
  let url = `/jobs?limit=${limit}&offset=${page * limit}&sort_by=match_score`;
  if (filters.status)        url += `&status=${filters.status}`;
  if (filters.role_category) url += `&role_category=${filters.role_category}`;
  if (filters.job_type)      url += `&job_type=${filters.job_type}`;
  if (filters.seniority)     url += `&seniority=${filters.seniority}`;
  if (filters.min_score)     url += `&min_score=${filters.min_score}`;
  if (filters.search)        url += `&search=${encodeURIComponent(filters.search)}`;

  try {
    setLoading(true);
    const data = await API.get(url);
    jobsState.jobs = data.jobs;
    jobsState.total = data.total;

    const listEl = document.getElementById('jobs-list');
    document.getElementById('jobs-count').textContent = `${data.total} jobs`;

    if (data.jobs.length === 0) {
      listEl.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">💼</div>
          <h3>No jobs found</h3>
          <p>Try adjusting filters or run a scrape</p>
        </div>`;
    } else {
      listEl.innerHTML = data.jobs.map(j => renderJobCard(j)).join('');
    }
  } catch (e) {
    showToast('Failed to load jobs: ' + e.message, 'error');
  } finally {
    setLoading(false);
  }
}

// ─── Skip a job ──────────────────────────────────────────────
async function skipJob(jobId) {
  try {
    await API.patch(`/jobs/${jobId}/status`, { status: 'skipped' });
    const card = document.getElementById(`job-${jobId}`);
    if (card) {
      card.style.transform = 'translateX(20px)';
      card.style.opacity = '0';
      card.style.transition = 'all 0.3s ease';
      setTimeout(() => {
        card.remove();
        // Update local count
        const countEl = document.getElementById('jobs-count');
        if (countEl) {
          const current = parseInt(countEl.textContent) || 0;
          if (current > 0) countEl.textContent = `${current - 1} jobs`;
        }
      }, 300);
    }
    showToast('Job permanently removed', 'info', 2000);
  } catch (e) {
    showToast('Failed to skip: ' + e.message, 'error');
  }
}

// ─── Open Job Detail Modal ───────────────────────────────────
async function openJobDetail(jobId) {
  openModal('modal-job');
  const content = document.getElementById('modal-job-content');
  content.innerHTML = `<div style="padding:40px;text-align:center;"><div class="loading-spinner"></div></div>`;

  try {
    const job = await API.get(`/jobs/${jobId}`);
    document.getElementById('modal-job-title').textContent = job.title;

    const sal = salary(job.salary_min, job.salary_max);
    const hasApp = job.application;

    content.innerHTML = `
      <div class="job-detail-panel" style="border:none;padding:0;">
        <div class="job-detail-header">
          <div>
            <div class="job-detail-title">${escHtml(job.title)}</div>
            <div class="job-detail-company">
              <a href="${job.url}" target="_blank" rel="noopener">${escHtml(job.company || 'Company')}</a>
            </div>
            <div class="job-detail-meta">
              ${jobTypeBadge(job.job_type)}
              ${categoryBadge(job.role_category)}
              ${sal ? `<span class="badge badge-other">💰 ${sal}</span>` : ''}
              <span class="badge badge-other">📍 ${escHtml(job.location || 'N/A')}</span>
              <span class="badge badge-other">📆 ${timeAgo(job.posted_at)}</span>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:8px;align-items:center;">
            ${scoreRing(job.match_score || 0)}
            <span class="text-xs text-muted">Match Score</span>
          </div>
        </div>

        <div class="job-desc" id="job-desc-${jobId}">${(job.description || 'No description available.').replace(/\n/g, '<br>')}</div>

        <!-- Company Intelligence (Enrichment) -->
        ${job.company_intel ? `
        <div style="background:rgba(79, 142, 247, 0.05); border:1px solid rgba(79, 142, 247, 0.2); border-radius:var(--radius-md); padding:16px; margin-bottom:24px;">
           <h4 style="font-size:12px;color:var(--accent);text-transform:uppercase;margin-bottom:8px;">🏢 Company Intelligence</h4>
           <p class="text-sm" style="margin-bottom:8px;"><strong>About:</strong> ${escHtml(job.company_intel.about)}</p>
           <p class="text-xs text-secondary"><strong>Recent News:</strong> ${escHtml(job.company_intel.recent_news)}</p>
           <div style="display:flex;gap:4px;margin-top:8px;flex-wrap:wrap;">
             ${(job.company_intel.tech_stack || []).map(t => `<span class="badge badge-other" style="font-size:10px;">${escHtml(t)}</span>`).join('')}
           </div>
        </div>
        ` : ''}

        <!-- Actions -->
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;">
          <a href="${job.url}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">🔗 View Original</a>
          ${hasApp
            ? `<button class="btn btn-success btn-sm" id="btn-autofill-${jobId}" onclick="autofillJob(${jobId})">✨ Autofill & Review</button>
               <button class="btn btn-secondary btn-sm" onclick="showExistingDraft(${jobId})">📋 View Draft</button>`
            : `<button class="btn btn-primary" id="btn-draft-${jobId}" onclick="generateDraft(${jobId})">✨ Generate AI Application</button>`
          }
          ${job.contact_email ? `<button class="btn btn-accent btn-sm" onclick="showEmailOutreach(${jobId})">📧 Send Cold Email</button>` : ''}
          <button class="btn btn-ghost btn-sm" onclick="skipJob(${jobId});closeModal('modal-job');">🚫 Skip Job</button>
        </div>

        <div id="email-outreach-panel-${jobId}" class="card hidden" style="background:var(--accent-glow); border-color:var(--accent); margin-bottom:20px;">
           <div class="card-header"><div class="card-title">📧 Direct Outreach Draft</div></div>
           <div id="email-outreach-content-${jobId}" style="padding:12px;">
              <p class="text-xs text-muted mb-2">Loading draft...</p>
           </div>
        </div>

        <!-- Existing application -->
        ${hasApp ? renderExistingApp(job.application) : `<div id="draft-container-${jobId}"></div>`}
      </div>`;
  } catch (e) {
    content.innerHTML = `<div class="empty-state"><h3>Error</h3><p>${e.message}</p></div>`;
  }
}

function renderExistingApp(app) {
  return `
    <div class="draft-panel" id="existing-app">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
        <h3>Current Application</h3>
        ${statusBadge(app.status)}
      </div>
      ${app.email_subject ? `<div class="draft-subject-field">📧 Subject: <strong>${escHtml(app.email_subject)}</strong></div>` : ''}
      <textarea class="draft-cover" readonly>${escHtml(app.cover_message || '')}</textarea>
      ${app.tailored_bullets && app.tailored_bullets.length
        ? `<ul class="draft-bullets">${app.tailored_bullets.map(b => `<li>${escHtml(b)}</li>`).join('')}</ul>`
        : ''}
      <div style="display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-top:12px;">
        <div style="display:flex;gap:8px;">
          <button class="btn btn-primary btn-sm" onclick="updateAppStatus(${app.id},'pending_review')">👁 Move to Review</button>
          <button class="btn btn-secondary btn-sm" onclick="updateAppStatus(${app.id},'sent')">📤 Mark as Sent</button>
        </div>
        <button class="btn btn-danger btn-sm" onclick="deleteExistingApp(${app.id}, ${app.job_id})">🗑 Delete</button>
      </div>
    </div>`;
}

async function deleteExistingApp(appId, jobId) {
  if (!confirm('Are you sure you want to completely delete this application record?')) return;
  try {
    await API.del(`/applications/${appId}`);
    showToast('Application deleted securely', 'success');
    closeModal('modal-job');
    if (typeof loadJobs === 'function' && document.getElementById('page-jobs').classList.contains('active')) loadJobs(false);
    if (typeof loadKanban === 'function' && document.getElementById('page-tracker').classList.contains('active')) loadKanban();
  } catch (e) {
    showToast('Failed to delete: ' + e.message, 'error');
  }
}

// ─── Generate AI Draft ───────────────────────────────────────
async function generateDraft(jobId) {
  const btn = document.getElementById(`btn-draft-${jobId}`);
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Generating...';
  }

  try {
    const result = await API.post(`/jobs/${jobId}/draft`, {});
    const container = document.getElementById(`draft-container-${jobId}`);
    if (container) {
      container.innerHTML = `
        <div class="draft-panel">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
            <h3>AI Generated Application</h3>
            <span class="badge badge-new">Draft</span>
          </div>
          <div class="draft-resume-badge">
            📄 ${escHtml(result.resume?.name || 'Resume')} — ${escHtml(result.resume?.role_type || '')}
            ${result.confidence ? `· ${Math.round(result.confidence * 100)}% match` : ''}
          </div>
          <div class="draft-subject-field">📧 Subject: <strong>${escHtml(result.subject)}</strong></div>
          <textarea class="draft-cover" id="cover-text-${result.application_id}">${escHtml(result.cover_message)}</textarea>
          ${result.tailored_bullets && result.tailored_bullets.length
            ? `<ul class="draft-bullets">${result.tailored_bullets.map(b => `<li>${escHtml(b)}</li>`).join('')}</ul>`
            : ''}
          ${result.reasoning ? `<p class="text-xs text-muted mt-2">💡 ${escHtml(result.reasoning)}</p>` : ''}
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;">
            <button class="btn btn-success" onclick="approveAndCopy(${result.application_id}, '${jobId}')">✅ Copy & Mark Ready</button>
            <button class="btn btn-secondary btn-sm" onclick="updateAppStatus(${result.application_id},'pending_review')">👁 Move to Review</button>
          </div>
        </div>`;
    }
    showToast('Application draft generated! Review before sending.', 'success');
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = '✨ Generate AI Application'; }
    showToast('Draft failed: ' + e.message, 'error');
  }
}

async function approveAndCopy(appId, jobId) {
  const textEl = document.getElementById(`cover-text-${appId}`);
  const text = textEl ? textEl.value : '';
  try {
    await navigator.clipboard.writeText(text);
    await updateAppStatus(appId, 'pending_review');
    showToast('Cover message copied! Application moved to review queue.', 'success', 4000);
  } catch (e) {
    showToast('Copy failed. Please select and copy manually.', 'warning');
  }
}

async function updateAppStatus(appId, status) {
  try {
    await API.patch(`/applications/${appId}`, { status });
    showToast(`Application moved to "${status}"`, 'success', 2500);
    await refreshUnreadBadge();
  } catch (e) {
    showToast('Update failed: ' + e.message, 'error');
  }
}

// ─── Autofill (Phase 5) ──────────────────────────────────────
async function autofillJob(jobId) {
  const btn = document.getElementById(`btn-autofill-${jobId}`);
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Prefilling form...';
  }

  try {
    notify_in_progress = showToast('Launching Playwright engine... this takes ~20s', 'info', 10000);
    const result = await API.post(`/jobs/${jobId}/autofill`, {});
    showToast('Form pre-filled! Check Telegram to review the screenshot.', 'success', 6000);
    btn.textContent = '✅ Sent to Review';
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = '✨ Autofill & Review'; }
    showToast('Autofill failed: ' + e.message, 'error');
  }
}

// ─── Email Outreach ──────────────────────────────────────────
async function showEmailOutreach(jobId) {
  const panel = document.getElementById(`email-outreach-panel-${jobId}`);
  const content = document.getElementById(`email-outreach-content-${jobId}`);
  panel.classList.remove('hidden');

  try {
    const job = await API.get(`/jobs/${jobId}`);
    const outreach = job.email_outreach;

    if (!outreach) {
      content.innerHTML = `<p class="text-sm text-secondary">No email draft found for this job. Make sure an email was extracted.</p>`;
      return;
    }

    content.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:10px;">
        <div>
           <label class="text-xs font-bold text-muted">RECIPIENT</label>
           <div class="text-sm">${escHtml(outreach.recipient)}</div>
        </div>
        <div>
           <label class="text-xs font-bold text-muted">SUBJECT</label>
           <div class="text-sm font-semibold">${escHtml(outreach.subject)}</div>
        </div>
        <div>
           <label class="text-xs font-bold text-muted">BODY</label>
           <textarea class="draft-cover" style="height:150px; font-size:13px; line-height:1.4;">${escHtml(outreach.body)}</textarea>
        </div>
        <div style="display:flex; gap:10px; margin-top:5px;">
           <button class="btn btn-primary" id="btn-send-email-${jobId}" onclick="sendColdEmail(${jobId})">📤 Send via Gmail</button>
           <button class="btn btn-ghost btn-sm" onclick="document.getElementById('email-outreach-panel-${jobId}').classList.add('hidden')">Cancel</button>
        </div>
      </div>
    `;
    
    if (outreach.status === 'sent') {
      const btn = document.getElementById(`btn-send-email-${jobId}`);
      btn.disabled = true;
      btn.textContent = '✅ Already Sent';
      btn.classList.replace('btn-primary', 'btn-secondary');
    }
  } catch (e) {
    content.innerHTML = `<p class="text-sm text-danger">Error: ${e.message}</p>`;
  }
}

async function sendColdEmail(jobId) {
  const btn = document.getElementById(`btn-send-email-${jobId}`);
  btn.disabled = true;
  btn.textContent = '⏳ Sending...';

  try {
    // Note: This endpoint currently returns HTML for the Telegram link flow,
    // so we handle it by checking if it contains "Success"
    const responseText = await API.get(`/jobs/${jobId}/email/send`, { responseType: 'text' });
    if (responseText.includes('Successfully')) {
      showToast('Email sent! check your Gmail Sent folder.', 'success');
      btn.textContent = '✅ Sent Successfully';
      btn.classList.replace('btn-primary', 'btn-success');
    } else {
      throw new Error('Failed to confirm send. Check logs.');
    }
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '📤 Try Again';
    showToast('Send failed: ' + e.message, 'error');
  }
}

// ─── Filters wiring ──────────────────────────────────────────
let searchDebounce;
document.getElementById('search-input').addEventListener('input', (e) => {
  clearTimeout(searchDebounce);
  jobsState.filters.search = e.target.value;
  searchDebounce = setTimeout(() => loadJobs(), 400);
});
document.getElementById('filter-status').addEventListener('change', (e) => {
  jobsState.filters.status = e.target.value;
  loadJobs();
});
document.getElementById('filter-category').addEventListener('change', (e) => {
  jobsState.filters.role_category = e.target.value;
  loadJobs();
});
document.getElementById('filter-type').addEventListener('change', (e) => {
  jobsState.filters.job_type = e.target.value;
  loadJobs();
});
document.getElementById('filter-seniority').addEventListener('change', (e) => {
  jobsState.filters.seniority = e.target.value;
  loadJobs();
});
document.getElementById('filter-score').addEventListener('input', (e) => {
  const val = parseInt(e.target.value);
  document.getElementById('filter-score-val').textContent = val;
  jobsState.filters.min_score = val;
});
document.getElementById('filter-score').addEventListener('change', (e) => loadJobs());

document.getElementById('filter-clear').addEventListener('click', () => {
  jobsState.filters = { status: '', role_category: '', job_type: '', seniority: '', min_score: 0, search: '' };
  document.getElementById('search-input').value = '';
  document.getElementById('filter-status').value = '';
  document.getElementById('filter-category').value = '';
  document.getElementById('filter-type').value = '';
  document.getElementById('filter-seniority').value = '';
  document.getElementById('filter-score').value = 0;
  document.getElementById('filter-score-val').textContent = 0;
  loadJobs();
});
