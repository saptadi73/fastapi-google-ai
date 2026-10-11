---
id: dashboard-dan-bahasa-alami
title: Mencari data dan membuat chart dengan bahasa alami
summary: Cara menyusun pertanyaan NL2SQL, memilih produk data, dan menampilkan hasil sebagai tabel atau chart.
routes: ["/dashboard", "/chat", "/data-catalog"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Dashboard hanya menggunakan produk data aktif yang dapat diakses oleh akun pengguna. Tulis pertanyaan dalam bahasa alami dengan menyebutkan ukuran, dimensi, periode, lokasi, dan produk data bila diperlukan. Contoh: "Tampilkan total penjualan per cabang bulan ini", "Bandingkan nilai penjualan dan jumlah transaksi per bulan selama satu tahun", atau "Tampilkan 10 produk dengan penjualan tertinggi".

Jika pertanyaan ambigu, aplikasi meminta klarifikasi atau menawarkan template yang sesuai. Pengguna tidak perlu menulis SQL. Setelah hasil tersedia, pilih tampilan tabel, bar, line, pie, atau gabungan yang cocok dengan struktur data. Chart membutuhkan dimensi sebagai label dan satu atau lebih nilai numerik.

Jika data tidak muncul, periksa apakah job dan batch terakhir sukses, konfigurasi sudah active, produk mempunyai dimensi dan metrik, serta policy akses mencakup pengguna. Perjelas periode dan ruang data pada pertanyaan. Hasil tetap mengikuti pembatasan role, yurisdiksi, data source, row scope, dan field sensitif.

Halaman **Katalog data** menampilkan seluruh Data Product aktif yang dapat ditemukan akun, nama tabel database dan semantic view, tautan ke spreadsheet/tab sumber, deskripsi, dimensi, metrik, dan saran kelengkapan metadata. Deskripsi dataset sebaiknya menjelaskan cakupan, grain, periode, dan arti nilai. Beri nama bisnis yang jelas pada kolom; definisikan metrik dengan rumus, unit, dan sinonim yang dipakai pengguna; gunakan dimensi untuk filter/pengelompokan. Jika perlu analisis lintas produk, tetapkan join relationship hanya setelah kolom kunci, keunikan, dan kardinalitas diverifikasi.

Perbaiki nilai atau header sumber di Google Sheet. Perbaiki mapping, tipe, transformasi, dan struktur output melalui revisi konfigurasi ETL yang melewati review, approval, dan deploy. Perbarui deskripsi, dimensi, metrik, dan sinonim melalui semantic catalog/Governance. Saran di Katalog data adalah checklist kelengkapan, bukan perubahan otomatis. Relasi join bersifat opsional dan hanya dibuat sesuai kebutuhan analitik.

Untuk kolom sumber baru, profiling ulang pada sumber yang sama sebelum membuat draft mapping baru. Perubahan struktur tabel target non-master yang sudah deployed memerlukan migrasi yang direview; approval ETL tidak otomatis menambah kolom database. Versi ACTIVE tidak dapat diedit langsung.

Query waktu membutuhkan tanggal lengkap dan dimensi waktu yang benar. Label `w1`, `w2`, `january`, atau `february` tidak menyatakan tahun/tanggal dengan pasti. Minta pemilik sumber melengkapi tanggal kejadian aktual untuk transaksi atau batas mulai/selesai untuk rekap periode, berdasarkan tahun dan kalender minggu yang disepakati. Jangan mengubah semua record Januari menjadi transaksi tanggal 1 Januari. Map sebagai date, validasi dry-run, lalu tentukan dimensi tanggal acuan untuk filter. Default periode metrik adalah jumlah hari pada dimensi tanggal/waktu; bukan pengurai label bulan. Query overlap periode atau pengelompokan kalender tidak boleh dijanjikan tanpa dukungan plan/katalog yang sesuai.
