const tokenInput = document.querySelector("#admin-token");
const saveTokenBtn = document.querySelector("#save-token");
const loadDashboardBtn = document.querySelector("#load-dashboard");
const statsBox = document.querySelector("#stats");
const result = document.querySelector("#admin-result");
const tbody = document.querySelector("#uploads-table tbody");
const searchBtn = document.querySelector("#search-btn");
const csvBtn = document.querySelector("#csv-btn");

const statusInput = document.querySelector("#filter-status");
const qInput = document.querySelector("#filter-q");
const ipInput = document.querySelector("#filter-ip");
const limitInput = document.querySelector("#filter-limit");

const TOKEN_KEY = "ofs_admin_token";

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
    <div class="stat"><span>Scanner</span><strong>${stats.scanner_up ? "UP" : "DOWN"}</strong></div>
  `;
}

function renderRows(rows) {
  tbody.innerHTML = rows
    .map(
      (row) => `
      <tr>
        <td>${row.id}</td>
        <td>${row.created_at}</td>
        <td title="${row.original_filename}">${row.original_filename}</td>
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
    result.textContent = `Loaded ${rows.length} records.`;
  } catch (error) {
    result.textContent = `Error: ${error.message}`;
  }
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

saveTokenBtn.addEventListener("click", saveToken);
loadDashboardBtn.addEventListener("click", loadDashboard);
searchBtn.addEventListener("click", loadDashboard);
csvBtn.addEventListener("click", exportCsv);

tokenInput.value = getToken();
