# Penyederhanaan workflow ETL — TODO dan review risiko

Status dokumen: sebagian perubahan terpasang di production pada 13 Oktober 2026 (backend `d76f897`, frontend `6986666`); TODO yang belum dicentang tetap belum dianggap selesai. Audit ulang terakhir: 13 Oktober 2026.

## Temuan dari implementasi saat ini

Audit endpoint, service, UI, role, dan workflow sudah didokumentasikan juga pada [review menyeluruh](REVIEW_PENYEDERHANAAN_WORKFLOW_AKSES.md). Dokumen ini menjadi checklist eksekusi; bila ada perbedaan, keputusan pengguna pada permintaan perubahan menjadi acuan. Khusus akses default, acuan pengguna adalah **business domain dan unit pemilik yang sama**, bukan unit saja.

- Registrasi sumber tetap memerlukan satu keputusan reviewer. Metadata dan aktivasi sumber lama masih memiliki endpoint/policy kompatibilitas; sumber yang telah ditinjau dapat mengubah metadata akses melalui owner workflow tanpa review kedua.
- Konfigurasi owner-managed divalidasi dan dapat di-deploy pemilik tanpa approval rutin; konfigurasi legacy masih dapat tertahan oleh reviewer/release approval IT dan unit.
- Batch import owner-managed memakai pertanyaan, revalidate, preview, konfirmasi konflik yang diwajibkan, dan Apply tanpa approval rutin untuk batch bersih. Workflow legacy tetap memakai approval lama.
- Master memiliki jalur Batch Import tersendiri; `MASTER_RUNTIME_PENDING` tetap memblokir tab MASTER pada jalur konfigurasi/sync ETL biasa, bukan seluruh pemuatan master.
- Policy evaluator bersifat default-deny; policy sumber dan data product serta assignment memengaruhi katalog dan query.
- Role `PLATFORM_ADMIN` sudah mempunyai aksi `ADMIN`, tetapi sejumlah alur administrasi dan resource tetap memiliki pemeriksaan policy tersendiri.
- Scope ALLOW eksplisit kini mensyaratkan assignment unit + domain dasar; yurisdiksi dan department tambahan hanya membatasi bila dimasukkan dalam policy. Setiap atribut policy tetap wajib menjadi assignment aktif subjek.
- Akses PLATFORM_ADMIN ke administrasi scope dibatasi tenant melalui repository/API role checks; mutasi scope dan evaluasi akses diaudit. Audit `query.executed` kini mencatat `action` QUERY/EXPORT dan identitas produk/join tanpa nilai hasil.
- Workflow owner-managed dan fallback akses domain+unit aktif di production; default kode keduanya ON dan konfigurasi production sudah diverifikasi.
- Submit konfigurasi owner-managed sebelumnya mewajibkan checklist kolom/bagian. Checklist kini opsional di owner-managed dan tetap ada untuk workflow reviewer legacy.
- Sync aktif sebelumnya menolak `FULL_REFRESH`. Owner-managed kini boleh langsung sync penuh setelah pemeriksaan status, freshness, akses, preview konflik, dan validasi baris.
- Monitor perubahan Drive lokal mendeteksi perubahan melalui polling dan mengantre discovery/profiling. Production bergantung pada migration, Drive API/permission, worker dan Beat; pelaku edit eksternal tidak dapat dipastikan hanya dari `modifiedTime`.
- Pada production, workflow owner-managed, fallback domain+unit, dan monitor aktif; `REQUIRE_SEPARATE_APPROVER=false` sudah disetel dan service API/worker/Beat aktif. Backend `d76f897` membedakan `403 accessNotConfigured` dari izin file. Poll berikutnya memperbarui notifikasi terbuka; pemeriksaan read-only menemukan 61 notifikasi dengan kode `DRIVE_API_NOT_ENABLED`. Admin project Google Cloud masih perlu mengaktifkan Google Drive API; sampai itu selesai, perubahan Sheet tidak dapat dipantau otomatis.

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
- [x] Audit ulang default flag, checklist submit, jalur FULL_REFRESH, dan deteksi perubahan sumber; production owner workflow, domain+unit fallback, dan monitor aktif; `REQUIRE_SEPARATE_APPROVER=false` disetel pada 13 Oktober 2026.

