# Website 3 — Final Mission
Flask + SQLite + python-pptx. Studi kasus: `data/final_mission.json`. Kelompok: `data/groups.json`. Ekspor PPTX tetap ada; tidak ada fitur upload.

**Windows PowerShell** (jalankan satu per satu; `&&` dan `VAR=nilai perintah` TIDAK dikenal PowerShell):
```powershell
pip install -r requirements.txt
$env:FINAL_CODE = "RESTORE-AXIS-2026"
python -m flask --app app run --port 5003
```
**macOS / Linux (bash)**:
```bash
pip install -r requirements.txt
export FINAL_CODE="RESTORE-AXIS-2026"
python -m flask --app app run --port 5003
```
Variabel `$env:` / `export` hanya berlaku di jendela terminal yang sama. Bila `pip` tidak dikenali: `python -m pip install -r requirements.txt`.

`FINAL_CODE` harus sama dengan Website 1. Lihat `../README_DEPLOY.md`.
