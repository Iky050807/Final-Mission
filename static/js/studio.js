/* ============================================================================
   studio.js — Presentation Studio.
   * Data resmi di backend; localStorage hanya untuk DRAFT yang belum tersimpan dan preferensi UI.
   * Autosave ke backend di-debounce 1,5 detik (bukan per karakter); status: Menyimpan / Tersimpan / Gagal.
   * Preview = halaman hasil mesin layout server (sama dengan PPTX), diperbarui setelah simpan berhasil.
   ============================================================================ */

const LAYOUT_FIELDS = {
  cover: ["fieldSubtitle", "fieldGroupName"],
  team: [],
  mission_grid: ["fieldMissions"],
  content: ["fieldBody"],
  steps: ["fieldBody"],
  two_column: ["fieldBody", "fieldBodyRight"],
  code: ["fieldBody"],
  closing: ["fieldClosingStatement", "fieldGroupName"],
};
const ALL_TOGGLE_FIELDS = ["fieldSubtitle", "fieldGroupName", "fieldClosingStatement", "fieldMissions", "fieldBody", "fieldBodyRight"];
const LS_DRAFT = "axis2026_presentation_draft_v1", LS_MEMBERS = "axis2026_members_draft_v1", LS_UI = "axis2026_ui_preferences_v1";
const SAVE_DELAY = 1500;

const ls = {
  get(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage tidak tersedia */ } },
  del(k) { try { localStorage.removeItem(k); } catch (e) { /* abaikan */ } },
};

let ST = { config: null, deck: null, index: 0, page: 0, dirty: false };
let PA = { index: 0 };
let __saveTimer = null, __saving = false;

document.addEventListener("DOMContentLoaded", () => {
  initParticles();
  ST.config = JSON.parse(document.getElementById("configData").textContent);
  ST.deck = JSON.parse(document.getElementById("deckData").textContent);
  if (!ST.config.slides || !ST.config.slides.length) ST.config.slides = [makeSlide("cover")];
  const ui = ls.get(LS_UI);
  if (ui && Number.isInteger(ui.studio_slide) && ui.studio_slide < ST.config.slides.length) ST.index = ui.studio_slide;

  bindFormEvents();
  bindMembers();
  document.getElementById("addSlideBtn").addEventListener("click", () => addSlide("content"));
  document.querySelectorAll(".studio-theme-swatch").forEach((btn) => {
    btn.addEventListener("click", () => applyTheme(btn.dataset.theme, btn.dataset.bg, btn.dataset.text, btn.dataset.accent));
  });
  document.getElementById("presentBtn").addEventListener("click", async () => { if (await flush()) window.location.href = "/present"; });
  document.getElementById("downloadBtn").addEventListener("click", async () => { if (await flush()) window.location.href = "/download/pptx"; });
  document.getElementById("retrySaveBtn").addEventListener("click", () => saveNow());
  document.getElementById("pagePrev").addEventListener("click", () => { if (ST.page > 0) { ST.page--; renderPreview(); } });
  document.getElementById("pageNext").addEventListener("click", () => { if (ST.page < pagesOf(ST.index).length - 1) { ST.page++; renderPreview(); } });
  const rb = document.getElementById("rebuildBtn");
  if (rb) rb.addEventListener("click", rebuild);
  window.addEventListener("resize", renderPreview);
  window.addEventListener("beforeunload", (e) => { if (ST.dirty) { e.preventDefault(); e.returnValue = ""; } });

  initPreviewAllModal();
  checkDraft();
  renderSlideList();
  selectSlide(ST.index);
});

function makeSlide(layout) {
  const big = layout === "cover" || layout === "closing";
  return {
    id: "s" + Math.random().toString(36).slice(2, 9), layout,
    title: big ? "Judul" : "Judul Slide", subtitle: "", body: "", body_right: "", members: "", missions_text: "",
    closing_statement: "", group_name: "", font_family: "Calibri", font_size: big ? 36 : 22,
    bold: big, italic: false, underline: false, align: big ? "center" : "left",
    text_color: "#eef3ff", bg_color: "#030b1a", accent_color: "#38bdf8",
  };
}

