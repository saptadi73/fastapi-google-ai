---
id: perintah-nl2sql-tersimpan
title: Simpan dan jalankan ulang perintah NL2SQL
summary: Cara menghemat pemanggilan AI dengan menyimpan hasil NL2SQL dan membandingkan beberapa data product.
routes: ["/chat", "/saved-queries", "/dashboard"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Setelah pertanyaan di Chat data berhasil, pilih **Simpan perintah**. Perintah akan muncul di menu **Analitik > Perintah tersimpan**. Cari dengan nama, pertanyaan, deskripsi, atau kode data product; gunakan pagination untuk daftar panjang. Pemilik perintah dapat mengubah nama/deskripsi, menjalankan, atau menghapusnya. Penghapusan perintah tidak menghapus data product maupun hasil ETL.

Menjalankan ulang perintah tersimpan tidak memanggil AI. Aplikasi menyimpan plan query yang tervalidasi dan SQL parameterized untuk pemeriksaan, lalu menyusun ulang query dari plan tersebut. Aplikasi tetap memeriksa hak akses terbaru, row scope, keamanan read-only, estimasi biaya query, timeout, dan batas baris pada setiap eksekusi. Jika izin atau katalog berubah, perintah bisa ditolak sampai pertanyaannya dibuat dan disimpan kembali dari Chat data. SQL yang tampil adalah pratinjau; ia tidak dieksekusi sebagai teks SQL bebas.

Pilih 2 sampai 4 perintah untuk **Jalankan perbandingan**. Setiap data product ditanya secara terpisah dengan akses masing-masing; hasil kemudian dijajarkan ke tabel gabungan menurut kategori/periode yang dipilih pada tiap query. Pilih satu metrik per hasil dan kategori yang memiliki nilai sepadan. Grafik mendukung **Multi bar** dan **Bar + line**.

Perbandingan ini bukan join database. Sebelum menafsirkan grafik, samakan rentang waktu, grain (hari/bulan/tahun), definisi metrik, satuan, dan format label periode. Contoh: `2026-01` cocok dijajarkan dengan `2026-01`; label bulan tanpa tahun dapat menggabungkan periode yang berbeda. Bila perlu relasi record-level atau filter satu tabel berdasarkan nilai tabel lain, buat relationship terverifikasi dan gunakan query lintas produk yang didukung, bukan perbandingan agregat ini.
