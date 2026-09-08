# BE-03 — Registry master dan binding sumber

Status: API dan penyimpanan metadata registry/binding tersedia. BE-03 sendiri tidak membuat tabel record master di `trusted`, tidak melakukan UPSERT master, dan tidak mengaktifkan FK transaksi. Storage kanonis kini tersedia melalui [BE-04](STORAGE_MASTER_BE04.md); review/apply data tetap mengikuti BE-05–BE-11.

## Alur

1. Discovery/profiling sumber dan konfirmasi tab sebagai MASTER melalui API BE-02.
2. Cari master melalui `GET /master-definitions?search=...`. Pencarian mencakup kode, nama, alias, termasuk nama/alias versi approved yang masih berlaku ketika draft diedit.
3. Jika membutuhkan definisi baru, jalankan preview kandidat. Pilih master lama jika sama; jika memang berbeda, tinjau kandidat dan catat alasan sebelum create.
4. Buat draft definisi, submit-review, lalu approve menggunakan akun berbeda. Approval menghasilkan `approved_version: 1`.
5. Simpan mapping tab ke versi master approved melalui PUT master-binding. Satu tab memiliki satu binding; beberapa tab/sumber dapat menunjuk master yang sama.
6. Reviewer memeriksa dry-run dan menyetujui binding. `metadata_ready: true` berarti binding/snapshot/versi sudah sesuai, tetapi `execution_ready` tetap false sampai runtime master tersedia.

Semua operasi memerlukan bearer token dan tenant scope. Hak baca metadata: PLATFORM_ADMIN, SOURCE_OWNER, DATA_STEWARD, TECHNICAL_APPROVER. Editor adalah tiga role pertama; approver adalah PLATFORM_ADMIN atau TECHNICAL_APPROVER. ANALYST/VIEWER tidak mendapat akses katalog metadata ini.

## Endpoint aktif

Semua path relatif terhadap `/api/v1`; semua respons menggunakan envelope proyek. Tabel lengkap juga tersedia di [API Reference](API_REFERENCE.md).

| Method | Path | Body / query | Hak |
|---|---|---|---|
| GET | `/master-definitions` | search, offset default 0, limit default 50 (maksimal 100) | Baca metadata |
| POST | `/master-definitions/preview` | MasterDefinitionCreate; optional query against=UUID untuk mengabaikan master yang sedang diedit | Editor |
| POST | `/master-definitions` | MasterDefinitionCreate | Editor |
| GET | `/master-definitions/{master_id}` | UUID master | Baca metadata |
| PATCH | `/master-definitions/{master_id}` | MasterDefinitionPatch | Editor |
| POST | `/master-definitions/{master_id}/submit-review` | MasterRevisionRequest | Editor |
| POST | `/master-definitions/{master_id}/approve` | MasterRevisionRequest | Approver |
| POST | `/master-definitions/{master_id}/reject` | MasterRevisionRequest | Approver |
| POST | `/master-definitions/{master_id}/deactivate` | MasterRevisionRequest | Approver |
| GET | `/source-sheets/{sheet_id}/master-binding` | UUID tab internal | Baca metadata |
| PUT | `/source-sheets/{sheet_id}/master-binding` | MasterBindingUpdate | Editor |
| POST | `/source-sheets/{sheet_id}/master-binding/approve` | MasterRevisionRequest | Approver |
| POST | `/source-sheets/{sheet_id}/master-binding/reject` | MasterRevisionRequest | Approver |

Create master menghasilkan HTTP 201; operasi lain pada tabel menghasilkan HTTP 200. Tidak ada job pada operasi metadata ini. GET list mengembalikan array record dengan meta.offset/limit; panjang array bukan total seluruh registry. Pencarian kandidat memakai kemiripan deterministik nama/alias, bukan panggilan AI atau keputusan otomatis bahwa dua master sama.

## Payload definisi master

Contoh MasterDefinitionCreate:

```json
{
  "code":"products",
  "definition":{
    "name":"Produk",
    "description":"Identitas produk baku",
    "aliases":["Barang","Product"],
    "fields":[
      {"name":"product_code","type":"text","nullable":false,"pii_classification":"NONE"},
      {"name":"product_name","type":"text","nullable":false,"pii_classification":"NONE"}
    ],
    "business_key":["product_code"],
    "label_field":"product_name",
    "policy":{"new_record_policy":"PROPOSE_INSERT","source_conflict_policy":"REQUIRE_REVIEW"}
  },
  "reviewed_candidate_ids":[],
  "duplicate_review_reason":""
}
```

Field `code` unik per tenant dan immutable melalui PATCH. Nama field bertipe mengikuti enum PostgreSQL yang sudah didukung ETL. Business key wajib unik dalam definisi, merujuk field yang ada, dan tidak nullable. Label wajib merujuk field yang ada. Kolom masa berlaku pada policy harus ada, bertipe tanggal/waktu sama, dan mempunyai batas berbeda; validasi interval record baru diimplementasikan pada runtime lanjutan.

