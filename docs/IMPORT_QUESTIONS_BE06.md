# Pertanyaan dan keputusan batch import — BE-06

BE-06 menambahkan pertanyaan terstruktur dan staging per batch pada alur BE-05. Nilai dari Google Sheet tetap tersimpan pada snapshot dan **tidak pernah ditulis balik** oleh jawaban pengguna. Jawaban berupa koreksi hanya berlaku pada staging batch tersebut; import/apply ke target belum tersedia sampai BE-07.

## Saat pertanyaan dibuat

Worker validasi BE-05 membuat staging untuk setiap baris tidak kosong pada snapshot yang dikunci. Staging menyimpan tiga bentuk data internal: `raw_data` (nilai snapshot), `transformed_data` (hasil transform yang valid), dan `corrected_data` (koreksi pengguna). Ketiganya tidak tersedia melalui endpoint publik.

Pertanyaan dibuat untuk setiap error tipe/null atau duplicate business key. Peringatan DQ juga dapat menjadi pertanyaan tidak wajib. Pertanyaan konfigurasi unresolved dibuat dengan scope konfigurasi, tanpa nomor baris. API tidak mengirim nilai mentah atau evidence internal; frontend menggunakan nomor baris, kolom, kode temuan, prompt, kategori, dan kandidat yang aman untuk membangun tampilan keputusan.

| Kategori | Mandatory | Pilihan standar |
|---|---:|---|
| `DATA_QUALITY` | Ya | `APPLY_CORRECTION`, `CORRECT_SOURCE`, `PROPOSE_MASTER` |
| `DUPLICATE_KEY` | Ya | `APPLY_CORRECTION`, `CORRECT_SOURCE`, `PROPOSE_MASTER` |
| `DATA_QUALITY_WARNING` | Tidak | `KEEP_ORIGINAL`, `APPLY_CORRECTION`, `CORRECT_SOURCE` |
| `CONFIGURATION` | Ya | `CORRECT_SOURCE` |

`SELECT_RECORD` tersedia bila sistem resolver di tahap berikutnya memasukkan kandidat approved ke pertanyaan. Frontend hanya boleh menawarkan aksi dalam `allowed_actions`, dan hanya boleh mengirim ID yang ada pada `candidates`. Jangan membuat kandidat sendiri dari teks input.

## Endpoint frontend

Semua menggunakan prefix `/api/v1`. E = `PLATFORM_ADMIN`, `SOURCE_OWNER`, atau `DATA_STEWARD`; S = E ditambah `TECHNICAL_APPROVER`. Tenant lain menerima 404; VIEWER/ANALYST menerima 403.

| Method | Path | Role | Fungsi |
|---|---|---|---|
| GET | `/import-reviews/{review_id}/questions` | S | List pertanyaan |
| POST | `/import-reviews/{review_id}/questions/{question_id}/answer` | E | Simpan satu keputusan baris/scope |
| POST | `/import-reviews/{review_id}/questions/{question_id}/resolve-master-proposal` | R | Tutup proposal setelah master registry approved |

List parameter: `status=OPEN|ANSWERED|PENDING_APPROVAL|CANCELLED`, `category`, `offset>=0`, `limit=1..100` (default 50). Respons memakai envelope standar dan `data.items`, `data.has_more`. `meta.offset` dan `meta.limit` tersedia.

Contoh item pertanyaan:

```json
{
  "id":"11111111-1111-4111-8111-111111111111",
  "import_review_id":"22222222-2222-4222-8222-222222222222",
  "staging_row_id":"33333333-3333-4333-8333-333333333333",
  "source_row":2,
  "source_column":"Total",
  "target_column":"net_amount",
  "category":"DATA_QUALITY",
  "prompt":"Nilai pada baris/kolom ini tidak dapat digunakan tanpa keputusan pengguna.",
  "mandatory":true,
  "allowed_actions":["APPLY_CORRECTION","CORRECT_SOURCE","PROPOSE_MASTER"],
  "candidates":[],
  "candidate_count":0,
  "status":"OPEN",
  "revision_no":1,
  "decisions":[]
}
```

Contoh koreksi staging numerik:

```json
{
  "revision_no":1,
  "action":"APPLY_CORRECTION",
  "corrected_value":321,
  "reason":"Nilai sudah dikonfirmasi dari dokumen sumber"
}
```

`corrected_value` harus dapat dicast ke tipe target batch. Nilai untuk text, integer, numeric, boolean, tanggal, timestamp, dan UUID divalidasi server. Tipe salah menghasilkan `IMPORT_DECISION_VALUE_INVALID`; nilai kosong saat koreksi menghasilkan `IMPORT_DECISION_VALUE_REQUIRED`.

Contoh memilih kandidat record yang memang disediakan:

```json
{
  "revision_no":1,
  "action":"SELECT_RECORD",
  "selected_candidate_id":"44444444-4444-4444-8444-444444444444"
}
```

Kandidat yang tidak ada di `question.candidates` ditolak dengan `IMPORT_DECISION_CANDIDATE_INVALID`. Pada BE-06 kandidat belum dibuat otomatis dari master; resolution master/fallback alias disediakan oleh BE-08. `SELECT_RECORD` belum membuat FK fisik atau mengaktifkan apply.

Untuk meminta pembetulan sheet, gunakan `CORRECT_SOURCE` dan alasan wajib. Nilai snapshot lama tetap tidak diubah; frontend harus meminta pengguna memperbaiki sumber lalu menjalankan profiling dan membuat batch baru. Untuk usulan master baru gunakan `PROPOSE_MASTER` dengan alasan dan `master_proposal` bertipe `MasterDefinitionCreate` lengkap. Server membuat draft registry dan mengembalikan `proposed_master_definition_id` pada keputusan. Pertanyaan menjadi `PENDING_APPROVAL` dan batch mendapat blocker `MASTER_PROPOSAL_PENDING`.

