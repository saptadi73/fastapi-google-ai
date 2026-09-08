# Google Sheet AI Platform — FastAPI

Backend modular untuk mengolah Google Sheets menjadi data PostgreSQL, dashboard operasional, dan query
berbahasa natural melalui semantic catalog. Acuan: [dokumen baseline](docs/Dokumentasi_Backend_FastAPI_Google_Sheet_AI_ETL_NL2SQL.md).
Lihat [cakupan implementasi dan batasannya](docs/IMPLEMENTASI.md).

Panduan konfigurasi production dan pergantian key tersedia di [Konfigurasi dan rotasi kredensial](docs/KONFIGURASI_DAN_ROTASI_KREDENSIAL.md).

## Menjalankan di Windows / PowerShell

Proyek menggunakan Python **3.11** (venv lokal: **3.11.16**). Runtime lokal berada di
`.python/cpython-3.11.16-windows-x86_64-none`, dikelola menggunakan `uv`. Simpan folder `.python`
selama venv ini dipakai. Venv Python 3.10 sebelumnya disimpan pada `venv-py310-backup` sebagai cadangan.
Perintah `python` global Windows dapat tetap mengarah ke 3.10; gunakan interpreter venv di bawah.

Untuk membuat environment pada checkout baru dengan `uv` yang sudah terpasang:

```powershell
uv python install 3.11 --install-dir .python --no-bin --no-registry
$env:UV_PYTHON_INSTALL_DIR = (Resolve-Path .python).Path
uv venv --python 3.11 --seed venv
```

Gunakan interpreter venv langsung; aktivasi PowerShell tidak diperlukan.

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
# Untuk mereproduksi dependency yang diuji di Windows/Python 3.11:
# .\venv\Scripts\python.exe -m pip install -r requirements.lock
```

File `.env` lokal sudah dibuat. Untuk instalasi baru, salin `.env.example` ke `.env`, isi koneksi PostgreSQL,
ganti `JWT_SECRET` dengan secret acak minimal 32 karakter dan isi `BOOTSTRAP_PASSWORD` minimal 12 karakter.
Jangan menimpa `.env` yang sudah terisi. `.env` dan folder `secrets/` tidak masuk version control.

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m app.cli bootstrap
.\venv\Scripts\python.exe -m app.server
```

- Swagger: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Liveness: http://127.0.0.1:8000/health/live
- Koneksi PostgreSQL: http://127.0.0.1:8000/health/database
- Readiness: http://127.0.0.1:8000/health/ready

Host/port, CORS, JWT, Google/OpenAI, database, Redis, batas query dan storage dibaca dari `.env`.
Migration dan bootstrap dijalankan eksplisit, bukan setiap startup API. Bootstrap idempotent dan tidak
mengubah password akun yang sudah ada. Password admin lokal ada pada `BOOTSTRAP_PASSWORD` di `.env`.

## Health check dan koneksi database

Endpoint monitoring tersedia tanpa JWT dan menggunakan response envelope yang sama dengan API:

| Endpoint | Pemeriksaan |
|---|---|
| `GET /health` | Aplikasi dapat merespons; alias `/health/live` |
| `GET /health/live` | Liveness aplikasi, tetap HTTP 200 walaupun database sedang down |
| `GET /health/database` | Membuka koneksi PostgreSQL dan menjalankan `SELECT current_database()` |
| `GET /health/ready` | Koneksi PostgreSQL, ketersediaan tabel migration, dan status Redis |

Contoh respons `/health/database` (latency berubah sesuai hasil pemeriksaan):

```json
{
  "status": "success",
  "data": {
    "database": "postgresql",
    "connected": true,
    "name": "googleai",
    "latency_ms": 12.5
  },
  "meta": {},
  "errors": []
}
```