### P1 — akses sederhana tanpa kehilangan isolasi

- [x] Jadikan fallback baca/query bagi domain + unit pemilik default ON untuk sumber yang sudah ditinjau. Fallback tidak memberi EXPORT dan tidak aktif bila ada policy resource non-REVOKED; sumber lama tanpa review tetap memakai policy sebelumnya.
- [~] Metadata setelah review sumber dapat diperbarui pemilik/data owner/steward tanpa review kedua; scope harus tetap assignment aktif, perubahan diaudit, dan aktivasi legacy dibatasi owner/admin saat feature flag ON.
- [x] Tetapkan interaksi default scope dengan `DataProduct.allowed_roles`: untuk sumber bermetadata yang sudah direview, fallback hanya dapat melewati allow-list lama pada DISCOVER/READ/QUERY; evaluator tetap harus mengizinkan aksi berdasarkan assignment domain+unit dan role capability. EXPORT dan produk tanpa metadata tetap memakai allow-list lama.
- [x] Jadikan restriction yurisdiksi/department opsional dan eksplisit pada policy: ALLOW memerlukan assignment unit+domain, lalu hanya atribut tambahan yang dipilih; setiap atribut terpilih tetap wajib dimiliki aktif oleh pengguna. Default hanya terbuka untuk sumber yang sudah ditinjau pada tenant/domain/unit yang sama; data lama yang belum ditinjau tetap tertutup.
- [~] Sediakan laporan dry-run read-only yang dapat diulang (`python -m app.cli source-access-backfill-report`) untuk mengelompokkan metadata sumber lama. Backfill perubahan data masih harus diputuskan terpisah; laporan tidak auto-approve atau membuka akses.
- [x] Pastikan PLATFORM_ADMIN mengelola scope lewat API admin tenant-bound yang mengaudit perubahan/evaluasi; query dan EXPORT mencatat aksi eksplisit, dan otorisasi sumber/produk tetap diperiksa sebelum data diberikan. Tes tenant end-to-end, cache, expiry/revoke, dan migrasi legacy tetap dilacak pada item tes terpisah.
- [x] Sediakan preview effective access yang menjelaskan allow/deny, reason code, policy revision, row/column scope tanpa mengembalikan nilai data; evaluasi diaudit dan UI admin mencari resource dengan pagination.
- [~] Tambahkan test scope role, katalog/template, DENY, dan policy yang sudah ada. Sebelum feature flag diaktifkan, masih perlu test expiry/revoke, isolasi tenant end-to-end, cache, serta migration/backfill.

### P2 — satu review saat registrasi

- [x] Perluas konteks review sumber agar approver dapat melihat semua tab yang ditemukan (termasuk tab hilang/nonaktif), klasifikasi, status profiling, jumlah baris, serta nama/tipe/indikasi PII kolom tanpa nilai contoh.
- [x] Kirim fingerprint bukti tab pada keputusan review dan tolak keputusan bila tab/profil berubah setelah approver membuka konteks. Perubahan inventory, klasifikasi, pengaturan tab, atau schema profil setelah approval mengembalikan sumber ke status perlu review.
- [x] Pertahankan pemeriksaan kepemilikan sumber, metadata assignment, akses Google Sheet, dan audit pada registrasi/review; tes integrasi mencakup validasi assignment serta kegagalan akses discovery (`tests/test_integration.py`).
- [x] Sediakan migrasi kompatibilitas untuk sumber lama yang telah melewati sebagian workflow: simpan snapshot tahap dan tindakan lanjut per sumber ke audit, pertahankan status/progress yang ada, dan minta bukti reviewer yang hilang. Tidak ada status approval, policy, assignment, atau akses yang dibuat otomatis.

