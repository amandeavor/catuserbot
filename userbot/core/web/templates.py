# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Aetheris V5 — Mission Control</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  <style>
    :root {
      --bg: #090b0e;
      --card-bg: #12161c;
      --card-border: #1e242d;
      --card-hover: #181d26;
      --text-primary: #f0f3f6;
      --text-secondary: #8b949e;
      --accent: #4f46e5;
      --accent-hover: #6366f1;
      --accent-glow: rgba(99, 102, 241, 0.15);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }
    body {
      background-color: var(--bg);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: 14px;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      padding: 24px;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 24px;
      margin-bottom: 32px;
      border-bottom: 1px solid var(--card-border);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-logo {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: linear-gradient(135deg, var(--accent), #9333ea);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 16px;
      color: #fff;
    }
    .brand h1 {
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.2);
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      color: var(--success);
    }
    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background-color: var(--success);
    }
    .grid-stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 20px;
      transition: border-color 0.2s ease, transform 0.2s ease;
    }
    .card:hover {
      border-color: #2e3846;
    }
    .stat-label {
      color: var(--text-secondary);
      font-size: 12px;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }
    .stat-value {
      font-size: 28px;
      font-weight: 700;
      letter-spacing: -0.03em;
      font-family: var(--font-mono);
    }
    .stat-subtext {
      color: var(--text-secondary);
      font-size: 12px;
      margin-top: 4px;
    }
    .main-grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 24px;
    }
    @media (max-width: 900px) {
      .main-grid {
        grid-template-columns: 1fr;
      }
    }
    .panel-title {
      font-size: 15px;
      font-weight: 600;
      margin-bottom: 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th {
      text-align: left;
      padding: 10px 12px;
      color: var(--text-secondary);
      border-bottom: 1px solid var(--card-border);
      font-weight: 500;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    td {
      padding: 12px;
      border-bottom: 1px solid #161b22;
      font-family: var(--font-mono);
      font-size: 12px;
    }
    tr:last-child td {
      border-bottom: none;
    }
    .btn {
      padding: 6px 14px;
      background: var(--accent);
      color: #fff;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s ease;
    }
    .btn:hover {
      background: var(--accent-hover);
    }
    .btn-outline {
      background: transparent;
      border: 1px solid var(--card-border);
      color: var(--text-primary);
    }
    .btn-outline:hover {
      background: #1e242d;
    }
    .empty-state {
      padding: 32px;
      text-align: center;
      color: var(--text-secondary);
      font-size: 13px;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="brand">
        <div class="brand-logo">Æ</div>
        <div>
          <h1>Aetheris V5 Control Plane</h1>
          <div style="font-size: 12px; color: var(--text-secondary);">High-Performance MTProto Automation Core</div>
        </div>
      </div>
      <div class="status-pill">
        <span class="status-dot"></span>
        <span id="runtime-status">System Operational</span>
      </div>
    </header>

    <div class="grid-stats">
      <div class="card">
        <div class="stat-label">Total Invocations</div>
        <div class="stat-value" id="stat-total-cmds">0</div>
        <div class="stat-subtext" id="stat-err-rate">0.00% error rate</div>
      </div>
      <div class="card">
        <div class="stat-label">Latency (P95)</div>
        <div class="stat-value" id="stat-p95">0.0 ms</div>
        <div class="stat-subtext" id="stat-p50">P50: 0.0 ms</div>
      </div>
      <div class="card">
        <div class="stat-label">FloodShield V5</div>
        <div class="stat-value" id="stat-flood-count" style="color: var(--success);">0</div>
        <div class="stat-subtext" id="stat-flood-sec">0s backoff enforced</div>
      </div>
      <div class="card">
        <div class="stat-label">Process Memory</div>
        <div class="stat-value" id="stat-mem">0.0 MB</div>
        <div class="stat-subtext" id="stat-uptime">Uptime: 0s</div>
      </div>
    </div>

    <div class="main-grid">
      <div class="card">
        <div class="panel-title">
          <span>Active Supervised Jobs</span>
          <span style="font-size: 12px; color: var(--text-secondary); font-weight: normal;" id="active-jobs-count">0 running</span>
        </div>
        <div style="overflow-x: auto;">
          <table>
            <thead>
              <tr>
                <th>Job ID</th>
                <th>Name</th>
                <th>Priority</th>
                <th>State</th>
                <th>Progress</th>
              </tr>
            </thead>
            <tbody id="jobs-table-body">
              <tr>
                <td colspan="5" class="empty-state">No active background jobs currently scheduled.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <div class="panel-title">
          <span>Plugin Generations</span>
          <button class="btn btn-outline" onclick="triggerReload()">Hot Reload</button>
        </div>
        <div id="plugin-info" style="font-size: 13px; color: var(--text-secondary); line-height: 1.8;">
          <div>Architecture: <strong>V5 Zero-Downtime Host</strong></div>
          <div>Active Handlers: <span id="active-handlers" style="color: var(--text-primary); font-family: var(--font-mono);">0</span></div>
          <div>Plugin Isolation: <strong>Atomic Swap</strong></div>
          <div>Memory Engine: <strong>Cached SQLite / PostgreSQL</strong></div>
        </div>
        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--card-border);">
          <div class="stat-label">Top Commands</div>
          <div id="top-commands" style="font-family: var(--font-mono); font-size: 12px; margin-top: 8px;">
            None yet
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    async function fetchTelemetry() {
      try {
        const res = await fetch('/api/status');
        if (!res.ok) return;
        const data = await res.json();
        
        document.getElementById('stat-total-cmds').innerText = data.metrics.total_commands || 0;
        document.getElementById('stat-err-rate').innerText = (data.metrics.error_rate_pct || 0) + '% error rate';
        document.getElementById('stat-p95').innerText = (data.metrics.latencies_ms.p95 || 0) + ' ms';
        document.getElementById('stat-p50').innerText = 'P50: ' + (data.metrics.latencies_ms.p50 || 0) + ' ms';
        
        const fCount = data.metrics.flood_waits.count || 0;
        const fElem = document.getElementById('stat-flood-count');
        fElem.innerText = fCount;
        fElem.style.color = fCount > 0 ? 'var(--warning)' : 'var(--success)';
        document.getElementById('stat-flood-sec').innerText = (data.metrics.flood_waits.total_seconds || 0) + 's backoff';

        document.getElementById('stat-mem').innerText = (data.metrics.memory_rss_mb || 0) + ' MB';
        document.getElementById('stat-uptime').innerText = 'Uptime: ' + (data.metrics.uptime_seconds || 0) + 's';
        
        document.getElementById('active-handlers').innerText = data.plugins.total_handlers || 0;

        // Top commands
        const top = data.metrics.top_commands || [];
        if (top.length > 0) {
          document.getElementById('top-commands').innerHTML = top.map(c => `<div>${c[0]}: ${c[1]} calls</div>`).join('');
        }

        // Active jobs
        const jobs = data.jobs || [];
        document.getElementById('active-jobs-count').innerText = jobs.length + ' active';
        const tbody = document.getElementById('jobs-table-body');
        if (jobs.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No active background jobs currently scheduled.</td></tr>';
        } else {
          tbody.innerHTML = jobs.map(j => `
            <tr>
              <td>${j.id}</td>
              <td>${j.name}</td>
              <td>${j.priority}</td>
              <td><span style="color: var(--success);">${j.state}</span></td>
              <td>${Math.round(j.progress * 100)}%</td>
            </tr>
          `).join('');
        }
      } catch (e) {
        console.error("Telemetry sync error:", e);
      }
    }

    async function triggerReload() {
      if (!confirm("Initiate zero-downtime hot reload across all active plugin generations?")) return;
      try {
        const res = await fetch('/api/plugins/reload', { method: 'POST' });
        const result = await res.json();
        alert(result.message || "Reload triggered");
        fetchTelemetry();
      } catch (e) {
        alert("Reload request failed: " + e);
      }
    }

    setInterval(fetchTelemetry, 2000);
    fetchTelemetry();
  </script>
</body>
</html>
"""
