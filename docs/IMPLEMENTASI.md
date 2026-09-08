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

Kebutuhan klasifikasi master/non-master, master kanonis lintas Sheet, foreign key referensi, review AI per import, dan pertanyaan pengguna didokumentasikan di [Master data dan validasi import](MASTER_DATA_DAN_VALIDASI_IMPORT.md). Pengerjaan mengikuti [TODO Backend](TODO_BACKEND.md).

BE-01 selesai pada tingkat kontrak dasar:

- Pengguna memilih klasifikasi per tab dan usulan insert kode master baru yang wajib disetujui.
- [Schema policy](../app/schemas/data_policy.py) memvalidasi jenis dataset, aturan master, sumber otoritatif, masa berlaku, serta batas apply/review.
- [Guard lifecycle](../app/domain/import_workflow.py) memvalidasi transisi status batch dan role; pemeriksaan tenant, evidence, approval terpisah, dan transaksi tetap harus ditambahkan pada service tahap berikutnya.
- Pengujian terarah policy/lifecycle dan kontrak API: 11 tes lulus; Ruff serta pemeriksaan API Reference lulus.

BE-01 tidak menambahkan endpoint atau migrasi database. BE-02 menyimpan klasifikasi tab dan menegakkan gate eksekusi; bukti review konfigurasi mengacu pada revision klasifikasi. BE-03 menyediakan registry definisi master, kandidat duplikat, lifecycle approval berversi, serta binding sumber approved dengan dry-run. BE-04 menyediakan storage kanonis bertipe dan pencarian record. Tab MASTER tetap tertahan sampai alur review/apply import tersedia pada BE-05–BE-11.

Detail BE-03, 13 endpoint baru, dan migrasi `d83a5f12c906` ada di [Registry master dan binding sumber](REGISTRY_MASTER_BE03.md). BE-04 menambah tiga endpoint storage/record; kontraknya ada di [Storage master BE-04](STORAGE_MASTER_BE04.md). API Reference kini mencakup 107 operasi. Pengguna melaporkan migrasi sebelumnya sudah dijalankan; sesi BE-04 tidak memigrasikan database aplikasi. Frontend katalog/binding/storage belum ditambahkan.

Verifikasi BE-04: 87 tes backend lulus pada database test, Ruff lulus, dan exporter API lulus. Tidak ada migrasi Alembic baru; tabel master dibuat melalui deploy-storage. Review/apply import dilanjutkan pada BE-05 dan seterusnya.

Migrasi `b762af03e219` menetapkan tab lama ke CLASSIFICATION_REQUIRED tanpa menebak jenisnya atau menghapus konfigurasi aktif. Pengujian backend memakai database test terpisah; rollout tetap perlu konfirmasi klasifikasi melalui API/Swagger karena frontend klasifikasi belum ditambahkan. Detail payload, respons, error, dan kompatibilitas tersedia di [Klasifikasi tab BE-02](KLASIFIKASI_TAB_BE02.md).


## API Reference frontend

Endpoint yang sudah tersedia beserta payload, respons, role, error, dan mekanisme frontend dijelaskan di [API Reference](API_REFERENCE.md). Snapshot OpenAPI dan schema dapat diperbarui dengan `scripts/export_api_reference.py`; contoh payload diverifikasi terhadap schema backend.

Panduan fitur baru: [Wizard review konfigurasi ETL dan import Excel](PANDUAN_REVIEW_ETL.md) memuat cara menjalankan migrasi, halaman Vue `/workspace`, payload preview/apply, dan mekanisme persetujuan.

## Batch review import BE-05

Model dan migrasi `5ab90e816eee`, tujuh endpoint batch/temuan, snapshot dan policy tetap, idempotency, checkpoint antar-job, cancel/revalidate/resume, serta recovery worker tersedia. Kontrak frontend ada di [Batch review BE-05](IMPORT_REVIEW_BE05.md); API Reference memuat 114 operasi. Temuan deterministik tidak mengekspos raw values. Batch berhenti pada NEEDS_INPUT untuk masalah data atau AI_REVIEW_NOT_IMPLEMENTED; belum ada review AI, pertanyaan/jawaban terstruktur, approval/apply batch, atau pengalihan sync NON_MASTER lama. Migrasi BE-05 hanya diterapkan di database test pada sesi implementasi ini.

Verifikasi BE-05: **95 tes lulus**, Ruff lulus, Alembic check lulus dan **114 operasi API** terverifikasi. Pengujian memakai database test serta provider mock; bukan bukti integrasi Google/OpenAI production. Tahap berikutnya BE-06.

## Pertanyaan batch BE-06

BE-06 menambah staging raw/transformed/corrected per batch, pertanyaan dan keputusan berversi, serta endpoint list/jawab/resolve proposal. Kontrak frontend ada di [Pertanyaan batch BE-06](IMPORT_QUESTIONS_BE06.md); API Reference memuat 117 operasi. Koreksi tidak menulis Google Sheet atau target trusted; proposal membuat draft registry dan hanya ditutup setelah master approved. Resolver kandidat otomatis/FK/apply belum tersedia. Migrasi `6d1305460956` hanya diterapkan pada database test di sesi ini.

Verifikasi BE-06: **99 tes lulus**, Ruff, Alembic check, dan exporter API lulus. Tahap berikutnya BE-07: preview dan apply master.