### P3 — konfigurasi dan deployment

- [x] Jadikan submit konfigurasi owner-managed aktif secara default (`ETL_OWNER_WORKFLOW_ENABLED=true`); validasi dan bukti pemilik tetap terikat pada snapshot serta klasifikasi.
- [x] Hilangkan checklist kolom/bagian berulang pada submit owner-managed; workflow legacy tetap meminta bukti reviewer yang diperlukan.
- [x] Pertahankan snapshot freshness, dry-run penuh, schema plan, checklist, collision check, audit, dan idempotency.
- [x] Izinkan data owner/steward men-deploy dan rollback konfigurasi owner-managed yang lolos; konfigurasi legacy tetap memerlukan reviewer.
- [x] Izinkan sync incremental maupun FULL_REFRESH langsung untuk konfigurasi owner-managed aktif tanpa release approval kedua; akses sumber dan freshness tetap diperiksa. Konfigurasi legacy yang sudah punya `approved_by` dan `approved_at` juga kompatibel dalam mode owner workflow, tetap dengan pemeriksaan owner/steward/platform admin; draft tanpa bukti approval tidak diloloskan otomatis.
- [x] Pertahankan transaksi FULL_REFRESH: validasi seluruh baris sebelum mengganti data; bila ada error, rollback dan data lama tetap tersedia. DDL destruktif tetap terpisah dan diblokir.
- [~] Backend memiliki jalur kompatibilitas untuk konfigurasi owner-managed dan legacy yang telah disetujui, sehingga release approval kedua tidak menghalangi deploy/sync. Endpoint lama dipertahankan untuk record dan klien lama; UI inbox, assignment configuration/import, navigasi, dan panduan frontend masih perlu dihapus.
- [~] Verifikasi ulang deploy hanya bila snapshot terbaru lulus; pesan dry-run menunjukkan baris/field/kode masalah tanpa nilai sel, dan blocker aturan kualitas menunjukkan baris serta field. Rincian validasi lain dan tahap runtime tetap perlu diperluas.
- [~] Jalur kompatibilitas backend siap: konfigurasi legacy hanya melewati release gate bila approval lama tercatat; draft tanpa approval tetap perlu validasi/pengajuan ulang pemilik. Hapus UI inbox/assignment approval konfigurasi serta tautan panduannya di repo frontend; endpoint/API lama tetap dipertahankan sementara untuk kompatibilitas klien.

### P4 — master dan import

- [~] Di mode `ETL_OWNER_WORKFLOW_ENABLED`, definisi master disahkan pemilik setelah schema/business key/authority checks; source binding dan column binding tervalidasi tanpa approver kedua.
- [~] Deploy storage dapat dilakukan pemilik setelah konfirmasi rencana schema; batas perubahan storage aman dan audit tetap berlaku.
- [~] Master dan non-master berbagi ImportReview create/worker/preview/apply, job, audit (`import.applied`), dan source tracking; URL kompatibilitas `/sources/{id}/sync` kini mengantrekan pipeline ini. Validator dan target writer masih memakai adapter MASTER untuk business key, authority/effective dating, dan storage. Jalur reprocess karantina lama masih perlu direkonsiliasi sebelum seluruh runtime langsung dapat dinyatakan satu jalur.
- [~] Pemetaan relasi master opsional tersedia pada `ColumnMapping.master_reference` untuk konfigurasi NON_MASTER dan tetap membaca `MasterColumnBinding` lama. Preview/apply memakai master aktif, alias UUID dan hash dependency; not-found/ambiguous tidak dipilih otomatis. Editor UI tersedia; uji PostgreSQL end-to-end untuk konfigurasi embedded masih menunggu test database yang sudah dimigrasikan.
- [~] Konflik master memerlukan konfirmasi hash preview dan alasan; konflik key/duplicate memblokir apply; deactivation kini memerlukan alasan audit; foreign key menggunakan `ON DELETE RESTRICT`. Perubahan business key/schema ditolak dengan `MASTER_SCHEMA_MIGRATION_REQUIRED` sampai workflow migrasi eksplisit tersedia.
- [x] Hapus approval reviewer rutin untuk batch bersih pada owner workflow; pemilik Apply mengikat preview token/hash dan menjalankan validasi ulang.
- [~] Konflik sumber membutuhkan konfirmasi + alasan pemilik; duplicate/key conflict terverifikasi, PRIVACY_RISK, usulan insert yang perlu policy review, pertanyaan teknis, dan ambiguous reference tetap menjadi blocker sampai ditangani.
- [x] Jadikan temuan AI VALUE_ISSUE dan coverage parsial sebagai peringatan; sediakan endpoint backend dan UI owner untuk menandai temuan lama telah ditinjau dengan alasan dan audit. Rollout production masih terbuka.
- [~] MASTER sudah memiliki jalur Batch Import dengan snapshot, preview, business-key checks, dan apply; response klasifikasi kini membedakan kesiapan `MASTER_BATCH_IMPORT` dari blocker konfigurasi/sync ETL biasa. Auto-load MASTER tetap ditolak secara sengaja. End-to-end owner flow dari binding/storage hingga batch Apply dan tracking gabungan masih perlu diselesaikan sebelum blocker standar dihapus atau dinyatakan complete.

