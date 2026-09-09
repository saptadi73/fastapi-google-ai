# Hasil tinjauan BE-13 — 9 September 2026

**Keputusan: belum memenuhi acceptance BE-13; BE-14 belum dimulai.** Registry,
versioning, normalisasi runtime/worker, pertanyaan otomatis dan workbook sudah tersedia;
saran AI generatif masih terbuka. Untuk integrasi bertahap gunakan
[handoff frontend BE-13](FRONTEND_BE13.md) dan [contoh payload](api/BE13_FRONTEND_PAYLOADS.json). Pemeriksaan ini mencakup kode endpoint, service
import/ETL, schema konfigurasi, renderer/parser XLSX, dan pengujian HTTP/PostgreSQL.

## Celah yang diperbaiki pada tinjauan ini

| Temuan | Perbaikan |
|---|---|
| Term/alias bisa ditambahkan ke taxonomy approved tanpa perubahan dependency yang memadai | Penambahan term hanya pada taxonomy DRAFT aktif; perubahan dan approval memakai lock taxonomy. Approval ulang approved bersifat idempotent dan tidak menaikkan versi. |
| Binding bisa disimpan/diapprove dengan revision lama saat request bersamaan | Save diserialkan lewat lock sheet/taxonomy; approval memeriksa ulang binding terkunci dan versi taxonomy. Approve/reject menaikkan revision. Edit mencabut metadata approval. |
| Alias diperiksa dengan normalisasi berbeda; alias ambigu dianggap valid oleh preview | Normalisasi TRIM_CASEFOLD bersama pada resolver, validate-values, preview, dan final write. Code exact diutamakan; label/alias yang cocok ke beberapa term menjadi ambiguous. |
| Preview memakai taxonomy, tetapi apply/ETL legacy dapat melewati pemeriksaannya | Binding approved, status/version taxonomy, required, dan normalisasi harus cocok dengan konfigurasi. Nilai kategori diperiksa lagi sebelum write; optional hanya membolehkan kosong, bukan nilai asing. |
| Perubahan term/binding setelah preview tidak selalu membuat batch stale | Hash dependency mencakup taxonomy, binding, serta semua term/alias; diperiksa saat capture/is_current, approval, dan apply di bawah lock. |
| Pembuatan pertanyaan ambigu memakai field ORM yang tidak ada dan key terpotong 64 karakter | Field invalid dibuang; key SHA-256 mencakup taxonomy/version/row/target/value; candidates diserialisasi aman ke JSON. |
| Pertanyaan dapat diarahkan ke staging batch lain atau nilai/kolom yang tidak sesuai | Wajib staging row dan target; tenant, batch, mapping taxonomy, nilai staging, serta status NEEDS_INPUT/FAILED diperiksa. Batch approved tidak dapat ditambahi pertanyaan lewat endpoint ini. |
| SELECT_RECORD taxonomy menulis UUID term sebagai nilai kategori | Kandidat terpilih diverifikasi kembali dan kode term disimpan sebagai koreksi staging; raw dipertahankan, keputusan tetap diaudit. |

Pemisahan pembuat/reviewer mengikuti `require_separate_approver`. Metadata taxonomy
yang dipakai di sini sudah diperbaiki pada [repair registry](REGISTRY_SCHEMA_REPAIR.md).
Lanjutan BE-13 menambahkan migrasi `9b07c8d6e5fa` untuk snapshot versi taxonomy.
Migrasi hanya diterapkan pada database test; production belum diubah.

## Kontrak frontend yang perlu diikuti

- `columns[].taxonomy_id` memerlukan `taxonomy_version` dan tipe target text/varchar.
  Nilai required harus cocok dengan binding tab/kolom yang approved.
- Binding hanya menerima normalisasi `TRIM_CASEFOLD`; mode lain ditolak 422.
  Binding baru memakai revision 0. Gunakan revision dari response terbaru setelah
  save/approve/reject. Request bersamaan dengan revision yang sama hanya memiliki
  satu pemenang.
- Term/alias ditambahkan sebelum approval taxonomy. Penambahan setelah approval
  menghasilkan `TAXONOMY_IMMUTABLE` (409). Jangan menyiasatinya dengan approval ulang;
  gunakan draft versi berikutnya melalui `POST /taxonomies/{id}/versions`.
