---
id: identitas-dataset-dari-file-tab
title: Nama bisnis dan kode produk data dari nama file Google Sheet dan tab
summary: Mengisi identitas dataset otomatis, aturan tanda baca, batas panjang, dan menjaga edit pengguna.
routes: ["/workspace", "/configurations/*"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/PANDUAN_REVIEW_ETL.md
---
Draft manual mengisi Nama dataset/Nama bisnis dan Kode analitik/Kode produk data
dari nama file Google Sheet pada profiling dan nama tab terpilih. Tidak perlu
menyalin ulang dari lembar kerja. Nama sumber terdaftar tidak diubah.

Pada review konfigurasi lama atau draft AI, tombol Gunakan nama file dan tab
memakai saran yang terlihat. Isian tersimpan tidak ditimpa otomatis. Tombol hanya
mengubah draft lokal, belum menyimpan/approve/deploy dan tidak mengubah nama tabel.
Periksa lalu Simpan draft seperti biasa. Pada profil lama yang belum menangkap
nama file asli, aplikasi menampilkan fallback nama sumber terdaftar. Profiling
ulang menangkap nama file asli; tidak otomatis mengubah identitas produk aktif.

Nama bisnis mempertahankan tanda baca yang valid, termasuk titik, slash, kurung
dan ampersand. Karakter kontrol menjadi spasi, spasi berulang dirapikan, maksimal
200 karakter. Kode produk hanya huruf ASCII, angka dan underscore, harus diawali
huruf, maksimal 63 karakter. Saran memakai huruf kecil; tanda/karakter lain
menjadi underscore, underscore berulang dirapikan. Awalan angka memerlukan
prefix dataset_. Nama tab tetap disertakan saat pemendekan saran.

Contoh file Keluhan KAN Jabung 2026 dan tab REKAP JENIS KELUHAN menjadi nama
bisnis Keluhan KAN Jabung 2026 / REKAP JENIS KELUHAN dan kode
keluhan_kan_jabung_2026_rekap_jenis_keluhan. Saran dapat diedit. Nama yang sama
setelah normalisasi belum tentu unik; konflik kode produk antar-tab tetap
ditolak saat deploy, bukan mengganti produk lain diam-diam.
