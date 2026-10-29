/* ============================================================================
   group.js — pemilihan kelompok (tanpa login, cukup identifikasi kelompok)
   ============================================================================ */

document.addEventListener("DOMContentLoaded", () => {
  initParticles();

  const overlay = document.getElementById("accessCodeOverlay");
  const groupLabel = document.getElementById("accessCodeGroupLabel");
  const codeInput = document.getElementById("accessCodeInput");
  const cancelBtn = document.getElementById("accessCodeCancel");
  const submitBtn = document.getElementById("accessCodeSubmit");

  let pendingGroupNumber = null;

  document.querySelectorAll(".group-card").forEach((card) => {
    card.addEventListener("click", () => {
      const groupNumber = card.dataset.number;
      const needsCode = card.dataset.needsCode === "true";

      if (needsCode) {
        pendingGroupNumber = groupNumber;
        groupLabel.textContent = card.querySelector(".g-name").textContent;
        codeInput.value = "";
        hideAlert("accessCodeError");
        overlay.classList.add("show");
        codeInput.focus();
      } else {
        selectGroup(groupNumber, "");
      }
    });
  });

  cancelBtn.addEventListener("click", () => overlay.classList.remove("show"));
  submitBtn.addEventListener("click", () => selectGroup(pendingGroupNumber, codeInput.value));
  codeInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") selectGroup(pendingGroupNumber, codeInput.value);
  });

  async function selectGroup(groupNumber, accessCode) {
    try {
      const res = await fetch("/group/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_number: parseInt(groupNumber, 10), access_code: accessCode }),
      });
      const data = await res.json();

      if (data.success) {
        window.location.href = "/dashboard";
      } else if (data.reason === "wrong_access_code") {
        showAlert("accessCodeError", "error");
      } else if (data.reason === "already_identified") {
        window.location.href = "/dashboard";
      } else {
        await showResultOverlay({ type: "error", title: "Kelompok tidak ditemukan.", subtitle: "Coba pilih ulang." });
      }
    } catch (err) {
      await showResultOverlay({ type: "error", title: "Koneksi bermasalah.", subtitle: "Coba lagi." });
    }
  }
});
