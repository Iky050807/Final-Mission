# ============================================================================
#  WEBSITE 3 — FINAL MISSION
#  Alur: Final Code (global, kode akses bersama) -> identifikasi kelompok -> studi
#  kasus & jawaban -> Presentation Sheet -> editor/preview/presentasi -> PPTX.
#  Data kelompok diisolasi lewat group_id di SESSION (bukan dari Final Code).
# ============================================================================
import os, json, hmac, time, hashlib, secrets
from functools import wraps
from flask import Flask, g, jsonify, redirect, render_template, request, send_file, session, url_for

from db_layer.db import init_db, query_all, query_one
from services.final_service import (get_final_mission_config, get_final_submission,
                                    save_final_submission_draft, submit_final_mission)
from services.presentation_service import (get_presentation_config, save_presentation_config, rebuild_presentation,
                                           THEMES, FONTS, LAYOUTS)
from services.pptx_export import build_pptx
from services.slide_layout import expand_deck
from services.final_service import get_members, save_members
from services.group_access import GROUP_NUMBERS, parse_group_number, verify_group_code
from services.reset_service import get_epoch, group_overview, reset_group

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ganti-secret-final-axis-2026")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=1024 * 1024)
init_db()


def final_code():
    return (os.environ.get("FINAL_CODE") or "RESTORE-AXIS-2026").strip().upper()   # SAMA dgn Website 1


_attempts = {}   # ip -> [timestamps]; ukurannya dibatasi agar memori tidak tumbuh


def _rate_limited(ip, limit=10, window=60):
    now = time.time(); hits = [t for t in _attempts.get(ip, []) if now - t < window]
    hits.append(now); _attempts[ip] = hits
    if len(_attempts) > 500:
        for k in [k for k, v in _attempts.items() if not v or now - v[-1] > window]: _attempts.pop(k, None)
    return len(hits) > limit


def admin_password():
    return os.environ.get("ADMIN_PASSWORD") or "axis2026"      # bawaan hanya untuk uji lokal — WAJIB diganti di produksi


def csrf_token():
    if not session.get("csrf"):
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def admin_required(fn):
    """Halaman admin: sesi admin di server (bukan dari klien)."""
    @wraps(fn)
    def w(*a, **k):
        if not session.get("w3_admin"):
            return redirect(url_for("admin_login"))
        return fn(*a, **k)
    return w


def admin_api_required(fn):
    """API admin: sesi admin + token CSRF yang cocok. 401/403 JSON, tidak pernah redirect."""
    @wraps(fn)
    def w(*a, **k):
        if not session.get("w3_admin"):
            return jsonify(success=False, reason="unauthorized"), 401
        tok = request.headers.get("X-CSRF-Token") or ""
        if not tok or not hmac.compare_digest(tok.encode(), str(session.get("csrf", "")).encode()):
            return jsonify(success=False, reason="csrf"), 403
        return fn(*a, **k)
    return w


def code_required(fn):
    @wraps(fn)
    def w(*a, **k):
        if not session.get("final_ok"):
            return (jsonify(success=False, reason="no_final_code"), 401) if request.path.startswith("/api/") else redirect(url_for("index"))
        return fn(*a, **k)
    return w


def group_required(fn):
    @wraps(fn)
    @code_required
    def w(*a, **k):
        grp = query_one("SELECT * FROM groups WHERE id = ?", (session.get("group_id"),)) if session.get("group_id") in GROUP_NUMBERS else None
        if not grp:
            return (jsonify(success=False, reason="no_group"), 401) if request.path.startswith("/api/") else redirect(url_for("group_select"))
        g.group = {"id": grp["id"], "group_number": grp["id"], "name": grp["name"]}
        # halaman lama yang dibuka sebelum admin mereset kelompok ini tidak boleh menulis ulang data lama
        hdr = request.headers.get("X-Reset-Epoch")
        if request.method == "POST" and hdr is not None and (not hdr.isdigit() or int(hdr) != get_epoch(grp["id"])):
            return jsonify(success=False, reason="reset_happened"), 409
        return fn(*a, **k)
    return w


def _submitted(gid):
    s = get_final_submission(gid)
    return bool(s and s["status"] == "submitted")


