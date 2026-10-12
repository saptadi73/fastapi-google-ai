# Penyederhanaan workflow ETL — TODO dan review risiko

Status dokumen: rancangan implementasi bertahap, belum menjadi perubahan production.

## Temuan dari implementasi saat ini

- Registrasi sumber, metadata akses, dan aktivasi akses memiliki review/policy terpisah.
- Konfigurasi harus divalidasi, diajukan, disetujui reviewer, lalu dapat tertahan lagi oleh approval rilis IT dan unit.
- Batch import masih memerlukan pertanyaan selesai, revalidate, preview, approval, dan apply.
- Master memakai lifecycle definisi/storage, binding sumber, binding kolom, serta batch import sendiri. `MASTER_RUNTIME_PENDING` masih menjadi blocker pada jalur ETL umum.
- Policy evaluator bersifat default-deny; policy sumber dan data product serta assignment memengaruhi katalog dan query.
- Role `PLATFORM_ADMIN` sudah mempunyai aksi `ADMIN`, tetapi sejumlah alur administrasi dan resource tetap memiliki pemeriksaan policy tersendiri.

## Target workflow

1. **Registrasi dan klasifikasi sumber:** satu pemeriksaan steward/approver atas daftar tab dan klasifikasi MASTER/NON_MASTER. Simpan identitas pemeriksa, versi sumber, tab yang diperiksa, keputusan, alasan, dan waktu. Pemeriksaan diulang hanya bila sumber/tab/klasifikasi berubah secara material.
2. **Hak akses:** PLATFORM_ADMIN mengelola akun, role, unit, domain, yurisdiksi, dan department. Data owner menetapkan lingkup akses produk. Default akses adalah domain + business unit yang sama; yurisdiksi/department menjadi pembatas tambahan hanya bila pemilik memilihnya. DENY eksplisit, tenant boundary, expiry, dan audit tetap berlaku.
3. **ETL biasa:** pemilik/steward menyelesaikan profiling, mapping, cleansing, kualitas, semantic, akses, dan validasi. Validasi memeriksa konfigurasi terhadap snapshot/header aktif, tipe, konflik nama, aturan kualitas, PII, dan rencana schema. Bila lulus, pemilik dapat deploy; tidak ada approval konfigurasi atau approval rilis kedua.
4. **Import/sync:** deploy dan sinkronisasi memakai snapshot tervalidasi. Review manusia hanya untuk konflik nilai/bisnis yang tidak dapat diputuskan aman oleh aturan, bukan approval rutin untuk setiap batch.
5. **Master:** master mengikuti validasi, deploy, dan import yang sama. Business key wajib unik/non-null. Saat non-master deploy, pemilik dapat memetakan field ke business key master aktif; resolver memeriksa keberadaan dan ambiguitas. Tidak ada approval binding terpisah. Perubahan key, penghapusan record yang direferensikan, atau konflik tetap memerlukan penanganan eksplisit.

## TODO implementasi bertahap

### P0 — inventarisasi dan acceptance criteria

- [ ] Inventaris semua state transition/API yang menghalangi profiling, konfigurasi, deploy, sync, dan query.
- [ ] Tetapkan satu keputusan registrasi/tab dan kondisi yang mengharuskan pemeriksaan ulang.
- [ ] Tetapkan aturan default scope domain + business unit, serta semantik tambahan yurisdiksi/department.
- [ ] Petakan data produksi lama: konfigurasi APPROVED/ACTIVE, policy, approval, binding master/taxonomy, batch, dan status legacy.
- [ ] Buat test matrix per role dan jalur UI/API langsung.

### P1 — akses sederhana tanpa kehilangan isolasi

- [ ] Implementasikan policy default berbasis domain + business unit dengan migrasi/data backfill yang dapat diulang.
- [ ] Jadikan restriction yurisdiksi/department opsional dan eksplisit; jangan mengubah data lama menjadi terbuka otomatis.
- [ ] Pastikan PLATFORM_ADMIN dapat mengelola semua scope melalui jalur administrasi yang diaudit; tindakan baca/export tetap tercatat dan tunduk pada batas tenant.
- [ ] Tambah preview effective access yang menjelaskan allow/deny dan alasan tanpa memaparkan data lintas tenant.

