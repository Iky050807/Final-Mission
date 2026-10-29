# ============================================================================
#  services/presentation_service.py
#  Presentation Sheet/PPT profesional yang dapat dikustomisasi penuh oleh
#  peserta (nama kelompok, anggota, tema, font, warna, slide, logo, foto) —
#  mirip mini-editor PowerPoint. Struktur slide disimpan sebagai JSON per
#  kelompok di tabel `presentations`.
#
#  Tiap slide punya `layout` yang menentukan TEMPLATE VISUAL-nya (bukan cuma
#  judul+teks polos):
#    cover        -> sampul dengan judul besar, subjudul, kelompok, logo
#    team         -> grid kartu anggota kelompok
#    mission_grid -> grid status pencapaian Mission 1-5 (TANPA Mission Code
#                    mentah — hanya status/achievement, sesuai kebijakan
#                    keamanan supaya kode rahasia tidak ikut dipresentasikan)
#    content      -> card informasi, isi dipisah baris kosong jadi beberapa
#                    blok (mirip beberapa "text box" berurutan)
#    two_column   -> dua kolom konten berdampingan (mis. Decomposition vs
#                    Pattern Recognition)
#    code         -> panel kode ala code-editor (dipakai untuk solusi Python)
#    closing      -> penutup dengan closing statement
# ============================================================================

import json
import random

from db_layer.db import query_one, execute
from services.final_service import get_final_mission_config, get_final_submission, now_str

THEMES = [
    ("future-blue", "Future Blue", "#38bdf8", "#22d3ee", "#030b1a", "#eef3ff"),
    ("cyber-purple", "Cyber Purple", "#22d3ee", "#ff4d6d", "#0b0616", "#f3ecff"),
    ("modern-white", "Modern White", "#0ea5e9", "#0891b2", "#ffffff", "#1b2036"),
    ("dark-tech", "Dark Tech", "#00e5c0", "#38bdf8", "#020304", "#e6f7ff"),
    ("academic", "Academic", "#1e3a5f", "#8a6d3b", "#f7f3e8", "#2b2b2b"),
    ("corporate", "Corporate", "#0f3d63", "#0ea5e9", "#f4f6f9", "#20283a"),
]
# tuple: key, label, accent, accent2, bg, text
MISSION_ROSTER = [("⌨", "Python Runtime"), ("◈", "Problem Analysis Center"), ("▤", "Database Validation"), ("⌁", "Algorithm Engine"), ("🧠", "Knowledge Core")]
THEME_MAP = {t[0]: t for t in THEMES}

# Font umum yang tersedia di PowerPoint/Windows/Mac (kompatibel). Default Calibri.
FONTS = ["Calibri", "Arial", "Verdana", "Georgia", "Trebuchet MS"]

LAYOUTS = [
    ("cover", "Cover (judul + kelompok + 10 anggota)"),
    ("content", "Konten (poin / paragraf)"),
    ("steps", "Langkah Berurutan (Algoritma)"),
    ("two_column", "Dua Kolom"),
    ("code", "Kode"),
    ("team", "Anggota Kelompok"),
    ("mission_grid", "Daftar Mission"),
    ("closing", "Penutup"),
]

SCHEMA_VERSION = 2   # 2 = struktur baru (cover, latar belakang, masalah, ... penutup); 1 = struktur lama


def _new_slide(layout, theme_key="future-blue", **overrides):
    theme = THEME_MAP.get(theme_key, THEMES[0])
    big = layout in ("cover", "closing")
    slide = {
        "id": f"s{random.randint(100000, 999999)}",
        "layout": layout,
        "title": "", "subtitle": "", "body": "", "body_right": "",
        "members": "", "missions_text": "", "closing_statement": "",
        "group_name": "",
        "font_family": "Calibri",
        "font_size": 36 if big else 22,
        "bold": big, "italic": False, "underline": False,
        "align": "center" if big else "left",
        "text_color": theme[5], "bg_color": theme[4], "accent_color": theme[2],
    }
    slide.update(overrides)
    return slide


def build_default_config(group):
    """Susun deck awal dari jawaban Final Mission kelompok. Satu fokus per slide; tidak ada materi yang
    diada-adakan: bagian yang belum diisi peserta tampil sebagai '(belum diisi)'. Anggota TIDAK disalin ke
    slide: cover/anggota selalu membaca daftar 10 slot dari database (sumber tunggal)."""
    theme_key = "future-blue"
    cfg = get_final_mission_config()
    sub = get_final_submission(group["id"])
    answers = json.loads(sub["answers_json"]) if sub else {}
    fields = {f["id"]: f for f in cfg.get("fields", [])}

    def ans(fid):
        return (answers.get(fid) or "").strip()

    slides = [_new_slide("cover", theme_key, title="Presentasi Final Mission", subtitle="Final Mission — Operation: Restore Data Lab",
                         group_name=group["name"])]
    background = "\n\n".join(x for x in (cfg.get("case_study", "").strip(), ans("latar_belakang")) if x)
    slides.append(_new_slide("content", theme_key, title="Latar Belakang", body=background))
    plan = [("masalah_utama", "content"), ("abstraction", "content"), ("decomposition", "content"),
            ("pattern_recognition", "content"), ("algoritma", "steps"), ("solusi", "content"),
            ("program_python", "code"), ("kesimpulan", "content")]
    for fid, layout in plan:
        f = fields.get(fid)
        if not f:
            continue
        slides.append(_new_slide(layout, theme_key, title=f.get("short") or f["label"], body=ans(fid)))
    slides.append(_new_slide("closing", theme_key, title="Terima Kasih", closing_statement="Mission Successfully Completed",
                             group_name=group["name"]))
    return {"theme": theme_key, "schema": SCHEMA_VERSION, "slides": slides}


def _import_legacy_members(group_id, config):
    """Config lama menyimpan anggota sebagai teks per baris pada slide 'team'. Jika slot anggota di database masih
    kosong, impor (maks. 10) supaya tidak ada nama yang hilang. Tidak menghapus apa pun."""
    from services.final_service import get_members, save_members
    if any(get_members(group_id)):
        return
    for sl in config.get("slides", []):
        names = [l.strip() for l in (sl.get("members") or "").split("\n") if l.strip()]
        if names:
            save_members(group_id, names[:10])
            return


def get_presentation_config(group):
    row = query_one("SELECT config_json FROM presentations WHERE group_id = ?", (group["id"],))
    if row:
        cfg = json.loads(row["config_json"])
        _import_legacy_members(group["id"], cfg)
        return cfg

    config = build_default_config(group)
    save_presentation_config(group["id"], config)
    return config


def rebuild_presentation(group):
    """Susun ulang deck dengan struktur baru dari jawaban. Versi lama disimpan di config['backup_prev'] (tidak hilang)."""
    old = get_presentation_config(group)
    new = build_default_config(group)
    new["backup_prev"] = {"slides": old.get("slides", []), "theme": old.get("theme"), "schema": old.get("schema", 1)}
    save_presentation_config(group["id"], new)
    return new


def save_presentation_config(group_id, config):
    existing = query_one("SELECT group_id FROM presentations WHERE group_id = ?", (group_id,))
    payload = json.dumps(config, ensure_ascii=False)
    if existing:
        execute(
            "UPDATE presentations SET config_json = ?, updated_at = ? WHERE group_id = ?",
            (payload, now_str(), group_id),
        )
    else:
        execute(
            "INSERT INTO presentations (group_id, config_json) VALUES (?, ?)",
            (group_id, payload),
        )
