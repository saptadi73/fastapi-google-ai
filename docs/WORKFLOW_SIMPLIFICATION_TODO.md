# Penyederhanaan workflow ETL — TODO dan review risiko

Status dokumen: implementasi lokal parsial; belum menjadi perubahan production. Audit ulang terakhir: 13 Oktober 2026.

## Temuan dari implementasi saat ini

Audit endpoint, service, UI, role, dan workflow sudah didokumentasikan juga pada [review menyeluruh](REVIEW_PENYEDERHANAAN_WORKFLOW_AKSES.md). Dokumen ini menjadi checklist eksekusi; bila ada perbedaan, keputusan pengguna pada permintaan perubahan menjadi acuan. Khusus akses default, acuan pengguna adalah **business domain dan unit pemilik yang sama**, bukan unit saja.

- Registrasi sumber, metadata akses, dan aktivasi akses memiliki review/policy terpisah.
- Konfigurasi harus divalidasi, diajukan, disetujui reviewer, lalu dapat tertahan lagi oleh approval rilis IT dan unit.
- Batch import masih memerlukan pertanyaan selesai, revalidate, preview, approval, dan apply.
- Master memakai lifecycle definisi/storage, binding sumber, binding kolom, serta batch import sendiri. `MASTER_RUNTIME_PENDING` masih menjadi blocker pada jalur ETL umum.
- Policy evaluator bersifat default-deny; policy sumber dan data product serta assignment memengaruhi katalog dan query.
- Role `PLATFORM_ADMIN` sudah mempunyai aksi `ADMIN`, tetapi sejumlah alur administrasi dan resource tetap memiliki pemeriksaan policy tersendiri.
- Workflow owner-managed sebelumnya default OFF. Default aplikasi kini ON, tetapi nilai `.env` production tetap perlu diverifikasi.
- Submit konfigurasi owner-managed sebelumnya mewajibkan checklist kolom/bagian. Checklist kini opsional di owner-managed dan tetap ada untuk workflow reviewer legacy.
- Sync aktif sebelumnya menolak `FULL_REFRESH`. Owner-managed kini boleh langsung sync penuh setelah pemeriksaan status, freshness, akses, preview konflik, dan validasi baris.
- Monitor perubahan Drive lokal mendeteksi perubahan melalui polling dan mengantre discovery/profiling. Production bergantung pada migration, Drive API/permission, worker dan Beat; pelaku edit eksternal tidak dapat dipastikan hanya dari `modifiedTime`.

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
- [x] Audit ulang default flag, checklist submit, jalur FULL_REFRESH, dan deteksi perubahan sumber; mismatch runtime production tetap perlu diverifikasi.

### P1 — akses sederhana tanpa kehilangan isolasi

- [x] Jadikan fallback baca/query bagi domain + unit pemilik default ON untuk sumber yang sudah ditinjau. Fallback tidak memberi EXPORT dan tidak aktif bila ada policy resource non-REVOKED; sumber lama tanpa review tetap memakai policy sebelumnya.
- [~] Metadata setelah review sumber dapat diperbarui pemilik/data owner/steward tanpa review kedua; scope harus tetap assignment aktif, perubahan diaudit, dan aktivasi legacy dibatasi owner/admin saat feature flag ON.
- [x] Tetapkan interaksi default scope dengan `DataProduct.allowed_roles`: untuk sumber bermetadata yang sudah direview, fallback hanya dapat melewati allow-list lama pada DISCOVER/READ/QUERY; evaluator tetap harus mengizinkan aksi berdasarkan assignment domain+unit dan role capability. EXPORT dan produk tanpa metadata tetap memakai allow-list lama.
- [ ] Jadikan restriction yurisdiksi/department opsional dan eksplisit; jangan mengubah data lama menjadi terbuka otomatis.
- [~] Sediakan laporan dry-run read-only yang dapat diulang (`python -m app.cli source-access-backfill-report`) untuk mengelompokkan metadata sumber lama. Backfill perubahan data masih harus diputuskan terpisah; laporan tidak auto-approve atau membuka akses.
- [ ] Pastikan PLATFORM_ADMIN dapat mengelola semua scope melalui jalur administrasi yang diaudit; tindakan baca/export tetap tercatat dan tunduk pada batas tenant.
- [x] Sediakan preview effective access yang menjelaskan allow/deny, reason code, policy revision, row/column scope tanpa mengembalikan nilai data; evaluasi diaudit dan UI admin mencari resource dengan pagination.
- [~] Tambahkan test scope role, katalog/template, DENY, dan policy yang sudah ada. Sebelum feature flag diaktifkan, masih perlu test expiry/revoke, isolasi tenant end-to-end, cache, serta migration/backfill.

