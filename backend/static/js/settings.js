/**
 * settings.js — Settings page: resumes, platform links, personas, system actions.
 */

// ─── Main loader ─────────────────────────────────────────────
async function loadSettings() {
  await Promise.all([loadSystemConfig(), loadResumes(), loadLinks(), loadPersonas(), loadGmailStatus()]);
}

// ─────────────────────────────────────────────────────────────
// RESUMES
// ─────────────────────────────────────────────────────────────
async function loadResumes() {
  const el = document.getElementById('resumes-list');
  try {
    const data = await API.get('/resumes');
    const resumes = data.resumes || [];

    if (resumes.length === 0) {
      el.innerHTML = `
        <div class="empty-state" style="padding:30px;">
          <div class="empty-state-icon">📄</div>
          <h3>No resumes yet</h3>
          <p>Upload at least one resume to start getting AI-matched applications</p>
        </div>`;
    } else {
      el.innerHTML = resumes.map(r => renderResumeCard(r)).join('');
    }
  } catch (e) {
    el.innerHTML = `<p class="text-sm" style="color:var(--danger)">Error: ${e.message}</p>`;
  }
}

function renderResumeCard(r) {
  const roleEmoji = {
    frontend: '🎨', backend: '⚙️', fullstack: '🔗', ai: '🤖',
    devops: '☁️', freelancer: '💼', other: '📄'
  };
  const skills = (r.skills || []).join(', ');
  const summary = r.experience_summary || 'No summary extracted';
  return `
    <div class="resume-card" style="align-items:flex-start;">
      <div class="resume-icon">${roleEmoji[r.role_type] || '📄'}</div>
      <div class="resume-info">
        <div class="resume-name">
          ${escHtml(r.name)}
          ${r.is_default ? '<span class="badge badge-new" style="margin-left:6px;">Default</span>' : ''}
        </div>
        <div class="resume-type">${escHtml(r.role_type)}</div>
        <div class="resume-skills text-muted" style="white-space:normal;margin-bottom:6px;">${escHtml(skills || 'No skills listed')}</div>
        <p class="text-xs text-secondary mt-1" style="font-style:italic; line-height: 1.5; white-space: pre-wrap;">${escHtml(summary)}</p>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px;align-items:flex-end;flex-shrink:0;">
        ${r.has_file ? '<span class="text-xs text-muted">📎 File attached</span>' : '<span class="text-xs text-muted">No file</span>'}
        <button class="btn btn-danger btn-sm" onclick="deleteResume(${r.id})">Delete</button>
      </div>
    </div>`;
}

async function deleteResume(id) {
  if (!confirm('Remove this resume? This cannot be undone.')) return;
  try {
    await API.del(`/resumes/${id}`);
    showToast('Resume removed', 'info', 2000);
    await loadResumes();
  } catch (e) {
    showToast('Delete failed: ' + e.message, 'error');
  }
}

// ─── Resume Upload Modal ─────────────────────────────────────
document.getElementById('btn-add-resume').addEventListener('click', () => {
  document.getElementById('resume-form').reset();
  document.getElementById('resume-file-name').textContent = '';
  document.getElementById('resume-auto-extract').checked = true;
  document.getElementById('manual-resume-fields').style.display = 'none';
  openModal('modal-resume');
});

document.getElementById('resume-auto-extract').addEventListener('change', (e) => {
  document.getElementById('manual-resume-fields').style.display = e.target.checked ? 'none' : 'block';
});

// Drop zone
const dropZone = document.getElementById('resume-drop-zone');
const fileInput = document.getElementById('resume-file');

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) {
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    document.getElementById('resume-file-name').textContent = `📎 ${file.name}`;
  }
});
fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  if (file) document.getElementById('resume-file-name').textContent = `📎 ${file.name}`;
});

