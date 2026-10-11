---
id: istilah-teknis-analitik
title: "Istilah teknis bahasa sederhana - Analitik, ketelitian dan konteks waktu"
summary: "Tabel penjelasan untuk non teknis: Dimensi, Metrik, Agregasi, Data product, Baseline, Gap, Denominator / penyebut, Presisi, Periode data, Waktu pengukuran, Waktu pengambilan"
routes: ["/guide"]
audiences: ["*"]
source: docs/ISTILAH_TEKNIS.md
---
Bayangkan Google Sheet sebagai buku pencatatan bisnis. Istilah berikut menjelaskan isi buku, aturan pencatatan dan cara aplikasi mengolahnya. Contoh memakai keluhan pelanggan dan rekap KPI.

| Istilah | Arti sederhana | Contoh bisnis |
| --- | --- | --- |
| **Dimensi** | Cara mengelompokkan atau membandingkan data. | Menurut unit, bulan atau jenis keluhan. |
| **Metrik** | Ukuran yang dihitung atau dibandingkan berdasarkan definisi bisnis. | Jumlah keluhan, target dan realisasi penyelesaian; kolom angka tidak otomatis menjadi metrik. |
| **Agregasi** | Menggabungkan banyak catatan menjadi ringkasan. | Menjumlahkan keluhan per bulan; rata-rata hanya jika ukuran dan basisnya sesuai. |
| **Data product** | Data yang disiapkan untuk katalog dan analisis sesuai izin pengguna. | Keluhan Pelanggan / Rekap Bulanan; memerlukan produk aktif dan hak baca yang cocok. |
| **Baseline** | Nilai awal yang dipakai sebagai pembanding. | Waktu respons 48 jam sebelum perbaikan; bandingkan dengan metode/periode yang sebanding. |
| **Gap** | Selisih terhadap target dengan arah dan rumus yang disepakati. | Target selesai 100, realisasi 90: kekurangan 10. Untuk batas maksimal keluhan, rumus/arahnya berbeda. |
| **Denominator / penyebut** | Jumlah dasar yang dipakai untuk menghitung rasio atau persentase. | 90 selesai dari 100 kasus = 90%; dari 200 kasus = 45%. Jangan menjumlahkan persen. |
| **Presisi** | Ketelitian/resolusi pencatatan atau pengukuran yang memang didukung sumber. | Berat dicatat 0,01 kg jika alat/metodenya mendukung; banyak digit tidak menjamin hasil benar. |
| **Periode data** | Rentang waktu bisnis yang dicakup record atau laporan. | period_start 2026-01-01 sampai period_end 2026-01-31 untuk rekap Januari. |
| **Waktu pengukuran** | Kapan kondisi atau kejadian benar-benar diamati. | measured_at atau event_at menunjukkan waktu di lapangan, bukan waktu sync. |
| **Waktu pengambilan** | Kapan data dikumpulkan/ditarik; berbeda dari periode yang dilaporkan. | collected_at 2026-02-02 untuk laporan Januari; waktu sync tidak mengubah bulan kinerja. |
