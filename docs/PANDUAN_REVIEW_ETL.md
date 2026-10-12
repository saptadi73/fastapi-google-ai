# Implementasi review konfigurasi ETL

Wizard Vue dan round-trip XLSX tersedia untuk parameter yang sudah didukung runtime ETL. AI menghasilkan draft; pengguna menyesuaikan konfigurasi, menjawab pertanyaan, memvalidasi, lalu mengajukan review. Approver berbeda menyetujui konfigurasi. Jika admin mengaktifkan aturan persetujuan tayang pada sumber, pemeriksa IT dan satu approver dari setiap unit terkait juga harus menyetujui revisi yang sama sebelum deployment. Master memakai [registry/binding](REGISTRY_MASTER_BE03.md), [storage](STORAGE_MASTER_BE04.md), dan [review/apply batch](MASTER_IMPORT_POLICY_BE07.md). [Referensi/FK master](MASTER_REFERENCES_BE08.md) serta [taxonomy](FRONTEND_BE13.md) tersedia melalui alur tersendiri. Rekomendasi AI bukan koreksi otomatis seluruh sel; keputusan ambigu tetap memerlukan review.

## Menjalankan

1. Jalankan migrasi pada database aplikasi yang dituju setelah meninjau konfigurasi koneksinya. Migrasi `b8r1e4o7v0x3` memerlukan PostgreSQL >=16 untuk role terpisah; admin memberi role runtime TO DDL dengan INHERIT FALSE, SET TRUE. Gunakan ALEMBIC_DATABASE_URL untuk koneksi admin tanpa mengganti DATABASE_URL operasional. `9c32a61d740e` menambahkan `review_state`; `a7q0d3n6u9w2` memberi role `DATABASE_DDL_URL` hanya USAGE schema audit dan INSERT event_log agar audit migrasi tersimpan dalam transaksi DDL. Role penerap Alembic harus berhak memberi grant tersebut. Izin terbatas ini tetap dipertahankan saat downgrade untuk retry/audit historis.

   ```powershell
   .\venv\Scripts\python.exe -m alembic upgrade head
   ```

2. Jalankan backend, Redis, dan worker sesuai [panduan implementasi](IMPLEMENTASI.md). Profiling, rekomendasi AI, deployment, dan sync berjalan sebagai job. Status QUEUED terus-menerus berarti worker perlu diperiksa. Validasi draft, export, dan import-preview dijalankan melalui API.
3. Di `C:\projek\vue-googlesheet-ai`, gunakan `npm run dev`. Pastikan `VITE_API_ORIGIN`, `VITE_API_BASE_PATH`, dan CORS backend sesuai. Buka `/workspace` atau tombol **Buka workspace ETL** pada halaman utama.
4. Login dengan tenant dan akun aplikasi. Token berada di memori; reload penuh memerlukan login ulang. Jika sesi kedaluwarsa, keluar/ganti akun lalu login kembali.
5. Pilih sumber/tab, atau hubungkan Google Sheet baru yang sudah dibagikan ke service account. Konfirmasi klasifikasi per tab di Workspace ETL. Jalankan rekomendasi AI setelah profiling selesai. Buka draft yang dihasilkan; lihat [kontrak dan rollout BE-02](KLASIFIKASI_TAB_BE02.md).
6. Periksa identitas, mapping kolom, cleansing berurutan, kualitas data, strategi pemuatan, dimensi, metrik, dan role akses. Simpan perubahan, periksa dry-run, isi checklist seluruh bagian/kolom, lalu **Ajukan review**.
7. Gunakan approver konfigurasi sumber yang berbeda dari pembuat konfigurasi/editor metadata. Baca ringkasan metadata sumber, pilih policy SOURCE APPROVED yang cocok, lalu setujui konfigurasi, metadata PENDING dan aktivasi akses dalam satu transaksi. Jika metadata/policy/revisi tidak valid, tidak ada approval sebagian. Jalur admin review metadata/aktivasi terpisah tetap tersedia untuk sumber aktif tanpa revisi; tidak perlu diulang setelah approval gabungan berhasil.
8. Jika aturan siap tayang aktif, akun IT dan approver bernama dari setiap unit terkait membuka `/release-approvals`. IT menyelesaikan checklist skema/mapping, kualitas data, dan keamanan/akses. Setiap kelompok memberi keputusan pada revisi konfigurasi, snapshot review, dan revisi aturan yang sama. Status kelompok tampil pada review konfigurasi; penolakan memerlukan versi baru atau revisi aturan yang diaudit. Aturan rilis dikonfigurasi admin di `/admin`.
9. Setelah status siap tayang, **Deploy konfigurasi**, tunggu job SUCCEEDED, lalu jalankan **Sync manual** dengan akun editor. NON_MASTER ACTIVE memakai approval konfigurasi terpisah serta akses/rilis yang masih berlaku: validasi teknis, AI dan preview konflik lolos berarti langsung dimuat tanpa approval batch tambahan. Master, FULL_REFRESH, jadwal dan batch biasa tetap memakai review/preview/approval/Apply. Approval dan deployment sendiri tidak memuat data. Rollback tetap diperiksa terhadap aturan rilis saat ini.