// Form submit
document.getElementById('resume-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('btn-save-resume');
  btn.disabled = true;

  const file = fileInput.files[0];
  if (!file) {
    showToast('Please select a resume file first', 'warning');
    btn.disabled = false;
    return;
  }

  const isAuto = document.getElementById('resume-auto-extract').checked;
  btn.textContent = isAuto ? '✨ AI Parsing Resume...' : 'Saving...';

  try {
    const name = document.getElementById('resume-name').value.trim();
    const roleType = document.getElementById('resume-role-type').value;
    const skillsRaw = document.getElementById('resume-skills').value;
    const skills = skillsRaw.split(',').map(s => s.trim()).filter(Boolean);
    const summary = document.getElementById('resume-summary').value.trim();

    const formData = new FormData();
    formData.append('file', file);
    formData.append('auto_extract', isAuto);
    
    if (!isAuto) {
      formData.append('name', name);
      formData.append('role_type', roleType);
      formData.append('skills', JSON.stringify(skills));
      formData.append('experience_summary', summary);
    } else if (name) {
      formData.append('name', name);  // Allows custom name while auto-extracting
    }
    
    formData.append('tags', '[]');
    formData.append('is_default', 'false');
    await API.postForm('/resumes/upload', formData);

    showToast('Resume saved successfully!', 'success');
    closeModal('modal-resume');
    await loadResumes();
  } catch (err) {
    showToast('Save failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Resume';
  }
});

// ─────────────────────────────────────────────────────────────
// PLATFORM LINKS
// ─────────────────────────────────────────────────────────────
const PLATFORM_ICONS = {
  github: '🐙', portfolio: '🌐', linkedin: '💼',
  upwork: '🟢', fiverr: '🟡', other: '🔗',
};

async function loadLinks() {
  const el = document.getElementById('links-list');
  try {
    const data = await API.get('/settings/links');
    const links = data.links || [];
    if (links.length === 0) {
      el.innerHTML = '<p class="text-sm text-muted">No links added yet.</p>';
    } else {
      el.innerHTML = links.map(l => `
        <div class="resume-card">
          <div class="resume-icon">${PLATFORM_ICONS[l.platform] || '🔗'}</div>
          <div class="resume-info">
            <div class="resume-name">${escHtml(l.platform)}</div>
            <div class="resume-type"><a href="${escHtml(l.url)}" target="_blank">${escHtml(l.url)}</a></div>
            <div class="resume-skills">For: ${(l.relevant_for || []).join(', ') || 'all roles'}</div>
          </div>
          <div style="display:flex;gap:6px;">
            <label style="display:flex;align-items:center;gap:4px;font-size:12px;cursor:pointer;">
              <input type="checkbox" ${l.is_active ? 'checked' : ''} onchange="toggleLink(${l.id}, this.checked)" /> Active
            </label>
            <button class="btn btn-danger btn-sm" onclick="deleteLink(${l.id})">×</button>
          </div>
        </div>`).join('');
    }
  } catch (e) {
    el.innerHTML = `<p style="color:var(--danger)">Error: ${e.message}</p>`;
  }
}

async function toggleLink(id, active) {
  try {
    await API.put(`/settings/links/${id}`, { is_active: active });
    showToast(`Link ${active ? 'activated' : 'deactivated'}`, 'info', 1500);
  } catch (e) {
    showToast('Update failed: ' + e.message, 'error');
  }
}

async function deleteLink(id) {
  if (!confirm('Remove this link?')) return;
  try {
    await API.del(`/settings/links/${id}`);
    showToast('Link removed', 'info', 1500);
    await loadLinks();
  } catch (e) {
    showToast('Delete failed: ' + e.message, 'error');
  }
}

document.getElementById('btn-add-link').addEventListener('click', () => openModal('modal-link'));

document.getElementById('btn-save-link').addEventListener('click', async () => {
  const platform = document.getElementById('link-platform').value;
  const url = document.getElementById('link-url').value.trim();
  const desc = document.getElementById('link-desc').value.trim();
  const relevantFor = Array.from(
    document.querySelectorAll('#link-roles input[type=checkbox]:checked')
  ).map(cb => cb.value);

  if (!url) { showToast('URL is required', 'warning'); return; }

  try {
    await API.post('/settings/links', { platform, url, description: desc, relevant_for: relevantFor });
    showToast('Link added!', 'success');
    closeModal('modal-link');
    await loadLinks();
  } catch (e) {
    showToast('Failed: ' + e.message, 'error');
  }
});