# ------------------------------------------------------------- akses & kelompok
@app.route("/")
def index():
    if session.get("final_ok"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/api/final/verify-code", methods=["POST"])
def api_verify_code():
    if _rate_limited(request.remote_addr or "x"):
        return jsonify(success=False, reason="too_many_attempts"), 429
    code = str((request.get_json(silent=True) or {}).get("code", "")).strip().upper()
    if code and hmac.compare_digest(code.encode(), final_code().encode()):
        session["final_ok"] = True
        return jsonify(success=True)
    return jsonify(success=False, reason="wrong_code")


@app.route("/group")
@code_required
def group_select():
    if session.get("group_id") in GROUP_NUMBERS:
        return redirect(url_for("dashboard"))
    groups = query_all("SELECT id AS group_number, name FROM groups WHERE id BETWEEN 1 AND 5 ORDER BY id")
    return render_template("group_select.html", groups=groups)


_fail_log = {}


def _fails(ip, add=False, window=300):
    now = time.time()
    lst = [t for t in _fail_log.get(ip, []) if now - t < window]
    if add:
        lst.append(now)
    _fail_log[ip] = lst
    return len(lst)


@app.route("/group/select", methods=["POST"])
@code_required
def group_select_submit():
    """Masuk kelompok dengan KODE AKSES; setelah masuk identitas terkunci di session server."""
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "?").split(",")[0].strip()
    if _fails(ip) >= 40:
        return jsonify(success=False, reason="too_many_attempts"), 429
    p = request.get_json(silent=True) or {}
    number = parse_group_number(p.get("group_number"))
    grp = query_one("SELECT * FROM groups WHERE id = ?", (number,)) if number else None
    if not grp:
        return jsonify(success=False, reason="not_found")
    locked = session.get("group_id")
    if locked in GROUP_NUMBERS and locked != grp["id"]:
        return jsonify(success=False, reason="already_identified"), 403
    if not verify_group_code(number, p.get("access_code", "")):
        _fails(ip, add=True)
        return jsonify(success=False, reason="wrong_access_code")
    session["group_id"] = grp["id"]
    return jsonify(success=True)


@app.route("/dashboard")
@group_required
def dashboard():
    return redirect(url_for("presentation_studio" if _submitted(g.group["id"]) else "final_mission_page"))


# ------------------------------------------------------------- Admin: reset pengerjaan SATU kelompok (Website 3 saja)
@app.route("/admin", methods=["GET"])
def admin_login():
    if session.get("w3_admin"):
        return redirect(url_for("admin_reset_page"))
    return render_template("admin_login.html", error=request.args.get("e"))


