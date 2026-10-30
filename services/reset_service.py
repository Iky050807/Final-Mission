# Reset pengerjaan SATU kelompok pada Website 3 saja.
# Menghapus: jawaban Final Mission (+ anggota) dan konfigurasi Presentasi milik kelompok itu. Menaikkan "reset_epoch" kelompok
# supaya draft localStorage lama di browser tidak dipulihkan. TIDAK menyentuh: tabel groups, kode akses, studi kasus/soal (data/*.json),
# kelompok lain, Website 1 dan 2. PPTX yang sudah diunduh peserta berada di perangkat mereka dan tidak dapat dihapus oleh sistem.
from db_layer.db import conn, query_one


def get_epoch(n):
    r = query_one("SELECT value FROM app_settings WHERE key = ?", (f"reset_epoch_{n}",))
    return int(r["value"]) if r and str(r["value"]).isdigit() else 0


def group_overview(n):
    sub = query_one("SELECT status, submitted_at, updated_at FROM final_mission_submissions WHERE group_id = ?", (n,))
    pres = query_one("SELECT 1 AS x FROM presentations WHERE group_id = ?", (n,))
    return {"group_number": n, "submission": sub["status"] if sub else None, "has_presentation": bool(pres), "epoch": get_epoch(n)}


class StaleEpoch(Exception):
    """expected_epoch tidak cocok di dalam transaksi: pengerjaan sudah dihapus/direset oleh permintaan lain."""


def reset_group(n, expected_epoch=None):
    """Satu transaksi. Melempar exception bila gagal (rollback penuh); pemanggil TIDAK boleh melaporkan sukses.
    expected_epoch (opsional, dipakai tombol 'Hapus Pengerjaan'): bila diberikan dan epoch kelompok sudah berbeda DI DALAM transaksi,
    tidak ada yang dihapus dan StaleEpoch dilempar (mencegah dua permintaan bersamaan sama-sama menghapus/menaikkan epoch)."""
    c = conn()
    try:
        c.execute("BEGIN IMMEDIATE")
        if expected_epoch is not None:
            cur = c.execute("SELECT value FROM app_settings WHERE key = ?", (f"reset_epoch_{n}",)).fetchone()
            if (int(cur["value"]) if cur and str(cur["value"]).isdigit() else 0) != expected_epoch:
                raise StaleEpoch()
        sub = c.execute("DELETE FROM final_mission_submissions WHERE group_id = ?", (n,)).rowcount
        pres = c.execute("DELETE FROM presentations WHERE group_id = ?", (n,)).rowcount
        row = c.execute("SELECT value FROM app_settings WHERE key = ?", (f"reset_epoch_{n}",)).fetchone()
        epoch = (int(row["value"]) if row and str(row["value"]).isdigit() else 0) + 1
        c.execute("INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (f"reset_epoch_{n}", str(epoch)))
        c.commit()
        return {"submissions_deleted": sub, "presentations_deleted": pres, "epoch": epoch}
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