- `POST /taxonomies/{id}/ambiguity-question` membutuhkan `import_review_id`,
  `staging_row_id`, `target_column`, dan `value` yang cocok dengan staging. Opsional
  source_column harus cocok dengan mapping. State batch harus NEEDS_INPUT/FAILED.
- Pertanyaan yang sama diulang menghasilkan ID yang sama, sedangkan baris berbeda
  menghasilkan pertanyaan berbeda. Pertanyaan wajib menjadi blocker batch.
  Gunakan endpoint jawaban import existing untuk memilih `selected_candidate_id`.
  UUID adalah identitas pilihan; nilai yang disimpan di kolom kategori adalah kode term.
- Untuk optional taxonomy, null/kosong diperbolehkan; string yang tidak ditemukan
  tetap menghasilkan `TAXONOMY_VALUE_INVALID` (422). Alias ambigu menghasilkan
  `TAXONOMY_VALUE_AMBIGUOUS` (422) pada validasi langsung; worker membuat pertanyaan wajib
  dan tidak memilih kandidat otomatis.
- Perubahan dependency bisa menghasilkan `IMPORT_STALE_REVIEW` atau
  `TAXONOMY_VERSION_STALE` (409). Revalidate/perbarui binding dan batch yang sesuai;
  jangan menggunakan token approval lama untuk memaksa apply.
- `TaxonomyTermCreate.parent_id` divalidasi sebagai UUID, dengan pengecekan parent
  dari taxonomy dan tenant yang sama. Alias tetap bagian draft taxonomy, bukan alias
  global yang dibuat otomatis dari jawaban pengguna.

## Pekerjaan yang masih menghalangi acceptance

1. **Saran AI generatif.** recommend-terms masih memakai SequenceMatcher, bukan
   provider generatif. Kandidat otomatis worker berasal dari exact/alias taxonomy
   approved, bukan usulan AI. Integrasi provider beserta pengujian tetap terbuka.

## Lanjutan: worker dan rule in_taxonomy

Worker kini menormalisasi nilai exact/label/alias pada staging sebelum fase AI.
Nilai ambigu menjadi pertanyaan wajib `TAXONOMY_AMBIGUOUS` dengan kandidat term approved;
nilai tidak dikenal/kosong wajib menjadi `TAXONOMY_INVALID`. Kandidat dipilih dengan
SELECT_RECORD, sedangkan nilai invalid dapat dikoreksi dengan APPLY_CORRECTION atau
CORRECT_SOURCE. Koreksi diperiksa terhadap taxonomy approved dan disimpan sebagai kode.
Raw data tetap utuh. Pertanyaan berulang memakai key stabil; resume memakai checkpoint
serta koreksi existing, tanpa menggandakan pertanyaan. Jumlah pertanyaan terbuka tersimpan
kembali setelah jawaban. Error tipe/kolom yang belum menghasilkan output tetap mengikuti
alur pertanyaan DQ existing.

Rule `in_taxonomy` tersedia pada JSON dan tab 05 XLSX, dengan mapping taxonomy versi
approved pada kolom yang sama. Contoh:

```json
{"column":"branch_name","rule":"in_taxonomy","action_on_fail":"REQUIRE_REVIEW"}
```

`value` harus null; rule tidak menerima daftar kategori lain atau action WARN. Required
mengikuti `taxonomy_required` pada binding; optional null/kosong diperbolehkan, tetapi
nilai asing/ambigu tetap gagal. STOP_BATCH dan pelanggaran threshold menghentikan batch.
REJECT_ROW menghasilkan issue; REQUIRE_REVIEW menghentikan eksekusi langsung, sedangkan
worker mempertahankan hasil transformasi dan membuat pertanyaan agar bisa dijawab.
Compiler menolak rule tanpa konteks taxonomy yang dimuat server. Seluruh jalur runtime
memuat binding approved; validasi mapping di preview/apply tetap berlaku tanpa rule eksplisit.

Benturan business key setelah normalisasi worker menjadi blocker TAXONOMY_KEY_COLLISION;
perbaiki sumber dan buat batch baru. Batch dengan runtime taxonomy sebelumnya menjadi stale.

