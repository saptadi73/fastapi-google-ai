# Kebijakan load lanjutan BE-12

## APPEND tanpa business key: runtime tersedia

`ETLConfiguration.append_duplicate_policy` bersifat opsional:

| Nilai | Perilaku |
|---|---|
| null / tidak dikirim | SKIP_IDENTICAL, kompatibel dengan ETL legacy tanpa key |
| SKIP_IDENTICAL | Simpan satu representasi baris; baris identik dilewati |
| REJECT_IDENTICAL | Duplikat menghentikan batch; semua penulisan dalam transaksi dibatalkan |

Field hanya boleh diisi untuk `load_strategy=APPEND` tanpa `is_business_key` atau
`is_primary_key`. UPSERT, FULL_REFRESH, dan APPEND berkunci menolak field non-null
dengan validasi 422. Policy master tetap terpisah.

Identitas memakai unique `(tenant_id, _row_hash)` yang sudah tersedia. Hash berasal
dari seluruh nilai bisnis **setelah transform/cast**, tanpa metadata sumber/baris/run.
Tanggal dan Decimal dari staging JSON dikembalikan ke tipe target sebelum INSERT;
transform, kurs, dan konversi satuan tidak dijalankan ulang. Dua kejadian bisnis yang
nilainya identik tidak dapat dibedakan dengan identitas ini. Jika keduanya perlu
disimpan, sumber harus menyediakan ID event berbeda; kebijakan KEEP_ALL tanpa
identitas event belum tersedia. Membuat ID acak saat retry bukan solusi idempotency.

Dry-run memeriksa duplikat di snapshot setelah DQ. SKIP mempertahankan baris valid
di staging dan menambahkan warning `APPEND_IDENTICAL_SKIPPED`; hitungan valid bukan
jumlah insert. REJECT mengembalikan `APPEND_IDENTICAL_REJECTED` (409). Dry-run
konfigurasi tidak membaca target: gunakan preview batch untuk duplikat terhadap data
yang sudah tersimpan.

Preview batch menghasilkan INSERT untuk hash baru, UNCHANGED untuk hash duplikat
pada mode SKIP, atau DUPLICATE yang menahan approval pada mode REJECT. `before=null`
untuk preview APPEND ini; identitas duplikat diperiksa dari hash, bukan payload target.
Duplikat antarbaris staging juga diperiksa. Apply memeriksa unique constraint lagi,
termasuk jika target berubah setelah approval. Mode SKIP dapat menyimpan lebih sedikit
baris daripada preview; gunakan `rows_applied` hasil apply sebagai hitungan aktual.
REJECT menggagalkan seluruh transaksi jika ditemukan duplikat ketika apply, dengan
error `APPEND_IDENTICAL_REJECTED` (409). Batch approved tetap dapat direview ulang
melalui revalidate; rollback error teknis tidak mengubah target/batch.

ETL legacy dan apply batch menggunakan helper INSERT yang sama untuk APPEND tanpa
key. Kontrak ini tidak mengubah kebijakan APPEND berkunci atau FULL_REFRESH.

XLSX baru menyediakan `14 Review!B8`; A8 adalah nama parameter yang ditandatangani.
Kosong berarti null. Workbook lama yang tidak mempunyai baris policy mempertahankan
nilai konfigurasi asal. Export JSON/YAML dan dependency hash membawa field ini melalui
schema konfigurasi existing. Tidak ada migrasi fisik target baru.

## Rancangan split grain / multi-target (belum menerima payload)

Satu konfigurasi saat ini tetap satu grain dan satu target. Rancangan lanjutan:

1. Setiap target mempunyai ID stabil, grain, key, mapping, DQ, dan strategi load
   sendiri. Target mengacu ke kolom snapshot yang sama; tidak melakukan baca ulang
   Sheet di tengah transaksi.
2. Pemisahan header invoice dan detail invoice harus menyatakan key header serta
   key detail. Baris header berulang hanya boleh digabung jika seluruh atribut
   header konsisten; perbedaan atribut menjadi pertanyaan, bukan memilih baris terakhir.
3. Dependency plan mengurutkan master/header sebelum child. Siklus menahan deploy
   dan apply. FK tenant + UUID mengikuti BE-09; join query mengikuti BE-14.
4. Preview berisi diff dan blocker tiap target, ditandatangani sebagai satu rencana
   bersama revision seluruh dependency. Approval berlaku untuk seluruh rencana.
