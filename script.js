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
  if (!window.LensApp) {
    alert('Application not ready. Please refresh the page.');
    return;
  }
  
  console.log('Starting upload for file:', file.name);
  
  try {
    await window.LensApp.requireAuth();
  } catch (e) {
    console.log('Auth required, starting sign in flow');
    return;
  }
  
  try {
    await window.LensApp.requireApiKey();
  } catch (e) {
    console.log('API key required, redirecting to settings');
    alert('Please add your Gemini API key in Settings first.');
    window.LensConfig.navigate("settings.html?reason=api_key_required");
    return;
  }
  
  const session = window.LensApp.session;
  if (!session) {
    alert('Session lost. Please sign in again.');
    return;
  }

  setUploadState("processing");
  setProcessingText("Validating file...", 10);
  
  try {
    // File validation
    const maxSize = 50 * 1024 * 1024; // 50MB
    if (file.size > maxSize) {
      throw new Error('File size exceeds 50MB limit');
    }
    
    const allowedTypes = ['application/pdf', 'text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(pdf|csv|xls|xlsx)$/i)) {
      throw new Error('Unsupported file type. Please upload PDF, CSV, XLS, or XLSX files.');
    }
    
    setProcessingText("Uploading secure file payload...", 30);
    console.log('Uploading to:', `${window.LensApp.apiBase}/api/upload`);
    
    const fd = new FormData();
    fd.append("file", file);
    
    const upRes = await fetch(`${window.LensApp.apiBase}/api/upload?include_ai_summary=true`, {
      method: "POST",
      headers: { Authorization: `Bearer ${session.access_token}` },
      body: fd,
    });
    
    console.log('Upload response status:', upRes.status);
    const upJson = await upRes.json();
    
    if (!upRes.ok) {
      console.error('Upload error:', upJson);
      throw new Error(upJson.detail || `Upload failed with status ${upRes.status}`);
    }
    
    console.log('Upload success:', upJson);
    
    setProcessingText("Retrieving dashboard insights...", 70);
    const fileId = upJson.file_id;
    localStorage.setItem("lens_last_file_id", fileId);
    
    const dashRes = await fetch(`${window.LensApp.apiBase}/api/dashboard/${fileId}`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    
    console.log('Dashboard response status:', dashRes.status);
    const dashJson = await dashRes.json();
    
    if (!dashRes.ok) {
      console.error('Dashboard error:', dashJson);
      throw new Error(dashJson.detail || `Dashboard fetch failed with status ${dashRes.status}`);
    }
    
    console.log('Dashboard success:', dashJson);
    localStorage.setItem("lens_last_dashboard", JSON.stringify(dashJson));

    // Update success message with actual data
    const successMsg = document.getElementById("successMessage");
    if (successMsg && dashJson.kpis) {
      const txCount = dashJson.transactions ? dashJson.transactions.length : 0;
      const leaksCount = dashJson.leaks ? dashJson.leaks.length : 0;
      successMsg.textContent = `Processed ${txCount} transactions and found ${leaksCount} potential money leaks.`;
    }

    setProcessingText("Analysis complete. Opening dashboard…", 100);
    setUploadState("success");
    
    setTimeout(() => {
      window.LensConfig.navigate("dashboard.html");
    }, 1000);
    
  } catch (err) {
    console.error('Upload flow error:', err);
    setUploadState("idle");
    
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      alert('Backend unreachable. Please check if the server is running at ' + window.LensApp.apiBase);
    } else {
      alert(err.message || "Upload failed. Please try again.");
    }
  }
}

// Dashboard button handler
const dashboardBtn = document.getElementById("dashboardBtn");
if (dashboardBtn) {
  dashboardBtn.addEventListener("click", () => {
    if (window.LensApp && window.LensApp.session) {
      window.LensConfig.navigate("dashboard.html");
    } else {
      // Redirect to upload section if not authenticated
      document.getElementById("upload").scrollIntoView({ behavior: "smooth" });
    }
  });
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