## Lanjutan: versi dan XLSX

- `POST /taxonomies/{id}/versions` dengan `base_version` membuat satu draft berikutnya;
  retry mengembalikan draft yang sama. GET koleksi versi mendukung offset/limit.
- PUT `/taxonomies/versions/{id}` memakai `revision_no` dan seluruh daftar `terms`.
  UUID/kode term lama tidak dapat diganti. Label/alias/hierarki/keaktifan dapat diubah;
  term baru memakai UUID baru. Parent harus ada dalam daftar, tanpa siklus, dan term
  aktif tidak boleh memiliki ancestor nonaktif.
- POST `/taxonomies/versions/{id}/approve` mempublikasikan satu transaksi. Reviewer
  harus berbeda dari editor terakhir bila kebijakan separate approver aktif. Term yang
  dihilangkan menjadi nonaktif di registry. Snapshot lama tetap utuh; versi terbit
  tidak dapat diedit. Binding versi lama menjadi stale, perlu save/approve versi terbaru.
- Migrasi mengarsipkan hanya versi approved yang masih tersedia, bukan merekonstruksi
  sejarah yang tidak tersimpan. Downgrade menghapus tabel snapshot beserta riwayatnya,
  tetapi tidak mengubah registry aktif. Backup snapshot sebelum downgrade.
- Tab `04 Taxonomy Mapping` kolom U/V/W mengedit UUID taxonomy, versi, wajib Ya/Tidak.
  Kolom sumber dan normalisasi `TRIM_CASEFOLD` tetap signed. Parser menolak UUID tidak
  valid, formula, perubahan referensi dan penambahan baris. Workbook lama tanpa marker
  format mempertahankan mapping JSON lama. Edit workbook hanya mengubah referensi
  konfigurasi; binding registry harus disimpan/disetujui melalui endpoint binding.
- Normalisasi menyimpan koreksi staging tanpa mengubah raw. Business key berbeda yang
  bertabrakan setelah normalisasi ditolak `TAXONOMY_KEY_COLLISION`. Batch taxonomy
  sebelum perubahan runtime ini menjadi stale dan memerlukan validasi ulang.

BE-14 tetap menunggu acceptance ini. Tinjauan tidak mengubah kondisi tersebut hanya
karena regresi yang ada lulus.

## Pengujian

Tes `test_taxonomy_workflow.py` mencakup immutable approval, ambiguity/normalisasi,
idempotency pertanyaan antarbaris, staging lintas batch/tenant, pilihan kode canonical,
dependency term/taxonomy/binding berubah sesudah approval, staging ambigu sebelum
apply, dua edit binding bersamaan, optional null vs nilai asing, dan approval stale.
Tes `test_taxonomy_postgres.py` memverifikasi persistence metadata dan hierarchy parent.
Provider review di-seed sebagai fixture; pemeriksaan dependency, endpoint HTTP,
token preview, staging, dan transaksi PostgreSQL memakai kode asli.

Regresi APPEND/effective dating juga dijalankan untuk memastikan guard taxonomy
tidak mengubah alur tanpa taxonomy. OpenAPI/schema dan dokumentasi request diperbarui;
tidak ada endpoint BE-14 baru.

Bukti lanjutan: 20 tes terarah versi/migrasi/workflow/kontrak lulus, kemudian 24 tes
normalisasi/kontrak/APPEND/effective dating lulus (kedua run saling overlap).
Regresi non-integrasi tanpa workbook: 205 lulus. Suite workbook: 9 lulus, ditambah
1 tes kompatibilitas workbook lama lulus (total 10 tes workbook). Alembic tidak menemukan schema drift; exporter memverifikasi 150 operasi
beserta contoh payload, dan Ruff serta git diff --check lulus.

Bukti lanjutan worker/rule: 25 tes gabungan import review, worker taxonomy, workflow
PostgreSQL dan compiler rule lulus; 1 tes worker collision dan 1 tes XLSX in_taxonomy
lulus terpisah. Regresi non-integrasi tanpa workbook: 210 lulus. Angka tersebut mencakup
run yang overlap, bukan jumlah unik. Ruff file perubahan dan exporter --check 150
operasi lulus. Tidak ada migrasi database baru pada lanjutan worker/rule ini.
