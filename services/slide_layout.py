"""Mesin layout slide — SATU sumber kebenaran untuk Preview, Mode Presentasi, dan ekspor PPTX.

Masukan : config presentasi kelompok (slides[]) + daftar 10 anggota.
Keluaran: halaman-halaman (960 x 540 pt = 16:9, sama dengan 13.333 x 7.5 inci PowerPoint) berisi
          elemen berposisi mutlak (rect / ellipse / text). Browser menggambarnya dengan <div>,
          python-pptx menggambarnya sebagai bentuk PPTX yang dapat diedit — sehingga susunannya sama.

Prinsip:
  * Ukuran font TIDAK dikecilkan otomatis agar muat. Jika materi terlalu panjang, slide DIPECAH
    menjadi beberapa halaman ("(2/3)").
  * Pengukuran teks = estimasi KONSERVATIF (lebar rata-rata karakter), tanpa ketergantungan font.
  * Tidak ada teks yang dipotong: semua kata tetap ada, hanya dipindah ke halaman lanjutan.
"""
import re

W, H = 960, 540
MX = 48                       # margin kiri/kanan
TITLE_Y, TITLE_SIZE = 30, 32  # judul 28-36 pt
BODY_TOP, BODY_BOTTOM = 124, 498
BODY_W = W - 2 * MX
PAD = 16                      # padding dalam kartu
LH = 1.25                     # tinggi baris = ukuran * LH (dipakai PPTX dan HTML)

FONT_SAFE = {"Calibri", "Arial", "Verdana", "Georgia", "Trebuchet MS", "Consolas"}
DEFAULT_FONT = "Calibri"
MIN_BODY, MAX_BODY, DEFAULT_BODY = 16, 40, 22


def _char_w(size, bold=False, mono=False):
    return size * (0.60 if mono else (0.56 if bold else 0.52))


def wrap_lines(text, size, width, bold=False, mono=False):
    """Bungkus teks (greedy). Kata yang lebih panjang dari baris dipecah per karakter. -> list[str]"""
    cw = _char_w(size, bold, mono)
    per = max(1, int(width / cw))
    out = []
    for raw in str(text or "").split("\n"):
        words = raw.split(" ")
        cur = ""
        for w in words:
            while len(w) > per:                      # kata sangat panjang
                if cur:
                    out.append(cur)
                    cur = ""
                out.append(w[:per])
                w = w[per:]
            cand = w if not cur else cur + " " + w
            if len(cand) <= per:
                cur = cand
            else:
                out.append(cur)
                cur = w
        out.append(cur)
    return out


def text_height(text, size, width, bold=False, mono=False):
    return len(wrap_lines(text, size, width, bold, mono)) * size * LH