### P2 — satu review saat registrasi

- [ ] Gabungkan review metadata dan klasifikasi tab ke satu keputusan registrasi.
- [ ] Simpan fingerprint spreadsheet/tab dan invalidasi keputusan hanya ketika sumber berubah.
- [ ] Pertahankan pemeriksaan kepemilikan sumber, akses Google Sheet, dan audit.
- [ ] Sediakan migrasi kompatibilitas untuk sumber lama yang telah melewati sebagian workflow.

### P3 — konfigurasi dan deployment

- [ ] Ubah submit konfigurasi menjadi validasi + bukti pemeriksaan pemilik; hilangkan reviewer configuration dan release groups.
- [ ] Pertahankan snapshot freshness, dry-run penuh, schema plan, collision check, dan idempotency.
- [ ] Deploy hanya bila validasi ulang pada snapshot terbaru lulus; error harus menjelaskan field/baris/tahap.
- [ ] Hapus UI inbox/assignment approval konfigurasi setelah endpoint dan data lama memiliki jalur kompatibilitas.

### P4 — master dan import

- [ ] Satukan pipeline master/non-master pada validator, job, audit, dan tracking yang sama.
- [ ] Hilangkan approval definisi/binding/storage rutin; validasi business key dan referential integrity sebelum apply.
- [ ] Tambahkan pemetaan relasi master opsional pada konfigurasi non-master dan pemeriksaan not-found/ambiguous.
- [ ] Pertahankan keputusan eksplisit untuk konflik master, perubahan key, deactivation, dan delete-restricted.
- [ ] Kurangi approval batch rutin; konflik tidak aman tetap menjadi item resolusi yang harus diputus pemilik.

### P5 — frontend, dokumentasi, rollout

- [ ] Tampilkan 7 langkah sebagai progres berurutan dengan status, blocker terakhir, tindakan berikutnya, dan helper per langkah.
- [ ] Hilangkan tombol/menu approval yang tidak lagi menjadi bagian alur setelah backend dan migration siap.
- [ ] Perbarui helper, knowledge base, glossary error, API docs, panduan admin, dan runbook operasional.
- [ ] Jalankan migrasi staging, dry-run data lama, regression/security tests, lalu canary terbatas.
- [ ] Siapkan rollback feature flag dan audit sebelum rollout global.

## Blocker yang jangan dihapus

Jangan melewati tenant isolation, autentikasi, validasi role admin, sumber tidak terbaca, profil/header stale, schema/data invalid, duplicate business key, PII/secret handling, idempotency, database constraint, atau audit. Ini pemeriksaan integritas dan keamanan, bukan approval birokratis.

## Risiko dan urutan rollout

Perubahan default akses berisiko membuka data lama; karena itu backfill harus konservatif dan policy lama tidak boleh diam-diam dilonggarkan. Penghapusan approval berisiko mengubah state lama yang masih menunggu keputusan; jalankan mode kompatibilitas dan rekonsiliasi status terlebih dahulu. Penyatuan runtime master berisiko pada referential integrity dan migrasi schema. Implementasikan per fase di staging, bandingkan hasil effective access dan dry-run dengan perilaku lama, lalu aktifkan per tenant/feature flag. Production deployment belum dilakukan.

## Review ulang sebelum tiap fase dianggap selesai

- Apakah owner dapat menyelesaikan alur dari sumber baru sampai tabel aktif tanpa inbox approval rutin?
- Apakah sumber lama dan keputusan audit tetap dapat dibaca setelah migrasi?
- Apakah akses domain/unit default bekerja dan DENY/tenant boundary tetap menang?
- Apakah deploy menolak snapshot stale, mapping invalid, konflik schema, dan business key ganda?
- Apakah master dan non-master terlihat dalam tracking yang sama serta mempunyai bukti hasil yang bisa ditelusuri?
- Apakah ada endpoint legacy yang masih dapat memblokir UI atau sebaliknya melewati validasi?
