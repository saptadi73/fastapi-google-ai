# Implementasi backend

Implementasi mengacu pada `Dokumentasi_Backend_FastAPI_Google_Sheet_AI_ETL_NL2SQL.md`.
Ini adalah backend operasional awal yang bisa dijalankan dan diuji; kriteria kesiapan produksi pada
bagian 29 dokumen baseline masih memerlukan pekerjaan hardening yang disebut di bawah.

## Struktur dan tanggung jawab

Runtime proyek minimal Python 3.11, dengan venv lokal Python 3.11.16. Requirements dan lock file
diregenerasi dari environment Python 3.11. Tes integrasi menggunakan `googleai_test`, yang dipersiapkan
melalui `scripts/prepare_test_db.py`, terpisah dari database aplikasi `googleai`.

| Direktori | Tanggung jawab |
|---|---|
| `app/api/v1` | HTTP routes, dependency autentikasi/role, response envelope |
| `app/schemas` | Validasi request, kontrak konfigurasi ETL, query plan dan response |
| `app/services` | Workflow, aturan bisnis, integrasi Google/OpenAI, compiler dan eksekusi |
| `app/repositories` | Akses metadata dengan scope tenant dan lookup berversi |
| `app/models` | Entity SQLAlchemy dan constraint relasi tenant |
| `app/core` | Environment, database async, JWT, exception, routing |
| `app/workers` | Celery, penjadwalan, durable job runner |
| `app/prompts` | Prompt OpenAI berversi; tidak menyimpan secret |
| `alembic/versions` | Migrasi eksplisit dan berversi |
| `tests` | Unit, kontrak API/AI, integrasi PostgreSQL |

## Fitur yang tersedia

- JWT access/refresh, Argon2 password hashing, rotasi refresh token, logout yang mencabut semua token akun,
  perubahan password, CRUD terbatas akun dalam tenant, role dan row scope per data product.
- Registrasi URL/ID Google Sheets, discovery tab, batch read read-only, retry error sementara,
  batas ukuran sumber, snapshot JSONB, profiling tipe/header/null/uniqueness, masking sample, fingerprint.
- Konfigurasi manual atau AI draft; optimistic revision locking, submit/reject/approve dengan approver
  terpisah, clone, diff, deployment, activation, rollback, serta artifact JSON/YAML/XLSX ber-hash.
- Schema compiler membuat tabel trusted per tab, unique business key dan semantic view. Perubahan bentuk
  tabel yang sudah ada ditolak dan perlu migrasi yang direview. Schema compiler tidak menjalankan SQL AI.
- ETL deterministik: transform allowlist, DQ rules, staging, UPSERT/APPEND/FULL_REFRESH, idempotency,
  quarantine, lineage ke nomor baris/snapshot/konfigurasi. FULL_REFRESH gagal secara atomic bila ada baris invalid.
- Job persisten, status/error, retry eksplisit, jadwal cron UTC, pause/resume. Source ID sekaligus menjadi
  identifier schedule pada endpoint `/etl-jobs`; belum ada tabel jadwal independen per tab.
- Katalog data product, metric/dimension dari konfigurasi approved, query filter/group/sort/pagination,
  dashboard sales/inventory, CSV export, saved query dan normalized intent.
- OpenAI Responses API menghasilkan structured query plan; backend membangun SQL. AST guard,
  transaksi read-only, EXPLAIN cost limit, statement timeout, row limit, quota dan audit penggunaan AI.
- Optional Redis query cache: key mencakup tenant, role, row scope, semantic version dan freshness version.
  Tanpa Redis, query tetap berjalan tanpa cache dan job dapat diproses lewat `worker-once`.
- Error envelope, request ID, structured HTTP log tanpa body/token/nilai sel, health live/ready,
  OpenAPI/Swagger, pencatatan event dan penggunaan token.

## Keputusan implementasi

1. API registrasi menyimpan source dan durable discovery job dengan HTTP 202. Pemeriksaan akses Google
   dilakukan worker; hasil sukses/gagal dibaca melalui `/jobs/{id}`. Tidak ada panggilan Google pada request registrasi.
2. Worker membaca tabel `platform.job` sebagai durable queue. Celery beat mengirim task polling, sehingga
   kegagalan publish broker tidak menghilangkan job yang sudah commit. Tidak memakai FastAPI BackgroundTasks.
3. Header ditentukan eksplisit melalui `header_row` dan `data_start_row`; default 1 dan 2. Header ambigu/duplikat
   ditolak, bukan ditebak. Range mulai baris 1; batas terakhir dapat dipilih eksplisit.
4. Semua nilai sample untuk AI dimasking. Deskripsi bisnis, nama header, tipe dan statistik tetap dikirim.
   Review klasifikasi PII sebelum approval karena deteksi heuristik tidak menjamin semua PII teridentifikasi.
