/* ============================================================================
   OPERATION: RESTORE DATA LAB — main.js
   Utilitas yang dipakai di SEMUA halaman.
   ============================================================================ */

window.addEventListener("load", () => {
  const loader = document.getElementById("loadingScreen");
  if (loader) setTimeout(() => loader.classList.add("hide"), 450);
});

// Efek partikel dihapus (hemat CPU/RAM di hosting gratis). Fungsi dipertahankan agar halaman lama tidak error.
function initParticles() {}

function showAlert(elementId, type = "error") {
  const el = document.getElementById(elementId);
  if (!el) return;
  el.classList.remove("alert-error", "alert-success");
  el.classList.add(type === "error" ? "alert-error" : "alert-success", "show");
}
function hideAlert(elementId) {
  const el = document.getElementById(elementId);
  if (el) el.classList.remove("show");
}

/* ---------------------------------------------------------------------
   Animasi scan generik ("Verifying / Repairing / Decrypting...")
   --------------------------------------------------------------------- */
function playScanAnimation({ overlayId, label = "Verifying..." }) {
  return new Promise((resolve) => {
    const overlay = document.getElementById(overlayId);
    const labelEl = overlay.querySelector(".scan-progress");
    const fillEl = overlay.querySelector(".scan-bar-fill");
    const percentEl = overlay.querySelector(".scan-percent");

    if (labelEl) labelEl.textContent = label;
    fillEl.style.width = "0%";
    percentEl.textContent = "0%";
    overlay.classList.add("show");

    let progress = 0;
    const step = () => {
      progress += Math.random() * 17 + 8;
      if (progress >= 100) progress = 100;
      fillEl.style.width = progress + "%";
      percentEl.textContent = Math.floor(progress) + "%";
      if (progress < 100) setTimeout(step, 140);
      else setTimeout(resolve, 380);
    };
    step();
  });
}

function hideOverlay(overlayId) {
  const overlay = document.getElementById(overlayId);
  if (overlay) overlay.classList.remove("show");
}

/* ---------------------------------------------------------------------
   Animasi terminal (efek ketik baris demi baris) — dipakai di
   "Decrypting Mission Codes..." pada Final Mission.
   --------------------------------------------------------------------- */
function playTerminalLines(elementId, lines, lineDelay = 550) {
  return new Promise((resolve) => {
    const el = document.getElementById(elementId);
    el.textContent = "";
    let i = 0;
    function next() {
      if (i >= lines.length) { resolve(); return; }
      el.textContent += (i > 0 ? "\n" : "") + lines[i];
      i++;
      setTimeout(next, lineDelay);
    }
    next();
  });
}

/* ---------------------------------------------------------------------
   EFEK SUARA — disintesis lewat Web Audio API supaya project tetap
   ringan (tidak perlu file audio eksternal). Panitia yang ingin memakai
   file suara sendiri tinggal ganti isi kedua fungsi ini agar memutar
   <audio> dari /static/audio/ (folder sudah disediakan).
   --------------------------------------------------------------------- */
let __audioCtx = null;
function getAudioCtx() {
  if (!__audioCtx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (AC) __audioCtx = new AC();
  }
  return __audioCtx;
}

function playTone(freq, startDelay, duration, type = "sine", gain = 0.16) {
  const ctx = getAudioCtx();
  if (!ctx) return;
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  const t0 = ctx.currentTime + startDelay;
  g.gain.setValueAtTime(0, t0);
  g.gain.linearRampToValueAtTime(gain, t0 + 0.02);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
  osc.connect(g).connect(ctx.destination);
  osc.start(t0);
  osc.stop(t0 + duration + 0.05);
}

function playSuccessSound() {
  // arpeggio naik — nuansa "access granted"
  playTone(523.25, 0.00, 0.16, "sine");   // C5
  playTone(659.25, 0.10, 0.16, "sine");   // E5
  playTone(783.99, 0.20, 0.28, "sine");   // G5
}

function playErrorSound() {
  // dua nada rendah turun — nuansa "denied / error"
  playTone(220, 0.00, 0.22, "sawtooth", 0.12);
  playTone(160, 0.14, 0.30, "sawtooth", 0.12);
}

/* ---------------------------------------------------------------------
   RESULT OVERLAY — dipakai untuk feedback ACCESS GRANTED / gagal
   di semua mission station & Final Mission code entry.
   --------------------------------------------------------------------- */
function ensureResultOverlay() {
  let overlay = document.getElementById("resultOverlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "resultOverlay";
    overlay.className = "overlay result-overlay";
    overlay.innerHTML = `
      <div class="modal-box glass hud-corners rise-in">
        <div class="result-icon" id="resultIcon"></div>
        <div class="result-title" id="resultTitle"></div>
        <div class="result-subtitle" id="resultSubtitle"></div>
      </div>`;
    document.body.appendChild(overlay);
  }
  return overlay;
}

/**
 * showResultOverlay({ type: 'success'|'error', title, subtitle, subnote, duration })
 * Menampilkan flash ACCESS GRANTED / error selama `duration` ms lalu
 * otomatis menutup. Mengembalikan Promise yang resolve setelah tertutup.
 */
function showResultOverlay({ type, title, subtitle = "", subnote = "", duration = 1700 }) {
  return new Promise((resolve) => {
    const overlay = ensureResultOverlay();
    overlay.classList.remove("flash-success", "flash-error");
    overlay.classList.add(type === "success" ? "flash-success" : "flash-error");

    document.getElementById("resultIcon").textContent = type === "success" ? "✓" : "✕";
    document.getElementById("resultTitle").textContent = title;
    document.getElementById("resultSubtitle").innerHTML =
      subtitle + (subnote ? `<small>${subnote}</small>` : "");

    if (type === "success") playSuccessSound();
    else playErrorSound();

    overlay.classList.add("show");
    setTimeout(() => {
      overlay.classList.remove("show");
      setTimeout(resolve, 300);
    }, duration);
  });
}

/* ---------------------------------------------------------------------
   Dipanggil ketika sebuah station berhasil diverifikasi: tampilkan
   Mission Code + kunci form + ubah indikator status ke ONLINE.
   --------------------------------------------------------------------- */
function onServerOnline(code) {
  const submitBtn = document.getElementById("submitBtn");
  if (submitBtn) submitBtn.disabled = true;
  document.querySelectorAll("#repairForm input, #repairForm select, #repairForm textarea")
    .forEach(el => el.disabled = true);

  const statusEl = document.getElementById("stationStatus");
  if (statusEl) {
    statusEl.classList.add("online");
    statusEl.querySelector(".status-label").textContent = "ONLINE";
  }

  const box = document.getElementById("codeRevealBox");
  if (box) {
    box.style.display = "block";
    box.querySelector(".code-value").textContent = code;
    box.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}
