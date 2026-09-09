# Batch review import — BE-05

BE-05 menyediakan batch persisten, snapshot tetap, checkpoint worker, idempotency, temuan deterministik, cancel, revalidate, dan kontrak resume. Batch tidak menulis ke trusted/master dan tidak memanggil AI. Pertanyaan/jawaban terstruktur mengikuti BE-06, preview/apply BE-07, dan review AI BE-10.

## Prasyarat dan pembuatan batch

Sumber tidak dijeda, tab enabled, klasifikasi CONFIRMED, dan profiling/snapshot harus tersedia. Batch menggunakan snapshot **yang sudah tersimpan**, bukan membaca Google Sheet langsung. Jalankan profiling terlebih dahulu jika ingin mengambil perubahan terbaru di Google Sheet.

- NON_MASTER: `configuration_id` wajib dan harus APPROVED atau ACTIVE untuk tab/fingerprint yang sama. Review konfigurasi tetap merupakan tahap terpisah.
- MASTER: jangan kirim `configuration_id`. Mapping berasal dari master source binding APPROVED yang cocok dengan klasifikasi, fingerprint, hash snapshot, dan versi master approved yang aktif. Penambahan snapshot berbeda mungkin memerlukan review binding BE-03 kembali. Storage master tidak diwajibkan untuk validasi batch; pemuatan belum tersedia.

`POST /api/v1/import-reviews` — HTTP 202:

```json
{
  "source_sheet_id":"33333333-3333-4333-8333-333333333333",
  "configuration_id":"44444444-4444-4444-8444-444444444444"
}
```

Untuk MASTER:

```json
{"source_sheet_id":"33333333-3333-4333-8333-333333333333"}
```

Respons `data` berisi `review` dan `reused`. `review` mengikuti kontrak detail di bawah, kecuali `dependencies_current` hanya disertakan GET detail. `reused=false` berarti batch/job pertama dibuat; `true` berarti batch identik dikembalikan tanpa job baru. Status HTTP 202 tetap digunakan saat reuse batch terminal; periksa `review.status`, jangan menganggap semua respons 202 mempunyai pekerjaan baru.

## Identitas batch dan idempotency

Kunci server adalah SHA-256 dari tenant, tab/sumber, hash snapshot, klasifikasi/revisinya, pengaturan header/range, fingerprint, konfigurasi beserta revisi/hash, binding beserta revisi, master approved beserta versi/hash, dan policy schema version 1.0. Unique constraint tenant+kunci serta advisory lock per tab mencegah dua create bersamaan menghasilkan batch berbeda.

Snapshot ID tidak masuk kunci agar profiling ulang dengan konten identik tetap memakai batch yang sama. Batch menyimpan FK snapshot awal dan memverifikasi hash nilai snapshot tersebut. Konfigurasi/policy disalin secara tetap. Snapshot, konfigurasi, atau dependency baru tidak menggantikan isi batch lama secara diam-diam.

Reuse batch CANCELLED tetap mengembalikan CANCELLED; tidak membuka ulang batch. Untuk data/dependency baru gunakan POST create lagi. Jika batch identik FAILED, gunakan revalidate. Tidak ada parameter force untuk menimpa bukti lama.

## Endpoint dan izin

Semua path memakai prefix `/api/v1`. E = PLATFORM_ADMIN/SOURCE_OWNER/DATA_STEWARD, S = E ditambah TECHNICAL_APPROVER. VIEWER/ANALYST tidak mendapat akses. Akses ID tenant lain mendapat 404.

| Method dan path | Role | Hasil |
|---|---|---|
| POST `/import-reviews` | E | 202; `review`, `reused` |
| GET `/import-reviews` | S | 200; `items`, `has_more` |
| GET `/import-reviews/{review_id}` | S | 200; detail batch |
| GET `/import-reviews/{review_id}/findings` | S | 200; `items`, `has_more` |
| POST `/import-reviews/{review_id}/cancel` | E | 200; batch CANCELLED |
| POST `/import-reviews/{review_id}/revalidate` | E | 200; batch VALIDATING atau tetap STALE_REVIEW |
| POST `/import-reviews/{review_id}/resume` | E | 200 jika blocker selesai; saat ini umumnya 409 IMPORT_INPUT_PENDING |

