# Final Mission (Website 3): studi kasus dari data/final_mission.json; jawaban tersimpan
# PER KELOMPOK (kunci = group_id dari session, BUKAN Final Code).
import json, os
from datetime import datetime
from db_layer.db import query_one, execute, BASE

ISO = "%Y-%m-%d %H:%M:%S"


def now_str():
    return datetime.now().strftime(ISO)


_CONFIG = None


def get_final_mission_config():
    global _CONFIG   # dibaca sekali dari file (tidak berubah saat acara)
    if _CONFIG is None:
        with open(os.path.join(BASE, "data", "final_mission.json"), encoding="utf-8") as f:
            _CONFIG = json.load(f)
    return _CONFIG


def get_final_submission(group_id):
    return query_one("SELECT * FROM final_mission_submissions WHERE group_id = ?", (group_id,))


def save_final_submission_draft(group_id, field_id, value):
    allowed = {f["id"] for f in get_final_mission_config().get("fields", [])}
    if field_id not in allowed:
        return None
    value = str(value)[:20000]
    sub = get_final_submission(group_id)
    if sub and sub["status"] == "submitted":
        return None   # jawaban terkunci setelah submit
    answers = json.loads(sub["answers_json"]) if sub else {}
    answers[field_id] = value
    execute("""INSERT INTO final_mission_submissions(group_id, answers_json, updated_at) VALUES (?,?,?)
               ON CONFLICT(group_id) DO UPDATE SET answers_json=excluded.answers_json, updated_at=excluded.updated_at""",
            (group_id, json.dumps(answers, ensure_ascii=False), now_str()))
    return answers


def submit_final_mission(group_id):
    sub = get_final_submission(group_id)
    answers = json.loads(sub["answers_json"]) if sub else {}
    required = [f["id"] for f in get_final_mission_config().get("fields", [])]
    if not all(str(answers.get(i, "")).strip() for i in required):
        return {"success": False, "reason": "incomplete"}
    execute("UPDATE final_mission_submissions SET status='submitted', submitted_at=? WHERE group_id=?", (now_str(), group_id))
    return {"success": True}


# ----------------------------------------------------------------------------- anggota (maks. 10 slot)
MAX_MEMBERS = 10
MAX_MEMBER_LEN = 120


def normalize_members(raw):
    """Selalu daftar PANJANG 10 (Anggota 1..10): string yang dirapikan (spasi ganda -> satu), slot kosong = ''.
    Return None jika bentuk data tidak valid. Nama TIDAK dipotong di bawah MAX_MEMBER_LEN."""
    if not isinstance(raw, list) or len(raw) > MAX_MEMBERS:
        return None
    out = []
    for v in raw:
        if v is None:
            v = ""
        if not isinstance(v, str):
            return None
        v = " ".join(v.split())
        if len(v) > MAX_MEMBER_LEN:
            return None
        out.append(v)
    return out + [""] * (MAX_MEMBERS - len(out))


def get_members(group_id):
    sub = get_final_submission(group_id)
    try:
        raw = json.loads(sub["members_json"]) if sub and sub.get("members_json") else []
    except (ValueError, TypeError):
        raw = []
    return normalize_members(raw) or [""] * MAX_MEMBERS


def save_members(group_id, raw):
    """Simpan 10 slot. Boleh dipanggil sebelum maupun sesudah submit (nama tidak memengaruhi penilaian)."""
    members = normalize_members(raw)
    if members is None:
        return None
    payload = json.dumps(members, ensure_ascii=False)
    execute("""INSERT INTO final_mission_submissions(group_id, answers_json, updated_at, members_json) VALUES (?,?,?,?)
               ON CONFLICT(group_id) DO UPDATE SET members_json=excluded.members_json""",
            (group_id, "{}", now_str(), payload))
    return members
