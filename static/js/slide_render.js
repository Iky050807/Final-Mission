/* ============================================================================
   slide_render.js — menggambar HALAMAN slide hasil mesin layout server (services/slide_layout.py).
   Server mengirim elemen berposisi mutlak pada kanvas 960 x 540 pt (16:9); PPTX digambar dari data yang
   SAMA, jadi Preview, Mode Presentasi, dan PowerPoint memiliki susunan yang sama. Browser hanya menskalakan.
   Tidak ada teks yang dipotong: tidak ada overflow:hidden / ellipsis / tinggi tetap yang menyembunyikan isi.
   ============================================================================ */

const SR_LH = 1.25;   // harus sama dengan LH di slide_layout.py
const SR_FONT = (f) => `'${f}','Carlito','Segoe UI',Arial,sans-serif`;

function srEscape(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function srTextEl(el, k) {
  const mono = el.font === "Consolas";
  const family = mono ? "Consolas,'DejaVu Sans Mono','Courier New',monospace" : SR_FONT(el.font);
  const justify = el.valign === "middle" ? "justify-content:center;" : "justify-content:flex-start;";
  const paras = el.paras.map((p) => {
    const st = [
      `font-size:${(p.size * k).toFixed(2)}px`, `line-height:${(p.size * SR_LH * k).toFixed(2)}px`,
      `font-weight:${p.bold ? 700 : 400}`, `font-style:${p.italic ? "italic" : "normal"}`,
      `text-decoration:${p.underline ? "underline" : "none"}`, `color:${p.color}`, `text-align:${p.align}`,
      `margin:0 0 ${((p.after || 0) * k).toFixed(2)}px 0`,
    ].join(";");
    return `<div style="${st}">${srEscape(p.text)}</div>`;
  }).join("");
  return `<div class="sr-text" style="position:absolute;left:${el.x * k}px;top:${el.y * k}px;width:${el.w * k}px;` +
    `min-height:${el.h * k}px;display:flex;flex-direction:column;${justify}font-family:${family};` +
    `white-space:pre-wrap;overflow-wrap:anywhere;">${paras}</div>`;
}

function srShapeEl(el, k) {
  const radius = el.t === "ellipse" ? "50%" : `${(el.radius || 0) * k}px`;
  const border = el.line ? `${Math.max(1, (el.lw || 1.25) * k)}px solid ${el.line}` : "none";
  return `<div class="sr-shape" style="position:absolute;left:${el.x * k}px;top:${el.y * k}px;width:${el.w * k}px;` +
    `height:${el.h * k}px;background:${el.fill || "transparent"};border:${border};border-radius:${radius};` +
    `box-sizing:border-box;"></div>`;
}

/** page -> HTML string satu slide; k = skala (px per pt). */
function renderPageHTML(page, k) {
  const inner = page.elements.map((el) => (el.t === "text" ? srTextEl(el, k) : srShapeEl(el, k))).join("");
  return `<div class="sr-page" style="position:relative;width:${960 * k}px;height:${540 * k}px;background:${page.bg};` +
    `border-radius:${6 * k}px;">${inner}</div>`;
}

/** Gambar page ke container, skala mengikuti lebar container. Dipanggil ulang saat ukuran berubah. */
function drawPage(container, page, maxWidth) {
  if (!container || !page) { if (container) container.innerHTML = ""; return; }
  const w = Math.min(maxWidth || 9999, container.clientWidth || 960);
  container.innerHTML = renderPageHTML(page, Math.max(0.2, w / 960));
}
