---
id: contoh-isian-sumber-google-sheet
title: Contoh pengisian pendaftaran sumber Google Sheet
summary: Contoh nama sumber, URL, deskripsi, unit, domain, yurisdiksi, purpose, owner, steward, dan sensitivitas.
routes: ["/workspace", "/sources/*", "/guide"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/CONTOH_ISIAN_APLIKASI.md
---
Contoh berikut fiktif dan mengandaikan admin sudah membuat atribut serta assignment yang diperlukan. Pada Workspace ETL → Hubungkan Google Sheet baru, isi:

| Isian | Contoh | Penjelasan |
|---|---|---|
| Nama sumber | `Penjualan Cabang Jawa Timur` | Nama bisnis yang mudah dikenali. |
| URL spreadsheet | URL Google Sheet asli yang telah dibagikan ke service account sebagai Viewer | Salin dari Google Sheet; contoh teks ini bukan URL yang bisa dipakai. |
| Deskripsi | `Transaksi penjualan harian per cabang untuk analisis bulanan.` | Jelaskan isi, periode, dan kegunaan data. |
| Jadwal otomatis | `Tanpa jadwal` | Pilih preset hanya bila proses memang perlu berjalan berkala. |
| Unit pemilik | `Departemen Keuangan` | Pilih atribut DEPARTMENT yang sesuai assignment aktif. |
| Domain bisnis | `Penjualan` | Pilih atribut BUSINESS_DOMAIN. |
| Yurisdiksi | `Jawa Timur` | Pilih atribut JURISDICTION; jangan memilih cakupan lebih luas tanpa alasan bisnis. |
| Purpose | `Analitik Manajemen` | Pilih PURPOSE resmi untuk penggunaan sumber. |
| Data owner | Pengguna pemilik bisnis yang tersedia pada dropdown | Pemilik keputusan penggunaan dan makna data. |
| Data steward | Pengguna steward yang tersedia pada dropdown | Pengelola kualitas dan definisi data. |
| Sensitivitas | `LOW`, hanya bila memang sesuai klasifikasi organisasi | Pilih `MEDIUM` atau `HIGH` bila konten lebih sensitif. |

Kode sumber, UUID, dan referensi kredensial ditentukan otomatis oleh sistem pada form frontend. Pilihan owner, steward, dan atribut berasal dari tenant aktif, bukan teks bebas. Jika dropdown tidak memiliki pilihan yang diperlukan, minta admin menyiapkan registry/assignment dan periksa izin pendaftar. Setelah disimpan, periksa hasil discovery dan profiling, lalu klasifikasikan setiap tab sebagai MASTER atau NON_MASTER.

