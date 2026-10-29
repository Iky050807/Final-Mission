/* admin_reset.js (Website 3) — dialog konfirmasi + POST JSON. Otorisasi & validasi kelompok sepenuhnya di server. */
(() => {
  const $ = (id) => document.getElementById(id), csrf = document.querySelector('meta[name="csrf"]').content; let busy = false;
  const say = (ok, t) => { $("notice").innerHTML = `<div class="alert ${ok ? "alert-success" : "alert-error"} show"></div>`; $("notice").firstChild.textContent = t; };
  $("openBtn").onclick = () => {
    $("dtext").textContent = `Apakah Anda yakin ingin mereset seluruh pengerjaan Kelompok ${$("grp").value} pada Website 3 — Final Mission? ` +
      "Semua jawaban, anggota, dan presentasi kelompok ini pada website tersebut akan dihapus. Data kelompok lain, identitas kelompok, dan konfigurasi tidak akan terpengaruh.";
    $("dlg").hidden = false; $("cancelBtn").focus();
  };
  $("cancelBtn").onclick = () => ($("dlg").hidden = true);
  $("okBtn").onclick = async () => {
    if (busy) return; busy = true; $("okBtn").disabled = true; const gn = Number($("grp").value);
    try {
      const r = await fetch("/admin/api/reset", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify({ group_number: gn, confirm_group: gn }) });
      const d = (r.headers.get("content-type") || "").includes("json") ? await r.json() : null; $("dlg").hidden = true;
      if (d && d.success) say(true, `Reset berhasil untuk Kelompok ${gn}: ${d.submissions_deleted} data Final Mission dan ${d.presentations_deleted} presentasi dihapus. Muat ulang halaman untuk melihat tabel terbaru.`);
      else say(false, "Reset GAGAL — tidak ada klaim berhasil. Kode: " + ((d && d.reason) || r.status));
    } catch (e) { $("dlg").hidden = true; say(false, "Reset GAGAL — server tidak dapat dihubungi."); }
    finally { busy = false; $("okBtn").disabled = false; }
  };
})();
