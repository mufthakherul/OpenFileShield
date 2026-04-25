const form = document.querySelector("#upload-form");
const result = document.querySelector("#result");
const dropZone = document.querySelector("#drop-zone");
const fileInput = document.querySelector("#file-input");
const fileName = document.querySelector("#file-name");
const submitBtn = document.querySelector("#submit-btn");
const scanModeInput = document.querySelector("#scan-mode");

function setFileName() {
  const file = fileInput.files[0];
  fileName.textContent = file ? `Selected: ${file.name}` : "";
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
  result.textContent = "Uploading file to quarantine and running malware scan...";

  const formData = new FormData(form);
  formData.set("consent", formData.get("consent") ? "true" : "false");
  const endpoint = scanModeInput?.value === "async" ? "/api/upload/async" : "/api/upload";
  formData.delete("scan_mode");

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      result.textContent = `Rejected: ${payload.detail || "Unknown error"}`;
      return;
    }

    result.textContent = JSON.stringify(payload, null, 2);
    form.reset();
    setFileName();
  } catch (error) {
    result.textContent = `Error: ${error.message}`;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Scan and Upload";
  }
});