def split_to_fit(text, size, width, max_height, bold=False):
    """Pecah satu paragraf panjang menjadi potongan (per batas baris) yang masing-masing muat max_height."""
    lines = wrap_lines(text, size, width, bold)
    per_page = max(1, int(max_height // (size * LH)))
    return [" ".join(lines[i:i + per_page]) for i in range(0, len(lines), per_page)] or [""]


# ------------------------------------------------------------------ warna
def _rgb(h):
    h = (h or "#000000").lstrip("#")
    if len(h) != 6:
        h = "000000"
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def blend(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(round(ra[i] * (1 - t) + rb[i] * t) for i in range(3))


def _style(s):
    font = s.get("font_family") or DEFAULT_FONT
    if font not in FONT_SAFE:
        font = DEFAULT_FONT           # font tidak umum -> Calibri agar sama di PowerPoint/Preview
    bg, tx, ac = s.get("bg_color") or "#030b1a", s.get("text_color") or "#eef3ff", s.get("accent_color") or "#38bdf8"
    return dict(font=font, bg=bg, text=tx, accent=ac, card=blend(bg, tx, 0.09), muted=blend(bg, tx, 0.62),
                italic=bool(s.get("italic")), underline=bool(s.get("underline")),
                bold=bool(s.get("bold")), align=s.get("align") or "left")


def body_size(s):
    try:
        v = int(s.get("font_size") or DEFAULT_BODY)
    except (TypeError, ValueError):
        v = DEFAULT_BODY
    return max(MIN_BODY, min(MAX_BODY, v))


# ------------------------------------------------------------------ elemen
def rect(x, y, w, h, fill=None, line=None, radius=10, lw=1.25):
    return dict(t="rect", x=x, y=y, w=w, h=h, fill=fill, line=line, radius=radius, lw=lw)


def ellipse(x, y, w, h, fill=None, line=None):
    return dict(t="ellipse", x=x, y=y, w=w, h=h, fill=fill, line=line, lw=1.25)


def text(x, y, w, h, paras, st, valign="top", mono=False):
    """paras: [{text,size,bold?,color?,align?,italic?,underline?,after?}]"""
    ps = []
    for p in paras:
        ps.append(dict(
            text=p["text"], size=p["size"], bold=p.get("bold", False), italic=p.get("italic", st["italic"]),
            underline=p.get("underline", st["underline"]), color=p.get("color", st["text"]),
            align=p.get("align", "left"), after=p.get("after", 0)))
    return dict(t="text", x=x, y=y, w=w, h=h, paras=ps, font="Consolas" if mono else st["font"], valign=valign)


def _title_els(title, st, align="left"):
    t = (title or "").strip() or "(tanpa judul)"
    lines = len(wrap_lines(t, TITLE_SIZE, BODY_W - 14, bold=True))
    size = TITLE_SIZE if lines <= 2 else 28
    return [
        rect(MX, TITLE_Y + 4, 6, 64, fill=st["accent"], radius=2),
        text(MX + 18, TITLE_Y, BODY_W - 18, 76, [dict(text=t, size=size, bold=True, align=align)], st, valign="middle"),
    ]


def _footer(st, group_name, n, total):
    els = []
    left = "AXIS 2026 · Operation: Restore Data Lab" + (f" · {group_name}" if group_name else "")
    els.append(text(MX, 512, 700, 18, [dict(text=left, size=11, color=st["muted"])], st))
    els.append(text(W - MX - 120, 512, 120, 18, [dict(text=f"{n} / {total}", size=11, color=st["muted"], align="right")], st))
    return els


# ------------------------------------------------------------------ parser teks
BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def parse_paragraphs(raw):
    """Teks -> daftar paragraf. Blok dipisah baris kosong; baris berpola '-', '*', '•', '1.' jadi butir."""
    out = []
    for block in re.split(r"\n\s*\n", str(raw or "")):
        lines = [l.rstrip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        if any(BULLET_RE.match(l) for l in lines):
            for l in lines:
                out.append(("• " + BULLET_RE.sub("", l).strip()) if BULLET_RE.match(l) else l.strip())
        elif len(lines) > 1:
            out.extend(l.strip() for l in lines)          # beberapa baris = beberapa paragraf pendek
        else:
            out.append(lines[0].strip())
    return out


def parse_steps(raw):
    lines = [BULLET_RE.sub("", l).strip() for l in str(raw or "").split("\n") if l.strip()]
    if len(lines) == 1:                                     # satu paragraf -> pecah per kalimat bila >= 3 kalimat
        parts = [p.strip() for p in re.split(r"(?<=[.;])\s+(?=[A-Z0-9])", lines[0]) if p.strip()]
        if len(parts) >= 3:
            lines = parts
    return lines


# ------------------------------------------------------------------ paginasi
def paginate_paras(paras, size, width, capacity, gap):
    """Bagi paragraf ke halaman (tanpa memotong kata, tanpa mengecilkan font)."""
    pages, cur, used = [], [], 0.0
    for p in paras:
        for piece in split_to_fit(p, size, width, capacity):
            h = text_height(piece, size, width)
            need = h + (gap if cur else 0)
            if cur and used + need > capacity:
                pages.append(cur)
                cur, used = [], 0.0
                need = h
            cur.append(piece)
            used += need
    if cur:
        pages.append(cur)
    return pages or [[]]


def _page(st, els, source, label=None):
    return dict(bg=st["bg"], elements=els, source=source, label=label)


def _suffix(i, n):
    return "" if n == 1 else f" ({i + 1}/{n})"


# ------------------------------------------------------------------ layout per jenis
def pages_content(s, source):
    st = _style(s)
    size = body_size(s)
    gap = size * 0.55
    inner_w = BODY_W - 2 * PAD
    cap = BODY_BOTTOM - BODY_TOP - 2 * PAD
    paras = parse_paragraphs(s.get("body")) or ["(belum diisi)"]
    chunks = paginate_paras(paras, size, inner_w, cap, gap)
    out = []
    for i, ch in enumerate(chunks):
        h = sum(text_height(p, size, inner_w) for p in ch) + gap * max(0, len(ch) - 1)
        card_h = min(BODY_BOTTOM - BODY_TOP, h + 2 * PAD + 4)
        els = _title_els((s.get("title") or "") + _suffix(i, len(chunks)), st)
        els.append(rect(MX, BODY_TOP, BODY_W, card_h, fill=st["card"], line=st["accent"]))
        els.append(text(MX + PAD, BODY_TOP + PAD, inner_w, card_h - 2 * PAD,
                        [dict(text=p, size=size, after=gap, align="left") for p in ch], st))
        out.append(_page(st, els, source))
    return out


def pages_two_column(s, source):
    st = _style(s)
    size = body_size(s)
    gap = size * 0.55
    col_w = (BODY_W - 24) / 2
    inner_w = col_w - 2 * PAD
    cap = BODY_BOTTOM - BODY_TOP - 2 * PAD
    left = paginate_paras(parse_paragraphs(s.get("body")) or ["(belum diisi)"], size, inner_w, cap, gap)
    right = paginate_paras(parse_paragraphs(s.get("body_right")) or [], size, inner_w, cap, gap)
    n = max(len(left), len(right))
    out = []
    for i in range(n):
        els = _title_els((s.get("title") or "") + _suffix(i, n), st)
        for side, pages in ((0, left), (1, right)):
            x = MX + side * (col_w + 24)
            ch = pages[i] if i < len(pages) else []
            els.append(rect(x, BODY_TOP, col_w, BODY_BOTTOM - BODY_TOP, fill=st["card"], line=st["accent"]))
            if ch:
                els.append(text(x + PAD, BODY_TOP + PAD, inner_w, BODY_BOTTOM - BODY_TOP - 2 * PAD,
                                [dict(text=p, size=size, after=gap) for p in ch], st))
        out.append(_page(st, els, source))
    return out


def pages_steps(s, source):
    st = _style(s)
    size = body_size(s)
    steps = parse_steps(s.get("body")) or ["(belum diisi)"]
    num_d = 36
    tx_w = BODY_W - num_d - 3 * PAD
    cap = BODY_BOTTOM - BODY_TOP
    rows, cur, used = [], [], 0.0
    for idx, step in enumerate(steps, start=1):
        for piece in split_to_fit(step, size, tx_w, cap - 2 * 10):
            h = max(num_d + 8, text_height(piece, size, tx_w) + 20)
            need = h + (10 if cur else 0)
            if cur and used + need > cap:
                rows.append(cur)
                cur, used = [], 0.0
                need = h
            cur.append((idx, piece, h))
            used += need
    if cur:
        rows.append(cur)
    out = []
    for i, page in enumerate(rows or [[]]):
        els = _title_els((s.get("title") or "") + _suffix(i, len(rows)), st)
        y = BODY_TOP
        for k, (idx, piece, h) in enumerate(page):
            els.append(rect(MX, y, BODY_W, h, fill=st["card"], line=st["accent"]))
            els.append(ellipse(MX + PAD, y + (h - num_d) / 2, num_d, num_d, fill=st["accent"]))
            els.append(text(MX + PAD, y + (h - num_d) / 2, num_d, num_d,
                            [dict(text=str(idx), size=18, bold=True, align="center", color=st["bg"])], st, valign="middle"))
            els.append(text(MX + 2 * PAD + num_d, y + 10, tx_w, h - 20,
                            [dict(text=piece, size=size)], st, valign="middle"))
            y += h + 10
        out.append(_page(st, els, source))
    return out


def pages_code(s, source):
    st = _style(s)
    size = 16
    panel_x, panel_w = MX, BODY_W
    cols = max(10, int((panel_w - 2 * PAD) / _char_w(size, mono=True)))
    cap_lines = int((BODY_BOTTOM - BODY_TOP - 2 * PAD) // (size * LH))
    lines = []
    for ln in (s.get("body") or "# (belum diisi)").replace("\t", "    ").split("\n"):
        lines.extend([ln[i:i + cols] for i in range(0, max(1, len(ln)), cols)] or [""])
    chunks = [lines[i:i + cap_lines] for i in range(0, len(lines), cap_lines)] or [[]]
    out = []
    for i, ch in enumerate(chunks):
        els = _title_els((s.get("title") or "") + _suffix(i, len(chunks)), st)
        els.append(rect(MX, BODY_TOP, panel_w, BODY_BOTTOM - BODY_TOP, fill="#0b0e1a", line=st["accent"]))
        els.append(text(MX + PAD, BODY_TOP + PAD, panel_w - 2 * PAD, BODY_BOTTOM - BODY_TOP - 2 * PAD,
                        [dict(text="\n".join(ch), size=size, color="#d4d9f0")], st, mono=True))
        out.append(_page(st, els, source))
    return out


def _member_rows(names, size, col_w):
    """Daftar (nomor, nama) -> tinggi tiap baris pada ukuran font tertentu."""
    return [text_height(f"{n}. {nm}", size, col_w) for n, nm in names]


def _fits_two_cols(names, size, col_w, avail):
    half = (len(names) + 1) // 2
    for col in (names[:half], names[half:]):
        gap = size * 0.4
        total = sum(_member_rows(col, size, col_w)) + gap * max(0, len(col) - 1)
        if total > avail:
            return False
    return True


def pages_cover(s, source, members, group_name):
    st = _style(s)
    names = [(i, m) for i, m in enumerate(members, start=1) if m.strip()]
    title = (s.get("title") or "").strip() or "Presentasi Final Mission"
    tsize = max(28, min(36, int(s.get("font_size") or 36))) if s.get("font_size") else 36
    tsize = 36 if tsize > 36 else tsize
    t_lines = wrap_lines(title, tsize, BODY_W, bold=True)
    t_h = min(3, len(t_lines)) * tsize * LH
    els = [rect(0, 0, W, 8, fill=st["accent"], radius=0),
           text(MX, 34, BODY_W, 20, [dict(text="AXIS 2026 · OPERATION: RESTORE DATA LAB", size=14, bold=True, color=st["accent"], align="center")], st)]
    y = 64
    els.append(text(MX, y, BODY_W, t_h + 4, [dict(text=title, size=tsize, bold=True, align="center")], st))
    y += t_h + 10
    els.append(rect(W / 2 - 40, y, 80, 4, fill=st["accent"], radius=2))
    y += 14
    sub = (s.get("subtitle") or "").strip()
    if sub:
        sh = text_height(sub, 20, BODY_W)
        els.append(text(MX, y, BODY_W, sh + 2, [dict(text=sub, size=20, color=st["muted"], align="center")], st))
        y += sh + 10
    gname = (s.get("group_name") or group_name or "").strip()
    if gname:
        els.append(text(MX, y, BODY_W, 34, [dict(text=gname, size=26, bold=True, color=st["accent"], align="center")], st))
        y += 40
    extra = []
    if names:
        avail = 506 - (y + 28)
        col_w = (BODY_W - 24) / 2 - 8
        size = next((sz for sz in (20, 18, 16) if _fits_two_cols(names, sz, col_w, avail)), None)
        if size:
            els.append(text(MX, y, BODY_W, 22, [dict(text="ANGGOTA KELOMPOK", size=14, bold=True, color=st["muted"], align="center")], st))
            y += 28
            half = (len(names) + 1) // 2
            for side, col in enumerate((names[:half], names[half:])):
                x = MX + side * ((BODY_W - 24) / 2 + 24)
                els.append(text(x, y, (BODY_W - 24) / 2, avail,
                                [dict(text=f"{n}. {nm}", size=size, after=size * 0.4) for n, nm in col], st))
        else:
            extra = [True]                                   # tidak muat di sampul -> halaman anggota terpisah
    out = [_page(st, els, source, "Cover")]
    if extra:
        out.extend(pages_team(dict(s, title="Anggota Kelompok"), source, members, group_name))
    return out


def pages_team(s, source, members, group_name):
    st = _style(s)
    names = [(i, m) for i, m in enumerate(members, start=1) if m.strip()] or [(1, "(belum diisi)")]
    size = 20
    col_w = (BODY_W - 24) / 2
    inner = col_w - 2 * PAD
    cap = BODY_BOTTOM - BODY_TOP
    cards = [(n, nm, max(52, text_height(f"{n}. {nm}", size, inner) + 20)) for n, nm in names]
    pages, cur_l, cur_r, ul, ur = [], [], [], 0.0, 0.0
    for c in cards:
        side_l = ul <= ur
        h = c[2]
        if side_l and ul + h + (10 if cur_l else 0) > cap and ur + h + (10 if cur_r else 0) > cap:
            pages.append((cur_l, cur_r)); cur_l, cur_r, ul, ur = [], [], 0.0, 0.0
        if ul <= ur:
            cur_l.append(c); ul += h + 10
        else:
            cur_r.append(c); ur += h + 10
    pages.append((cur_l, cur_r))
    out = []
    for i, (lc, rc) in enumerate(pages):
        els = _title_els((s.get("title") or "Anggota Kelompok") + _suffix(i, len(pages)), st)
        for side, col in enumerate((lc, rc)):
            x = MX + side * (col_w + 24)
            y = BODY_TOP
            for n, nm, h in col:
                els.append(rect(x, y, col_w, h, fill=st["card"], line=st["accent"]))
                els.append(text(x + PAD, y + 10, inner, h - 20, [dict(text=f"{n}. {nm}", size=size, bold=True)], st, valign="middle"))
                y += h + 10
        out.append(_page(st, els, source))
    return out


def pages_mission_grid(s, source):
    st = _style(s)
    lines = [l.strip() for l in (s.get("missions_text") or "").split("\n") if l.strip()] or ["(belum diisi)"]
    size = 18
    cols = 2
    cw = (BODY_W - 24) / cols
    cap = BODY_BOTTOM - BODY_TOP
    out, i = [], 0
    rows_per = max(1, int((cap + 10) // 62))
    per_page = rows_per * cols
    chunks = [lines[k:k + per_page] for k in range(0, len(lines), per_page)]
    for ci, ch in enumerate(chunks):
        els = _title_els((s.get("title") or "") + _suffix(ci, len(chunks)), st)
        for k, line in enumerate(ch):
            x = MX + (k % cols) * (cw + 24)
            y = BODY_TOP + (k // cols) * 62
            els.append(rect(x, y, cw, 52, fill=st["card"], line=st["accent"]))
            els.append(text(x + PAD, y + 6, cw - 2 * PAD, 40, [dict(text=line, size=size, bold=True)], st, valign="middle"))
        out.append(_page(st, els, source))
    return out


def pages_closing(s, source, group_name):
    st = _style(s)
    title = (s.get("title") or "").strip() or "Terima Kasih"
    tsize = 36
    stmt = (s.get("closing_statement") or "").strip()
    gname = (s.get("group_name") or group_name or "").strip()
    th = min(3, len(wrap_lines(title, tsize, BODY_W, bold=True))) * tsize * LH
    sh = text_height(stmt, 24, BODY_W - 80) if stmt else 0
    total = th + 24 + (sh + 20 if stmt else 0) + (50 if gname else 0)
    y = max(90, (H - total) / 2 - 10)
    els = [rect(0, 0, W, 8, fill=st["accent"], radius=0)]
    els.append(text(MX, y, BODY_W, th + 4, [dict(text=title, size=tsize, bold=True, align="center")], st))
    y += th + 12
    els.append(rect(W / 2 - 40, y, 80, 4, fill=st["accent"], radius=2))
    y += 22
    if stmt:
        els.append(text(MX + 40, y, BODY_W - 80, sh + 4, [dict(text=stmt, size=24, align="center")], st))
        y += sh + 20
    if gname:
        els.append(text(MX, y, BODY_W, 34, [dict(text=gname, size=24, bold=True, color=st["accent"], align="center")], st))
    return [_page(st, els, source, "Penutup")]


def expand_deck(config, members, group_name=""):
    """-> {"width","height","pages":[{bg, elements, source, n}]}. Nomor halaman & footer ditambahkan di akhir."""
    pages = []
    for i, s in enumerate(config.get("slides", [])):
        layout = s.get("layout", "content")
        if layout == "cover":
            ps = pages_cover(s, i, members, group_name)
        elif layout == "closing":
            ps = pages_closing(s, i, group_name)
        elif layout == "team":
            ps = pages_team(s, i, members, group_name)
        elif layout == "mission_grid":
            ps = pages_mission_grid(s, i)
        elif layout == "two_column":
            ps = pages_two_column(s, i)
        elif layout == "steps":
            ps = pages_steps(s, i)
        elif layout == "code":
            ps = pages_code(s, i)
        else:
            ps = pages_content(s, i)
        pages.extend(ps)
    total = len(pages)
    for n, p in enumerate(pages, start=1):
        st = _style((config.get("slides") or [{}])[p["source"]])
        if p["label"] not in ("Cover", "Penutup"):
            p["elements"] += _footer(st, group_name, n, total)
        p["n"] = n
    return {"width": W, "height": H, "pages": pages}