function currentSlide() { return ST.config.slides[ST.index]; }
function pagesOf(i) { return (ST.deck.pages || []).filter((p) => p.source === i); }
function esc(str) { const d = document.createElement("div"); d.textContent = str == null ? "" : String(str); return d.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;"); }

/* ------------------------------------------------------------ daftar slide */
function renderSlideList() {
  const container = document.getElementById("slideListItems");
  container.innerHTML = ST.config.slides.map((s, i) => `
    <div class="studio-slide-item ${i === ST.index ? "active" : ""}" data-index="${i}">
      <span class="slide-num">${i + 1}</span>
      <span class="slide-title">${esc(s.title || "(tanpa judul)")}</span>
      <span class="slide-actions">
        <button type="button" data-action="up" title="Naik">▲</button>
        <button type="button" data-action="down" title="Turun">▼</button>
        <button type="button" data-action="dup" title="Duplikat">⧉</button>
        <button type="button" data-action="del" title="Hapus">✕</button>
      </span>
    </div>`).join("");
  container.querySelectorAll(".studio-slide-item").forEach((item) => {
    const idx = parseInt(item.dataset.index, 10);
    item.addEventListener("click", (e) => { if (!e.target.dataset.action) selectSlide(idx); });
    item.querySelectorAll("[data-action]").forEach((btn) => {
      btn.addEventListener("click", (e) => { e.stopPropagation(); handleSlideAction(idx, btn.dataset.action); });
    });
  });
}

function handleSlideAction(idx, action) {
  const slides = ST.config.slides;
  if (action === "up" && idx > 0) { [slides[idx - 1], slides[idx]] = [slides[idx], slides[idx - 1]]; ST.index = idx - 1; }
  if (action === "down" && idx < slides.length - 1) { [slides[idx + 1], slides[idx]] = [slides[idx], slides[idx + 1]]; ST.index = idx + 1; }
  if (action === "dup") {
    const clone = JSON.parse(JSON.stringify(slides[idx]));
    clone.id = "s" + Math.random().toString(36).slice(2, 9);
    slides.splice(idx + 1, 0, clone); ST.index = idx + 1;
  }
  if (action === "del" && slides.length > 1) {
    if (!confirm("Hapus slide ini?")) return;
    slides.splice(idx, 1); ST.index = Math.max(0, idx - 1);
  }
  renderSlideList(); selectSlide(ST.index); markDirty();
}

function addSlide(layout) {
  ST.config.slides.push(makeSlide(layout));
  ST.index = ST.config.slides.length - 1;
  renderSlideList(); selectSlide(ST.index); markDirty();
}

function selectSlide(i) {
  ST.index = i; ST.page = 0;
  ls.set(LS_UI, Object.assign(ls.get(LS_UI) || {}, { studio_slide: i }));
  document.querySelectorAll(".studio-slide-item").forEach((el) => el.classList.toggle("active", parseInt(el.dataset.index, 10) === i));
  renderForm(); renderPreview();
}

/* ------------------------------------------------------------ form */
function syncFieldsForLayout() {
  const toShow = new Set(LAYOUT_FIELDS[currentSlide().layout] || []);
  ALL_TOGGLE_FIELDS.forEach((id) => { document.getElementById(id).style.display = toShow.has(id) ? "block" : "none"; });
}

function bindFormEvents() {
  const bind = (id, field, transform) => {
    document.getElementById(id).addEventListener("input", (e) => {
      currentSlide()[field] = transform ? transform(e.target.value) : e.target.value;
      if (field === "title") renderSlideList();
      markDirty();
    });
  };
  bind("ed_title", "title"); bind("ed_subtitle", "subtitle"); bind("ed_group_name", "group_name");
  bind("ed_closing_statement", "closing_statement"); bind("ed_missions_text", "missions_text");
  bind("ed_body", "body"); bind("ed_body_right", "body_right"); bind("ed_font", "font_family");
  bind("ed_size", "font_size", (v) => parseInt(v, 10) || 22);
  bind("ed_text_color", "text_color"); bind("ed_bg_color", "bg_color"); bind("ed_accent_color", "accent_color");

  document.getElementById("ed_layout").addEventListener("change", (e) => {
    currentSlide().layout = e.target.value; syncFieldsForLayout(); renderSlideList(); markDirty();
  });
  ["bold", "italic", "underline"].forEach((prop) => {
    document.getElementById(`ed_${prop}`).addEventListener("click", (e) => {
      currentSlide()[prop] = !currentSlide()[prop]; e.currentTarget.classList.toggle("active", currentSlide()[prop]); markDirty();
    });
  });
  document.querySelectorAll(".studio-align").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentSlide().align = btn.dataset.align;
      document.querySelectorAll(".studio-align").forEach((b) => b.classList.toggle("active", b === btn)); markDirty();
    });
  });
}

