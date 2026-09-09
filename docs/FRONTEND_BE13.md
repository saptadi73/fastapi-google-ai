# Handoff frontend BE-13: taxonomy, bertahap

Acuan kode workspace: 9 September 2026. **Tahap 1–4 di bawah dapat mulai diintegrasikan;
Tahap 5 menambahkan saran AI generatif; verifikasi provider/deployment tujuan masih diperlukan. BE-14 belum dimulai.**
Migrasi registry/version sudah diuji pada database test, belum merupakan bukti deployment
ke environment frontend. Backend tujuan harus memiliki migrasi sampai `9b07c8d6e5fa`
dan kode worker terbaru sebelum pengujian bersama.

Bahan handoff:

- [Payload siap diadaptasi](api/BE13_FRONTEND_PAYLOADS.json): setiap entri memuat method,
  path, model, dan body. Kirim hanya `body`; ganti placeholder path, UUID dan revision
  dengan respons aktual. UUID contoh sintetis, tidak menunjuk data existing.
- [API Reference](API_REFERENCE.md#5-taxonomy-be-13), [schema](api/SCHEMAS.md),
  [OpenAPI](api/openapi.json), dan [bukti/batas implementasi](REVIEW_BE13.md).
- [Frontend BE-12](FRONTEND_BE12.md) untuk form konfigurasi, review, dan workbook existing.

## Kontrak bersama

Semua path relatif ke `/api/v1`. Gunakan Authorization Bearer dan tenant dari sesi.
Envelope sukses: `{"status":"success","data":...,"meta":{},"errors":[]}`.
HTTP error: `errors[].code/message/details`; validasi schema memakai `VALIDATION_ERROR`
dan `details[].field/message`. Download artifact adalah file, bukan envelope JSON.

Editor: PLATFORM_ADMIN, SOURCE_OWNER, DATA_STEWARD. Reviewer: PLATFORM_ADMIN,
TECHNICAL_APPROVER. Router taxonomy membolehkan baca bagi kelompok tersebut; jangan
menganggap ANALYST/VIEWER memiliki akses. Approval tunduk `require_separate_approver`.
Tampilkan aksi berdasarkan izin dan state, lalu tetap tangani 403 dari backend.

Jangan menyamakan tiga angka berikut:

| Nilai | Penggunaan |
|---|---|
| `taxonomy.version` | Versi kategori terbit yang dipin pada binding/configuration |
| `revision_no` pada binding/version draft/configuration/review | Optimistic concurrency objek masing-masing |
| `revision_no` pada question | Body answer memakai revisi pertanyaan, bukan revisi batch |

Ambil ulang record setelah mutation. Jangan menebak bahwa revision/version berikutnya
adalah angka tertentu. Approval awal taxonomy menaikkan version; approval ulang taxonomy
yang sudah approved tidak menaikkannya. `TaxonomyVersion.id` berbeda dari `taxonomy_id`.

## Tahap 1 — daftar kategori dan resolver

Prioritas UI: daftar taxonomy, daftar term/hierarki, form draft dan tombol approval.

| Aksi | Endpoint | Hasil yang dipakai UI |
|---|---|---|
| Daftar taxonomy | GET /taxonomies | `data` array; id, code, name, status, version, is_active |
| Buat draft | POST /taxonomies | 201, record DRAFT; body `create_taxonomy` |
| Daftar term | GET /taxonomies/{taxonomy_id}/terms | `data` array; id, code, label, aliases, parent_id, is_active |
| Tambah term | POST /taxonomies/{taxonomy_id}/terms | 201; body `create_term`, hanya taxonomy DRAFT aktif |
| Approval awal | POST /taxonomies/{taxonomy_id}/approve | 200 record taxonomy; tanpa body, reviewer |
| Resolver | POST /taxonomies/{taxonomy_id}/resolve-term | 200; body `resolve_term` |
| Validasi awal | POST /taxonomies/{taxonomy_id}/validate-values | 200; body `validate_values`, baca `data.valid` |

Endpoint list taxonomy saat ini mengembalikan maksimal 100 record tanpa pagination
publik. List term memuat term nonaktif juga; jangan menawarkan term nonaktif sebagai
pilihan aktif. Parent berasal dari taxonomy yang sama. Belum ada DELETE/PATCH term langsung;
perubahan term approved dilakukan melalui draft versi pada tahap 4.

Resolver mengembalikan `EXACT` dengan `term`, atau `CANDIDATE`/`AMBIGUOUS`/`NOT_FOUND`
dengan `candidates`. Selalu baca `requires_question`. Trim/case-fold dan kode exact
diutamakan, lalu label/alias. CANDIDATE merupakan saran, tidak boleh dipilih otomatis.
Resolver memakai pencarian kandidat tambahan bila tidak ada exact; kandidat worker
otomatis terbatas pada kecocokan exact/alias yang ambigu.

`recommend-terms` tersedia sebagai ranking kemiripan teks. Jika ditampilkan, labeli
sebagai saran kemiripan dan minta konfirmasi; jangan beri label saran AI generatif.

**Selesai tahap 1:** editor dapat membuat taxonomy/term, reviewer menyetujui, UI membaca
version aktual, serta membedakan hasil exact, kandidat, ambigu, dan tidak ditemukan.

## Tahap 2 — binding kolom dan konfigurasi ETL

Urutan: pilih taxonomy approved → simpan binding DRAFT → reviewer approve binding →
simpan referensi yang sama dalam konfigurasi draft → validate/review konfigurasi.

| Aksi | Endpoint | Body / hasil |
|---|---|---|
| Baca binding | GET /taxonomies/source-sheets/{sheet_id}/column-bindings | `data` array |
| Simpan binding | PUT /taxonomies/source-sheets/{sheet_id}/column-bindings | `save_binding`; baru revision 0, edit revision existing |
| Approve binding | POST /taxonomies/column-bindings/{binding_id}/approve | `binding_approve`, reviewer |
| Reject binding | POST /taxonomies/column-bindings/{binding_id}/reject | `binding_reject`, reviewer |
| Simpan konfigurasi | PATCH /configurations/{config_id} | `patch_configuration`: objek configuration lengkap |
| Dry-run | POST /configurations/{config_id}/validate | Tanpa body; baca validasi atau HTTP error |

Binding memiliki `taxonomy_id`, `taxonomy_version`, `source_column`, `required`, dan
`normalization=TRIM_CASEFOLD`. Configuration menggunakan `taxonomy_required`, bukan
`required`. UUID/version/required harus sama dengan binding approved; target hanya
text/varchar. `source_column` adalah header sheet, `target_column` nama kolom target.
Save binding existing mencabut approval. Save/approve/reject mengubah revisi.

PATCH configuration mengganti seluruh objek/daftar yang dikirim: mulai dari
`configuration_json` terbaru dan pertahankan field lain. Clone configuration immutable
sebelum edit. Menghapus referensi taxonomy dari konfigurasi berarti id/version null
dan required false; ini tidak menghapus registry binding.

Rule opsional `in_taxonomy` memakai mapping kolom tersebut. Contoh ada pada payload
configuration. `value` null; `WARN` ditolak. `REQUIRE_REVIEW` membuat pertanyaan di worker
dan menghentikan ETL langsung; `STOP_BATCH`/pelanggaran threshold menghentikan batch.
Validasi mapping tetap berlaku walaupun rule tidak ditulis. Required menolak kosong;
optional membolehkan null/kosong tetapi tetap menolak nilai asing/ambigu.

**Selesai tahap 2:** konfigurasi lolos dengan binding yang cocok, perubahan binding
mengharuskan approval ulang, dan UI menampilkan error mismatch tanpa retry paksa.

## Tahap 3 — pertanyaan taxonomy otomatis pada import

1. POST `/import-reviews` dengan `create_import`; 202 mengembalikan `data.review`
   dan penanda `data.reused`. Poll GET `/import-reviews/{review_id}`.
2. Saat NEEDS_INPUT, ambil GET `/import-reviews/{review_id}/questions?status=OPEN&offset=0&limit=50`.
   Hasil `data.items` dan `data.has_more`; lanjutkan pagination. Filter category opsional.
3. Render `prompt`, `source_row`, `source_column`, `target_column`, `candidates`,
   `mandatory`, `status`, dan `allowed_actions`. Jangan mengasumsikan semua pertanyaan
   memiliki kandidat atau aksi yang sama.
4. POST `/import-reviews/{review_id}/questions/{question_id}/answer` menggunakan revisi
   question. Respons normal memuat `data.question` dan `data.review`; muat ulang daftar.
5. Resume hanya ketika NEEDS_INPUT dan `checkpoint.blocking_codes` kosong, dengan
   revision batch terbaru. POST `/import-reviews/{review_id}/resume` mengembalikan 200.
   Poll kembali; resume tidak berarti batch sudah approved atau applied.

| Category otomatis | Aksi yang tersedia | Payload contoh |
|---|---|---|
| TAXONOMY_AMBIGUOUS | SELECT_RECORD atau CORRECT_SOURCE | `answer_candidate` |
| TAXONOMY_INVALID | APPLY_CORRECTION atau CORRECT_SOURCE | `answer_correction` |

SELECT_RECORD mengirim UUID kandidat dari respons; backend menyimpan **kode term**.
Koreksi teks harus cocok dengan taxonomy approved dan dinormalisasi sebelum disimpan.
Pertanyaan wajib tidak menawarkan KEEP_ORIGINAL. Tetap ikuti `allowed_actions` aktual;
endpoint pertanyaan manual existing dapat memiliki kategori/aksi berbeda.

CORRECT_SOURCE membutuhkan reason (`answer_source`). Aksi ini mencatat keputusan,
tidak mengubah Google Sheet atau snapshot batch. Setelah sumber diperbaiki, ambil
snapshot/configuration yang sesuai dan buat batch baru. Jangan menganggap pertanyaan
ANSWERED berarti nilai snapshot lama sudah diperbaiki.

HTTP 200 pada answer bisa memuat `data.stale=true`, `question=null`, dan review yang
stale. Perlakukan sebagai dependency berubah, bukan jawaban berhasil. Batch stale
tidak otomatis dipindahkan ke snapshot/versi baru oleh revalidate. Perbarui referensi
dan buat batch baru bila sumber/configuration/taxonomy sudah berubah.

Setelah fase deterministik, batch melewati AI_REVIEWING. Jika review AI belum
dikonfigurasi, backend dapat memberi blocker `AI_REVIEW_NOT_IMPLEMENTED`; tampilkan
status dan alasannya. UI tidak boleh melewati blocker ini. Saran taxonomy generatif
dan review AI import merupakan dua kemampuan berbeda.

Alur final existing: READY_FOR_APPROVAL → POST preview (`preview_import`) → tampilkan
perubahan dan `can_approve` → reviewer POST approve (`approve_import`) → editor POST
apply (`apply_import`) dengan token preview dan revision batch terbaru. Preview/approval
harus valid; jawaban pertanyaan saja tidak memberi izin apply. Token workbook tidak
dapat dipakai sebagai token preview import. Raw staging tetap utuh; koreksi berisi kode.

**Selesai tahap 3:** nilai valid dinormalisasi, ambiguous/invalid wajib dijawab,
counter pertanyaan ikut berubah, resume tidak menggandakan pertanyaan, dan stale/AI
blocker tidak dapat dilompati lewat UI.

## Tahap 4 — versi taxonomy dan XLSX

| Aksi | Endpoint | Kontrak |
|---|---|---|
| Buat draft versi | POST /taxonomies/{taxonomy_id}/versions | `create_version` dengan base_version aktif; 201, retry mengembalikan draft sama |
| Riwayat | GET /taxonomies/{taxonomy_id}/versions?offset=0&limit=50 | `data.items`, `has_more`, terbaru dahulu; limit maksimal 100 |
| Detail draft/snapshot | GET /taxonomies/versions/{version_id} | `definition_json.terms`, revision_no, status, version, base_version |
| Simpan seluruh term | PUT /taxonomies/versions/{version_id} | `update_version`; bukan patch parsial |
| Publikasi | POST /taxonomies/versions/{version_id}/approve | `publish_version`; reviewer berbeda dari editor terakhir jika kebijakan aktif |

Term lama mempertahankan UUID/kode. Term baru memakai UUID baru; label/alias/parent/
is_active dapat diedit. Semua parent harus ikut daftar, tanpa siklus; ancestor term
aktif harus aktif. Term yang dihilangkan menjadi nonaktif di registry. Tampilkan diff
termasuk penghilangan term sebelum submit. Snapshot terbit immutable; tidak ada
endpoint cancel/delete draft versi. Riwayat sebelum snapshot migrasi tidak direkonstruksi.
Sesudah publikasi, binding versi lama stale: perbarui binding dan konfigurasi, approve
ulang, lalu gunakan batch baru.

XLSX mengikuti alur [BE-12](FRONTEND_BE12.md): export XLSX → download artifact →
workbook-preview (`content_base64`) → baca errors/diff/validation/can_apply →
workbook-apply menggunakan configuration, question_answers, revision_no, preview_token
dari preview yang sama. Ini menyimpan draft konfigurasi, bukan apply data import.

| Tab | Sel yang relevan | Batas |
|---|---|---|
| 04 Taxonomy Mapping | U=taxonomy_id, V=taxonomy_version, W=taxonomy_required Ya/Tidak | Referensi konfigurasi; bukan editor term/approval registry |
| 04 Taxonomy Mapping | Identitas sumber dan X=TRIM_CASEFOLD | Sel signed, tidak diedit |
| 05 Data Quality | E=rule, H=action_on_fail, baris mulai 5 | `in_taxonomy` didukung; WARN ditolak |

Simpan/approve binding registry lebih dahulu supaya workbook-preview dapat memvalidasi
referensi baru. Workbook lama tanpa editor taxonomy mempertahankan mapping existing;
unduh format terbaru untuk mengeditnya. Formula, identitas yang diubah, dan baris kolom
baru ditolak. `can_apply` workbook berarti bisa menyimpan draft, bukan approval data.

**Selesai tahap 4:** revisi bersamaan tidak saling menimpa, snapshot lama terbaca,
publikasi menandai referensi lama perlu diperbarui, dan round-trip XLSX menjaga field lain.

## Error dan pemulihan UI

| Kode/kondisi | Tindakan frontend |
|---|---|
| REVISION_CONFLICT, IMPORT_REVISION_CONFLICT, IMPORT_QUESTION_REVISION_CONFLICT | Muat ulang objek terkait; minta pengguna meninjau perubahan sebelum submit ulang |
| TAXONOMY_IMMUTABLE, TAXONOMY_VERSION_IMMUTABLE | Matikan edit langsung; gunakan draft versi berikutnya |
| TAXONOMY_VERSION_STALE/MISMATCH, TAXONOMY_BINDING_STALE/REQUIRED | Muat versi aktif, binding dan konfigurasi; samakan lalu approve ulang |
| TAXONOMY_VALUE_INVALID/AMBIGUOUS | Tampilkan perbaikan/pilihan dari pertanyaan; jangan auto-pilih |
| TAXONOMY_KEY_COLLISION | Perbaiki key sumber dan buat batch baru; jangan melewati blocker |
| IMPORT_STALE_REVIEW atau 200 dengan stale=true | Tampilkan stale; buang token preview lokal dan muat state baru |
| IMPORT_INPUT_PENDING, IMPORT_STATE_CONFLICT | Tampilkan state dan blocking_codes; jangan retry otomatis |
| IMPORT_PREVIEW_STALE/CONFLICT | Muat ulang batch/target; buat preview dan approval yang sesuai |
| SEPARATE_APPROVER_REQUIRED | Minta reviewer berbeda; jangan mengubah identitas pembuat di payload |
| WORKBOOK_STALE, WORKBOOK_TOKEN_INVALID | Unduh/preview ulang memakai draft dan sesi yang sesuai |
| 403 / 404 | Akses ditolak / data tidak tersedia; jangan mencoba UUID tenant lain |

Label catalog kemampuan umum bukan satu-satunya penentu kesiapan taxonomy. Cocokkan
kontrak ini dengan OpenAPI dan deployment backend tujuan. Tidak perlu menunggu BE-14
untuk mengerjakan tahap 1–4; tahan klaim saran AI generatif sampai kontraknya tersedia.


## Tahap 5 ? saran AI generatif sesuai permintaan

Tambahkan tombol Minta saran AI pada editor kategori/pertanyaan TAXONOMY_INVALID.
Panggil POST `/taxonomies/{taxonomy_id}/recommend-terms-ai` dengan body `recommend_terms_ai`
pada file payload. Hanya editor; taxonomy_version wajib versi aktif. Maksimal 50 nilai
nonblank (masing-masing sampai 500 karakter), limit kandidat 1-10. Backend mengirim nilai
kategori yang dipilih dan taxonomy aktif ke provider, tanpa mengambil raw row import lain.
Jangan memanggil endpoint otomatis setiap ketikan atau mengirim field sensitif lain.

Tampilkan recommendations[].input_index/value/candidates dan provenance ai_model,
prompt_version serta recommendation_kind=GENERATIVE. candidates[].term memuat data term
registry; confidence adalah estimasi model, bukan probabilitas terkalibrasi. Kandidat
kosong berarti tidak ada saran yang didukung. Selalu minta konfirmasi pengguna.

Untuk pertanyaan TAXONOMY_INVALID, setelah konfirmasi kirim term.code sebagai corrected_value
melalui APPLY_CORRECTION. SELECT_RECORD tetap hanya untuk kandidat yang sudah ada di
pertanyaan; ID AI tidak menambah daftar kandidat pertanyaan. Endpoint ini tidak membuat
term/alias/binding dan tidak memberikan approval. Alias baru tetap draft/publikasi versi.

Tangani OPENAI_NOT_CONFIGURED/AI_UPSTREAM_FAILED (503), AI_CONFIGURATION_INVALID atau
TAXONOMY_AI_RESULT_INVALID (422), TAXONOMY_AI_SCOPE_LIMIT (422), TAXONOMY_VERSION_STALE
(409), serta kuota/budget existing (429). Jangan mengubah kegagalan menjadi sukses kosong.
Boleh tampilkan tombol saran kemiripan existing sebagai pilihan terpisah dengan label jelas.

Backend memakai OPENAI_MODEL_ETL_CONFIG dan kebijakan provider existing. Implementasi
HTTP/DB diuji dengan respons provider terkontrol; kualitas saran dan kredensial model nyata
harus diverifikasi pada environment tujuan. Rincian: [API Reference](API_REFERENCE.md#saran-taxonomy-generatif-be-13).

**Selesai tahap 5:** saran hanya dipakai setelah konfirmasi, penolakan/stale/limit ditampilkan,
koreksi tetap diverifikasi backend, dan kegagalan AI tidak melewati approval import.


## Approval dua akun: kontrak baca preview

TECHNICAL_APPROVER sekarang dapat memanggil GET `/import-reviews/{review_id}/preview`.
Gunakan data.changes, summary, period_closures, masked_fields, can_approve. Simpan pasangan
review.revision_no dan preview_hash dari respons yang sama untuk POST approve. Jangan
menggunakan preview_revision sebagai revision batch setelah approval. GET tidak mengubah
staging dan tidak mengembalikan token apply; token tetap berasal dari POST milik editor.

Jika belum ada preview atau masih format lama: 409 IMPORT_PREVIEW_REQUIRED, minta editor
membuat ulang. Jika stale: buang tampilan lama dan minta preview/approval baru. Field sensitif
before/after tampil [REDACTED] bagi TECHNICAL_APPROVER, meskipun editor admin melihat nilai
aslinya. Hash tetap sama karena dihitung sebelum masking. can_approve bukan pengganti
pemeriksaan role/status/versi pada server. Lihat [kontrak lengkap](API_REFERENCE.md#membaca-preview-import-untuk-approval-dua-akun).