### P2 — satu review saat registrasi

- [x] Perluas konteks review sumber agar approver dapat melihat semua tab yang ditemukan (termasuk tab hilang/nonaktif), klasifikasi, status profiling, jumlah baris, serta nama/tipe/indikasi PII kolom tanpa nilai contoh.
- [x] Kirim fingerprint bukti tab pada keputusan review dan tolak keputusan bila tab/profil berubah setelah approver membuka konteks. Perubahan inventory, klasifikasi, pengaturan tab, atau schema profil setelah approval mengembalikan sumber ke status perlu review.
- [ ] Pertahankan pemeriksaan kepemilikan sumber, akses Google Sheet, dan audit.
- [ ] Sediakan migrasi kompatibilitas untuk sumber lama yang telah melewati sebagian workflow.

### P3 — konfigurasi dan deployment

- [x] Jadikan submit konfigurasi owner-managed aktif secara default (`ETL_OWNER_WORKFLOW_ENABLED=true`); validasi dan bukti pemilik tetap terikat pada snapshot serta klasifikasi.
- [x] Hilangkan checklist kolom/bagian berulang pada submit owner-managed; workflow legacy tetap meminta bukti reviewer yang diperlukan.
- [x] Pertahankan snapshot freshness, dry-run penuh, schema plan, checklist, collision check, audit, dan idempotency.
- [x] Izinkan data owner/steward men-deploy dan rollback konfigurasi owner-managed yang lolos; konfigurasi legacy tetap memerlukan reviewer.
- [x] Izinkan sync incremental maupun FULL_REFRESH langsung untuk konfigurasi owner-managed aktif tanpa release approval kedua; akses sumber dan freshness tetap diperiksa.
- [x] Pertahankan transaksi FULL_REFRESH: validasi seluruh baris sebelum mengganti data; bila ada error, rollback dan data lama tetap tersedia. DDL destruktif tetap terpisah dan diblokir.
- [~] Owner-managed ETL tidak lagi memanggil endpoint atau menampilkan UI release approval; konfigurasi legacy tetap memakai keduanya. Hapus release groups global/inbox hanya setelah kompatibilitas data lama dan rollout siap.
- [~] Verifikasi ulang deploy hanya bila snapshot terbaru lulus; pesan dry-run menunjukkan baris/field/kode masalah tanpa nilai sel, dan blocker aturan kualitas menunjukkan baris serta field. Rincian validasi lain dan tahap runtime tetap perlu diperluas.
- [ ] Hapus UI inbox/assignment approval konfigurasi setelah endpoint dan data lama memiliki jalur kompatibilitas.

### P4 — master dan import

- [~] Di mode `ETL_OWNER_WORKFLOW_ENABLED`, definisi master disahkan pemilik setelah schema/business key/authority checks; source binding dan column binding tervalidasi tanpa approver kedua.
- [~] Deploy storage dapat dilakukan pemilik setelah konfirmasi rencana schema; batas perubahan storage aman dan audit tetap berlaku.
- [ ] Satukan runtime/pipeline master dan non-master pada validator, job, apply, audit, dan tracking yang sama.
- [ ] Tambahkan pemetaan relasi master opsional pada konfigurasi non-master dan pemeriksaan not-found/ambiguous.
- [ ] Pertahankan keputusan eksplisit untuk konflik master, perubahan key, deactivation, dan delete-restricted.
- [x] Hapus approval reviewer rutin untuk batch bersih pada owner workflow; pemilik Apply mengikat preview token/hash dan menjalankan validasi ulang.
- [~] Konflik sumber membutuhkan konfirmasi + alasan pemilik; duplicate/key conflict terverifikasi, PRIVACY_RISK, usulan insert yang perlu policy review, pertanyaan teknis, dan ambiguous reference tetap menjadi blocker sampai ditangani.
- [x] Jadikan temuan AI VALUE_ISSUE dan coverage parsial sebagai peringatan; sediakan endpoint backend dan UI owner untuk menandai temuan lama telah ditinjau dengan alasan dan audit. Rollout production masih terbuka.
- [~] MASTER sudah memiliki jalur Batch Import dengan snapshot, preview, business-key checks, dan apply; response klasifikasi kini membedakan kesiapan `MASTER_BATCH_IMPORT` dari blocker konfigurasi/sync ETL biasa. Auto-load MASTER tetap ditolak secara sengaja. End-to-end owner flow dari binding/storage hingga batch Apply dan tracking gabungan masih perlu diselesaikan sebelum blocker standar dihapus atau dinyatakan complete.