Konfigurasi APPROVED/ACTIVE lama yang tidak memiliki bukti review tetap tidak dapat diedit. Bila perlu deployment ulang, clone menjadi draft, validasi, submit, dan approve. Runtime sync konfigurasi yang sudah ACTIVE tidak memerlukan checklist ulang untuk setiap sync. Rollback konfigurasi memeriksa snapshot yang disetujui; perubahan data dapat mengharuskan draft baru. Rollback bukan pemulihan data historis.

## Perubahan sumber, kolom, dan periode waktu

Workspace ETL mengedit konfigurasi pembacaan, mapping, transformasi, kualitas, dan semantic;
ia tidak menulis kolom atau nilai ke Google Sheets. Gunakan sumber/tab yang sudah terdaftar,
bukan registrasi ulang, untuk memperbarui dataset.

| Perubahan | Alur |
|---|---|
| Kolom sumber baru atau header diubah/dihapus | Ubah Google Sheets, profiling ulang, lalu buat draft dari profile terbaru dan sesuaikan mapping |
| Cleansing, DQ, label bisnis, dimensi/metrik untuk kolom yang sudah tersedia | Edit draft; jika versi sudah APPROVED/ACTIVE/REJECTED, clone dahulu; validasi dan review snapshot terkini |
| Nilai/baris berubah tanpa perubahan struktur | Sync manual NON_MASTER aktif membaca/profiling snapshot terbaru dan langsung memuat data valid; master/batch biasa tetap review import |
| Kolom/type/nullability/business key target non-master berubah pada tabel yang sudah ada | Migrasi manual yang direview sebelum deployment; approval konfigurasi tidak menjalankan ALTER TABLE otomatis |

Urutan untuk kolom baru:

1. Tambahkan header dan data di Google Sheets. Pastikan kolom berada dalam range baca.
   Range/header/`enabled` tab dengan konfigurasi aktif tidak dapat diubah langsung
   (`CONFIGURATION_CONFLICT`); perubahan range aktif memerlukan penanganan terencana.
2. Jalankan profiling pada sumber yang sama, tunggu job selesai, dan pilih profile tab terbaru.
3. Clone versi lama bila semua header mapping lama masih tersedia. Jika clone ditolak karena
   header lama sudah hilang/berubah, buat draft manual atau AI dari profile terbaru.
4. Tambah/perbaiki mapping melalui form. `source_column` harus cocok persis dengan header
   profile. Draft lama dengan fingerprint berbeda tidak dapat dipakai tanpa versi baru.
5. Validate/dry-run, selesaikan pertanyaan, submit-review, approve, dan selesaikan
   persetujuan tayang bila diaktifkan. Jangan mengubah Sheet lagi di antara review dan deploy;
   deploy membaca ulang sumber dan menolak snapshot yang sudah berubah.
6. Pada langkah **Validasi & persetujuan**, periksa **Preview perubahan schema**:
   operasi, jumlah record lama, contoh tanggal, dan blocker. Centang konfirmasi schema
   sebelum submit bila target/view berubah. Approval mengikat fingerprint schema dan data;
   worker menjalankan perubahan aman saat deploy, bukan saat dry-run atau approval.
7. Deploy, tunggu sukses, kemudian Sync manual untuk NON_MASTER yang memenuhi syarat; master/batch biasa tetap review import sebelum Apply.

### Draft manual APPEND dan key

Template manual menandai kandidat business key dari header seperti ID/kode/nomor
yang tidak kosong pada sampel. Periksa keunikan dan arti key; kandidat bukan bukti
bahwa semua data unik. Key pilihan pengguna tetap dipertahankan.