5. Config JSON database merupakan sumber kebenaran. Worker memeriksa status ACTIVE, relasi, SHA-256
   artifact dan kesamaan payload sebelum menjalankan ETL. Artifact export tidak dapat mengaktifkan config.
6. Tabel trusted memakai suffix UUID tab; tenant lain tidak memakai tabel fisik yang sama. Semantic view
   memfilter tenant tetap, dan query builder menambahkan tenant serta row scope dari akun database aplikasi.
7. Metadata menggunakan composite FK untuk mencegah referensi tenant/source/tab silang. API tidak menyediakan
   SQL bebas. Role aplikasi harus dibatasi sebelum deployment produksi; RLS menyeluruh belum dipasang.
8. DDL dan registry dapat menggunakan koneksi berbeda. Jika DDL commit tetapi aktivasi registry gagal,
   object fisik yang belum aktif mungkin tertinggal. Retry memeriksa kompatibilitas object; tidak ada aktivasi otomatis.
9. SQL fallback bebas sengaja tidak diekspos. NL2SQL menggunakan structured plan satu data product, tanpa join.
   Pertanyaan berulang dapat dijadikan template setelah validasi dan activation.
10. Saved query menyimpan query plan dan parameter konkret. Contoh intent berlaku untuk plan yang sama;
    tanggal relatif seperti "bulan ini" sebaiknya memakai endpoint dashboard dengan parameter tanggal,
    bukan template bertanggal tetap. Klarifikasi meminta user mengirim ulang pertanyaan lengkap.
11. Model OpenAI harus dipilih melalui `.env`; tidak ada default model atau API key. Model prices opsional
    dipakai sebagai estimasi konservatif (cached input dihitung dengan tarif penuh). Nilai biaya null berarti
    harga belum diisi. Budget USD hanya aktif jika harga telah dikonfigurasi.
12. Schema drift menghentikan load tab tersebut, mencatat profile baru dan status CHANGE_DETECTED.
    Jika OpenAI sudah dikonfigurasi, job AI draft diantrikan; konfigurasi aktif tidak otomatis diganti.
13. Job gagal menyimpan error pada `platform.job`. ETL batch yang rollback belum memiliki record sukses
    di `/etl-runs`; lihat `/jobs/{id}` untuk kegagalan extract, DQ STOP_BATCH, atau deployment.
14. API metadata mengembalikan JSON terstandar. Endpoint unduhan artifact/CSV mengembalikan file dengan
    Content-Disposition. Export mengikuti filter, izin dan limit query, bukan export data tanpa batas.

## Cakupan lanjutan dari baseline

Yang belum diimplementasikan: split satu tab menjadi beberapa grain/tabel; taxonomy/reference mapper;
FK/join lintas data product; migrasi otomatis schema evolution; incremental watermark; append event
yang mempertahankan baris identik; DEFAULT_VALUE DQ; workflow melanjutkan batch REQUIRE_REVIEW
(saat ini menghentikan job); semantic similarity/embedding; template dengan parameter dinamis;
query cache statistics dashboard; SSE; Prometheus; notification; autentikasi OIDC; distributed login
rate limiting; RLS seluruh tabel; immutable audit storage di tingkat database; pengujian beban, backup/restore,
disaster recovery dan penetration test produksi.

`APPEND` mengabaikan duplikat berdasarkan business key jika tersedia, atau hash seluruh baris. Worker saat
ini memuat baris satu per satu; gunakan batch/COPY dan object storage sebelum menaikkan skala data besar.

OpenAI/Google asli memerlukan kredensial Anda. Kontrak adapter diuji dengan mock; tidak ada klaim bahwa
model, biaya akun, akses Service Account, atau kuota eksternal sudah diuji live.

## Referensi resmi saat implementasi

- [FastAPI JWT dan hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Google Sheets batchGet](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/batchGet)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)


## Rencana master data dan validasi import

Kebutuhan baru untuk klasifikasi master/non-master, master kanonis lintas Sheet, foreign key referensi, review AI per import, dan pertanyaan pengguna didokumentasikan di [Master data dan validasi import](MASTER_DATA_DAN_VALIDASI_IMPORT.md). Dokumen tersebut adalah spesifikasi lanjutan; fitur-fitur itu belum termasuk implementasi saat ini.


## API Reference frontend

Endpoint yang sudah tersedia beserta payload, respons, role, error, dan mekanisme frontend dijelaskan di [API Reference](API_REFERENCE.md). Snapshot OpenAPI dan schema dapat diperbarui dengan `scripts/export_api_reference.py`; contoh payload diverifikasi terhadap schema backend.

Panduan fitur baru: [Wizard review konfigurasi ETL dan import Excel](PANDUAN_REVIEW_ETL.md) memuat cara menjalankan migrasi, halaman Vue `/workspace`, payload preview/apply, dan mekanisme persetujuan.
