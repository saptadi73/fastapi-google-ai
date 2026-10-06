---
id: contoh-isian-master-dan-analitik
title: Contoh pengisian master data dan pertanyaan dashboard
summary: Contoh master cabang, business key, label, relasi transaksi, metrik, dan pertanyaan bahasa alami.
routes: ["/masters", "/masters/*", "/workspace", "/dashboard", "/chat"]
audiences: ["*"]
source: docs/CONTOH_ISIAN_APLIKASI.md
---
Contoh fiktif: sebuah tab `Cabang` berisi kode dan nama cabang yang dipakai berulang oleh transaksi penjualan. Tab ini dapat diklasifikasikan MASTER. Registry master dapat diberi kode `cabang` dan nama `Master Cabang`; contoh field: `kode_cabang` bertipe teks dan wajib, `nama_cabang` bertipe teks sebagai label, serta `wilayah` bertipe teks bila tersedia. Business key contoh adalah `kode_cabang`, bukan nama cabang yang bisa berubah. Kebijakan import master harus dipilih sesuai sumber otoritatif dan cara organisasi mengizinkan penambahan atau perubahan record.

Tab `Penjualan` berisi `tanggal`, `kode_cabang`, `nomor_transaksi`, dan `nilai_penjualan`. Tab ini NON_MASTER. Kolom `kode_cabang` direlasikan ke master Cabang melalui binding yang disetujui; sistem menyimpan identitas record referensi secara internal. Bila kode cabang tidak ditemukan atau ambigu, batch import perlu pertanyaan atau perbaikan sebelum apply.

Pada produk semantik, contoh dimensi adalah `tanggal` dan `cabang`; contoh metrik adalah `total_penjualan` dari jumlah nilai penjualan. Pengguna dashboard dapat bertanya: `Tampilkan total penjualan per cabang bulan ini` atau `Bandingkan total penjualan per bulan di Jawa Timur tahun ini`. Sebutkan ukuran, dimensi, periode, dan wilayah untuk mengurangi ambiguitas. Dashboard hanya menampilkan data yang diizinkan untuk akun tersebut. Contoh ini menjelaskan konsep; nama field aktual harus mengikuti header dan konfigurasi dataset yang benar.

