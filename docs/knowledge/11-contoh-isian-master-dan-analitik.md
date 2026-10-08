---
id: contoh-isian-master-dan-analitik
title: Contoh pengisian master data dan pertanyaan dashboard
summary: Contoh master cabang, business key, label, relasi transaksi, metrik, dan pertanyaan bahasa alami.
routes: ["/masters", "/masters/*", "/workspace", "/sources/*", "/dashboard", "/chat"]
audiences: ["*"]
source: docs/CONTOH_ISIAN_APLIKASI.md
---
Contoh fiktif: sebuah tab `Cabang` berisi kode dan nama cabang yang dipakai berulang oleh transaksi penjualan. Tab ini dapat diklasifikasikan MASTER. Registry master dapat diberi kode `cabang` dan nama `Master Cabang`; contoh field: `kode_cabang` bertipe teks dan wajib, `nama_cabang` bertipe teks sebagai label, serta `wilayah` bertipe teks bila tersedia. Business key contoh adalah `kode_cabang`, bukan nama cabang yang bisa berubah. Kebijakan import master harus dipilih sesuai sumber otoritatif dan cara organisasi mengizinkan penambahan atau perubahan record.

Tab `Penjualan` berisi `tanggal`, `kode_cabang`, `nomor_transaksi`, dan `nilai_penjualan`. Tab ini NON_MASTER. Di Workspace ETL, pilih tab yang sudah diprofiling lalu buka **Atur referensi master**. Buat binding kolom sumber `kode_cabang` ke master Cabang, field `kode_cabang`, versi approved yang aktif. Field tujuan harus berisi nilai yang unik dan stabil; field business key biasanya pilihan yang tepat. Tidak perlu mengisi UUID di Sheet. Setelah binding disimpan dan disetujui reviewer, sistem menyelesaikan nilai kode ke identitas record master internal saat proses import.

Tombol **Muat rekomendasi** dapat mengusulkan relasi dari kemiripan nama. Contohnya, header `Kode Produk` dapat menemukan field `product_code` melalui normalisasi snake_case dan padanan `kode/code`, `produk/product`. Hasil memperlihatkan confidence dan apakah field adalah business key, tetapi tidak menganalisis nilai baris. Pastikan nilai kode benar-benar cocok dan unik; jangan menyetujui hanya berdasarkan skor.

Untuk contoh produk, kolom sumber `Kode Produk` dengan nilai `SKU-001` dipetakan ke field `product_code` pada master Produk yang memiliki tepat satu record bernilai `SKU-001`. Pilih `MANY_TO_ONE` bila banyak transaksi dapat merujuk produk yang sama, dan tandai wajib bila setiap baris harus mempunyai referensi. Buat batch import baru sesudah binding approved. Nilai yang tidak ditemukan atau cocok ke lebih dari satu record perlu diselesaikan pada review batch, bukan dipilih otomatis. Binding mencari satu field master; untuk business key gabungan, gunakan satu kode unik yang juga tersedia di kolom sumber.

Pada produk semantik, contoh dimensi adalah `tanggal` dan `cabang`; contoh metrik adalah `total_penjualan` dari jumlah nilai penjualan. Pengguna dashboard dapat bertanya: `Tampilkan total penjualan per cabang bulan ini` atau `Bandingkan total penjualan per bulan di Jawa Timur tahun ini`. Sebutkan ukuran, dimensi, periode, dan wilayah untuk mengurangi ambiguitas. Dashboard hanya menampilkan data yang diizinkan untuk akun tersebut. Contoh ini menjelaskan konsep; nama field aktual harus mengikuti header dan konfigurasi dataset yang benar.