// ─────────────────────────────────────────────────────────────
// PERSONAS
// ─────────────────────────────────────────────────────────────
const PERSONA_EMOJIS = {
  frontend: '🎨', backend: '⚙️', fullstack: '🔗',
  ai: '🤖', devops: '☁️', freelancer: '💼', other: '👤',
};

async function loadPersonas() {
  const el = document.getElementById('personas-list');
  try {
    const data = await API.get('/settings/personas');
    const personas = data.personas || [];
    if (personas.length === 0) {
      el.innerHTML = '<p class="text-sm text-muted">No personas configured.</p>';
    } else {
      el.innerHTML = personas.map(p => `
        <div class="resume-card">
          <div class="resume-icon">${PERSONA_EMOJIS[p.persona] || '👤'}</div>
          <div class="resume-info">
            <div class="resume-name">${escHtml(p.persona)} (Priority ${p.priority})</div>
            <div class="resume-type">${escHtml(p.tone_guidance || 'No tone guidance set')}</div>
            <div class="resume-skills">Keywords: ${(p.preferred_keywords || []).join(', ') || 'None set'}</div>
          </div>
          <label style="display:flex;align-items:center;gap:4px;font-size:12px;cursor:pointer;">
            <input type="checkbox" ${p.is_active ? 'checked' : ''} onchange="togglePersona(${p.id}, this.checked)" /> Active
          </label>
        </div>`).join('');
    }
  } catch (e) {
    el.innerHTML = `<p style="color:var(--danger)">Error: ${e.message}</p>`;
  }
}

async function togglePersona(id, active) {
  try {
    await API.put(`/settings/personas/${id}`, { is_active: active });
    showToast(`Persona ${active ? 'enabled' : 'disabled'}`, 'info', 1500);
  } catch (e) {
    showToast('Update failed: ' + e.message, 'error');
  }
}

document.getElementById('btn-add-persona').addEventListener('click', () => {
  document.getElementById('persona-name').value = '';
  document.getElementById('persona-tone').value = '';
  document.getElementById('persona-keywords').value = '';
  openModal('modal-persona');
});

document.getElementById('btn-save-persona').addEventListener('click', async () => {
  const persona = document.getElementById('persona-name').value.trim();
  const tone = document.getElementById('persona-tone').value.trim();
  const keywords = document.getElementById('persona-keywords').value.split(',').map(k => k.trim()).filter(Boolean);

  if (!persona) { showToast('Persona name is required', 'warning'); return; }

  try {
    await API.post('/settings/personas', {
      persona: persona,
      tone_guidance: tone,
      preferred_keywords: keywords,
      avoided_keywords: [],
      is_active: true,
      priority: 5
    });
    showToast('Persona added!', 'success');
    closeModal('modal-persona');
    await loadPersonas();
  } catch (e) {
    showToast('Failed to save persona: ' + e.message, 'error');
  }
});

// ─── Global System Config ──────────────────────────────────────────
async function loadSystemConfig() {
  try {
    const config = await API.get('/settings/config');
    
    // Candidate Profile
    document.getElementById('setting-first-name').value = config.candidate_first_name || '';
    document.getElementById('setting-last-name').value = config.candidate_last_name || '';
    document.getElementById('setting-email').value = config.candidate_email || '';
    document.getElementById('setting-phone').value = config.candidate_phone || '';
    document.getElementById('setting-linkedin').value = config.candidate_linkedin || '';
    document.getElementById('setting-github').value = config.candidate_github || '';
    
    // Scraper Tuning
    document.getElementById('setting-scrape-mode').value = config.scrape_mode || 'local';
    document.getElementById('setting-salary-min').value = config.salary_minimum || 0;
    document.getElementById('setting-target-seniority').value = config.target_seniority || '';
    
    // AI Feature Flags
    document.getElementById('setting-enable-embeddings').checked = !!config.enable_embeddings;
    document.getElementById('setting-enable-enrichment').checked = !!config.enable_enrichment;

  } catch (e) {
    showToast('Failed to load system config: ' + e.message, 'error');
  }
}