@app.route("/admin/login", methods=["POST"])
def admin_login_post():
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "?").split(",")[0].strip()
    if _rate_limited("admin:" + ip, limit=8, window=60):
        return redirect(url_for("admin_login", e="Terlalu banyak percobaan. Coba lagi sebentar lagi."))
    if not hmac.compare_digest((request.form.get("password") or "").encode(), admin_password().encode()):
        return redirect(url_for("admin_login", e="Password salah."))
    session["w3_admin"] = True
    session["csrf"] = secrets.token_hex(16)
    return redirect(url_for("admin_reset_page"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("w3_admin", None); session.pop("csrf", None)
    return redirect(url_for("admin_login"))


@app.route("/admin/reset")
@admin_required
def admin_reset_page():
    groups = query_all("SELECT id AS group_number, name FROM groups WHERE id BETWEEN 1 AND 5 ORDER BY id")
    for gr in groups:
        gr.update(group_overview(gr["group_number"]))
    return render_template("admin_reset.html", groups=groups, csrf=csrf_token(), selected=request.args.get("group", type=int))


@app.route("/admin/api/reset", methods=["POST"])
@admin_api_required
def admin_api_reset():
    """JSON {group_number, confirm_group}. Grup divalidasi di server (1..5, harus sama dengan konfirmasi). Satu transaksi."""
    p = request.get_json(silent=True)
    gn = p.get("group_number") if isinstance(p, dict) else None
    cf = p.get("confirm_group") if isinstance(p, dict) else None
    gn = int(gn) if isinstance(gn, str) and gn.isdigit() else gn
    cf = int(cf) if isinstance(cf, str) and cf.isdigit() else cf
    if isinstance(gn, bool) or not isinstance(gn, int) or gn not in GROUP_NUMBERS:
        return jsonify(success=False, reason="invalid_group"), 400
    if cf != gn:
        return jsonify(success=False, reason="not_confirmed"), 400
    try:
        r = reset_group(gn)
    except Exception:
        app.logger.exception("reset W3 gagal")
        return jsonify(success=False, reason="server_error"), 500
    return jsonify(success=True, group_number=gn, **r)


# ------------------------------------------------------------- Final Mission
@app.route("/final")
@group_required
def final_mission_page():
    if _submitted(g.group["id"]):
        return redirect(url_for("presentation_studio"))
    cfg = get_final_mission_config(); sub = get_final_submission(g.group["id"])
    return render_template("final_mission.html", group=g.group, case_study=cfg.get("case_study", ""),
                           fields=cfg.get("fields", []), answers=json.loads(sub["answers_json"]) if sub else {},
                           members=get_members(g.group["id"]), updated_at=(sub or {}).get("updated_at") or "",
                           reset_epoch=get_epoch(g.group["id"]))


@app.route("/api/final/autosave", methods=["POST"])
@group_required
def api_autosave():
    p = request.get_json(silent=True) or {}
    return jsonify(success=save_final_submission_draft(g.group["id"], p.get("field_id"), p.get("value", "")) is not None)


@app.route("/api/final/members", methods=["GET", "POST"])
@group_required
def api_members():
    """10 slot anggota KELOMPOK DI SESSION (tidak menerima group_id dari klien)."""
    if request.method == "GET":
        return jsonify(success=True, members=get_members(g.group["id"]))
    p = request.get_json(silent=True) or {}
    saved = save_members(g.group["id"], p.get("members"))
    if saved is None:
        return jsonify(success=False, reason="invalid"), 400
    return jsonify(success=True, members=saved)


@app.route("/api/final/submit", methods=["POST"])
@group_required
def api_submit():
    return jsonify(submit_final_mission(g.group["id"]))


# ------------------------------------------------------------- Presentasi
@app.route("/presentation")
@group_required
def presentation_sheet():
    return redirect(url_for("presentation_studio"))


def _need_submitted(gid):
    return None if _submitted(gid) else redirect(url_for("final_mission_page"))


def _deck(group, config):
    return expand_deck(config, get_members(group["id"]), group["name"])


_TEXT_KEYS = ("title", "subtitle", "body", "body_right", "members", "missions_text", "closing_statement", "group_name")
_LAYOUT_KEYS = {k for k, _ in LAYOUTS}


def _clean_config(cfg):
    """Validasi/bersihkan konfigurasi dari klien: tipe, panjang, daftar layout/font yang dikenal. None jika tidak valid."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("slides"), list) or not (1 <= len(cfg["slides"]) <= 60):
        return None
    slides = []
    for sl in cfg["slides"]:
        if not isinstance(sl, dict):
            return None
        c = {"id": str(sl.get("id") or "")[:20], "layout": sl.get("layout") if sl.get("layout") in _LAYOUT_KEYS else "content"}
        for k in _TEXT_KEYS:
            v = sl.get(k, "")
            if not isinstance(v, str):
                return None
            c[k] = v[:20000] if k in ("body", "body_right") else v[:600]
        c["font_family"] = sl.get("font_family") if sl.get("font_family") in FONTS else "Calibri"
        try:
            c["font_size"] = max(10, min(60, int(sl.get("font_size") or 22)))
        except (TypeError, ValueError):
            c["font_size"] = 22
        for k in ("bold", "italic", "underline"):
            c[k] = bool(sl.get(k))
        c["align"] = sl.get("align") if sl.get("align") in ("left", "center", "right") else "left"
        for k, d in (("text_color", "#eef3ff"), ("bg_color", "#030b1a"), ("accent_color", "#38bdf8")):
            v = sl.get(k)
            c[k] = v if isinstance(v, str) and len(v) == 7 and v[0] == "#" else d
        slides.append(c)
    out = {"theme": str(cfg.get("theme") or "future-blue")[:30], "schema": 2, "slides": slides}
    if isinstance(cfg.get("backup_prev"), dict):
        out["backup_prev"] = cfg["backup_prev"]
    return out


@app.route("/studio")
@group_required
def presentation_studio():
    r = _need_submitted(g.group["id"])
    if r:
        return r
    cfg = get_presentation_config(g.group)
    return render_template("studio.html", group=g.group, config=cfg, deck=_deck(g.group, cfg),
                           members=get_members(g.group["id"]), themes=THEMES, fonts=FONTS, layouts=LAYOUTS,
                           old_schema=(cfg.get("schema", 1) < 2), reset_epoch=get_epoch(g.group["id"]))


@app.route("/api/studio/save", methods=["POST"])
@group_required
def api_studio_save():
    """Simpan deck KELOMPOK DI SESSION lalu kembalikan render resmi (halaman) untuk preview."""
    if not _submitted(g.group["id"]):
        return jsonify(success=False, reason="not_submitted"), 403
    cfg = _clean_config(request.get_json(silent=True))
    if cfg is None:
        return jsonify(success=False, reason="invalid"), 400
    save_presentation_config(g.group["id"], cfg)
    return jsonify(success=True, deck=_deck(g.group, cfg))


@app.route("/api/studio/rebuild", methods=["POST"])
@group_required
def api_studio_rebuild():
    if not _submitted(g.group["id"]):
        return jsonify(success=False, reason="not_submitted"), 403
    cfg = rebuild_presentation(g.group)
    return jsonify(success=True, config=cfg, deck=_deck(g.group, cfg))


@app.route("/present")
@group_required
def present_mode():
    r = _need_submitted(g.group["id"])
    if r:
        return r
    cfg = get_presentation_config(g.group)
    return render_template("present_mode.html", group=g.group, deck=_deck(g.group, cfg))


@app.route("/download/pptx")
@group_required
def download_pptx():
    r = _need_submitted(g.group["id"])
    if r: return r
    buf = build_pptx(get_presentation_config(g.group), get_members(g.group["id"]), g.group["name"])
    name = "".join(ch if ch.isalnum() else "_" for ch in g.group["name"])
    return send_file(buf, as_attachment=True, download_name=f"presentation_{name}.pptx",
                     mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation")


# ------------------------------------------------------------- utilitas
@app.route("/api/fingerprint")
def api_fingerprint():
    r = jsonify(final=hashlib.sha256(final_code().encode()).hexdigest()[:8])
    r.headers["Access-Control-Allow-Origin"] = "*"
    return r


@app.route("/healthz")
def healthz():
    return "ok"
