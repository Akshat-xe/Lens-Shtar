const navbar = document.getElementById("navbar");
window.addEventListener("scroll", () => {
  if (navbar) navbar.style.boxShadow = window.scrollY > 50 ? "0 4px 24px rgba(0,0,0,0.4)" : "none";
});

const mobileBtn = document.getElementById("mobileMenuBtn");
const navLinks = document.getElementById("navLinks");
const navActions = document.getElementById("navActions");
if (mobileBtn && navLinks) {
  mobileBtn.addEventListener("click", () => {
    const isOpen = navLinks.classList.toggle("active");
    if (navbar) navbar.classList.toggle("mobile-open", isOpen);
    if (navActions) navActions.classList.toggle("active", isOpen);
    mobileBtn.classList.toggle("open");
  });
}

function setUploadState(state) {
  const idle = document.getElementById("stateIdle");
  const processing = document.getElementById("stateProcessing");
  const success = document.getElementById("stateSuccess");
  if (!idle || !processing || !success) return;
  idle.classList.toggle("active", state === "idle");
  processing.classList.toggle("active", state === "processing");
  success.classList.toggle("active", state === "success");
}

function setProcessingText(msg, pct) {
  const text = document.getElementById("mockStatusText");
  const bar = document.getElementById("mockProgressBar");
  if (text) text.innerText = msg;
  if (bar && typeof pct === "number") bar.style.width = `${pct}%`;
}

async function uploadRealFile(file) {
  if (!window.LensApp) return;
  try {
    await window.LensApp.requireAuth();
    await window.LensApp.requireApiKey();
  } catch (_) {
    return;
  }
  const session = window.LensApp.session;
  if (!session) return;

  setUploadState("processing");
  setProcessingText("Uploading secure file payload...", 20);
  try {
    const fd = new FormData();
    fd.append("file", file);
    const upRes = await fetch(`${window.LensApp.apiBase}/api/upload?include_ai_summary=true`, {
      method: "POST",
      headers: { Authorization: `Bearer ${session.access_token}` },
      body: fd,
    });
    const upJson = await upRes.json();
    if (!upRes.ok) throw new Error(upJson.detail || "Upload failed");

    setProcessingText("Retrieving dashboard insights...", 74);
    const fileId = upJson.file_id;
    localStorage.setItem("lens_last_file_id", fileId);
    const dashRes = await fetch(`${window.LensApp.apiBase}/api/dashboard/${fileId}`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    const dashJson = await dashRes.json();
    if (!dashRes.ok) throw new Error(dashJson.detail || "Dashboard fetch failed");
    localStorage.setItem("lens_last_dashboard", JSON.stringify(dashJson));

    setProcessingText("Analysis complete. Opening dashboard…", 100);
    setUploadState("success");
    setTimeout(() => (window.location.href = "/dashboard.html"), 650);
  } catch (err) {
    setUploadState("idle");
    alert(err.message || "Upload failed.");
  }
}

const uploadInput = document.getElementById("realUploadInput");
const browseBtn = document.getElementById("browseUploadBtn");
if (browseBtn && uploadInput) browseBtn.addEventListener("click", () => uploadInput.click());
if (uploadInput) {
  uploadInput.addEventListener("change", () => {
    const file = uploadInput.files && uploadInput.files[0];
    if (file) uploadRealFile(file);
  });
}

const uploadBox = document.getElementById("uploadBox");
if (uploadBox) {
  uploadBox.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadBox.style.borderColor = "var(--primary)";
  });
  uploadBox.addEventListener("dragleave", () => {
    uploadBox.style.borderColor = "";
  });
  uploadBox.addEventListener("drop", (e) => {
    e.preventDefault();
    const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) uploadRealFile(file);
  });
}