async function saveAllSettings() {
  const btn = document.getElementById('btn-save-all-settings');
  btn.disabled = true;
  btn.textContent = '⏳ Saving...';

  try {
    const payload = {
      candidate_first_name: document.getElementById('setting-first-name').value.trim(),
      candidate_last_name: document.getElementById('setting-last-name').value.trim(),
      candidate_email: document.getElementById('setting-email').value.trim(),
      candidate_phone: document.getElementById('setting-phone').value.trim(),
      candidate_linkedin: document.getElementById('setting-linkedin').value.trim(),
      candidate_github: document.getElementById('setting-github').value.trim(),
      
      scrape_mode: document.getElementById('setting-scrape-mode').value,
      salary_minimum: parseInt(document.getElementById('setting-salary-min').value) || 0,
      target_seniority: document.getElementById('setting-target-seniority').value.trim(),
      
      enable_embeddings: document.getElementById('setting-enable-embeddings').checked,
      enable_enrichment: document.getElementById('setting-enable-enrichment').checked
    };

    await API.patch('/settings/config', payload);
    showToast('Settings saved successfully! These changes are live for this session.', 'success', 3000);
  } catch (e) {
    showToast('Failed to save settings: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '💾 Save All Changes';
  }
}


document.getElementById('btn-save-all-settings').addEventListener('click', saveAllSettings);

// ─── Manual Actions ──────────────────────────────────────────
document.getElementById('btn-test-telegram').addEventListener('click', async () => {
  try {
    const btn = document.getElementById('btn-test-telegram');
    btn.disabled = true;
    btn.textContent = '⏳ Testing...';
    await API.post('/settings/test-telegram', {});
    showToast('Telegram connected! Check your chat 🎉', 'success', 4000);
  } catch (e) {
    showToast('Telegram failed: ' + e.message, 'error', 5000);
  } finally {
    const btn = document.getElementById('btn-test-telegram');
    if (btn) { btn.disabled = false; btn.textContent = '🔔 Test Telegram'; }
  }
});

document.getElementById('btn-rescore-jobs').addEventListener('click', async () => {
  const btn = document.getElementById('btn-rescore-jobs');
  btn.disabled = true;
  btn.textContent = '⏳ Rescoring...';
  try {
    const res = await API.post('/settings/rescore-jobs', {});
    showToast(res.message || 'Rescoring launched.', 'info', 4000);
  } catch (e) {
    showToast('Rescoring failed: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '↻ Re-Score Everything';
  }
});

// ─── Gmail Integration ──────────────────────────────────────────
async function loadGmailStatus() {
  const dot = document.getElementById('gmail-status-dot');
  const text = document.getElementById('gmail-status-text');
  const sub = document.getElementById('gmail-status-subtext');
  const btn = document.getElementById('btn-connect-gmail');

  try {
    const status = await API.get('/gmail/status');
    if (status.is_authenticated) {
      dot.style.background = 'var(--success)';
      text.textContent = 'Gmail Connected';
      text.style.color = 'var(--success)';
      sub.textContent = 'System is ready to send cold emails and track replies.';
      btn.textContent = 'Re-Link Account';
      btn.classList.replace('btn-primary', 'btn-secondary');
    } else {
      dot.style.background = 'var(--danger)';
      text.textContent = 'Not Connected';
      text.style.color = 'var(--danger)';
      sub.textContent = status.credentials_missing 
        ? 'Missing credentials.json in backend/data folder.' 
        : 'Sign in to enable automated outreach.';
      btn.textContent = 'Connect Gmail';
      btn.classList.replace('btn-secondary', 'btn-primary');
    }
  } catch (e) {
    text.textContent = 'Status Error';
    sub.textContent = e.message;
  }
}

document.getElementById('btn-connect-gmail').addEventListener('click', () => {
  // Use a full page redirect for OAuth
  window.location.href = API_BASE + '/gmail/auth';
});