function renderForm() {
  const s = currentSlide();
  const set = (id, v) => { document.getElementById(id).value = v; };
  set("ed_layout", s.layout); set("ed_title", s.title || ""); set("ed_subtitle", s.subtitle || "");
  set("ed_group_name", s.group_name || ""); set("ed_closing_statement", s.closing_statement || "");
  set("ed_missions_text", s.missions_text || ""); set("ed_body", s.body || ""); set("ed_body_right", s.body_right || "");
  set("ed_font", s.font_family || "Calibri"); set("ed_size", s.font_size || 22);
  set("ed_text_color", s.text_color || "#eef3ff"); set("ed_bg_color", s.bg_color || "#030b1a"); set("ed_accent_color", s.accent_color || "#38bdf8");
  document.getElementById("ed_bold").classList.toggle("active", !!s.bold);
  document.getElementById("ed_italic").classList.toggle("active", !!s.italic);
  document.getElementById("ed_underline").classList.toggle("active", !!s.underline);
  document.querySelectorAll(".studio-align").forEach((b) => b.classList.toggle("active", b.dataset.align === s.align));
  syncFieldsForLayout();
}

function applyTheme(themeKey, bg, text, accent) {
  ST.config.theme = themeKey;
  ST.config.slides.forEach((s) => { s.bg_color = bg; s.text_color = text; s.accent_color = accent; });
  renderForm(); markDirty();
}

/* ------------------------------------------------------------ preview (halaman dari server) */
function renderPreview() {
  const pages = pagesOf(ST.index);
  const frame = document.getElementById("previewFrame");
  if (ST.page >= pages.length) ST.page = Math.max(0, pages.length - 1);
  drawPage(frame, pages[ST.page], 760);
  const stale = ST.dirty ? " · menunggu simpan, preview diperbarui setelah tersimpan" : "";
  document.getElementById("pageLabel").textContent = pages.length
    ? `Halaman ${ST.page + 1} dari ${pages.length} untuk slide ini${stale}` : "Slide ini belum punya halaman (simpan dulu)";
  document.getElementById("pagePrev").disabled = ST.page === 0;
  document.getElementById("pageNext").disabled = ST.page >= pages.length - 1;
}

function initPreviewAllModal() {
  const overlay = document.getElementById("previewAllOverlay");
  document.getElementById("previewBtn").addEventListener("click", async () => {
    if (ST.dirty) await saveNow();
    const first = (ST.deck.pages || []).findIndex((p) => p.source === ST.index);
    PA.index = Math.max(0, first);
    overlay.classList.add("show"); renderPreviewAll();
  });
  document.getElementById("closePreviewAllBtn").addEventListener("click", () => overlay.classList.remove("show"));
  document.getElementById("previewAllPrevBtn").addEventListener("click", () => { if (PA.index > 0) { PA.index--; renderPreviewAll(); } });
  document.getElementById("previewAllNextBtn").addEventListener("click", () => { if (PA.index < ST.deck.pages.length - 1) { PA.index++; renderPreviewAll(); } });
}

function renderPreviewAll() {
  const n = ST.deck.pages.length;
  drawPage(document.getElementById("previewAllFrame"), ST.deck.pages[PA.index], 820);
  document.getElementById("previewAllCounter").textContent = `${PA.index + 1} / ${n}`;
  document.getElementById("previewAllPrevBtn").disabled = PA.index === 0;
  document.getElementById("previewAllNextBtn").disabled = PA.index >= n - 1;
}

/* ------------------------------------------------------------ simpan (debounce) + draft lokal */
function setStatus(text, failed) {
  document.getElementById("saveStatus").textContent = text;
  document.getElementById("retrySaveBtn").style.display = failed ? "inline-block" : "none";
}

function markDirty() {
  ST.dirty = true;
  ls.set(LS_DRAFT, { group: GROUP_NO, epoch: RESET_EPOCH, ts: Date.now(), config: ST.config });   // draft lokal (bukan hasil resmi)
  setStatus("Belum tersimpan…", false);
  renderPreview();
  clearTimeout(__saveTimer);
  __saveTimer = setTimeout(saveNow, SAVE_DELAY);
}

