# SQLite ringan untuk Website 3. DB_PATH dapat diarahkan ke persistent disk (lihat README_DEPLOY).
import os, sqlite3, json

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "instance", "final.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY, name TEXT NOT NULL, access_code TEXT);
CREATE TABLE IF NOT EXISTS final_mission_submissions(
  group_id INTEGER PRIMARY KEY REFERENCES groups(id), answers_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'draft', submitted_at TEXT, updated_at TEXT,
  members_json TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS presentations(
  group_id INTEGER PRIMARY KEY REFERENCES groups(id), config_json TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now')), updated_at TEXT);
CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


_WAL_READY = set()


def conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10); c.row_factory = sqlite3.Row
    if DB_PATH not in _WAL_READY:          # mode WAL cukup diset sekali per proses (mengubahnya per koneksi memicu "database is locked")
        c.execute("PRAGMA journal_mode=WAL"); _WAL_READY.add(DB_PATH)
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    c = conn(); c.executescript(SCHEMA)
    # Migrasi DB lama: kolom anggota (10 slot) ditambahkan tanpa menghapus data apa pun.
    cols = {r["name"] for r in c.execute("PRAGMA table_info(final_mission_submissions)")}
    if "members_json" not in cols:
        c.execute("ALTER TABLE final_mission_submissions ADD COLUMN members_json TEXT NOT NULL DEFAULT '[]'")
    # hanya lima kelompok (1..5): baris kelompok lain (jika ada di DB lama) dibiarkan, tetapi tidak dapat dipakai masuk
    if not c.execute("SELECT 1 FROM groups LIMIT 1").fetchone():
        for g in json.load(open(os.path.join(BASE, "data", "groups.json"), encoding="utf-8")):
            c.execute("INSERT INTO groups VALUES (?,?,?)", (g["group_number"], g["name"], g.get("access_code") or None))
    c.commit(); c.close()


def query_all(sql, p=()):
    c = conn(); r = [dict(x) for x in c.execute(sql, p).fetchall()]; c.close(); return r


def query_one(sql, p=()):
    c = conn(); r = c.execute(sql, p).fetchone(); c.close(); return dict(r) if r else None


def execute(sql, p=()):
    c = conn(); cur = c.execute(sql, p); c.commit(); i = cur.lastrowid; c.close(); return i
