---
id: konfigurasi-import-dan-operasi
title: Konfigurasi ETL, batch import, dan operasi
summary: Approval metadata sumber gabungan, sync manual langsung, lokasi temuan, audit trail, dan perubahan schema.
routes: ["/sources", "/workspace", "/etl-review/*", "/configurations/*", "/import-reviews", "/import-reviews/*", "/release-approvals", "/imports/*", "/jobs", "/quality", "/data-catalog"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/PANDUAN_REVIEW_ETL.md
---
Konfigurasi ETL menetapkan mapping, tipe, transformasi, DQ, key, strategi load dan semantic. Tetapkan periode/watermark sesuai sumber dan validasi sampai tanpa blocker.

Di review ETL, tujuh langkah menunjukkan kemajuan dan blocker. Owner-managed tidak perlu centang checklist approval pada tiap bagian; cukup tinjau mapping dan hasil dry-run, lalu validasi. Workflow legacy tetap dapat menampilkan checklist review. Langkah terakhir membedakan validasi tersimpan/diajukan, siap diproses, konfigurasi aktif, dan job gagal. Indikator ini hanya panduan UI; dry-run, fingerprint sumber, bukti schema, dan validasi server tetap menjadi sumber keputusan.

Pada daftar sumber, kolom Approval IT adalah pemeriksaan awal registrasi sumber dan klasifikasi tab, bukan gate konfigurasi/deploy yang berulang. Workflow owner-managed yang tervalidasi diteruskan pemilik melalui deploy dan sync. Persetujuan tayang dan approval batch hanya digunakan untuk item legacy atau jalur yang secara eksplisit masih menampilkannya.

Jika deploy gagal dengan CONFIGURATION_INVALID, gunakan lokasi baris, field, dan kode masalah pada pesan job untuk memperbaiki sumber atau mapping. Aturan kualitas yang menghentikan batch menunjukkan rule/field/baris; threshold menunjukkan persentase dan batas. Pesan sengaja tidak menampilkan nilai sel. Jalankan Dry-run lagi setelah perbaikan; jangan mengulang deploy pada snapshot yang sama tanpa mengatasi blocker.

Tambah/rename kolom di Google Sheets, lalu profiling ulang sumber/tab yang sama. Workspace tidak menulis data ke Sheet. APPROVED/ACTIVE/REJECTED immutable: clone jika header lama ada, atau buat draft terkini. Fingerprint berubah membuat draft lama stale. Langkah Validasi & persetujuan menampilkan Preview perubahan schema: schema lama/baru (kolom, tipe, nullability, key), view/dependency, operasi, record lama, contoh tanggal dan blocker. Centang konfirmasi schema sebelum submit; approval mengikat fingerprint schema/data. Worker memigrasikan perubahan aman saat deploy, bukan saat review. Jangan hapus tabel/registrasi ulang.

Label bulan/minggu memerlukan tahun/kalender, bukan perubahan tipe saja. Jangan menebak tanggal dari bulan/minggu. Gunakan tanggal kejadian atau periode mulai dan selesai sesuai grain; uji parser dan dimensi waktu.

Master memakai definisi/binding, bukan ETL biasa. Tambah field nullable: approve, deploy-storage ulang, record lama null; review binding versi master/profil terbaru sebelum import. Field wajib baru atau perubahan key/tipe/nullability/rename/drop perlu migrasi khusus.

Review ulang start_date/end_date: tanggal native Sheets berupa angka serial (46023 = 2026-01-01, 46053 = 2026-01-31). Map target date dan tambahkan parse_date_id dan pilih Format nilai tanggal = Serial Google Sheets pada Cleansing untuk kedua kolom; pola tanggal boleh kosong untuk serial, text tanggal memakai pola strptime sesuai sumber. Simpan draft, Dry-run ulang, baca kolom/baris TYPE_OR_NULL_ERROR, isi checklist lalu Ajukan review. Jangan nullable/hapus record untuk menutupi format salah. Jaga nama target lama untuk revisi dataset yang sama kecuali perpindahan direview; draft manual baru bukan clone seluruh konfigurasi lama.

View mengikuti ID tab, bukan tabel; perpindahan/proyeksi direview. Worker: nullable baru (record lama null), tipe pada tabel kosong, bigint serial menjadi date dengan parse_date_id, date_input_format=GOOGLE_SHEETS_SERIAL dan semua nilai valid; angka bigint bukan bukti tanggal. DDL/konversi/hash transaksional; view/ACL dijaga tanpa DROP CASCADE. Rename/drop fisik, key, kolom wajib baru pada tabel berisi data/dependency tidak aman diblokir. SCHEMA_MIGRATION_STALE: review preview baru; SCHEMA_REVIEW_REQUIRED: clone versi tanpa bukti schema; SCHEMA_MIGRATION_BLOCKED: selesaikan blocker. Cocokkan configuration_id job/versi APPROVED. Deploy SUCCEEDED baru sync; /guide#review-ulang-tanggal.

Submit untuk reviewer berbeda dari pembuat. Jika aturan rilis aktif, IT dan approver tiap unit menyetujui revisi/snapshot yang sama pada Persetujuan tayang. IT memeriksa skema/mapping, DQ, keamanan/akses. Semua kelompok setuju sebelum deploy. Tanpa aturan rilis, review konfigurasi biasa berlaku. Revisi/snapshot/aturan berubah membatalkan keputusan lama; penolakan perlu versi baru/revisi aturan diaudit. Rollback tetap memeriksa aturan rilis kini. Profil/taxonomy/master/binding berubah dapat membuat konfigurasi stale.

Reviewer terpisah dapat menyetujui konfigurasi, metadata PENDING dan akses melalui policy SOURCE APPROVED dalam satu transaksi. Gate rilis dan izin pembaca tetap berlaku.

Pilih sumber di Sumber & tracking atau Workspace, tekan Sync manual / Sync manual data, lalu Jalankan sync sekarang. Untuk konfigurasi owner-managed aktif dengan akses POLICY_APPROVED, sinkronisasi memvalidasi sumber, mapping, kualitas, preview konflik, dan referensi sebelum apply; tidak ada approval konfigurasi/rilis rutin. `FULL_REFRESH` mengganti seluruh baris target dalam transaksi setelah semua baris lolos validasi. Jika validasi gagal, data aktif sebelumnya tetap utuh. Full refresh tidak mengizinkan perubahan skema destruktif. Konflik bisnis, drift, PII atau error dapat tetap menghentikan pekerjaan dan memberi langkah perbaikan. Periksa SUCCEEDED dan Baris dimuat per tab, bukan hanya job induk. Riwayat dan audit tetap tersedia.

Katalog: Buka Google Sheet/Buka sumber untuk role operasional. Versi aktif tampil selama revisi jika lolos akses; Sedang diperbarui menandai job/revisi/drift/snapshot/batch belum selesai. Terakhir aktif dari audit aktivasi/pemuatan sukses, timestamp keduanya terpisah. Perubahan file dipantau berkala melalui Google Drive modifiedTime, bukan live push. Saat berubah, status sumber menjadi CHANGE_DETECTED, audit mencatat deteksi oleh Sistem, lalu discovery membaca ulang daftar tab dan menjalankan profiling. Jumlah sumber per siklus dibatasi. Project Google Cloud milik Service Account harus mengaktifkan Google Drive API dan Service Account harus dapat membaca metadata Drive. Bila Google mengembalikan `accessNotConfigured`, notifikasi `SOURCE_MONITOR_UNAVAILABLE` sekarang secara spesifik meminta admin project mengaktifkan Google Drive API (`DRIVE_API_NOT_ENABLED`); bila API aktif tetapi izin metadata kurang, steward diminta memeriksa izin Drive. Discovery/profiling manual tetap dapat digunakan saat pemantauan belum aktif.

Notifikasi Google Sheet berubah tetap terbuka bila profiling gagal, schema berubah, atau konfigurasi/review lama perlu diperiksa. Tanpa konfigurasi aktif/draft yang menunggu, notifikasi ditutup setelah discovery dan profiling berhasil. Jika ada konfigurasi, perbarui draft, validasi ulang, dan ajukan review; notifikasi ditutup setelah review baru lolos. Review/deploy lama tetap stale jika memakai snapshot sebelum perubahan. Audit `source.external_change_detected`, `source.discovered`, `source.profiled`, dan stage job menampilkan actor Sistem. Audit tindakan dalam aplikasi menyimpan user pelaku; Google Drive modifiedTime tidak mengidentifikasi editor eksternal.

**Batch import** menyediakan pencarian sumber dan status proses; pilih sumber lalu tab terklasifikasi. **Persetujuan tayang** hanya menampilkan konfigurasi yang ditugaskan kepada approver, dengan pencarian dan detail keputusan.
# Konfirmasi temuan AI

NEEDS_INPUT = Menunggu tindakan, bukan worker berjalan. Lihat detail berikon mata pada tracking/hasil ETL/sync/audit membuka keterangan, kode, baris asli Sheet saat snapshot (termasuk header), kolom dan tautan batch. Audit menyimpan maksimal 20 lokasi tanpa nilai mentah; Muat temuan berikutnya memaginasi pertanyaan. Riwayat kegagalan lama bukan hasil terbaru. Membuka detail tidak sync/approve.

Temuan AI_REVIEW, termasuk batch lama, dapat dijawab KEEP_ORIGINAL dengan alasan verifikasi yang diaudit. Dugaan PII/salah mapping perlu pemilik data; error teknis tidak bisa dilewati. CORRECT_SOURCE meminta perbaikan Sheet dan snapshot baru. Setelah semua jawaban, AI COMPLETE dan validasi selesai tanpa blocker, batch siap. Sync manual kembali dapat memuat batch NON_MASTER siap berdasarkan approval konfigurasi aktif; batch biasa/master tetap preview, approval, Apply. Jawaban saja tidak memuat record.

DDL, view, konversi, hash, aktivasi dan audit/status sukses satu transaksi; gagal mempertahankan kondisi lama. Alasan UI/audit dicatat setelah rollback; retry memeriksa fingerprint.

Pada konfigurasi owner-managed, data owner/steward terdaftar atau PLATFORM_ADMIN dapat deploy dan rollback versi yang sudah divalidasi setelah konfirmasi. Backend memverifikasi identitas pelaku dan snapshot ulang. Konfigurasi legacy tetap memerlukan reviewer serta release approval yang berlaku.

Text/varchar: trim otomatis sebelum DQ/AI/load; spasi tengah dan nol depan tetap. Duplikat AI diverifikasi dari data asli; lihat panduan cleansing text.