### P5 — frontend, dokumentasi, rollout

- [~] Tampilkan 7 langkah sebagai progres berurutan: checklist ditinjau/kedaluwarsa, status validasi/deploy, job gagal, dan tindakan berikutnya; helper per tahap tetap tersedia. Status tiap tahap hanya mencerminkan bukti UI yang ada dan tidak menggantikan validasi backend. Helper tracking menjelaskan approval IT awal; batch import dan Persetujuan tayang telah diperjelas untuk owner-managed versus legacy. Helper tujuh langkah kini ringkas dan menjelaskan jalur owner-managed/legacy secara terpisah; masih perlu menuntaskan keselarasan navigasi/panduan admin dan review semua teks workflow lama.
- [ ] Hilangkan tombol/menu approval yang tidak lagi menjadi bagian alur setelah backend dan migration siap.
- [~] Perbarui helper/knowledge base untuk AI review, sumber legacy, rollback owner workflow, error owner/legacy, serta alur master owner-managed versus legacy. Generator backend dan salinan helper frontend diselaraskan; ringkasan alur dan helper tujuh langkah telah disederhanakan; panduan admin lengkap dan review teks lama masih perlu dituntaskan.
- [~] Jalankan migrasi staging, dry-run data lama, regression/security tests, lalu canary terbatas. Migration source-change monitor `a7q0w3e6r9t2` telah diterapkan di production; tes backend workflow/monitor lulus sebelum deploy dan tes terarah terakhir lulus 7/7. Dry-run akses legacy, regression/security penuh, dan canary bertahap masih terbuka.
- [ ] Siapkan rollback feature flag dan audit sebelum rollout global.
- [~] Verifikasi `.env` production dan worker/Beat: owner workflow serta domain+unit fallback aktif dari default; `REQUIRE_SEPARATE_APPROVER=false` tersimpan; worker/Beat aktif. Drive metadata belum tersedia karena Google Drive API project Service Account belum aktif (`accessNotConfigured`); setelah diaktifkan, verifikasi ulang izin metadata dan tunggu poll monitor.
- [x] Samakan frontend dengan owner-managed default: CTA “Validasi & siapkan deploy”, tanpa approval rutin pada konfigurasi owner-managed, dan FULL_REFRESH dijelaskan sebagai penggantian isi tabel setelah validasi. Jalur review tetap tersedia untuk konfigurasi legacy.
- [ ] Audit dan koreksi panduan/helper yang masih menyajikan approval legacy sebagai langkah umum. Prioritas: `docs/knowledge/16-error-response-import.md`, `23-sheet-format-operasi.md`, `24-sheet-format-contoh.md`, `35-binding-master-langkah.md`, `36-binding-master-pemuatan.md`, serta generator/help frontend; pisahkan owner-managed, legacy, dan blocker integritas.
- [ ] Setelah Google Drive API diaktifkan, verifikasi notifikasi monitor beralih dari `DRIVE_API_NOT_ENABLED` ke pemantauan sukses dan tertutup; uji satu perubahan Sheet terkendali sampai discovery/profiling selesai, termasuk tes warning terbuka diperbarui dan kemudian diakui otomatis.

