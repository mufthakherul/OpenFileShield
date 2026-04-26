const tokenInput = document.querySelector("#admin-token");
const saveTokenBtn = document.querySelector("#save-token");
const loadDashboardBtn = document.querySelector("#load-dashboard");
const statsBox = document.querySelector("#stats");
const result = document.querySelector("#admin-result");
const tbody = document.querySelector("#uploads-table tbody");
const searchBtn = document.querySelector("#search-btn");
const refreshBtn = document.querySelector("#refresh-btn");
const toggleAutoBtn = document.querySelector("#toggle-auto-btn");
const csvBtn = document.querySelector("#csv-btn");
const trendDaysInput = document.querySelector("#trend-days");
const trendCanvas = document.querySelector("#trend-chart");
const adminRoot = document.querySelector("#admin-root");

const statusInput = document.querySelector("#filter-status");
const qInput = document.querySelector("#filter-q");
const ipInput = document.querySelector("#filter-ip");
const limitInput = document.querySelector("#filter-limit");

const TOKEN_KEY = "ofs_admin_token";
let autoTimer = null;
let autoEnabled = true;

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function saveToken() {
  const token = tokenInput.value.trim();
  if (!token) {
    result.textContent = "Provide a token before saving.";
    return;
  }
  localStorage.setItem(TOKEN_KEY, token);
  result.textContent = "Token saved in browser local storage for this device.";
}

function buildQuery() {
  const params = new URLSearchParams();
  if (statusInput.value) params.set("status", statusInput.value);
  if (qInput.value.trim()) params.set("q", qInput.value.trim());
  if (ipInput.value.trim()) params.set("ip", ipInput.value.trim());
  params.set("limit", limitInput.value || "100");
  return params.toString();
}

function bytesToHuman(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function renderStats(stats) {
  statsBox.innerHTML = `
    <div class="stat"><span>Total</span><strong>${stats.total}</strong></div>
    <div class="stat"><span>Stored</span><strong>${stats.stored}</strong></div>
    <div class="stat"><span>Rejected</span><strong>${stats.rejected}</strong></div>
    <div class="stat"><span>Duplicates</span><strong>${stats.duplicates}</strong></div>
    <div class="stat"><span>Queued</span><strong>${stats.queued}</strong></div>
    <div class="stat"><span>Scanner</span><strong>${stats.scanner_up ? "UP" : "DOWN"}</strong></div>
  `;
}

function drawTrendChart(points) {
  if (!trendCanvas) return;
  const ctx = trendCanvas.getContext("2d");
  if (!ctx) return;

  const dpr = window.devicePixelRatio || 1;
  const cssWidth = trendCanvas.clientWidth || 1100;
  const cssHeight = trendCanvas.clientHeight || 280;
  trendCanvas.width = Math.floor(cssWidth * dpr);
  trendCanvas.height = Math.floor(cssHeight * dpr);
  ctx.scale(dpr, dpr);

  ctx.clearRect(0, 0, cssWidth, cssHeight);
  ctx.fillStyle = "rgba(0,0,0,0.22)";
  ctx.fillRect(0, 0, cssWidth, cssHeight);

  if (!points?.length) return;

  const maxY = Math.max(
    1,
    ...points.map((p) => Math.max(p.stored, p.rejected, p.queued)),
  );

  const pad = { l: 42, r: 16, t: 18, b: 28 };
  const w = cssWidth - pad.l - pad.r;
  const h = cssHeight - pad.t - pad.b;

  ctx.strokeStyle = "rgba(255,255,255,0.15)";
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + (h * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad.l, y);
    ctx.lineTo(cssWidth - pad.r, y);
    ctx.stroke();
  }

  const drawLine = (key, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    points.forEach((point, index) => {
      const x = pad.l + (w * index) / Math.max(1, points.length - 1);
      const y = pad.t + h - (h * point[key]) / maxY;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  };

  drawLine("stored", "#00e5b3");
  drawLine("rejected", "#ff9d7a");
  drawLine("queued", "#9ec5ff");

  ctx.fillStyle = "#cde9f3";
  ctx.font = "12px Space Grotesk";
  ctx.fillText(`Max/day: ${maxY}`, pad.l, 12);
  ctx.fillText("Stored", pad.l + 120, 12);
  ctx.fillStyle = "#ff9d7a";
  ctx.fillText("Rejected", pad.l + 180, 12);
  ctx.fillStyle = "#9ec5ff";
  ctx.fillText("Queued", pad.l + 255, 12);
}

function renderRows(rows) {
  tbody.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${row.id}</td>
        <td>${row.created_at}</td>
        <td title="${row.original_filename}">${row.original_filename}</td>
        <td title="${row.uploader_notes || ""}">${row.uploader_notes || ""}</td>
        <td>${row.upload_status}</td>
        <td>${row.scan_result}</td>
        <td>${bytesToHuman(row.file_size_bytes)}</td>
        <td>${row.uploader_ip}</td>
        <td title="${row.device_fingerprint}">${row.device_fingerprint.slice(0, 12)}...</td>
      </tr>
    `,
    )
    .join("");
}

async function loadDashboard() {
  const token = getToken();
  if (!token) {
    result.textContent = "Set and save admin token first.";
    return;
  }

  const headers = { "x-admin-token": token };
  const query = buildQuery();

  try {
    const [statsRes, uploadsRes] = await Promise.all([
      fetch("/api/stats", { headers }),
      fetch(`/api/uploads?${query}`, { headers }),
    ]);

    if (!statsRes.ok || !uploadsRes.ok) {
      result.textContent = "Admin API access failed. Verify token.";
      return;
    }

    const [stats, rows] = await Promise.all([statsRes.json(), uploadsRes.json()]);
    renderStats(stats);
    renderRows(rows);
    await loadTrends(headers);
    result.textContent = `Loaded ${rows.length} records.`;
  } catch (error) {
    result.textContent = `Error: ${error.message}`;
  }
}

async function loadTrends(headers) {
  const days = Number(trendDaysInput?.value || 14);
  const trendsRes = await fetch(`/api/trends?days=${days}`, { headers });
  if (!trendsRes.ok) {
    return;
  }
  const points = await trendsRes.json();
  drawTrendChart(points);
}

function exportCsv() {
  const token = getToken();
  if (!token) {
    result.textContent = "Set and save admin token first.";
    return;
  }

  const query = buildQuery();
  window.location.href = `/api/uploads/export.csv?${query}&x_admin_token=${encodeURIComponent(token)}`;
}

function startAutoRefresh() {
  const seconds = Number(adminRoot?.dataset.refreshSeconds || 15);
  if (autoTimer) clearInterval(autoTimer);
  autoTimer = setInterval(() => {
    if (autoEnabled) {
      loadDashboard();
    }
  }, Math.max(5, seconds) * 1000);
}

function toggleAuto() {
  autoEnabled = !autoEnabled;
  toggleAutoBtn.textContent = autoEnabled ? "Pause Auto Refresh" : "Resume Auto Refresh";
}

saveTokenBtn.addEventListener("click", saveToken);
loadDashboardBtn.addEventListener("click", loadDashboard);
searchBtn.addEventListener("click", loadDashboard);
refreshBtn.addEventListener("click", loadDashboard);
toggleAutoBtn.addEventListener("click", toggleAuto);
csvBtn.addEventListener("click", exportCsv);

tokenInput.value = getToken();
if (trendDaysInput && adminRoot?.dataset.trendDays) {
  trendDaysInput.value = adminRoot.dataset.trendDays;
}
startAutoRefresh();
