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

  document.addEventListener("keydown", (e) => {
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