List mendukung `status`, `source_sheet_id`, `offset>=0`, `limit=1..100` (default 50). Urutan dibuat terbaru lalu UUID. `findings` mendukung offset/limit sama; memuat lokasi baris, kode error/kolom atau warning, tanpa nilai sel mentah. Temuan saat ini belum mempunyai question ID atau endpoint jawaban BE-06.

Payload cancel/revalidate/resume memakai revisi dari detail terbaru:

```json
{"revision_no":3,"comment":"Tindak lanjut hasil review batch"}
```

Revisi bertambah pada transisi status; jangan menghitung sendiri di frontend. `generation` bertambah saat revalidate/resume mengantrekan percobaan baru. Job lama hanya boleh mengubah batch jika generation dan `job_id` masih cocok.

## Respons detail dan polling

Contoh NON_MASTER setelah dua tahap worker selesai, dengan UUID/hash fiktif:

```json
{
  "status":"success",
  "data":{
    "id":"11111111-1111-4111-8111-111111111111",
    "tenant_id":"22222222-2222-4222-8222-222222222222",
    "source_id":"55555555-5555-4555-8555-555555555555",
    "source_sheet_id":"33333333-3333-4333-8333-333333333333",
    "snapshot_id":"66666666-6666-4666-8666-666666666666",
    "snapshot_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "idempotency_key":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "created_by":"77777777-7777-4777-8777-777777777777",
    "created_at":"2026-09-08T00:00:00Z",
    "status":"NEEDS_INPUT",
    "revision_no":3,
    "generation":1,
    "job_id":"88888888-8888-4888-8888-888888888888",
    "dataset_kind":"NON_MASTER",
    "configuration_id":"44444444-4444-4444-8444-444444444444",
    "configuration_revision":1,
    "master_id":null,
    "master_version":null,
    "policy":{
      "schema_version":"1.0",
      "classification_scope":"SHEET",
      "dataset_kind":"NON_MASTER",
      "master":null,
      "apply_mode":"ATOMIC_BATCH",
      "mandatory_question_policy":"BLOCK_APPLY",
      "ai_review_policy":"REQUIRED_FOR_ALLOWED_FIELDS"
    },
    "checkpoint":{
      "deterministic_complete":true,
      "rows_valid":3,
      "rows_invalid":0,
      "warning_count":0,
      "blocking_codes":["AI_REVIEW_NOT_IMPLEMENTED"],
      "ai_coverage":"NOT_STARTED"
    },
    "finding_count":0,
    "dependencies_current":true,
    "execution_ready":false
  },
  "meta":{},
  "errors":[]
}
```

Respons list adalah proyeksi yang sama tanpa `dependencies_current`. List/findings menyertakan `meta.offset` dan `meta.limit`. Konfigurasi tersimpan dan dependency internal tidak dikirim ke frontend karena dapat mengandung literal sensitif. `checkpoint` dapat kosong sebelum worker pertama, atau menyertakan `last_error_code` setelah kegagalan. Untuk DQ STOP_BATCH/REQUIRE_REVIEW, validasi dapat berhenti lebih awal: `deterministic_complete=false` dan jumlah baris lengkap tidak diklaim.

Poll GET detail batch saat VALIDATING/AI_REVIEWING. `job_id` menunjuk job tahap terbaru, jadi dapat berubah setelah checkpoint. GET `/jobs/{job_id}` tetap berguna untuk error teknis satu tahap; Job SUCCEEDED dapat menghasilkan batch AI_REVIEWING, NEEDS_INPUT, STALE_REVIEW, atau hasil skipped. Itu bukan keberhasilan load import.

Berhenti polling otomatis saat NEEDS_INPUT, FAILED, STALE_REVIEW, atau CANCELLED. Tampilkan `blocking_codes` dan temuan; jangan mengirim resume/retry dalam loop. `AI_REVIEW_NOT_IMPLEMENTED` adalah batas capability BE-05, bukan pertanyaan yang dapat dijawab pengguna sekarang.

