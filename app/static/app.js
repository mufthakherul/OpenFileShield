const form = document.querySelector("#upload-form");
const result = document.querySelector("#result");
const dropZone = document.querySelector("#drop-zone");
const fileInput = document.querySelector("#file-input");
const fileName = document.querySelector("#file-name");
const submitBtn = document.querySelector("#submit-btn");
const scanModeInput = document.querySelector("#scan-mode");
const uploadProgressLabel = document.querySelector("#upload-progress-label");
const uploadProgressFill = document.querySelector("#upload-progress-fill");
const uploadProgressTrack = document.querySelector(".upload-progress-track");
const metricSuccessCount = document.querySelector("#metric-success-count");
const metricSuccessPct = document.querySelector("#metric-success-pct");
const metricFailedCount = document.querySelector("#metric-failed-count");
const metricFailedPct = document.querySelector("#metric-failed-pct");
const metricProcessingCount = document.querySelector("#metric-processing-count");
const metricProcessingPct = document.querySelector("#metric-processing-pct");
const metricCheckingCount = document.querySelector("#metric-checking-count");
const metricCheckingPct = document.querySelector("#metric-checking-pct");

function toPct(part, total) {
  if (!total) return "0%";
  return `${Math.round((part / total) * 100)}%`;
}

function setUploadProgress(value) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));
  if (uploadProgressLabel) uploadProgressLabel.textContent = `${pct}%`;
  if (uploadProgressFill) uploadProgressFill.style.width = `${pct}%`;
  if (uploadProgressTrack) uploadProgressTrack.setAttribute("aria-valuenow", String(pct));
}

function setOutcomeMetrics({ success = 0, failed = 0, processing = 0, checking = 0, total = 0 }) {
  if (metricSuccessCount) metricSuccessCount.textContent = String(success);
  if (metricFailedCount) metricFailedCount.textContent = String(failed);
  if (metricProcessingCount) metricProcessingCount.textContent = String(processing);
  if (metricCheckingCount) metricCheckingCount.textContent = String(checking);

  if (metricSuccessPct) metricSuccessPct.textContent = toPct(success, total);
  if (metricFailedPct) metricFailedPct.textContent = toPct(failed, total);
  if (metricProcessingPct) metricProcessingPct.textContent = toPct(processing, total);
  if (metricCheckingPct) metricCheckingPct.textContent = toPct(checking, total);
}

function summarizeItems(items) {
  const total = items.length;
  let success = 0;
  let failed = 0;
  let processing = 0;
  let checking = 0;

  for (const item of items) {
    const status = String(item.upload_status || "").toLowerCase();
    const scan = String(item.scan_result || "").toLowerCase();
    if (status === "stored" || status === "stored_duplicate") {
      success += 1;
      continue;
    }
    if (status === "rejected") {
      failed += 1;
      continue;
    }
    if (status === "processing") {
      processing += 1;
      continue;
    }
    if (status === "queued" || scan === "queued" || scan === "processing") {
      checking += 1;
      continue;
    }
    checking += 1;
  }

  return { total, success, failed, processing, checking };
}

function uploadWithProgress(endpoint, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", endpoint);
    xhr.responseType = "text";

    xhr.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) return;
      const pct = Math.round((event.loaded / event.total) * 100);
      onProgress(pct);
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Network error while uploading files"));
    });

    xhr.addEventListener("load", () => {
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, body: xhr.responseText || "" });
    });

    xhr.send(formData);
  });
}

function setFileName() {
  const files = Array.from(fileInput.files || []);
  if (!files.length) {
    fileName.textContent = "";
    return;
  }
  const preview = files.slice(0, 3).map((file) => file.name).join(", ");
  fileName.textContent = files.length > 3 ? `Selected ${files.length} files: ${preview}, ...` : `Selected ${files.length} file${files.length > 1 ? "s" : ""}: ${preview}`;
}

fileInput.addEventListener("change", setFileName);

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("is-drag");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("is-drag");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-drag");
  if (event.dataTransfer?.files?.length) {
    fileInput.files = event.dataTransfer.files;
    setFileName();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  submitBtn.disabled = true;
  submitBtn.textContent = "Scanning...";
  const selectedCount = fileInput.files?.length || 0;
  setUploadProgress(0);
  setOutcomeMetrics({ success: 0, failed: 0, processing: 0, checking: selectedCount, total: selectedCount });
  result.textContent = selectedCount
    ? `Uploading ${selectedCount} file${selectedCount === 1 ? "" : "s"} to quarantine and running malware scan...`
    : "Uploading files to quarantine and running malware scan...";

  const formData = new FormData(form);
  formData.set("consent", formData.get("consent") ? "true" : "false");
  const endpoint = scanModeInput?.value === "async" ? "/api/upload/async" : "/api/upload";
  formData.delete("scan_mode");

  try {
    const response = await uploadWithProgress(endpoint, formData, (pct) => {
      setUploadProgress(pct);
    });

    const rawBody = response.body;
    let payload = null;
    if (rawBody) {
      try {
        payload = JSON.parse(rawBody);
      } catch {
        payload = null;
      }
    }

    if (!response.ok) {
      result.textContent = `Rejected: ${payload?.detail || rawBody || "Unknown error"}`;
      return;
    }

    if (payload?.items?.length) {
      setUploadProgress(100);
      const stats = summarizeItems(payload.items);
      if (typeof payload.processing === "number") stats.processing = payload.processing;
      if (typeof payload.checking === "number") stats.checking = payload.checking;
      setOutcomeMetrics(stats);
      const summary = [
        `Batch ${payload.request_id} completed`,
        `Stored: ${payload.stored} (${toPct(payload.stored, payload.total_files)}) | Rejected: ${payload.rejected} (${toPct(payload.rejected, payload.total_files)}) | Queued: ${payload.queued} (${toPct(payload.queued, payload.total_files)})`,
        `Success: ${stats.success} (${toPct(stats.success, stats.total)}) | Failed: ${stats.failed} (${toPct(stats.failed, stats.total)}) | Processing: ${stats.processing} (${toPct(stats.processing, stats.total)}) | Checking: ${stats.checking} (${toPct(stats.checking, stats.total)})`,
        ...payload.items.map((item) => `${item.original_filename}: ${item.upload_status} (${item.scan_result})`),
      ].join("\n");
      result.textContent = summary;
    } else {
      setUploadProgress(100);
      result.textContent = payload ? JSON.stringify(payload, null, 2) : rawBody || "Upload completed.";
    }
    form.reset();
    setFileName();
  } catch (error) {
    result.textContent = `Error: ${error.message}`;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Scan and Upload";
  }
});
