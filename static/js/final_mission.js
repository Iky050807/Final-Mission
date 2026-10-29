/* ============================================================================
   final_mission.js — form Final Mission: autosave (debounce) jawaban + 10 slot anggota + submit.
   * Backend = data resmi. localStorage = salinan DRAFT sementara (kunci axis2026_final_draft_v1).
   * Status jelas: Menyimpan / Tersimpan di server / GAGAL (draft aman di browser) + tombol coba lagi.
   * Tidak menyatakan "tersimpan" sebelum server mengonfirmasi.
   ============================================================================ */
const LS_FINAL = "axis2026_final_draft_v1", DELAY = 1500;
const lsf = {
  get() { try { return JSON.parse(localStorage.getItem(LS_FINAL) || "null"); } catch (e) { return null; } },
  set(v) { try { localStorage.setItem(LS_FINAL, JSON.stringify(v)); } catch (e) { /* abaikan */ } },
  del() { try { localStorage.removeItem(LS_FINAL); } catch (e) { /* abaikan */ } },
};
let pending = {};          // field_id -> nilai yang belum dikonfirmasi server
let pendingMembers = null; // array 10 atau null
let timer = null, saving = false;

function draftAll() { return { group: GROUP_NO, epoch: RESET_EPOCH, ts: Date.now(), fields: pending, members: pendingMembers }; }
function status(text, failed) {
  document.getElementById("saveStatus").textContent = text;
  document.getElementById("memberStatus").textContent = text;
  document.getElementById("retryBtn").style.display = failed ? "inline-block" : "none";
}
const members = () => Array.from({ length: 10 }, (_, i) => document.getElementById(`member_${i}`).value);

document.addEventListener("DOMContentLoaded", () => {
  initParticles();
  // Pulihkan draft lokal yang belum pernah dikonfirmasi server (bukan menimpa data server yang lebih baru tanpa izin:
  // draft hanya dipakai jika kolomnya berbeda dan pengguna tidak sedang mengisi).
  let d = lsf.get();
  if (d && (d.group !== GROUP_NO || (d.epoch ?? 0) !== RESET_EPOCH)) { lsf.del(); d = null; }   // draft dari sebelum reset / kelompok lain dibuang
  if (d && d.group === GROUP_NO) {
    let restored = false;
    Object.entries(d.fields || {}).forEach(([fid, val]) => {
      const ta = document.querySelector(`textarea[data-field="${fid}"]`);
      if (ta && ta.value !== val) { ta.value = val; pending[fid] = val; restored = true; }
    });
    if (Array.isArray(d.members) && d.members.length === 10 && JSON.stringify(d.members) !== JSON.stringify(members())) {
      d.members.forEach((v, i) => { document.getElementById(`member_${i}`).value = v; });
      pendingMembers = d.members; restored = true;
    }
    if (restored) { status("Draft lokal dipulihkan — menyimpan ke server…", false); schedule(0); }
  }
  document.querySelectorAll("#finalForm textarea[data-field]").forEach((el) => {
    el.addEventListener("input", () => { pending[el.dataset.field] = el.value; touch(); });
  });
  for (let i = 0; i < 10; i++) {
    document.getElementById(`member_${i}`).addEventListener("input", () => { pendingMembers = members(); touch(); });
  }
  document.getElementById("retryBtn").addEventListener("click", () => flush());
  document.getElementById("submitFinalBtn").addEventListener("click", handleSubmit);
  window.addEventListener("beforeunload", (e) => {
    if (Object.keys(pending).length || pendingMembers) { e.preventDefault(); e.returnValue = ""; }
  });
});

function touch() { lsf.set(draftAll()); status("Belum tersimpan…", false); schedule(DELAY); }
function schedule(ms) { clearTimeout(timer); timer = setTimeout(flush, ms); }

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-Reset-Epoch": String(RESET_EPOCH) }, body: JSON.stringify(body) });
  const data = await res.json();
  if (!res.ok || !data.success) throw new Error(data.reason || res.status);
  return data;
}

function onReset() {                       // admin mereset kelompok ini saat halaman terbuka: buang draft lama, jangan tulis ulang
  clearTimeout(timer); pending = {}; pendingMembers = null; lsf.del();
  status("Pengerjaan kelompok ini telah direset oleh panitia. Muat ulang halaman untuk mulai dari awal.", true);
  const rb = document.getElementById("retryBtn"); if (rb) rb.style.display = "none";
}

async function flush() {
  clearTimeout(timer);
  if (saving) { schedule(400); return false; }
  saving = true; status("Menyimpan…", false);
  const fields = Object.entries(pending), mem = pendingMembers;
  try {
    for (const [fid, val] of fields) {                       // satu request per kolom yang berubah (bukan per karakter)
      await post("/api/final/autosave", { field_id: fid, value: val });
      if (pending[fid] === val) delete pending[fid];
    }
    if (mem) {
      await post("/api/final/members", { members: mem });
      if (JSON.stringify(pendingMembers) === JSON.stringify(mem)) pendingMembers = null;
    }
    if (!Object.keys(pending).length && !pendingMembers) { lsf.del(); status("Tersimpan di server", false); }
    else { status("Belum tersimpan…", false); schedule(DELAY); }
    return true;
  } catch (err) {
    if (err && err.message === "reset_happened") { onReset(); return false; }
    status("GAGAL menyimpan ke server — draft aman di browser ini. Cek koneksi lalu coba lagi.", true);
    return false;
  } finally { saving = false; }
}

async function handleSubmit() {
  const ok = await flush();                                   // pastikan semua tersimpan SEBELUM submit
  if (!ok || Object.keys(pending).length || pendingMembers) {
    await showResultOverlay({ type: "error", title: "Belum tersimpan ke server.", subtitle: "Tekan 'Coba simpan lagi' lalu submit." });
    return;
  }
  await playScanAnimation({ overlayId: "scanOverlay", label: "Memeriksa Hasil Final Mission..." });
  hideOverlay("scanOverlay");
  try {
    const res = await fetch("/api/final/submit", { method: "POST", headers: { "X-Reset-Epoch": String(RESET_EPOCH) } });
    const data = await res.json();
    if (data.success) {
      await showResultOverlay({ type: "success", title: "MISSION SUCCESS", subtitle: "Final Mission selesai!" });
      window.location.href = "/presentation";
    } else if (data.reason === "reset_happened") {
      onReset(); await showResultOverlay({ type: "error", title: "Pengerjaan direset panitia.", subtitle: "Muat ulang halaman untuk mulai dari awal." });
    } else {
      await showResultOverlay({ type: "error", title: "Belum lengkap.", subtitle: "Semua kolom jawaban harus diisi sebelum submit." });
    }
  } catch (err) {
    await showResultOverlay({ type: "error", title: "Koneksi bermasalah.", subtitle: "Coba lagi." });
  }
}
