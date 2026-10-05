---
id: dashboard-dan-bahasa-alami
title: Mencari data dan membuat chart dengan bahasa alami
summary: Cara menyusun pertanyaan NL2SQL, memilih produk data, dan menampilkan hasil sebagai tabel atau chart.
routes: ["/dashboard", "/chat"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Dashboard hanya menggunakan produk data aktif yang dapat diakses oleh akun pengguna. Tulis pertanyaan dalam bahasa alami dengan menyebutkan ukuran, dimensi, periode, lokasi, dan produk data bila diperlukan. Contoh: "Tampilkan total penjualan per cabang bulan ini", "Bandingkan nilai penjualan dan jumlah transaksi per bulan selama satu tahun", atau "Tampilkan 10 produk dengan penjualan tertinggi".

Jika pertanyaan ambigu, aplikasi meminta klarifikasi atau menawarkan template yang sesuai. Pengguna tidak perlu menulis SQL. Setelah hasil tersedia, pilih tampilan tabel, bar, line, pie, atau gabungan yang cocok dengan struktur data. Chart membutuhkan dimensi sebagai label dan satu atau lebih nilai numerik.

Jika data tidak muncul, periksa apakah job dan batch terakhir sukses, konfigurasi sudah active, produk mempunyai dimensi dan metrik, serta policy akses mencakup pengguna. Perjelas periode dan ruang data pada pertanyaan. Hasil tetap mengikuti pembatasan role, yurisdiksi, data source, row scope, dan field sensitif.

