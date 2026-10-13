---
id: konfigurasi-import-dan-operasi
title: Konfigurasi ETL, batch import, dan operasi
summary: Cara owner memvalidasi, deploy, sync, dan menelusuri blocker; review rutin hanya untuk item legacy.
routes: ["/sources", "/workspace", "/etl-review/*", "/configurations/*", "/import-reviews", "/import-reviews/*", "/release-approvals", "/imports/*", "/jobs", "/quality", "/data-catalog"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/PANDUAN_REVIEW_ETL.md
---
Konfigurasi menentukan mapping kolom, tipe, cleansing, kualitas, key, strategi load, dan semantic. Mulai dengan draft manual dari template hasil profiling untuk kontrol yang jelas; rekomendasi AI bersifat opsional bila tersedia.

Approver memeriksa spreadsheet dan semua tab saat registrasi sumber, termasuk klasifikasi MASTER/NON_MASTER dan risiko sumber ganda. Sesudah lolos pemeriksaan awal, data owner/steward mengelola konfigurasi, validasi, deploy, serta sync tanpa approval rutin kedua. Konfigurasi atau batch legacy dapat tetap menampilkan reviewer; ikuti gate yang tampil pada item tersebut.

**Alur NON_MASTER:** pilih sumber/tab, siapkan mapping dan aturan, jawab pertanyaan, jalankan dry-run, perbaiki blocker, lalu Validasi & siapkan deploy. Pemilik data yang tercatat dapat Deploy. Setelah aktif, Sync manual menjalankan pemeriksaan sumber, akses, kualitas, AI bila dikonfigurasi, dan konflik sebelum memuat. `FULL_REFRESH` mengganti semua baris dalam transaksi setelah validasi; bila gagal, data aktif lama dipertahankan.

**Alur MASTER:** kelola definisi dan business key pada Registry master, validasi, tinjau rencana lalu deploy storage. Petakan tab MASTER, simpan binding dan jalankan validasi. Buat batch import, selesaikan temuan, jalankan Preview, lalu Apply setelah konfirmasi. Binding valid tidak berarti record sudah dimuat. Untuk item legacy, ikuti reviewer yang masih ditampilkan.

**Jika Google Sheet berubah:** tekan Temukan tab untuk membaca ulang tab, lalu Profiling ulang. Perbarui draft dan mapping berdasarkan profil terbaru, validasi ulang dan deploy. Notifikasi perubahan tetap terbuka jika profiling gagal atau konfigurasi masih perlu diperiksa; owner validation yang berhasil menutupnya pada jalur owner-managed. Sheet tidak dipantau secara live. `DRIVE_API_NOT_ENABLED` berarti admin perlu mengaktifkan Google Drive API pada project service account; profiling manual masih dapat digunakan. `SOURCE_CHANGE_CHECK_DENIED` juga dapat menunjukkan izin metadata Drive belum cukup.

**Temuan dan audit:** `NEEDS_INPUT` berarti batch menunggu tindakan, bukan worker berjalan. Tekan **Lihat detail** berikon mata untuk melihat kode, baris asli saat snapshot, kolom, dan catatan tanpa nilai mentah. Audit trail mencatat tindakan user dan tahap sistem. `KEEP_ORIGINAL` hanya untuk nilai yang diverifikasi pemilik data dengan alasan wajib; error teknis tidak dapat dilewati. Setelah blocker selesai, jalankan validasi/preview atau Sync manual sesuai status.

**Tanggal dan schema:** jangan menebak tanggal dari label `january`, `w1`, atau nama bulan; gunakan tanggal kejadian atau periode mulai dan selesai. Workspace tidak menulis data ke Sheet. Nilai serial Google Sheets seperti `46023` memerlukan `parse_date_id` dan format `GOOGLE_SHEETS_SERIAL`; tipe `date` saja tidak mengubah angka. `TYPE_OR_NULL_ERROR` menunjukkan nilai/tipe gagal. Periksa **Preview perubahan schema** sebelum deploy; `SCHEMA_MIGRATION_STALE` berarti preview sudah usang. Cocokkan `configuration_id` job dengan versi yang diperiksa. Migrasi tidak menjalankan `DROP CASCADE`; rename/drop fisik dan dependency berisiko tetap diblokir. Detail parser ada di panduan review ETL.

Di **Sumber & tracking**, gunakan pencarian dan pagination untuk memilih sumber lalu **Buka sumber**. Tabel tahap per tab menunjukkan discovery, profiling, konfigurasi/binding, approval IT awal, database, dan status kegagalan terakhir. **Approval IT** adalah pemeriksaan registrasi sumber/tab, bukan persetujuan ETL berulang. **Batch Import** juga menyediakan daftar sumber yang dapat dicari.

Di Katalog, produk aktif belum tentu sudah memuat baris. Periksa job dan batch per tab, jumlah baris, timestamp, konfigurasi aktif, binding dependency, dan izin pembaca. Default READ/QUERY menggunakan domain dan business unit pemilik; pemilik dapat membatasi lebih lanjut dengan policy khusus. Akses data terpisah dari approval sumber.

Perubahan skema target, key, kolom wajib, rename/drop fisik, atau dependency berisiko dapat diblokir. Periksa Preview perubahan schema dan blocker; jangan menghapus tabel atau mendaftarkan ulang sumber untuk melewati validasi. Detail teknis perubahan skema ada di [Panduan review ETL](../PANDUAN_REVIEW_ETL.md); istilah dan tindakan error ada di [Tabel error response](../ERROR_RESPONSES.md).
