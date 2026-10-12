---
id: istilah-teknis-operasi
title: "Istilah teknis bahasa sederhana - Proses aplikasi dan pemuatan"
summary: "Tabel penjelasan untuk non teknis: ETL, Discovery / Temukan tab, Preview, Approval, Deploy, Sync, APPEND, UPSERT, FULL_REFRESH, Freshness, Watermark"
routes: ["/guide"]
audiences: ["*"]
source: docs/ISTILAH_TEKNIS.md
---
Bayangkan Google Sheet sebagai buku pencatatan bisnis. Istilah berikut menjelaskan isi buku, aturan pencatatan dan cara aplikasi mengolahnya. Contoh memakai keluhan pelanggan dan rekap KPI.

| Istilah | Arti sederhana | Contoh bisnis |
| --- | --- | --- |
| **ETL** | Mengambil, mengolah, lalu memasukkan data ke database. | Membaca Sheet, merapikan/memvalidasi nilai, kemudian memuat data. |
| **Discovery / Temukan tab** | Memeriksa tab yang sekarang tersedia di Google Sheet. | Setelah tab dihapus/di-rename, jalankan Temukan tab untuk memperbarui daftar aplikasi. |
| **Preview** | Melihat rencana dan dampak perubahan sebelum dijalankan. | Meninjau kolom baru, contoh konversi tanggal dan blocker sebelum persetujuan. |
| **Approval** | Persetujuan reviewer terhadap versi yang diperiksa. | Reviewer berwenang berbeda dari pembuat menyetujui konfigurasi; bukan izin baca otomatis. |
| **Deploy** | Mengaktifkan konfigurasi yang disetujui dan menyiapkan struktur database yang diperlukan. | Versi menjadi ACTIVE setelah deploy sukses; cek pemuatan data sebagai tahap terpisah. |
| **Sync** | Membaca dan memproses pembaruan sumber sesuai konfigurasi aktif. | Owner-managed memvalidasi sumber, mapping, akses, kualitas, dan konflik sebelum memuat; tidak meminta approval rutin kedua. |
| **APPEND** | Menambahkan catatan baru. | Cocok untuk kejadian baru; snapshot/koreksi tanpa key yang tepat bisa terhitung ganda. |
| **UPSERT** | Memperbarui catatan jika key sudah ada, atau menambahkan jika belum ada. | Koreksi rekap unit/indikator/periode yang sama memperbarui record tersebut. |
| **FULL_REFRESH** | Mengganti seluruh isi baris target dengan snapshot lengkap sumber yang valid. | Seluruh baris divalidasi sebelum transaksi penggantian; jika ada error data lama tetap utuh. Perubahan skema tetap terpisah. |
| **Freshness** | Seberapa mutakhir data yang tersedia. | Dimuat hari ini belum tentu menggambarkan kondisi hari ini; lihat periode dan data_as_of_at. |
| **Watermark** | Penanda sampai mana data sudah diproses untuk pengambilan bertahap sesuai konfigurasi. | Nomor/tanggal checkpoint pemuatan; bukan penentu arti periode bisnis. |