## Lifecycle dan checkpoint

1. Create menyimpan batch VALIDATING dan job dalam transaksi yang sama.
2. Worker memverifikasi dependency, memakai snapshot/config tetap, menjalankan transformasi/DQ, dan menyimpan checkpoint/temuan tanpa raw values.
3. Jika ada masalah data, batch menjadi NEEDS_INPUT dan job selesai normal. Jika valid, batch menjadi AI_REVIEWING dan job tahap berikutnya dibuat bersama checkpoint dalam transaksi yang sama.
4. Tahap AI BE-05 mencatat blocker AI_REVIEW_NOT_IMPLEMENTED dan berhenti pada NEEDS_INPUT. Tidak ada permintaan OpenAI, bukti AI, atau status READY_FOR_APPROVAL yang dihasilkan.
5. Kegagalan teknis me-rollback tahap aktif; transaksi penanganan gagal menandai job/batch FAILED serta menyimpan kode error generik. Checkpoint tahap sebelumnya tetap ada.
6. Worker yang terputus setelah claim dipulihkan oleh scheduler berdasarkan batas stale job. Lock job mencegah scheduler menandai job yang masih diproses dalam transaksi aktif. Recovery bukan retry otomatis.

State machine mencakup READY_FOR_APPROVAL, APPROVED, APPLYING dan SUCCEEDED. Endpoint preview/approve/apply BE-07 kini tersedia; preview menghasilkan token yang terikat snapshot dan revision, approval memerlukan reviewer terpisah sesuai kebijakan, dan apply melakukan UPSERT atomik ke storage trusted. Gate sync MASTER lama tetap berlaku. Sync NON_MASTER lama belum dialihkan ke batch ini; integrasi seluruh jalur mengikuti BE-11.

`cancel` berlaku sebelum APPLYING/SUCCEEDED dan tidak menghapus snapshot/temuan. Job queued lama dapat diproses sekali menjadi skipped. Jika cancel bersaing dengan worker, row lock menserialisasi perubahan dan request dengan revisi lama mendapat 409.

`revalidate` dipakai untuk FAILED/STALE_REVIEW. Dependency harus masih identik; jika berbeda batch tetap/menjadi STALE_REVIEW dan respons 200 menginstruksikan frontend membuat batch baru. Jika identik, batch kembali VALIDATING dengan generation/job baru. Checkpoint deterministik yang sudah lengkap dan tanpa blocker dipakai ulang; tidak membaca ulang Sheet atau memproses ulang nilai yang sudah divalidasi. Error terakhir tetap tercatat untuk diagnosis.

`resume` hanya berlaku untuk NEEDS_INPUT setelah blocker benar-benar diselesaikan. BE-05 tidak menyediakan endpoint untuk menghapus blocker; mekanisme keputusan BE-06 dan capability BE-10 akan menghubungkannya. Revalidate pada NEEDS_INPUT dengan dependency sama juga ditolak, sehingga snapshot buruk tidak berulang diproses tanpa perubahan. Perbaiki sumber, profile, sesuaikan konfigurasi/binding bila perlu, lalu buat batch baru.

GET detail menghitung `dependencies_current` tanpa mengganti snapshot atau status. Perubahan baru disimpan sebagai STALE_REVIEW ketika worker/revalidate/resume memeriksanya. Refresh list saja bukan invalidasi proaktif. Hash dependency ini belum mencakup revision record target/alias/FK yang belum terintegrasi; gate preview/apply BE-07 dan seterusnya harus menambah bukti tersebut.

## Error frontend

