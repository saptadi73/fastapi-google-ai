# Migrasi environment ke Python 3.11

Runtime proyek: Python 3.11.16 Windows x64. Python di `venv/Scripts/python.exe` memakai runtime lokal
`.python/cpython-3.11.16-windows-x86_64-none/python.exe`. Runtime dipasang melalui distribusi terkelola
[`uv` / python-build-standalone](https://docs.astral.sh/uv/guides/install-python/).
Python 3.10 global tidak dihapus dan PATH/registry Windows tidak diubah.

## Perubahan

- Venv dibuat ulang pada path `venv` menggunakan Python 3.11; venv lama disimpan di `venv-py310-backup`.
- Metadata project menetapkan `requires-python >=3.11`, target Ruff `py311`, dan `.python-version` adalah `3.11`.
- Versi dependency aplikasi dipertahankan saat instalasi; wheel dipilih ulang untuk CPython 3.11.
  `requirements.lock` diregenerasi dari dependency yang benar-benar diperlukan pada Python 3.11.
- Kontrak HTTP test menggunakan HTTPX ASGI async transport dengan lifespan aplikasi, sehingga tidak
  menggunakan alias BlockingPortal yang deprecated. Tidak ada filter warning Google yang ditambahkan.
- User `openpg` berhasil membuat database `googleai_test`; migration Alembic diterapkan dari database kosong.
- `TEST_DATABASE_URL` pada `.env` menunjuk `googleai_test`; `DATABASE_URL` tetap menunjuk `googleai`.
- Tes integrasi menolak database test dengan nama yang sama seperti database aplikasi, termasuk jika
  credential/alias host berbeda. Fallback menjalankan tes integrasi pada database aplikasi dihapus.

## Verifikasi dan pengulangan

Hasil verifikasi migrasi ini: **52 tes lulus** dengan `-W error`, 73 modul aplikasi berhasil diimpor
tanpa warning, `pip check` dan Ruff bersih, serta smoke test HTTP login/JWT/health berhasil dengan
80 path OpenAPI. Server development di `127.0.0.1:8000` dihidupkan kembali memakai Python 3.11.
Redis belum berjalan; mode worker manual tetap tersedia.

```powershell
.\venv\Scripts\python.exe --version
.\venv\Scripts\python.exe -W error::FutureWarning -c "import google.api_core, googleapiclient.discovery; print('Google imports OK')"
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe scripts\prepare_test_db.py
.\venv\Scripts\python.exe -m pytest -q -W error
.\venv\Scripts\python.exe -m ruff check app tests scripts
.\venv\Scripts\python.exe scripts\smoke_test.py
```

`prepare_test_db.py` dapat diulang tanpa mereset database. Tes integrasi mencakup pemeriksaan
`current_database()` untuk memastikan koneksi benar-benar menuju `googleai_test`.
Smoke test terakhir memakai database aplikasi untuk memeriksa login admin melalui HTTP.
Integrasi Google/OpenAI live tetap memerlukan kredensial; pengujiannya menggunakan mock.

Untuk menjalankan server secara manual:

```powershell
.\venv\Scripts\python.exe -m app.server
```

Jika terminal atau editor masih memperlihatkan Python 3.10, pilih interpreter
`C:\projek\fastapi-googlesheet-ai\venv\Scripts\python.exe`. Setelah aktivasi ulang venv,
`python --version` harus menunjukkan 3.11.16. Folder `.python` diperlukan oleh venv; jangan dihapus.
