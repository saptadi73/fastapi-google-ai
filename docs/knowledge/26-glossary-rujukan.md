---
id: istilah-teknis-rujukan
title: "Istilah teknis bahasa sederhana - Rujukan dan persiapan data"
summary: "Tabel penjelasan untuk non teknis: Master data, Taxonomy, Alias, Mapping, Cleansing, Trim, Profiling, Data quality / DQ, Snapshot, Provenance"
routes: ["/guide"]
audiences: ["*"]
source: docs/ISTILAH_TEKNIS.md
---
Bayangkan Google Sheet sebagai buku pencatatan bisnis. Istilah berikut menjelaskan isi buku, aturan pencatatan dan cara aplikasi mengolahnya. Contoh memakai keluhan pelanggan dan rekap KPI.

| Istilah | Arti sederhana | Contoh bisnis |
| --- | --- | --- |
| **Master data** | Daftar rujukan resmi untuk entitas yang dipakai bersama. | Master unit: UNIT-01 = Layanan Anggota, dengan satu kode unik per unit. |
| **Taxonomy** | Daftar kategori atau istilah yang disepakati. | Jenis keluhan: Pelayanan, Produk, Pembayaran; gunakan kode/term baku. |
| **Alias** | Nama lain yang telah diakui untuk istilah yang sama. | Cust Service sebagai alias Layanan Pelanggan setelah diverifikasi. |
| **Mapping** | Menentukan kolom sumber masuk ke kolom tujuan yang mana. | Tanggal Keluhan pada Sheet dipetakan ke event_date. |
| **Cleansing** | Merapikan nilai agar konsisten menurut aturan yang ditinjau. | Meratakan format kategori atau membuang spasi tepi sebelum validasi. |
| **Trim** | Menghapus spasi di awal dan akhir teks; spasi di tengah tetap. | "  UNIT-01  " menjadi "UNIT-01"; otomatis untuk input text/varchar. |
| **Profiling** | Memeriksa kondisi awal data untuk membantu review. | Membaca header, perkiraan tipe, nilai kosong dan dugaan data sensitif; bukan jaminan semua baris valid. |
| **Data quality / DQ** | Pemeriksaan apakah data memenuhi aturan kualitas. | ID tidak kosong/berulang, tanggal valid dan kode unit ditemukan di master. |
| **Snapshot** | Salinan kondisi sumber pada waktu tertentu. | Data Sheet yang dibaca saat review; perubahan setelahnya dapat membuat review kedaluwarsa. |
| **Provenance** | Jejak asal dan cara memperoleh data agar angka dapat ditelusuri. | Sumber pengukuran, metode, waktu pengambilan dan versi koreksi. |