| HTTP | Code | Arti/tindakan |
|---|---|---|
| 403/404 | FORBIDDEN / RESOURCE_NOT_FOUND | Role atau tenant tidak sesuai |
| 409 | IMPORT_SOURCE_UNAVAILABLE | Tab disabled/sumber paused |
| 409 | IMPORT_CLASSIFICATION_REQUIRED | Klasifikasi/profiling belum lengkap |
| 409 | IMPORT_SNAPSHOT_INVALID | Snapshot hilang/hash tidak sesuai |
| 409 | IMPORT_CONFIGURATION_REQUIRED / IMPORT_CONFIGURATION_INVALID | Gunakan konfigurasi approved untuk tab yang sesuai |
| 409 | IMPORT_MAPPING_INVALID / IMPORT_BINDING_REQUIRED | MASTER perlu binding approved terkini, bukan configuration_id |
| 409 | IMPORT_MASTER_STALE | Master/versinya tidak sesuai |
| 409 | IMPORT_REVISION_CONFLICT | GET ulang sebelum melakukan aksi |
| 409 | IMPORT_STATE_CONFLICT | Aksi tidak berlaku untuk status sekarang |
| 409 | IMPORT_INPUT_PENDING | Blocker belum selesai; jangan retry otomatis |
| 409 | IMPORT_REVALIDATE_REQUIRED | Retry job IMPORT_REVIEW ditolak; gunakan revalidate batch |
| 422 | VALIDATION_ERROR | Payload atau query tidak sesuai schema |

## Migrasi dan operasi

Migrasi `5ab90e816eee` menambah `platform.import_review`, FK tenant ke sumber/tab/snapshot/actor/job, unique idempotency, serta check revision/status. Sudah dijalankan pada database test terpisah; **belum diterapkan ke database aplikasi** pada sesi BE-05.

Saat rollout, hentikan/pause worker versi lama sesuai prosedur deployment lalu jalankan dari root backend:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

Jalankan backend dan worker dengan kode yang sama. Antrean database tetap diproses oleh dispatcher/runner yang sudah tersedia; tidak ada queue Redis baru. Downgrade menghapus tabel batch dan bukti review; backup terlebih dahulu dan hentikan job IMPORT_REVIEW sebelum rollback. Snapshot/registry/record trusted tidak dihapus oleh migrasi ini.

Temuan disimpan sebagai JSON per batch dan dipaginasi oleh API; chunk processing/storage temuan berskala besar belum dibenchmark. Snapshot/config persisten tidak dihapus otomatis. AI, pertanyaan, approval dan apply masih tahap berikutnya, sehingga BE-05 bukan klaim bahwa alur import production lengkap sudah siap.

Lihat [API Reference](API_REFERENCE.md), [TODO backend](TODO_BACKEND.md), dan [Storage BE-04](STORAGE_MASTER_BE04.md). Frontend belum diubah pada tahap ini.

Verifikasi 8 September 2026: **95 tes backend lulus**, Ruff lulus, Alembic check lulus, dan **114 operasi API** terverifikasi. Tes baru mencakup create bersamaan, checkpoint antar-job, blocker tanpa retry loop, temuan tanpa raw values, cancel/revisi stale, snapshot berubah/identik, perubahan master, kegagalan teknis, simulasi worker terputus dan checkpoint reuse, job duplikat/generation lama, tenant actor FK, serta upgrade/downgrade migrasi dalam transaksi yang di-rollback. Tidak ada panggilan provider nyata pada tes ini.


## Pembacaan preview oleh reviewer

GET `/import-reviews/{review_id}/preview` tersedia untuk editor/reviewer termasuk
TECHNICAL_APPROVER. POST preview tetap editor. GET memverifikasi rencana tersimpan via
hash/revision, memberi before/after yang dimasking menurut role, dan tidak menerbitkan
token atau mengubah staging. Reviewer mengirim preview_hash dan review.revision_no dari
hasil GET saat approve. Rincian respons, stale, serta compatibility preview lama ada di
[API Reference](API_REFERENCE.md#membaca-preview-import-untuk-approval-dua-akun).


Verifikasi endpoint baca preview: 21 tes PostgreSQL gabungan dua akun/stale/APPEND/
taxonomy lulus, ditambah 1 tes GET canonical taxonomy tanpa mutation staging. Regresi
non-integrasi tanpa workbook: 214 lulus. Ruff file perubahan, exporter --check 152
operasi, payload approval dua akun, dan git diff --check lulus. Tidak memerlukan migrasi.