Koneksi gagal atau timeout menghasilkan HTTP **503** dengan error code `DATABASE_UNAVAILABLE`.
Atur batas waktu melalui `HEALTH_CHECK_TIMEOUT_SECONDS=3` pada `.env`. Redis yang tidak tersedia hanya
membuat `/health/ready` gagal apabila `REDIS_REQUIRED=true`. Pemeriksaan database tidak bergantung pada
Redis atau kredensial Google/OpenAI; koneksi database dapat sehat meskipun migration belum siap, sedangkan
readiness memeriksa keduanya. Detail password, connection URL dan stack trace tidak dikembalikan.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/health/database
```

## Login dan akun operasional

Panggil `POST /api/v1/auth/login` dengan JSON:

```json
{
  "tenant_code": "default",
  "username": "admin",
  "password": "ISI_DARI_BOOTSTRAP_PASSWORD_DI_ENV"
}
```

Ambil `data.access_token`, klik **Authorize** di Swagger, lalu masukkan token tersebut. Request berikutnya
memakai `Authorization: Bearer <access_token>`. Login adalah JSON, bukan OAuth2 form.

Admin dapat membuat akun lewat `POST /api/v1/users`. Buat `TECHNICAL_APPROVER` terpisah untuk approval;
default `REQUIRE_SEPARATE_APPROVER=true` mencegah pembuat draft menyetujui draft sendiri.

```json
{
  "username": "viewer_jakarta",
  "password": "GANTI_DENGAN_PASSWORD_KUAT",
  "full_name": "Operasional Jakarta",
  "role": "VIEWER",
  "row_scope": {"SALES": {"branch_name": ["Jakarta"]}}
}
```

Role: `PLATFORM_ADMIN`, `SOURCE_OWNER`, `DATA_STEWARD`, `TECHNICAL_APPROVER`, `ANALYST`, `VIEWER`.
Admin hanya mengelola tenant sendiri. Viewer/analyst memakai katalog/query, tanpa akses raw/quarantine.
Row scope kosong berarti semua baris dalam data product yang diizinkan role; list kosong untuk field
scope berarti tidak ada baris yang diizinkan. Perubahan role/scope mencabut token lama akun.

## Mengaktifkan Google dan OpenAI nanti

Isi di `.env`:

```dotenv
GOOGLE_SERVICE_ACCOUNT_FILE=secrets/google-service-account.json
GOOGLE_CREDENTIAL_REF=default
OPENAI_API_KEY=
OPENAI_MODEL_ETL_CONFIG=
OPENAI_MODEL_NL2SQL=
DATABASE_NL2SQL_URL=
```

Aktifkan Google Sheets API di project Google Cloud, simpan key Service Account pada lokasi tersebut,
dan bagikan spreadsheet kepada email Service Account sebagai **Viewer**. Key tidak dikirim melalui API.
`credential_ref` dalam request harus sama dengan `GOOGLE_CREDENTIAL_REF`.

Isi model OpenAI yang disetujui/tersedia di akun Anda. `OPENAI_STORE_RESPONSES=false` secara default.
Dashboard, ETL deterministik dan saved query tidak memanggil OpenAI.

NL2SQL AI memerlukan koneksi role PostgreSQL terpisah yang hanya boleh SELECT semantic views. DBA membuat
role tersebut; jangan memakai `openpg` yang memiliki privilege tulis untuk `DATABASE_NL2SQL_URL`.
Berikan `USAGE` pada schema `semantic` dan `SELECT` pada view yang dideploy. Role DDL harus dapat memberikan
grant view kepada role reader. Adapter memeriksa bahwa reader bukan superuser dan tidak mempunyai privilege
tulis pada schema aplikasi. Pada lokal, `DATABASE_DDL_URL` kosong memakai koneksi aplikasi; pada produksi,
gunakan role DDL terpisah di database yang sama.

## Worker dan scheduler

Untuk pengembangan lokal tanpa Redis, proses satu job antrean:

```powershell
.\venv\Scripts\python.exe -m app.cli worker-once
```

Untuk worker dan jadwal otomatis, jalankan Redis (contoh menggunakan Docker):

```powershell
docker compose up -d redis
```

Di dua terminal terpisah:

```powershell
.\venv\Scripts\python.exe -m celery -A app.workers.celery_app:celery_app worker --pool=solo --loglevel=info
```

```powershell
New-Item -ItemType Directory -Force storage
.\venv\Scripts\python.exe -m celery -A app.workers.celery_app:celery_app beat --loglevel=info --schedule=storage/celerybeat-schedule
```

`--pool=solo` ditujukan untuk development Windows. Deployment worker produksi sebaiknya pada Linux.
Hanya satu scheduler beat. Cron menggunakan UTC. Set `REDIS_REQUIRED=true` bila Redis harus menjadi
syarat readiness. Tanpa Redis, readiness menjelaskan mode manual dan job tetap tersimpan di PostgreSQL.

## Alur Sheet sampai dashboard

1. `POST /api/v1/sources/google-sheets` menggunakan contoh berikut; simpan source ID dan job ID.
2. Worker menjalankan discovery dan profiling. Poll `GET /api/v1/jobs/{job_id}` sampai SUCCEEDED.
3. Ambil tab pada `GET /api/v1/sources/{source_id}/sheets` dan profile pada `/profiling-runs`.
4. Buat konfigurasi manual melalui `POST /api/v1/configurations`, atau antrekan draft AI melalui
   `POST /api/v1/sources/{source_id}/ai-configurations` dengan `source_sheet_id`.
5. Review output, PATCH dengan `revision_no`, perbaiki unresolved questions dan mapping, lalu validate
   dan submit-review. Konfigurasi APPROVED/ACTIVE tidak boleh diedit; clone untuk versi baru.
6. Akun approver memanggil `/configurations/{id}/approve` dengan `revision_no` terbaru.
7. Panggil `/configurations/{id}/deploy`; worker memeriksa ulang sumber, artifact dan DDL, lalu mengaktifkan.
8. `POST /api/v1/sources/{source_id}/sync`, jalankan worker, dan periksa `/jobs/{id}` serta `/etl-runs`.
9. Query `/data-products/{code}/query`, endpoint `/reports/...`, atau export CSV melalui `/data-products/{code}/export`.

```json
{
  "source_code": "sales_cabang",
  "name": "Penjualan Cabang",
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/ISI_SPREADSHEET_ID/edit",
  "description": "Satu baris per transaksi penjualan",
  "credential_ref": "default",
  "sync_schedule": "0 */6 * * *"
}
```

Contoh konfigurasi tersedia pada [examples/sales-configuration.json](examples/sales-configuration.json).
Sesuaikan `source_column` persis dengan header Sheet. Bungkus JSON tersebut dengan
`{"source_sheet_id":"UUID_TAB","configuration":{...}}` ketika membuat konfigurasi.

Contoh query dashboard:

```json
{
  "metrics": ["net_sales", "transaction_count"],
  "dimensions": ["branch_name"],
  "filters": [{"field": "transaction_date", "operator": "between", "value": ["2026-09-01", "2026-09-30"]}],
  "sort": [{"field": "net_sales", "direction": "desc"}],
  "limit": 100
}
```

Semua respons JSON mengikuti bentuk:

```json
{
  "status": "success",
  "data": [{"branch_name": "Jakarta", "net_sales": 1500000, "transaction_count": 12}],
  "meta": {"data_product": "SALES", "query_source": "OPERATIONAL", "cached": false, "row_count": 1},
  "errors": []
}
```

Error menggunakan HTTP status yang sesuai dan `errors` berisi `code`, `message`, `details`.
Stack trace, token, password, dan nilai input sensitif tidak dimasukkan ke error response.

Endpoint laporan sales mengharapkan katalog `SALES`, metric `net_sales`/`transaction_count`, dimension
`transaction_date`/`branch_name`. Inventory mengharapkan `INVENTORY`, metric `stock_quantity`, dimension
`product_code`/`warehouse_code`. Laporan tidak membuat tabel/contoh data bisnis secara otomatis.

## Pengujian

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m ruff check app tests scripts
```