### P5 — frontend, dokumentasi, rollout

- [~] Tampilkan 7 langkah sebagai progres berurutan: checklist ditinjau/kedaluwarsa, status validasi/deploy, job gagal, dan tindakan berikutnya; helper per tahap tetap tersedia. Status tiap tahap hanya mencerminkan bukti UI yang ada dan tidak menggantikan validasi backend. Helper tracking menjelaskan approval IT awal; batch import dan Persetujuan tayang telah diperjelas untuk owner-managed versus legacy. Masih perlu menuntaskan keselarasan navigasi/panduan admin dan review semua teks workflow lama.
- [ ] Hilangkan tombol/menu approval yang tidak lagi menjadi bagian alur setelah backend dan migration siap.
- [~] Perbarui helper/knowledge base untuk AI review, sumber legacy, rollback owner workflow, error owner/legacy, serta alur master owner-managed versus legacy. Generator backend dan salinan helper frontend diselaraskan; helper semua 7 langkah, panduan admin lengkap, dan runbook rollout masih perlu dituntaskan.
- [ ] Jalankan migrasi staging, dry-run data lama, regression/security tests, lalu canary terbatas.
- [ ] Siapkan rollback feature flag dan audit sebelum rollout global.
- [ ] Verifikasi `.env` production: `ETL_OWNER_WORKFLOW_ENABLED=true`, `REQUIRE_SEPARATE_APPROVER=false`, `UNIT_DOMAIN_DEFAULT_ACCESS_ENABLED=true`; pastikan worker/Beat berjalan dan Drive metadata permission tersedia untuk deteksi otomatis.
- [ ] Samakan frontend dengan owner-managed default: CTA “Validasi & siapkan deploy”, hilangkan approval rutin, dan jelaskan FULL_REFRESH sebagai penggantian isi tabel setelah validasi.

## Blocker yang jangan dihapus

Jangan melewati tenant isolation, autentikasi, validasi role admin, sumber tidak terbaca, profil/header stale, schema/data invalid, duplicate business key, PII/secret handling, idempotency, database constraint, atau audit. Ini pemeriksaan integritas dan keamanan, bukan approval birokratis.

## Risiko dan urutan rollout

Perubahan default akses berisiko membuka data lama; backfill harus konservatif dan policy lama tidak boleh diam-diam dilonggarkan. Owner workflow ON tidak mengubah assignment domain/unit, access status, tenant boundary, atau approval registrasi sumber. Pertahankan endpoint/status legacy untuk record lama tanpa memalsukan keputusan reviewer. Full refresh hanya mengganti isi data setelah lulus validasi dan tidak mengesahkan perubahan schema secara otomatis. Penyatuan runtime master tetap berisiko pada referential integrity dan migrasi schema. Uji per fase di staging; periksa setting runtime dan preview sebelum production. Perubahan lokal pada default, checklist, dan sync FULL_REFRESH belum dideploy.

## Review ulang sebelum tiap fase dianggap selesai

- Apakah owner dapat menyelesaikan alur dari sumber baru sampai tabel aktif tanpa inbox approval rutin?
- Apakah sumber lama dan keputusan audit tetap dapat dibaca setelah migrasi?
- Apakah akses domain/unit default bekerja dan DENY/tenant boundary tetap menang?
- Apakah deploy menolak snapshot stale, mapping invalid, konflik schema, dan business key ganda?
- Apakah master dan non-master terlihat dalam tracking yang sama serta mempunyai bukti hasil yang bisa ditelusuri?
- Apakah ada endpoint legacy yang masih dapat memblokir UI atau sebaliknya melewati validasi?