5. Versi awal wajib satu transaksi PostgreSQL: kegagalan satu target membatalkan semua
   target dan checkpoint. Partial load lintas target serta target lintas database
   ditunda sampai ada protokol recovery yang terpisah.
6. XLSX perlu identitas target pada setiap mapping/rule; parser harus menolak target
   hilang, key ambigu, atau relasi rusak. Jangan menafsirkan tabel tambahan sebagai
   target secara otomatis.

Acceptance: invoice dua detail tidak menggandakan nominal header, konflik atribut
header menjadi blocker, rollback target kedua mengembalikan target pertama, dan
retry tidak menggandakan identitas. `multi_target` masih unsupported di catalog.

## Rancangan schema evolution (belum menerima payload)

Non-master tetap CREATE_ONLY_OR_IDENTICAL; master memakai aturan kompatibilitas
storage existing (metadata dan penambahan atribut nullable). Perubahan schema yang
lebih luas membutuhkan rencana migrasi tersendiri, bukan efek samping PATCH konfigurasi.

Rencana harus menyimpan schema fisik sebelum/sesudah, hash data/dependency, pemeriksaan
nilai yang tidak dapat dikonversi, dependency FK/view, lock yang diperlukan, estimasi
durasi, serta referensi backup. Approval migration berbeda dari approval mapping.
DDL dan publikasi konfigurasi baru hanya dianggap selesai setelah verifikasi target.

Penambahan kolom nullable merupakan kandidat tahap pertama. Rename/drop, perubahan
key, penyempitan numeric/varchar, perubahan timezone/unit/currency, dan perubahan grain
memerlukan backfill yang direview. Jangan mengubah arti angka historis dengan mengganti
metadata kurs. Rollback DDL tidak sama dengan pemulihan data yang sudah terkonversi;
backup/restore harus diuji sebelum fitur tersebut diaktifkan.

Acceptance: apply rencana stale ditolak; data/FK yang tidak kompatibel menahan DDL;
gagal migrasi tidak mempublikasikan revision baru; retry aman; backup dapat dipulihkan.
`schema_evolution` masih unsupported di catalog.

## Default dan kondisi update

Default scalar bertipe sudah tersedia pada DQ: berlaku untuk nilai kosong/null setelah
transform, sebelum nullability/DQ, dalam satuan target. Ini bukan ekspresi SQL dan
bukan perintah mengganti record lama yang tidak hadir dalam snapshot.

Kondisi update dinamis belum tersedia. Tahap berikutnya harus memakai AST allowlist
dengan operand bertipe `incoming` dan `existing`, operator yang didefinisikan, dan
semantik null eksplisit. Tidak menerima SQL/Python/expression string bebas.
Keputusan UPDATE atau SKIP harus muncul dalam preview, terikat versi target, dan
dihitung ulang di bawah lock. Perubahan business key, periode immutable, dan metadata
identitas tetap melewati workflow masing-masing. Acceptance mencakup null, target
berubah sesudah approval, masking field kondisi, dan retry. Tidak ada key payload
baru yang boleh dikirim sebelum compiler, schema, artifact, serta XLSX mendukungnya.

## Bukti pengujian 9 September 2026

- 208 tes non-integrasi lulus, termasuk schema, dry-run, hash, dan round-trip/edit XLSX.
- 6 tes PostgreSQL APPEND lulus: default/skip pada target dan snapshot duplikat,
  blocker preview REJECT, rollback HTTP apply ketika duplikat muncul sesudah approval,
  serta SKIP/REJECT pada sync legacy. Tes batch menyimpan postcondition review AI
  sebagai fixture; tidak memanggil provider. Jalur preview/approval/apply HTTP,
  dependency freshness, penyimpanan bertipe, dan transaksi memakai kode asli.
- 7 tes PostgreSQL effective dating juga tetap lulus.
- Ruff seluruh file kode yang berubah dan exporter `--check` 145 operasi lulus.

Database test diperbarui memakai migrasi existing sampai `7i85f6b4c3de` karena
cleanup fixture awal menemukan tabel taxonomy belum tersedia. Tidak ada migrasi baru
untuk policy APPEND. `alembic check` masih mendeteksi ketidaksesuaian model/migrasi
existing pada master_column_binding dan taxonomy (index, FK tenant, dan kolom
metadata); ini perlu diselaraskan pada pekerjaan registry/taxonomy berikutnya.
Database aplikasi/production tidak dimigrasikan. Fixture awal yang gagal cleanup
sudah dibersihkan berdasarkan UUID tenant/target pengujian tersebut saja.