APPEND tanpa business/primary key memakai `SKIP_IDENTICAL` secara default.
APPEND dengan key tidak mengirim `append_duplicate_policy`, karena policy tersebut
hanya berlaku tanpa key. UPSERT dan FULL_REFRESH juga tidak memakai policy ini.
Pesan `append_duplicate_policy requires APPEND without business/primary keys`
menandakan kombinasi parameter tidak valid, bukan kegagalan policy akses sumber.
Jangan menghapus key yang benar hanya untuk melewati pesan tersebut.

### Temuan yang menghentikan pemuatan

`NEEDS_INPUT` tampil **Menunggu tindakan**, bukan worker masih berjalan. Tekan **Lihat
detail** berikon mata pada tracking/hasil ETL/hasil sync/audit trail untuk melihat
kode, alasan, nomor baris asli Sheet pada snapshot dan kolom. Audit menyimpan aktor,
waktu dan maksimal 20 lokasi tanpa nilai mentah; daftar pertanyaan dapat dimuat bertahap.
Temuan AI bukan kepastian data salah. Verifikasi dengan pemilik data, koreksi mapping/PII
atau sumber jika diperlukan. `KEEP_ORIGINAL` hanya untuk AI yang telah diverifikasi sah,
dengan alasan wajib; bukan bypass error teknis. Setelah batch sync langsung siap tanpa
blocker, Sync manual kembali dapat melanjutkan pemuatan. Batch biasa tetap approval/Apply.

### Mengganti label periode text dengan tanggal

`w1`, `w2`, `january`, atau `february` bukan tanggal lengkap. Tentukan tahun dan arti minggu
(minggu ISO, minggu dalam bulan, atau kalender perusahaan) bersama pemilik data; jangan
menebak tanggal atau memakai tanggal hari ini untuk menutupi informasi yang hilang.

- Transaksi/kejadian: isi tanggal aktual kejadian, misalnya `tanggal_transaksi`.
- Rekap mingguan/bulanan: isi `periode_mulai` dan `periode_selesai` sesuai grain dan
  kalender yang disepakati; simpan label periode lama untuk jejak sumber.
- Contoh fiktif rekap Januari 2026: `2026-01-01` sampai `2026-01-31`. Ini batas
  periode rekap, bukan tanggal transaksi setiap record.

Gunakan tanggal lengkap tidak ambigu, disarankan tampilan `yyyy-mm-dd`. Tanggal native
Google Sheets maupun text tanggal lengkap yang cocok dengan parser dapat digunakan.
Mapping target memakai `date`; gunakan `parse_date_id` dengan `date_format` yang sesuai
bila diperlukan dan buktikan hasilnya pada dry-run. Jangan menganggap label bulan/minggu
dapat diubah menjadi tanggal melalui perubahan `target_type` saja.

Tambahkan kolom tanggal sebagai dimensi semantic dan tentukan arti filter waktu.
Default periode metrik saat ini memakai dimensi tanggal/waktu dan jumlah hari, bukan
konversi otomatis nama bulan. Filter rentang tanggal tersedia; pemilihan tanggal acuan
dan analisis overlap periode tetap harus ditentukan eksplisit, bukan fitur otomatis.
Penambahan kolom target tanggal pada tabel non-master yang ada tetap memerlukan migrasi.

Nama view semantic mengikuti ID tab, bukan tabel. Preview juga menampilkan perubahan
proyeksi atau perpindahan target view; mengganti tabel bukan jalan pintas menghindari review.
Worker mendukung kolom nullable baru (record lama null), perubahan tipe pada tabel kosong,
serta `bigint` serial Sheets menjadi `date` pada tabel berisi data bila mapping memakai
`parse_date_id`, `date_input_format=GOOGLE_SHEETS_SERIAL` dan seluruh nilai valid. Hash record diperbarui agar APPEND tetap mengenali
record identik. View dibuat ulang hanya tanpa dependency yang menghalangi, menjaga ACL dan
komentar, tanpa CASCADE atau menghapus record. DDL, view, konversi, hash, aktivasi konfigurasi, audit sukses dan status job SUCCEEDED berada dalam satu transaksi. Kegagalan sebelum commit mempertahankan schema/data serta konfigurasi aktif sebelumnya. Audit kegagalan dan alasan UI dicatat setelah rollback; retry memeriksa fingerprint review kembali. Perubahan di luar aplikasi, termasuk target yang sudah cocok atau
perubahan data tanpa operasi DDL, tetap memerlukan review ulang.
Rollback versi yang pernah aktif boleh memakai tabel yang telah dimuat bila tidak
memerlukan operasi schema/view; pemeriksaan snapshot sumber dan gate rilis tetap berlaku.
Rollback yang mengubah schema tidak mendapat pengecualian fingerprint ini.