Unit/contract berjalan tanpa panggilan Google/OpenAI asli. Integration test hanya menggunakan database
terpisah yang ditentukan oleh `TEST_DATABASE_URL`. Database aplikasi `googleai` tidak dipakai oleh tes integrasi.

Buat database pengujian dan terapkan migration menggunakan akun `DATABASE_URL` yang memiliki izin CREATEDB:

```powershell
.\venv\Scripts\python.exe scripts\prepare_test_db.py
.\venv\Scripts\python.exe -m pytest -q
```

Script membuat `googleai_test` jika belum ada, mengisi `TEST_DATABASE_URL` pada `.env`, lalu menjalankan
migrasi terhadap database test. Script dapat diulang; ia tidak menghapus/reset database. Nama database test
wajib berakhiran `_test` dan berbeda dari nama database aplikasi. Akun/server untuk provisioning harus sama
dengan `DATABASE_URL`. Credential tidak dicetak ke terminal.

Di database test, fixture membuat tenant berawalan `integration_` dan tabel trusted dengan UUID unik, lalu
membersihkan data tersebut. Tanpa `TEST_DATABASE_URL`, tes integrasi dilewati; fallback lama `RUN_DB_TESTS`
yang menggunakan database aplikasi sudah dihapus. `scripts/smoke_test.py` tetap menguji login aplikasi nyata
dengan akun bootstrap pada database aplikasi, bukan memuat fixture ETL.

Tes mencakup JWT/refresh/logout, akses lintas tenant, scope cabang, approval terpisah, revision conflict,
profiling, DQ, idempotency, schema drift, rollback FULL_REFRESH, integritas artifact, clone/activation rollback,
SQL AST guard, template intent, error envelope, serta adapter Responses API dengan mock.
#   f a s t a p i - g o o g l e - a i  
 