Policy mengikuti [BE-01](KEBIJAKAN_DATA_BE01.md). AUTHORITATIVE_SOURCE wajib mempunyai ID tab MASTER yang dikonfirmasi dalam tenant yang sama. Pemeriksaan ini dilakukan ulang saat submit/approve. Otoritas tidak menggantikan approval binding atau review data. `UPDATE_ONLY` tersedia sebagai kebijakan eksplisit yang lebih ketat; keputusan awal proyek tetap PROPOSE_INSERT dengan approval.

Contoh `data` respons preview:

```json
{
  "creates_master":false,
  "candidates":[{
    "id":"11111111-1111-4111-8111-111111111111",
    "code":"products","name":"Produk","status":"APPROVED","is_active":true,
    "score":1.0,"reason":"Nama/alias mirip; periksa apakah master yang sama."
  }]
}
```

Preview tidak menyimpan apa pun. Create dan PATCH menghitung ulang kandidat. Jika ada kandidat, seluruh ID kandidat harus tercantum pada `reviewed_candidate_ids` dengan `duplicate_review_reason` nonkosong untuk melanjutkan sebagai definisi berbeda. Master draft/nonaktif juga masuk pencarian agar tidak dibuat ulang diam-diam. Jika ingin memakai master lama, lakukan binding ke ID tersebut, bukan create ulang.

Untuk mengedit definisi, gunakan preview `?against={master_id}` dengan bentuk body create dan kode master yang sedang diedit; endpoint memeriksa akses ke ID tersebut. PATCH menggunakan `revision_no`, objek `definition` lengkap, dan field review kandidat yang sama, tanpa `code`. Candidate review tidak mengabaikan unique constraint kode dan tidak memberi izin merge record. Create/PATCH diserialisasi per tenant untuk mencegah dua request bersamaan melewati deteksi nama serupa.

## Lifecycle dan versi

Record master berisi `id`, `tenant_id`, `code`, `name`, `aliases`, `definition_json`, `approved_definition_json`, `revision_no`, `approved_version`, `status`, `is_active`, `created_by` (editor terakhir), `submitted_by`, `approved_by/at`, dan `created_at`.

`definition_json` merupakan working draft. `approved_definition_json` merupakan snapshot terakhir yang disetujui. Saat master approved diedit, status kembali DRAFT dan revision naik, tetapi snapshot/version approved sebelumnya tetap tersedia untuk binding yang sudah sesuai. Nama/alias pada record atas mengikuti draft; gunakan snapshot approved untuk membaca definisi yang telah disetujui.

```text
Create: DRAFT (revision 1, approved_version 0)
Submit: NEEDS_REVIEW (revision 2)
Approve: APPROVED (revision 3, approved_version 1)
PATCH: DRAFT (revision 4, approved_version tetap 1)
Submit + approve: APPROVED (revision 6, approved_version 2)
```

Payload submit/approve/reject/deactivate:

```json
{"revision_no":2,"comment":"Key, tipe, label, policy, dan kandidat master sudah diperiksa."}
```

Gunakan revision terbaru dari respons, bukan angka contoh. Default approver harus berbeda dari editor dan pengaju definisi. Reject menghasilkan REJECTED; editor dapat memperbaiki atau mengajukan ulang. Deactivate menandai INACTIVE/is_active=false sehingga binding tidak ready. Untuk mengaktifkan kembali: PATCH draft, submit, dan approve. Approval versi baru membuat binding ke versi lama stale; tidak ada upgrade binding otomatis atau migrasi tabel data pada BE-03.

Audit menyimpan perubahan draft, keputusan kandidat, komentar, serta snapshot sebelum/sesudah approval versi. Belum ada endpoint restore versi master; audit bukan pengganti tabel histori record master BE-04 dan seterusnya.

## Payload binding

```json
{
  "revision_no":0,
  "master_definition_id":"11111111-1111-4111-8111-111111111111",
  "master_version":1,
  "classification_revision":2,
  "columns":[
    {"source_column":"Kode Produk","target_column":"product_code","target_type":"text","nullable":false,"is_business_key":true,"transformation_codes":["trim"]},
    {"source_column":"Nama Produk","target_column":"product_name","target_type":"text","nullable":false,"transformation_codes":["trim","normalize_whitespace"]}
  ]
}
```

Revision 0 berarti membuat binding pertama. Gunakan revision binding yang dikembalikan untuk menyimpan ulang; setiap save menghasilkan DRAFT dan mengosongkan approval binding. Revisi binding, revisi klasifikasi, revisi master, dan approved_version master adalah angka yang berbeda.

Mapping memakai ColumnMapping yang sama dengan ETL; tipe, nullable, PII, dan business key harus sama dengan field master. Primary key record master dikelola server, sehingga `is_primary_key: true` tidak diterima pada binding. Key, label, dan seluruh field nonnullable harus dipetakan; field nullable lain boleh tidak dipetakan. Source header harus ada pada profil tab. Transformasi bertipe allowlist digunakan dalam dry-run atas snapshot tersimpan, termasuk pemeriksaan key duplikat.

