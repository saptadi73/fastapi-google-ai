# Penyederhanaan workflow ETL — TODO dan review risiko

Status dokumen: rancangan implementasi bertahap, belum menjadi perubahan production.

## Temuan dari implementasi saat ini

Audit endpoint, service, UI, role, dan workflow sudah didokumentasikan juga pada [review menyeluruh](REVIEW_PENYEDERHANAAN_WORKFLOW_AKSES.md). Dokumen ini menjadi checklist eksekusi; bila ada perbedaan, keputusan pengguna pada permintaan perubahan menjadi acuan. Khusus akses default, acuan pengguna adalah **business domain dan unit pemilik yang sama**, bukan unit saja.

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

### P0 — inventarisasi dan acceptance criteria (selesai untuk audit kode)

- [x] Inventaris state transition/API yang menghalangi profiling, konfigurasi, deploy, sync, dan query.
- [x] Tetapkan target satu keputusan registrasi/tab dan kondisi yang mengharuskan pemeriksaan ulang.
- [x] Tetapkan default scope business domain + unit pemilik; yurisdiksi/department menjadi pembatas opsional.
- [x] Petakan state approval, policy, binding master/taxonomy, dan batch lama; detail backfill masih menjadi TODO P1.
- [x] Buat skenario penerimaan untuk role, tenant boundary, keamanan data, dan jalur UI/API.

### P1 — akses sederhana tanpa kehilangan isolasi

- [x] Tambahkan jalur fallback baca/query untuk pasangan business domain + unit pemilik di belakang `UNIT_DOMAIN_DEFAULT_ACCESS_ENABLED` (default OFF). Fallback hanya berlaku untuk sumber yang sudah ditinjau, tidak memberi EXPORT, dan tidak aktif bila ada policy resource non-REVOKED.
- [~] Metadata setelah review sumber dapat diperbarui pemilik/data owner/steward tanpa review kedua; scope harus tetap assignment aktif, perubahan diaudit, dan aktivasi legacy dibatasi owner/admin saat feature flag ON.
- [x] Tetapkan interaksi default scope dengan `DataProduct.allowed_roles`: untuk sumber bermetadata yang sudah direview, fallback hanya dapat melewati allow-list lama pada DISCOVER/READ/QUERY; evaluator tetap harus mengizinkan aksi berdasarkan assignment domain+unit dan role capability. EXPORT dan produk tanpa metadata tetap memakai allow-list lama.
- [ ] Jadikan restriction yurisdiksi/department opsional dan eksplisit; jangan mengubah data lama menjadi terbuka otomatis.
- [ ] Rancang migrasi/backfill yang dapat diulang dan laporan dry-run untuk metadata sumber lama.
- [ ] Pastikan PLATFORM_ADMIN dapat mengelola semua scope melalui jalur administrasi yang diaudit; tindakan baca/export tetap tercatat dan tunduk pada batas tenant.
- [ ] Tambah preview effective access yang menjelaskan allow/deny dan alasan tanpa memaparkan data lintas tenant.
- [~] Tambahkan test scope role, katalog/template, DENY, dan policy yang sudah ada. Sebelum feature flag diaktifkan, masih perlu test expiry/revoke, isolasi tenant end-to-end, cache, serta migration/backfill.

### P2 — satu review saat registrasi

- [x] Perluas konteks review sumber agar approver dapat melihat semua tab yang ditemukan (termasuk tab hilang/nonaktif), klasifikasi, status profiling, jumlah baris, serta nama/tipe/indikasi PII kolom tanpa nilai contoh.
- [x] Kirim fingerprint bukti tab pada keputusan review dan tolak keputusan bila tab/profil berubah setelah approver membuka konteks. Perubahan inventory, klasifikasi, pengaturan tab, atau schema profil setelah approval mengembalikan sumber ke status perlu review.
- [ ] Pertahankan pemeriksaan kepemilikan sumber, akses Google Sheet, dan audit.
- [ ] Sediakan migrasi kompatibilitas untuk sumber lama yang telah melewati sebagian workflow.

### P3 — konfigurasi dan deployment

- [x] Tambahkan mode submit konfigurasi sebagai validasi + bukti pemeriksaan pemilik di balik `ETL_OWNER_WORKFLOW_ENABLED` (default OFF).
- [x] Pertahankan snapshot freshness, dry-run penuh, schema plan, checklist, collision check, audit, dan idempotency.
- [x] Izinkan pemilik men-deploy konfigurasi yang lolos; rollback masih membutuhkan role reviewer.
- [ ] Hapus release groups dan UI inbox approval setelah kompatibilitas konfigurasi lama dan test rollout siap.
- [ ] Verifikasi ulang deploy hanya bila snapshot terbaru lulus; perbaiki error agar menjelaskan field/baris/tahap.
- [ ] Hapus UI inbox/assignment approval konfigurasi setelah endpoint dan data lama memiliki jalur kompatibilitas.

### P4 — master dan import

- [~] Di mode `ETL_OWNER_WORKFLOW_ENABLED`, definisi master disahkan pemilik setelah schema/business key/authority checks; source binding dan column binding tervalidasi tanpa approver kedua.
- [~] Deploy storage dapat dilakukan pemilik setelah konfirmasi rencana schema; batas perubahan storage aman dan audit tetap berlaku.
- [ ] Satukan runtime/pipeline master dan non-master pada validator, job, apply, audit, dan tracking yang sama.
- [ ] Tambahkan pemetaan relasi master opsional pada konfigurasi non-master dan pemeriksaan not-found/ambiguous.
- [ ] Pertahankan keputusan eksplisit untuk konflik master, perubahan key, deactivation, dan delete-restricted.
- [ ] Hapus approval batch rutin untuk batch bersih; konflik, usulan insert, ambiguous reference, dan source conflict tetap memerlukan resolusi steward.
- [ ] Hilangkan blocker `MASTER_RUNTIME_PENDING` setelah master memiliki jalur preview/apply yang setara dan sudah diuji end-to-end.

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