Editor mengajukan draft melalui endpoint lifecycle master BE-03, reviewer menyetujuinya dengan endpoint master approve, lalu reviewer memanggil `resolve-master-proposal` menggunakan revision pertanyaan terbaru dan `master_definition_id` yang sama. Server menolak resolve jika master belum `APPROVED` dan aktif atau tidak terkait dengan proposal itu. Resolve menutup pertanyaan dan menghapus blocker proposal jika tidak ada proposal lain. Pembuatan/approval registry ini belum menulis record master, FK, maupun target import.

`KEEP_ORIGINAL` hanya tersedia untuk pertanyaan tidak wajib. Server menolak penggunaan aksi ini untuk error wajib. `reason` juga wajib untuk `PROPOSE_MASTER` dan `CORRECT_SOURCE`. Field `corrected_value` dan `selected_candidate_id` tidak boleh dikirim untuk aksi lain.

## Revision, stale, dan status batch

Jawaban selalu memeriksa `question.revision_no`. Setelah jawaban tersimpan, pertanyaan menjadi `ANSWERED` dan revisinya bertambah; jawaban kedua mendapat `IMPORT_QUESTION_ALREADY_ANSWERED`. Batch juga menaikkan revisi dan audit mencatat actor, waktu, scope baris, tindakan, serta ID keputusan.

Sebelum menyimpan jawaban, server memeriksa snapshot/config/binding/master/policy yang dipin pada batch. Bila dependency berubah, respons tetap HTTP 200 dengan:

```json
{"data":{"question":null,"review":{"status":"STALE_REVIEW"},"stale":true}}
```

Tidak ada keputusan yang disimpan. Frontend harus memuat ulang, lalu membuat batch baru untuk snapshot/dependency baru. Status ini dibuat dalam transaksi yang sama agar tidak hilang karena rollback respons error.

Saat semua pertanyaan wajib OPEN sudah dijawab, blocker `DATA_QUALITY_ISSUES` dihapus dari checkpoint. Hal ini tidak berarti batch siap apply: blocker AI BE-05 (`AI_REVIEW_NOT_IMPLEMENTED`), proposal master pending, pertanyaan lain, serta gate tahap berikutnya masih tetap menahan resume. Jangan retry atau resume secara berulang dari frontend.

## Data dan keamanan

Decision menyimpan before/after internal, evidence, pengguna, waktu, action, reason, kandidat dan scope. Respons publik keputusan hanya memuat metadata aman; nilai raw, before/after, evidence internal, frozen configuration, dependency, dan staging tidak diekspos. Koreksi hanya memperbarui `corrected_data` staging melalui row lock bersama question/review lock. Keputusan setiap baris berdiri sendiri, tidak membuat alias global atau mengubah master lain.

Batch lama dapat dibatalkan seperti BE-05. Cancel tidak menghapus snapshot, staging, pertanyaan, atau keputusan. Endpoint BE-06 tidak menulis Google Sheet, tidak mengubah record master kanonis, tidak membuat foreign key, dan tidak menjalankan OpenAI.

## Error penting

| HTTP | Code | Tindakan frontend |
|---|---|---|
| 403/404 | `FORBIDDEN` / `RESOURCE_NOT_FOUND` | Role atau tenant tidak sesuai |
| 409 | `IMPORT_STATE_CONFLICT` | Batch belum pada NEEDS_INPUT/FAILED |
| 409 | `IMPORT_QUESTION_REVISION_CONFLICT` | Muat ulang pertanyaan lalu ulangi bila masih OPEN |
| 409 | `IMPORT_QUESTION_ALREADY_ANSWERED` | Tampilkan keputusan tersimpan; jangan membuat jawaban kedua |
| 409 | `IMPORT_STAGING_MISSING` | Batch tidak konsisten; jangan retry otomatis |
| 422 | `IMPORT_DECISION_ACTION_INVALID` | Gunakan allowed_actions yang tersedia |
| 422 | `IMPORT_DECISION_CANDIDATE_INVALID` | Gunakan kandidat dari respons terbaru |
| 422 | `IMPORT_DECISION_REASON_REQUIRED` | Isi alasan untuk source correction/proposal |
| 422 | `IMPORT_DECISION_VALUE_REQUIRED` / `IMPORT_DECISION_VALUE_INVALID` | Isi nilai koreksi yang cocok dengan tipe target |

## Migrasi dan batasan

Migrasi `6d1305460956` menambah `staging.import_review_row`, `platform.import_question`, dan `platform.import_decision`, lengkap dengan FK tenant, unique question key/revision, dan status/check constraint. Migrasi diuji di database test; **belum diterapkan ke database aplikasi** pada sesi ini.

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

Rollout perlu menjalankan backend dan worker kode yang sama. Downgrade menghapus staging, pertanyaan, dan keputusan BE-06; backup dahulu serta hentikan job import sebelum rollback. BE-07–BE-11 tetap perlu menambahkan preview/apply, resolver/FK, review AI, dan integrasi semua jalur sync.

Lihat [API Reference](API_REFERENCE.md), [Batch BE-05](IMPORT_REVIEW_BE05.md), dan [TODO backend](TODO_BACKEND.md).

Verifikasi 8 September 2026: **99 tes backend lulus**, Ruff lulus, Alembic check lulus, dan **117 operasi API** terverifikasi. Tes mencakup koreksi typed staging dengan raw tetap, allowlist kandidat, tenant/role, jawaban ganda, revision/dependency stale, source correction, proposal master draft → submit → approve → resolve, batch resume ke AI blocker, serta downgrade/upgrade migrasi. Provider nyata tidak dipanggil.