Contoh ringkas respons save dalam `data`:

```json
{
  "binding":{
    "id":"22222222-2222-4222-8222-222222222222",
    "source_sheet_id":"33333333-3333-4333-8333-333333333333",
    "master_definition_id":"11111111-1111-4111-8111-111111111111",
    "master_version":1,"classification_revision":2,"revision_no":1,"status":"DRAFT",
    "columns_json":[],"fingerprint":"HASH_SCHEMA","snapshot_hash":"HASH_DATA"
  },
  "validation":{"valid":true,"sample_rows_valid":10,"sample_rows_invalid":0},
  "execution_ready":false
}
```

Contoh disingkat; respons nyata memuat semua kolom mapping, metadata actor/time, dan hasil validasi lengkap. `validation.valid:false` masih dapat disimpan sebagai draft; approval binding ditolak sampai error selesai. Dry-run tidak membuat tabel atau memuat record master.

Binding tidak mempunyai endpoint submit terpisah: save menghasilkan draft yang dapat direview approver. Approve/reject menggunakan MasterRevisionRequest. Approve memeriksa ulang versi master, klasifikasi, fingerprint, snapshot hash, dan DQ. Snapshot berubah memerlukan save/review ulang, walaupun header sama.

GET master-binding mengembalikan `binding`, `validation`, `metadata_ready`, `execution_ready:false`, dan `blocking_reason`. Jika belum ada binding, binding=null, metadata_ready=false, blocker=MASTER_BINDING_REQUIRED. Binding approved yang masih sesuai mempunyai metadata_ready=true dengan blocker=MASTER_RUNTIME_PENDING. GET klasifikasi MASTER juga menambahkan ringkasan `master_binding`; runtime tetap tertahan.

## Error utama

| HTTP | Kode | Penanganan |
|---|---|---|
| 409 | MASTER_DUPLICATE_REVIEW_REQUIRED | Preview kandidat; pilih master lama atau jelaskan perbedaan |
| 409 | MASTER_CANDIDATES_CHANGED | Preview ulang; jangan kirim ID kandidat lama/asing |
| 409 | RESOURCE_CONFLICT | Kode master atau binding tab duplikat |
| 409 | MASTER_REVISION_CONFLICT / MASTER_STATE_CONFLICT | Muat ulang revision/status master |
| 409 | MASTER_AUTHORITY_INVALID | Periksa klasifikasi tab sumber otoritatif |
| 409 | MASTER_VERSION_UNAVAILABLE | Pilih versi approved aktif terbaru; tinjau binding ulang |
| 409 | CLASSIFICATION_CONFLICT | Tab harus MASTER dengan revision klasifikasi yang sesuai |
| 409 | MASTER_BINDING_CONFLICT / MASTER_BINDING_STALE | Muat ulang binding dan snapshot; save ulang dengan revision terbaru |
| 422 | MASTER_MAPPING_INVALID / MASTER_BINDING_INVALID | Perbaiki mapping atau error data dry-run |
| 403 | SEPARATE_APPROVER_REQUIRED | Gunakan akun approver berbeda |
| 409 | MASTER_RUNTIME_PENDING | Metadata dan storage tersedia; tunggu review/apply import master |

Hak role salah tetap 403 dan referensi lintas tenant/tidak ada 404. Error header/fingerprint/profiling juga dapat memakai kode ETL yang sudah tersedia pada API Reference. GET detail binding dapat memberi valid=false dan blocker pada respons 200 untuk membantu perbaikan, tanpa mengklaim binding siap.

## Migrasi, kompatibilitas, dan rollout

Migrasi `d83a5f12c906` menambah `platform.master_definition` dan `platform.master_source_binding`, unique constraint kode per tenant/binding per tab, serta FK komposit tenant ke master, tab, dan actor. Tidak ada perubahan target `trusted`.

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

Migrasi diterapkan hanya pada database test selama pengembangan; database aplikasi belum dimigrasikan. Downgrade menghapus metadata registry/binding baru, sehingga memerlukan backup metadata dan versi backend yang sesuai. Schema database test sudah diperiksa terhadap model melalui Alembic.

Perubahan terhadap BE-02: blocker eksekusi MASTER kini `MASTER_RUNTIME_PENDING`; `MASTER_BINDING_REQUIRED` tetap dipakai pada GET binding yang belum ada. NON_MASTER dan gate klasifikasi lainnya tetap berlaku. Frontend katalog/binding belum dibuat; endpoint dapat dipakai melalui Swagger/API.

Hasil verifikasi: **83 tes backend lulus**, Ruff lulus, Alembic tidak menemukan perbedaan model/schema database test, dan exporter memverifikasi **104 operasi API**. Tes mencakup lifecycle terpisah, pencarian/duplikat, concurrency create, dua tab ke satu master, binding stale saat snapshot/versi berubah, master nonaktif, mismatch mapping, dan FK actor lintas tenant. Provider Google/OpenAI pada pengujian menggunakan mock; ini bukan verifikasi integrasi akun nyata.
