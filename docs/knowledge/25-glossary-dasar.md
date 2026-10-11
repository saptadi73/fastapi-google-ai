---
id: istilah-teknis-dasar
title: "Istilah teknis bahasa sederhana - Dasar pencatatan data"
summary: "Tabel penjelasan untuk non teknis: Dataset, Record, Grain, Business key, Primary key, Schema, Tipe data, Nullable"
routes: ["/guide"]
audiences: ["*"]
source: docs/ISTILAH_TEKNIS.md
---
Bayangkan Google Sheet sebagai buku pencatatan bisnis. Istilah berikut menjelaskan isi buku, aturan pencatatan dan cara aplikasi mengolahnya. Contoh memakai keluhan pelanggan dan rekap KPI.

| Istilah | Arti sederhana | Contoh bisnis |
| --- | --- | --- |
| **Dataset** | Sekumpulan data tentang satu hal. | Daftar keluhan pelanggan selama 2026. |
| **Record** | Satu catatan, biasanya satu baris. | Satu keluhan dengan kode KLH-001. |
| **Grain** | Satu baris mewakili apa? Ini menentukan tingkat rincian data. | Satu baris per keluhan berbeda dari satu baris rekap per unit per bulan. |
| **Business key** | Kode atau gabungan informasi yang membedakan setiap catatan bisnis; harus stabil, unik dan tidak kosong. | keluhan_id; untuk rekap, gabungan unit + indikator + periode. |
| **Primary key** | Identitas utama untuk menunjuk satu record di database; dapat berbeda dari kode bisnis. | ID unik internal untuk record keluhan KLH-001. |
| **Schema** | Rancangan kolom, tipe dan aturan tabel. | ID wajib terisi, tanggal bertipe date, dan jumlah bertipe angka. |
| **Tipe data** | Jenis isi yang diperbolehkan pada kolom. | Tanggal untuk event_date, teks untuk kode 0012, angka untuk jumlah. |
| **Nullable** | Apakah nilai pada kolom boleh kosong? | Tanggal penyelesaian boleh kosong selama keluhan belum selesai; ID tetap wajib. |
