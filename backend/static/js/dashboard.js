/**
 * dashboard.js — Dashboard page logic.
 */

async function loadDashboard() {
  try {
    setLoading(true);
    const stats = await API.get('/jobs/stats');

    // Stat cards
    document.getElementById('stat-total').textContent     = stats.total_jobs;
    document.getElementById('stat-high').textContent      = stats.high_match_count;
    document.getElementById('stat-pending').textContent   = stats.pending_review;
    document.getElementById('stat-applied').textContent   = stats.total_applied;
    document.getElementById('stat-interviews').textContent = stats.interviews;
    document.getElementById('stat-today').textContent     = stats.new_today;

    // Category breakdown
    const catEl = document.getElementById('category-breakdown');
    const catColors = {
      frontend: 'var(--cyan)', backend: 'var(--purple)',
      fullstack: 'var(--accent)', ai: 'var(--warning)',
      devops: 'var(--success)', other: 'var(--text-muted)',
    };
    const catLabels = {
      frontend: 'Frontend', backend: 'Backend', fullstack: 'Full Stack',
      ai: 'AI / ML', devops: 'DevOps', other: 'Other',
    };
    const cats = Object.entries(stats.categories || {}).sort((a, b) => b[1] - a[1]);
    const catTotal = cats.reduce((s, [, v]) => s + v, 0);

    catEl.innerHTML = cats.length
      ? cats.map(([cat, count]) => {
          const pct = catTotal ? Math.round((count / catTotal) * 100) : 0;
          const color = catColors[cat] || 'var(--text-muted)';
          return `
            <div style="display:flex;align-items:center;gap:10px;">
              <div style="width:80px;font-size:12px;color:var(--text-secondary);">${catLabels[cat] || cat}</div>
              <div style="flex:1;background:var(--bg-elevated);border-radius:4px;height:6px;overflow:hidden;">
                <div style="width:${pct}%;height:100%;background:${color};border-radius:4px;transition:width 0.6s ease;"></div>
              </div>
              <div style="font-size:12px;color:var(--text-muted);width:30px;text-align:right;">${count}</div>
            </div>`;
        }).join('')
      : '<p class="text-sm text-muted">No data yet</p>';

    // Top companies
    const compEl = document.getElementById('top-companies');
    compEl.innerHTML = (stats.top_companies || []).length
      ? stats.top_companies.map((c, i) => `
          <div class="activity-item">
            <div class="activity-dot" style="background:var(--accent);"></div>
            <div>
              <div class="activity-text">${c.company}</div>
              <div class="activity-time">${c.count} listing${c.count > 1 ? 's' : ''}</div>
            </div>
          </div>`).join('')
      : '<p class="text-sm text-muted">No data yet</p>';

    // Top jobs
    const topJobsData = await API.get('/jobs?min_score=70&limit=8&sort_by=match_score');
    const topJobsEl = document.getElementById('top-jobs-list');
    if (topJobsData.jobs && topJobsData.jobs.length > 0) {
      topJobsEl.innerHTML = topJobsData.jobs.map(j => renderJobCard(j)).join('');
    } else {
      topJobsEl.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">💡</div>
          <h3>No high-match jobs yet</h3>
          <p>Click "Scan Jobs Now" to start searching</p>
        </div>`;
    }

    // Health Status
    loadHealthStatus();

  } catch (e) {
    showToast('Failed to load dashboard: ' + e.message, 'error');
  } finally {
    setLoading(false);
  }
}

/**
 * Fetch and render live system health from /api/health
 */
async function loadHealthStatus() {
  try {
    const health = await API.get('/health');
    const queueEl = document.getElementById('health-queue');
    const scrapeEl = document.getElementById('health-scrape');
    const geminiEl = document.getElementById('health-gemini');
    const dot = document.getElementById('health-dot');
    const timeEl = document.getElementById('health-last-check');

    // 1. Queue Status
    const qCount = health.queue.pending || 0;
    queueEl.textContent = qCount > 0 ? `${qCount} jobs pending` : "Idle (0)";
    if (qCount > 20) {
      dot.style.background = 'var(--warning)';
      dot.classList.add('pulse');
    } else if (qCount > 0) {
       dot.style.background = 'var(--accent)';
       dot.classList.add('pulse');
    } else {
       dot.style.background = 'var(--success)';
       dot.classList.remove('pulse');
    }

    // 2. Scrape Status
    const ls = health.last_scrape || {};
    if (ls.time) {
      const lastTime = timeAgo(ls.time);
      scrapeEl.innerHTML = `<span style="color:${ls.status === 'success' ? 'var(--success)' : 'var(--danger)'}">${ls.status.toUpperCase()}</span> (${ls.found} found) <span class="text-xs text-muted">${lastTime}</span>`;
    } else {
      scrapeEl.textContent = "Never run";
    }

    // 3. Gemini Status
    const gemStatus = health.services.gemini || 'unknown';
    geminiEl.innerHTML = `<span style="color:${gemStatus === 'connected' ? 'var(--success)' : 'var(--danger)'}">${gemStatus.toUpperCase()}</span>`;

    // 4. Timestamp
    if (timeEl) timeEl.textContent = `Last check: ${new Date().toLocaleTimeString()}`;

  } catch (e) {
    console.error("Health check failed", e);
  }
}