async function saveNow() {
  clearTimeout(__saveTimer);
  if (__saving) { __saveTimer = setTimeout(saveNow, 400); return false; }
  __saving = true; setStatus("Menyimpan…", false);
  const sent = JSON.stringify(ST.config);
  try {
    const res = await fetch("/api/studio/save", { method: "POST", headers: { "Content-Type": "application/json", "X-Reset-Epoch": String(RESET_EPOCH) }, body: sent });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.reason || res.status);
    ST.deck = data.deck;
    if (JSON.stringify(ST.config) === sent) { ST.dirty = false; ls.del(LS_DRAFT); setStatus("Tersimpan di server", false); }
    else { setStatus("Belum tersimpan…", false); __saveTimer = setTimeout(saveNow, SAVE_DELAY); }
    renderPreview();
    return true;
  } catch (err) {
    if (err && err.message === "reset_happened") { ST.dirty = false; ls.del(LS_DRAFT); ls.del(LS_MEMBERS); setStatus("Pengerjaan kelompok ini telah direset oleh panitia. Muat ulang halaman.", true); return false; }
    setStatus("GAGAL menyimpan ke server — draft aman di browser ini", true);
    return false;
  } finally { __saving = false; }
}

async function flush() { return ST.dirty ? saveNow() : true; }

function checkDraft() {
  const d = ls.get(LS_DRAFT);
  if (d && (d.epoch ?? 0) !== RESET_EPOCH) { ls.del(LS_DRAFT); return; }
  if (!d || d.group !== GROUP_NO || !d.config || !Array.isArray(d.config.slides)) return;
  if (JSON.stringify(d.config) === JSON.stringify(ST.config)) { ls.del(LS_DRAFT); return; }
  const banner = document.getElementById("draftBanner");
  banner.style.display = "block";
  document.getElementById("draftRestore").onclick = () => {
    ST.config = d.config; ST.index = 0; banner.style.display = "none"; renderSlideList(); selectSlide(0); markDirty();
  };
  document.getElementById("draftDiscard").onclick = () => { ls.del(LS_DRAFT); banner.style.display = "none"; };
}

async function rebuild() {
  if (!confirm("Susun ulang presentasi dengan struktur baru dari jawaban Final Mission? Versi lama disimpan sebagai cadangan.")) return;
  const res = await fetch("/api/studio/rebuild", { method: "POST", headers: { "X-Reset-Epoch": String(RESET_EPOCH) } });
  const data = await res.json();
  if (data.success) { ST.config = data.config; ST.deck = data.deck; ST.index = 0; ST.dirty = false; ls.del(LS_DRAFT);
    const b = document.getElementById("oldBanner"); if (b) b.style.display = "none"; renderSlideList(); selectSlide(0); setStatus("Tersimpan di server", false); }
  else setStatus("Gagal menyusun ulang", true);
}

/* ------------------------------------------------------------ anggota (10 slot) */
let __memTimer = null;
function readMembers() { return Array.from({ length: 10 }, (_, i) => document.getElementById(`member_${i}`).value); }

function bindMembers() {
  const draft = ls.get(LS_MEMBERS);
  if (draft && (draft.epoch ?? 0) !== RESET_EPOCH) { ls.del(LS_MEMBERS); }
  else if (draft && draft.group === GROUP_NO && Array.isArray(draft.members) && draft.members.length === 10) {
    const cur = readMembers();
    if (JSON.stringify(cur) !== JSON.stringify(draft.members)) {
      draft.members.forEach((v, i) => { document.getElementById(`member_${i}`).value = v; });
      saveMembers();                                   // draft belum terkirim -> kirim ulang (idempoten)
    }
  }
  for (let i = 0; i < 10; i++) {
    document.getElementById(`member_${i}`).addEventListener("input", () => {
      ls.set(LS_MEMBERS, { group: GROUP_NO, epoch: RESET_EPOCH, members: readMembers() });
      document.getElementById("memberStatus").textContent = "Belum tersimpan…";
      clearTimeout(__memTimer); __memTimer = setTimeout(saveMembers, SAVE_DELAY);
    });
  }
}

async function saveMembers() {
  const el = document.getElementById("memberStatus");
  el.textContent = "Menyimpan…";
  const sent = readMembers();
  try {
    const res = await fetch("/api/final/members", { method: "POST", headers: { "Content-Type": "application/json", "X-Reset-Epoch": String(RESET_EPOCH) }, body: JSON.stringify({ members: sent }) });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error("x");
    if (JSON.stringify(readMembers()) === JSON.stringify(sent)) { ls.del(LS_MEMBERS); el.textContent = "Tersimpan di server"; }
    // preview memakai anggota terbaru: minta render ulang dari server lewat simpan deck
    ST.dirty = true; await saveNow();
  } catch (e) { el.textContent = "GAGAL menyimpan anggota — tersimpan sementara di browser; ketik ulang/ubah untuk mencoba lagi"; }
}
