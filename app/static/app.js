const form = document.querySelector("#upload-form");
const result = document.querySelector("#result");
const dropZone = document.querySelector("#drop-zone");
const fileInput = document.querySelector("#file-input");
const fileName = document.querySelector("#file-name");
const submitBtn = document.querySelector("#submit-btn");
const scanModeInput = document.querySelector("#scan-mode");

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
  result.textContent = selectedCount
    ? `Uploading ${selectedCount} file${selectedCount === 1 ? "" : "s"} to quarantine and running malware scan...`
    : "Uploading files to quarantine and running malware scan...";

  const formData = new FormData(form);
  formData.set("consent", formData.get("consent") ? "true" : "false");
  const endpoint = scanModeInput?.value === "async" ? "/api/upload/async" : "/api/upload";
  formData.delete("scan_mode");

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      body: formData,
    });

    const rawBody = await response.text();
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
      const summary = [
        `Batch ${payload.request_id} completed`,
        `Stored: ${payload.stored} | Rejected: ${payload.rejected} | Queued: ${payload.queued}`,
        ...payload.items.map((item) => `${item.original_filename}: ${item.upload_status} (${item.scan_result})`),
      ].join("\n");
      result.textContent = summary;
    } else {
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