## Hasil audit ulang dan urutan terdekat

1. **Operasional segera:** 61 notifikasi `DRIVE_API_NOT_ENABLED` masih terbuka pada pemeriksaan production 13 Oktober 2026. Admin Google Cloud perlu mengaktifkan Drive API pada project Service Account; setelah itu uji satu perubahan file dan pastikan discovery/profiling jalan serta peringatan ditutup otomatis.
2. **Panduan pengguna:** beberapa artikel masih menyuruh semua pengguna melewati approval. Perbarui teks dan helper owner-managed versus legacy sebelum menghapus inbox atau endpoint legacy.
3. **Akses dan data lama:** fallback domain+unit aktif hanya bagi sumber yang sudah ditinjau. Yurisdiksi/department kini opsional sebagai restriction eksplisit; tidak ada pembukaan otomatis untuk sumber lama yang belum ditinjau. Migration kompatibilitas mencatat tahap lama dan tindakan lanjut pada audit tanpa mengubah progress. PLATFORM_ADMIN mengelola scope melalui jalur yang diaudit dan tenant-bound. Dry-run/backfill perubahan status dan tes tenant/cache/revoke end-to-end masih perlu diselesaikan konservatif.
4. **Master:** jalur Batch Import ada dan sengaja terpisah dari sync ETL biasa; penyatuan tracking/runtime serta pemetaan referensi opsional dan uji konflik tetap menjadi pekerjaan besar tersisa.
5. **Pembersihan legacy:** inbox/gate reviewer dan migrasi kompatibilitas hanya dihapus setelah bukti sumber/config/import lama dapat dilanjutkan tanpa mengubah audit atau melemahkan tenant/policy boundary.

## Blocker yang jangan dihapus

Jangan melewati tenant isolation, autentikasi, validasi role admin, sumber tidak terbaca, profil/header stale, schema/data invalid, duplicate business key, PII/secret handling, idempotency, database constraint, atau audit. Ini pemeriksaan integritas dan keamanan, bukan approval birokratis.

## Risiko dan urutan rollout

Perubahan default akses berisiko membuka data lama; backfill harus konservatif dan policy lama tidak boleh diam-diam dilonggarkan. Owner workflow ON tidak mengubah assignment domain/unit, access status, tenant boundary, atau approval registrasi sumber. Pertahankan endpoint/status legacy untuk record lama tanpa memalsukan keputusan reviewer. FULL_REFRESH hanya mengganti isi data setelah lulus validasi dan tidak mengesahkan perubahan schema secara otomatis. Penyatuan runtime master tetap berisiko pada referential integrity dan migrasi schema. Uji per fase di staging; periksa setting runtime dan preview sebelum production. Backend `d76f897` dan frontend `6986666` telah terpasang; perubahan akses/master berikutnya tetap memerlukan rollout bertahap.

## Review ulang sebelum tiap fase dianggap selesai

- Apakah owner dapat menyelesaikan alur dari sumber baru sampai tabel aktif tanpa inbox approval rutin?
- Apakah sumber lama dan keputusan audit tetap dapat dibaca setelah migrasi?
- Apakah akses domain/unit default bekerja dan DENY/tenant boundary tetap menang?
- Apakah deploy menolak snapshot stale, mapping invalid, konflik schema, dan business key ganda?
- Apakah master dan non-master terlihat dalam tracking yang sama serta mempunyai bukti hasil yang bisa ditelusuri?
- Apakah ada endpoint legacy yang masih dapat memblokir UI atau sebaliknya melewati validasi?
