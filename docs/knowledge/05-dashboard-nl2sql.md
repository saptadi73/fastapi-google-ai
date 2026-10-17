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

Halaman **Katalog data** menampilkan seluruh Data Product aktif yang dapat ditemukan akun, nama tabel database dan semantic view, tautan ke spreadsheet/tab sumber, deskripsi, dimensi, metrik, dan saran kelengkapan metadata. Pemilik/steward dengan hak edit dapat membuka detail produk lalu **Edit metadata semantik untuk NL2SQL**. Bila tabel database dan nilai datanya sudah benar, ini cara utama dan paling ringkas untuk memperbaiki kemampuan pencarian: editor mengubah nama/deskripsi produk, deskripsi/nama bisnis/sinonim kolom publik, dimensi, dan definisi metrik tanpa profiling, mengulang ETL, atau mengubah data fisik. Simpanan menaikkan versi semantic dan tercatat di audit. Jika ada konflik versi, muat ulang detail sebelum mengedit ulang.

Deskripsi dataset sebaiknya menjelaskan cakupan, grain, periode, dan arti nilai. Beri nama bisnis dan deskripsi yang jelas pada kolom; definisikan metrik dengan rumus, unit, agregasi, dan sinonim yang dipakai pengguna; gunakan dimensi untuk filter/pengelompokan. Hindari menjumlahkan persentase kecuali definisi bisnis memang mengizinkan. Kolom sensitif tidak tersedia untuk metadata katalog. Jika pertanyaan meminta ukuran yang belum didefinisikan sebagai metrik, NL2SQL harus meminta klarifikasi dan tidak menggantinya dengan kolom yang hanya mirip namanya. Jika perlu analisis lintas produk, tetapkan join relationship hanya setelah kolom kunci, keunikan, dan kardinalitas diverifikasi.

Gunakan Katalog data untuk perubahan makna/metadata yang tidak mengubah struktur output. Gunakan Workspace ETL, discovery/profiling, dan revisi konfigurasi hanya bila header/struktur, tipe, transformasi, aturan kualitas, atau strategi pemuatan memang perlu berubah. Jika hanya nilai sumber yang dikoreksi, koreksi Sheet lalu sync agar nilai target ikut diperbarui; profiling tidak diperlukan selama header dan mapping tetap sama. Saran di Katalog data adalah checklist kelengkapan, bukan perubahan otomatis. Relasi join bersifat opsional dan hanya dibuat sesuai kebutuhan analitik.

Untuk kolom sumber baru, profiling ulang pada sumber yang sama sebelum membuat draft mapping baru. Perubahan struktur tabel target non-master yang sudah deployed memerlukan migrasi yang direview; approval ETL tidak otomatis menambah kolom database. Versi ACTIVE tidak dapat diedit langsung.

Query waktu membutuhkan tanggal lengkap dan dimensi waktu yang benar. Label `w1`, `w2`, `january`, atau `february` tidak menyatakan tahun/tanggal dengan pasti. Minta pemilik sumber melengkapi tanggal kejadian aktual untuk transaksi atau batas mulai/selesai untuk rekap periode, berdasarkan tahun dan kalender minggu yang disepakati. Jangan mengubah semua record Januari menjadi transaksi tanggal 1 Januari. Map sebagai date, validasi dry-run, lalu tentukan dimensi tanggal acuan untuk filter. Default periode metrik adalah jumlah hari pada dimensi tanggal/waktu; bukan pengurai label bulan. Query overlap periode atau pengelompokan kalender tidak boleh dijanjikan tanpa dukungan plan/katalog yang sesuai.