Rename/drop kolom fisik, perubahan key, tipe lain pada tabel berisi data, kolom wajib baru
pada tabel berisi data, dan dependency/owner/grant tidak aman tetap diblokir.
`SCHEMA_REVIEW_REQUIRED`: clone/review versi lama yang belum punya bukti schema.
`SCHEMA_MIGRATION_STALE`: schema/data berubah sejak review; muat preview baru pada draft
dan ajukan ulang. `SCHEMA_MIGRATION_BLOCKED`: selesaikan blocker, bukan deploy berulang.
Migrasi aplikasi bukan untuk schema master atau backfill otomatis kolom baru.
Cocokkan konfigurasi APPROVED dengan payload job DEPLOY, bukan URL draft lama.

### Pengecualian untuk schema master

Master tidak memakai konfigurasi ETL biasa. Perbarui definisi master dan minta approval.
Field baru nullable didukung melalui deploy-storage ulang; record lama bernilai null.
Perbarui/review binding sesuai versi approved dan profile sumber terbaru, lalu gunakan
batch import. Field wajib baru, perubahan key/type/nullability, rename, atau penghapusan
memerlukan migrasi khusus. Lihat [storage master](STORAGE_MASTER_BE04.md#perubahan-schema-dan-record).

## Kontrak API review

Semua path relatif terhadap `/api/v1`. Respons JSON dibungkus `{status, data, meta, errors}` sebagaimana [API Reference](API_REFERENCE.md). Editor adalah PLATFORM_ADMIN, DATA_STEWARD, atau SOURCE_OWNER. Pembaca konfigurasi juga mencakup TECHNICAL_APPROVER.

`GET /configurations/{id}/review` mengembalikan:

```json
{
  "configuration": {"id":"UUID", "revision_no":1, "status":"AI_DRAFT", "configuration_json":{}, "review_state":{}},
  "source": {"id":"UUID", "name":"Penjualan"},
  "sheet": {"id":"UUID", "sheet_name":"Sales"},
  "profile": {"columns":[]},
  "validation": {
    "valid":true,
    "snapshot_id":"UUID",
    "snapshot_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "sample_rows_valid":3,
    "sample_rows_invalid":0,
    "row_previews":[{"source_row":2,"before":{"ID":"001"},"after":{"transaction_id":"001"}}],
    "issues":[], "warnings":[], "unresolved_questions":[], "deployment_plan":{}
  },
  "capabilities": {
    "review_sections":["identity","columns","cleansing","quality","load","semantic"],
    "editable_template_tabs":[], "unsupported":[], "max_workbook_bytes":2000000, "preview_expiry_minutes":15
  }
}
```

Contoh record/kolom/plan/capabilities disingkat; struktur konfigurasi lengkap ada di [PAYLOADS.json](api/PAYLOADS.json). Jika dry-run melempar error domain, review tetap mengembalikan form dengan `validation: {valid:false, errors:[{code,message}]}` agar pengguna dapat memperbaikinya. Endpoint `/validate` sendiri tetap dapat mengembalikan HTTP 422/409. Preview menampilkan maksimal 10 baris valid dan 50 baris bermasalah, tanpa nilai mentah baris bermasalah. Nilai MEDIUM/HIGH atau kolom dengan indikasi PII dari profil disamarkan pada before/after. Validasi memeriksa seluruh snapshot tersimpan.

`PATCH /configurations/{id}` menerima objek konfigurasi lengkap, bukan patch per field:

```json
{
  "revision_no":1,
  "configuration":{"...":"Gunakan objek ETLConfiguration lengkap"},
  "question_answers":{"Apakah ID unik?":"Ya, ID adalah nomor transaksi unik."}
}
```

Setiap pertanyaan yang dihapus dari `unresolved_questions` wajib mempunyai jawaban nonkosong maksimal 2.000 karakter. Key jawaban adalah teks pertanyaan persis, bukan ID baru. Sesuaikan parameter bisnis pada konfigurasi; jawaban teks tidak otomatis mengubah mapping. Jawaban disimpan di `review_state.answers` bersama user_id dan waktu. PATCH menaikkan revision dan membatalkan submission sebelumnya.

`POST /configurations/{id}/submit-review` kini **wajib mempunyai body**:

```json
{
  "revision_no":2,
  "snapshot_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "reviewed_columns":["transaction_id","transaction_date","branch_name","net_amount"],
  "reviewed_sections":["identity","columns","cleansing","quality","load","semantic"]
}
```

Gunakan hash dari dry-run terbaru dan nama target seluruh kolom konfigurasi. Server memvalidasi ulang, memeriksa revisi/hash/checklist, menaikkan revision, serta menyimpan submitted_by/at, submitted_revision, snapshot_id/hash, dan checklist di `review_state`. Respons adalah Configuration terbaru. Approve memakai revision dari respons tersebut dan ditolak jika submission tidak tersedia atau snapshot berubah. Kontrol ini memastikan keterkaitan review; checklist tidak membuktikan kebenaran keputusan bisnis pengguna.

## Excel: export, preview, apply

Identitas dataset dapat diisi dari **nama file Google Sheet + nama tab**. Draft
manual mengisi saran awal; review draft lama menyediakan tombol **Gunakan nama
file dan tab**, tanpa menimpa nama/kode tersimpan secara otomatis. Profiling baru
menangkap nama file asli; profil lama memakai nama sumber terdaftar dengan
keterangan fallback dan dapat diprofil ulang. Nama bisnis mempertahankan tanda
baca yang valid (maksimal 200 karakter); karakter kontrol menjadi spasi. Kode
produk data memakai huruf ASCII/angka/underscore, diawali huruf, maksimal 63
karakter; karakter lain menjadi underscore. Nama tab tetap disertakan saat
pemendekan saran kode. Saran tetap harus diperiksa; konflik kode produk antar-tab
ditolak saat deploy, bukan mengganti kode produk aktif diam-diam. Mengambil saran
tidak menyimpan draft, menyetujui konfigurasi, atau mengubah nama tabel tujuan.
Kode tidak valid yang diketik/ditempel dirapikan otomatis saat keluar dari field
atau menyimpan draft dengan pemberitahuan. Kode valid tetap dipertahankan.

1. Simpan draft lalu `POST /configurations/{id}/export` dengan `{"format":"XLSX"}`. Download artifact menggunakan endpoint download berautentikasi.
2. Workbook mempertahankan 14 tab template, menambah **14 Review** untuk identitas/jawaban dan tab metadata tersembunyi. Contoh data template dibersihkan. Sel kuning dapat diedit; sel referensi dan parameter yang belum didukung dilindungi. Jangan mengganti nama tab atau menambahkan kolom/tab. Penambahan/penghapusan mapping kolom dilakukan melalui form.
3. Isi input dengan nilai literal. Formula pada input, macro, dan external links ditolak. Gunakan enum API: misalnya `numeric`, bukan `numeric(18,2)`. Pengaturan type/null/key pada tab 02 menjadi sumber referensi tab 06.
4. Unggah file maksimal **2.000.000 byte** sebagai base64 JSON:

   ```json
   {"content_base64":"BASE64_DARI_BYTE_FILE_XLSX"}
   ```

   Kirim ke `POST /configurations/{id}/workbook-preview`. Ini hanya pemeriksaan, **tidak menyimpan konfigurasi dan tidak memberi approval**.

5. Respons sukses preview dalam `data`:

   ```json
   {
     "can_apply":true,
     "revision_no":2,
     "configuration":{"...":"Konfigurasi lengkap hasil parsing"},
     "question_answers":{},
     "diff":{"dataset_business_name":{"before":"Sales","after":"Penjualan"}},
     "validation":{"valid":true,"snapshot_hash":"HASH","...":"Hasil dry-run lengkap"},
     "errors":[],
     "preview_token":"TOKEN_BERTANDA_TANGAN"
   }
   ```

   Kesalahan sel mengembalikan `can_apply:false`, `configuration:null`, `preview_token:null`, dan `errors:[{location,message}]`, misalnya `04 Taxonomy Mapping!C5`. Identitas/revision workbook tidak cocok memakai HTTP 409. `can_apply:true` berarti konfigurasi dapat disimpan sebagai draft; approval tetap mensyaratkan `validation.valid:true`. Pertanyaan atau baris REJECT_ROW yang tersisa dapat diperbaiki setelah draft disimpan; STOP_BATCH/REQUIRE_REVIEW yang menghentikan validasi membuat preview tidak dapat diterapkan.

6. Setelah pengguna menerima diff, kirim **persis** kandidat dari preview ke `POST /configurations/{id}/workbook-apply`:

   ```json
   {
     "revision_no":2,
     "configuration":{"...":"Objek lengkap dari preview"},
     "question_answers":{},
     "preview_token":"TOKEN_DARI_PREVIEW"
   }
   ```

   Respons adalah Configuration draft revisi berikutnya. Token berlaku 15 menit, terikat pengguna/tenant, konfigurasi asal, revisi, snapshot, dan kandidat. Mengubah kandidat atau memakai ulang token setelah apply ditolak. Impor tidak menjalankan DDL, deploy, atau sync. Checklist harus diperiksa kembali setelah apply.

Identitas export berlaku 7 hari. Perubahan draft, isi snapshot, atau JWT secret membatalkan workbook/preview lama; unduh atau preview ulang. Ekspor dibatasi 100 kolom, 1.000 langkah cleansing, 100 aturan kualitas, 200 metrik, dan 100 pertanyaan. Sel di luar kapasitas, identitas referensi, dan parameter unsupported ditolak jika diubah; tidak diam-diam diabaikan. Array dimensi/role dan nilai aturan di Excel mengikuti JSON, sedangkan form menyediakan pilihan tanpa JSON.

Status `Tidak` pada cleansing atau `Nonaktif` pada aturan kualitas/metrik berarti menghapus aturan tersebut dari kandidat runtime. Baris nonaktif tidak disimpan sebagai arsip konfigurasi dan tidak muncul pada export berikutnya; periksa bagian diff sebelum menerima perubahan.

## Error yang perlu ditangani frontend

| Kode | HTTP | Tindakan |
|---|---|---|
| CONFIGURATION_CONFLICT / WORKBOOK_STALE | 409 | Muat ulang draft; unduh workbook terbaru |
| WORKBOOK_PREVIEW_STALE / WORKBOOK_TOKEN_INVALID | 409 | Preview ulang dengan akun dan draft yang sama |
| REVIEW_REQUIRED | 409 | Ajukan review revision terbaru |
| REVIEW_STALE | 409 | Profiling/validasi ulang; untuk approved, clone dan review draft baru |
| REVIEW_INCOMPLETE | 422 | Lengkapi checklist semua bagian dan kolom |
| QUESTION_ANSWER_REQUIRED / QUESTION_INVALID | 422 | Cocokkan pertanyaan dan isi jawaban |
| WORKBOOK_INVALID / WORKBOOK_STRUCTURE | 422 | Gunakan XLSX export aplikasi yang utuh |
| SEPARATE_APPROVER_REQUIRED | 403 | Gunakan approver berbeda |
| RELEASE_APPROVAL_REQUIRED | 409 | Periksa status IT dan setiap unit di Persetujuan tayang sebelum deploy/rollback |
| RELEASE_REJECTED | 409 | Buat versi konfigurasi baru atau minta admin meninjau aturan rilis |
| RELEASE_POLICY_STALE / RELEASE_CONFIGURATION_STALE | 409 | Muat ulang aturan/status dan gunakan revisi konfigurasi terbaru |

## Verifikasi pengembangan

Jumlah pengujian/operasi berikut adalah catatan fase awal, bukan jumlah suite/API terkini.

- Unit test workbook: round-trip konfigurasi, identitas/revisi, sel unsupported, formula input, jawaban pertanyaan.
- Integration test pada database `_test`: preview tanpa mutasi, apply bertoken, perubahan kandidat/replay ditolak, isolasi tenant/role, gate submission, dan perubahan data sebelum deployment.
- Regression suite ETL: approve/deploy, sync/idempotency, rollback, permission, query tetap diuji.
- Frontend: `npm run build` menjalankan TypeScript dan build Vite. OpenAI dan Google pada integration test memakai mock; konfigurasi/integrasi akun nyata tetap harus diuji pada lingkungan tujuan.
- Hasil verifikasi implementasi: 63 pengujian backend lulus. Smoke test Edge headless dengan API mock juga lulus untuk login, edit/simpan draft, checklist, submit, dan approval akun berbeda tanpa exception JavaScript. Pengujian browser ini tidak mengakses data aplikasi nyata.
- `scripts/export_api_reference.py --check` kini memeriksa 116 operasi setelah penambahan pertanyaan dan keputusan batch BE-06, serta seluruh contoh payload terhadap schema runtime.

Batch data persisten terpisah dari review konfigurasi tersedia di [BE-05](IMPORT_REVIEW_BE05.md). Saat NEEDS_INPUT karena temuan, frontend memuat dan menjawab pertanyaan dari [BE-06](IMPORT_QUESTIONS_BE06.md); koreksi hanya staging, tidak mengubah Google Sheet. NEEDS_INPUT tidak boleh diatasi dengan retry otomatis. Preview/approval/apply tersedia pada [BE-07](MASTER_IMPORT_POLICY_BE07.md), dan review AI terkontrol dijelaskan pada [BE-13](REVIEW_BE13.md).


Parameter runtime terbaru (DQ, precision, unit, timezone, currency) dan mapping XLSX untuk frontend: [Panduan frontend BE-12](FRONTEND_BE12.md).

### Review perubahan schema NON_MASTER

Langkah 7 menampilkan `deployment_plan.migration.comparison`: kolom lama/baru beserta tipe dan nullability, key sebelum/sesudah, target/proyeksi view dan dependency. Operasi, jumlah record lama, contoh konversi dan blocker tersedia sebelum submit/approval/deploy. Reviewer menyetujui schema dan mapping pada revisi serta fingerprint schema/data yang sama. Perubahan setelah review meminta review ulang (`SCHEMA_MIGRATION_STALE`).

Untuk `bigint menjadi date` pada tabel berisi data, pilih **Format nilai tanggal = Serial Google Sheets** (`date_input_format: "GOOGLE_SHEETS_SERIAL"`) bersama `parse_date_id`. Tipe bigint atau angka dalam rentang valid saja tidak membuktikan bahwa nilainya tanggal. Konfirmasi makna sumber melalui mapping; backend memeriksa seluruh nilai non-null dan menampilkan `validation.checked`, `convertible`, `invalid`, serta contoh. Nilai di luar rentang 1..2958465 menghentikan migrasi. Mode serial eksplisit menolak text, pecahan dan nilai non-finite; mode `TEXT` memakai pola strptime dan menolak angka. Default null mempertahankan parser konfigurasi lama, tetapi tidak mengizinkan migrasi berisiko tanpa deklarasi format. Workbook menyimpan pilihan ini di `02 Struktur Kolom`, kolom AD.

Worker mendukung kolom nullable baru dan perubahan tipe pada tabel kosong. View yang perlu dibuat ulang mempertahankan ACL/komentar; dependency yang tidak aman, rename/drop fisik, perubahan key dan backfill wajib diblokir. DDL, view, konversi, hash, aktivasi konfigurasi, audit sukses dan status job SUCCEEDED berada dalam satu transaksi. Kegagalan sebelum commit mempertahankan schema/data serta konfigurasi aktif sebelumnya. Audit kegagalan dan alasan UI dicatat setelah rollback; retry memeriksa fingerprint review kembali.

`DATABASE_RETRY_REQUIRED`: database sibuk/timeout/konflik; tunggu lalu retry. `DATABASE_PERMISSION_DENIED`: admin memeriksa role DDL, ownership dan izin SET ke role aplikasi. Catat ID job; jangan mengubah SQL atau menghapus data untuk melewati blocker. Migrasi platform saat rollout berbeda dari perubahan schema dataset melalui aplikasi.

Verifikasi 11 Oktober 2026: 497 pengujian backend tanpa integrasi (di luar workbook), 20 alur integrasi schema dan 12 tes PostgreSQL lulus. Round-trip workbook juga lulus. Frontend: 117 unit dan 15 browser test dengan API mock lulus; type-check/build statis berhasil. Export/check kontrak memeriksa 234 operasi. Tes rollback mencakup kegagalan aktivasi dan status job, dengan role runtime/DDL terpisah.


### Cleansing text otomatis dan bukti temuan AI

Kolom `text` dan `varchar` selalu mendapat `trim` otomatis pada nilai sumber sebelum transformasi tambahan, validasi DQ/key, pemeriksaan AI, dan pemuatan. `"  KAN  Jabung  "` menjadi `"KAN  Jabung"`: spasi di tengah, huruf, dan nol depan tetap dipertahankan. Nilai berisi spasi saja menjadi kosong/NULL; nullable mengizinkannya, kolom wajib tetap menghasilkan TYPE_OR_NULL_ERROR. Transformasi tambahan seperti normalize_whitespace, prefix/suffix, atau koreksi ejaan perlu aturan yang direview; trim dasar tidak perlu ditambahkan satu per satu. Nilai sumber di Sheet tidak ditulis ulang.

AI tidak boleh menganggap `[REDACTED]` sebagai data rusak atau menyimpulkan duplikat dari nilai yang disamarkan. Temuan duplikat memakai `issue_kind=EXACT_DUPLICATE` dan `related_source_row`; server membandingkan seluruh data asli di staging. Temuan pada nilai tersembunyi atau duplikat yang tidak terbukti dicatat sebagai temuan yang diabaikan pada checkpoint/audit tanpa membocorkan nilai. Masalah nyata pada kolom terbuka, dugaan PII, dan coverage tidak lengkap tetap menghentikan batch.

Sync manual pada konfigurasi NON_MASTER aktif yang telah disetujui dapat memeriksa ulang batch NEEDS_INPUT dengan blocker AI saja dan seluruh pertanyaan masih terbuka tanpa keputusan pengguna. Worker mengulang cleansing/validasi lalu review AI, mempertahankan identitas staging dan audit pertanyaan lama. Batch dengan keputusan, blocker teknis, konflik, atau gate akses/rilis belum selesai tidak dilompati. Muat ulang halaman tidak menjalankan sync.


### Tabel error response

Lihat [Error response: kemungkinan penyebab dan tindakan](ERROR_RESPONSES.md). Tabel mencakup error sumber, review/deploy schema, validasi/import, akses katalog serta layanan database/AI. Di aplikasi: **Bantuan > Tabel error response** atau **Panduan lengkap > Tabel error response**; gunakan pencarian kode. Alasan keputusan akses dan blocker batch dibedakan dari error HTTP.


### Format Google Sheet ideal untuk analitik dan action plan

Baca [Panduan lengkap format Google Sheet](PANDUAN_FORMAT_GOOGLE_SHEET.md): penamaan file/tab dan produk, header tabular, grain/key, master/taxonomy, tipe/satuan/presisi, waktu/periode wajib untuk data periodik, metrik, kualitas, provenance, action plan berbasis bukti dan contoh tabel. Di aplikasi buka **Bantuan > Format Google Sheet ideal** atau **Panduan lengkap > Format Google Sheet ideal**. Waktu kejadian/pengukuran, periode data dan waktu pengambilan dibedakan; tanggal sync bukan pengganti waktu bisnis. Definisi metrik dan tindakan tetap perlu review, bukan asumsi otomatis dari nama kolom.


### Istilah teknis untuk pengguna non teknis

[Tabel istilah teknis dalam bahasa sederhana](ISTILAH_TEKNIS.md) menjelaskan grain, business/primary key, master, taxonomy, mapping, tipe, nullable, dimensi/metrik, snapshot, ETL, periode, waktu pengambilan serta proses pemuatan dengan contoh bisnis. Buka **Bantuan > Istilah teknis dalam bahasa sederhana** atau **Panduan lengkap > Istilah teknis dalam bahasa sederhana**; cari istilah, arti atau contoh.


### Lima contoh Excel untuk analitik dan action plan

Lihat [Contoh data analitik](CONTOH_DATA_ANALITIK.md): keluhan pelanggan, sebaran marketing ATL/BTL, kepuasan berbasis produk, competitiveness harga/layanan dan plan/goal/KPI. File dapat diunduh dari **Bantuan > Contoh Excel untuk analitik dan action plan** atau **Panduan lengkap > Contoh Excel**. Data fiktif dilengkapi master, waktu/periode, kamus, rencana ETL, formula dan baseline tindakan; target/bobot/hipotesis tetap perlu verifikasi bisnis.


## Formula analitik dan aturan action plan

Lima contoh Excel memuat Formula_Analitik dan Aturan_Action_Plan. Kedua tab kontrol Dikecualikan dari ETL; produk data utamanya harus ACTIVE. Backend menerima impor melalui API analytics-rules/import-sheet, menyediakan preview, approval reviewer berbeda, evaluate berbasis metrik yang diizinkan dan REVOKE untuk menghentikan aturan. Hasil berupa usulan PROPOSED dengan bukti angka, periode dan versi; unit, sampel serta hipotesis diperiksa manusia. Workflow aturan saat ini melalui API, belum terhubung otomatis ke wizard ETL atau chat AI.

Lihat [panduan aturan dan formula](PANDUAN_ATURAN_ANALITIK.md) serta [lima template Excel](CONTOH_DATA_ANALITIK.md).
