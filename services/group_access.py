"""Akses kelompok — modul yang SAMA (isi identik) dipakai Website 1, 2 dan 3.

Aturan:
  * Hanya ada lima kelompok: nomor 1..5 (MAX_GROUPS).
  * Peserta masuk ke sebuah kelompok dengan KODE AKSES kelompok. Server memeriksa
    kode itu; hasilnya disimpan di session (cookie bertanda tangan), bukan di
    localStorage dan bukan di field form/URL.
  * Sumber kode (prioritas): GROUP{n}_CODE  >  GROUP_CODES="1=AAA,2=BBB,..."  >  bawaan KEL{n}-AXIS.
    Nilai bawaan HANYA untuk uji lokal; di produksi wajib diatur lewat environment
    variable yang sama di ketiga website supaya satu kelompok = satu kode di mana-mana.
"""
import hmac
import os

MAX_GROUPS = 5
GROUP_NUMBERS = tuple(range(1, MAX_GROUPS + 1))


def _env_map():
    out = {}
    for part in os.environ.get("GROUP_CODES", "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip().isdigit() and v.strip():
                out[int(k)] = v.strip()
    return out


def group_code(n):
    """Kode akses resmi kelompok n (None jika n bukan kelompok 1..5)."""
    if n not in GROUP_NUMBERS:
        return None
    v = os.environ.get(f"GROUP{n}_CODE", "").strip() or _env_map().get(n)
    return v or f"KEL{n}-AXIS"


def code_is_default(n):
    return not (os.environ.get(f"GROUP{n}_CODE", "").strip() or _env_map().get(n))


def parse_group_number(value):
    """Ubah input apa pun jadi nomor kelompok sah 1..5, atau None."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n in GROUP_NUMBERS else None


def verify_group_code(n, supplied):
    expected = group_code(n)
    if not expected:
        return False
    a = str(supplied or "").strip().upper().encode()
    b = expected.strip().upper().encode()
    return hmac.compare_digest(a, b)
