/* ============================================================================
   present_mode.js — Mode Presentasi (fullscreen). Halaman berasal dari mesin layout server (sama dengan
   Preview dan PPTX). Navigasi: tombol, panah kiri/kanan, spasi, Esc untuk keluar.
   ============================================================================ */

let PM = { pages: [], index: 0 };

document.addEventListener("DOMContentLoaded", () => {
  PM.pages = JSON.parse(document.getElementById("deckData").textContent).pages || [];

  renderCurrentSlide();

  document.getElementById("pmPrevBtn").addEventListener("click", goPrev);
  document.getElementById("pmNextBtn").addEventListener("click", goNext);
  document.getElementById("enterFullscreenBtn").addEventListener("click", enterFullscreen);
  document.getElementById("pmExitBtn").addEventListener("click", exitPresentationMode);
  window.addEventListener("resize", renderCurrentSlide);          // hanya saat ukuran jendela berubah

  initDeleteWork();

  document.addEventListener("keydown", (e) => {
    if (deleteDialogOpen()) return;                                // dialog konfirmasi terbuka: pintasan presentasi dinonaktifkan (Esc dipegang dialog)
    if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); goNext(); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); goPrev(); }
    else if (e.key === "Escape") { exitPresentationMode(); }
  });

  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement) document.body.classList.remove("pm-fullscreen");
    renderCurrentSlide();
  });
});

function renderCurrentSlide() {
  const stage = document.getElementById("pmStage");
  const container = document.getElementById("pmSlideContainer");
  const availW = stage.clientWidth - 52, availH = stage.clientHeight - 90;     // sisakan ruang tombol navigasi
  const w = Math.max(240, Math.min(availW, availH * 16 / 9, 1600));
  container.style.width = w + "px";
  container.style.margin = "0 auto";
  drawPage(container, PM.pages[PM.index], w);
  updateNav();
}

function updateNav() {
  document.getElementById("pmCounter").textContent = `${PM.index + 1} / ${PM.pages.length}`;
  document.getElementById("pmPrevBtn").disabled = PM.index === 0;
  document.getElementById("pmNextBtn").disabled = PM.index === PM.pages.length - 1;
}

function goNext() { if (PM.index < PM.pages.length - 1) { PM.index++; renderCurrentSlide(); } }
function goPrev() { if (PM.index > 0) { PM.index--; renderCurrentSlide(); } }

function enterFullscreen() {
  document.body.classList.add("pm-fullscreen");
  const el = document.documentElement;
  if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
}

/** Keluar: hanya menutup tampilan dan kembali ke Studio; tidak pernah mengubah/menghapus data presentasi. */
function exitPresentationMode() {
  document.body.classList.remove("pm-fullscreen");
  if (document.fullscreenElement && document.exitFullscreen) {
    document.exitFullscreen().catch(() => {});
  }
  window.location.href = STUDIO_URL;
}


/* ============================================================================
   Hapus Pengerjaan — dialog konfirmasi lalu POST ke backend. Kelompok yang dihapus ditentukan SERVER dari sesi;
   group_number dikirim hanya sebagai pemeriksaan silang. Batal / Esc / klik latar = tidak ada perubahan data.
   ============================================================================ */
let DELETE_BUSY = false;
const deleteDialogOpen = () => { const d = document.getElementById("deleteDialog"); return !!d && !d.hidden; };

function initDeleteWork() {
  const dlg = document.getElementById("deleteDialog"), openBtn = document.getElementById("deleteWorkBtn");
  if (!dlg || !openBtn) return;
  const cancel = document.getElementById("deleteCancelBtn"), ok = document.getElementById("deleteConfirmBtn"), go = document.getElementById("deleteGoBtn");
  const notice = document.getElementById("deleteNotice");
  let lastFocus = null;

  const showNotice = (kind, text) => { notice.className = "pm-notice " + kind; notice.textContent = text; notice.hidden = false; };
  const openDlg = () => {
    lastFocus = document.activeElement;
    notice.hidden = true; go.hidden = true; ok.hidden = false; cancel.hidden = false; ok.disabled = false; cancel.disabled = false;
    dlg.hidden = false; requestAnimationFrame(() => dlg.classList.add("show"));
    cancel.focus();                                               // fokus awal ke Batal (aksi aman)
  };
  const closeDlg = () => {
    if (DELETE_BUSY) return;                                      // jangan ditutup saat permintaan berjalan
    dlg.classList.remove("show"); dlg.hidden = true;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  };

  openBtn.addEventListener("click", openDlg);
  cancel.addEventListener("click", closeDlg);
  dlg.addEventListener("click", (e) => { if (e.target === dlg) closeDlg(); });
  dlg.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); closeDlg(); }
    else if (e.key === "Tab") {                                   // fokus tetap di dalam dialog
      const f = [...dlg.querySelectorAll("button, a[href]")].filter((x) => !x.hidden && !x.disabled);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });

  ok.addEventListener("click", async () => {
    if (DELETE_BUSY) return;                                      // cegah permintaan ganda
    DELETE_BUSY = true; ok.disabled = true; cancel.disabled = true; ok.textContent = "Menghapus…"; notice.hidden = true;
    try {
      const res = await fetch("/api/final/delete-work", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": PM_CSRF, "X-Reset-Epoch": String(PM_EPOCH) },
        body: JSON.stringify({ confirm: true, group_number: PM_GROUP }),
      });
      let data = null;
      try { data = await res.json(); } catch (e) { data = null; }
      if (res.ok && data && data.success) {
        ok.hidden = true; cancel.hidden = true; go.hidden = false; go.focus();
        document.getElementById("deleteTitle").textContent = "Pengerjaan Dihapus";
        showNotice("ok", "Pengerjaan berhasil dihapus. Kelompok dapat mengerjakan Final Mission kembali.");
      } else {
        const why = data && data.reason;
        const msg = why === "reset_happened" ? "Pengerjaan kelompok ini sudah dihapus/direset sebelumnya. Muat ulang halaman."
          : why === "no_group" ? "Sesi kelompok tidak ditemukan. Masuk ulang ke kelompokmu lalu coba lagi."
          : why === "csrf" ? "Sesi halaman sudah tidak valid. Muat ulang halaman lalu coba lagi."
          : why === "group_mismatch" ? "Halaman ini bukan milik kelompok pada sesi saat ini. Muat ulang halaman."
          : "Pengerjaan GAGAL dihapus (" + (why || ("HTTP " + res.status)) + "). Tidak ada data yang dihapus; coba lagi atau hubungi panitia.";
        showNotice("err", msg); ok.disabled = false; cancel.disabled = false; ok.textContent = "Ya, Hapus Pengerjaan";
      }
    } catch (err) {
      showNotice("err", "Tidak dapat menghubungi server. Pengerjaan belum dihapus; periksa koneksi lalu coba lagi.");
      ok.disabled = false; cancel.disabled = false; ok.textContent = "Ya, Hapus Pengerjaan";
    } finally { DELETE_BUSY = false; }
  });
}
