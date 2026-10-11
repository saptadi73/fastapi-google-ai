---
id: format-google-sheet-struktur
title: Format Google Sheet ideal - Penamaan, header, grain dan key Google Sheet
summary: "Rekomendasi data analitik modern, akurat dan presisi: Penamaan, header, grain dan key Google Sheet."
routes: ["/workspace", "/sources", "/etl-review/*", "/guide"]
audiences: ["*"]
source: docs/PANDUAN_FORMAT_GOOGLE_SHEET.md
---
Panduan berdasarkan kemampuan aplikasi Google Sheet AI ini. Tujuannya: data dapat diproses, konsisten lintas sumber dan periode, memiliki ketelitian yang sesuai pengukuran, serta mendukung keputusan yang dapat ditelusuri. Setiap data periodik/berbasis waktu wajib memiliki konteks waktu yang eksplisit.

## 1. Nama file, tab, bisnis dan produk data

Nama harus menjelaskan subjek bisnis, cakupan dan isi dataset. Gunakan nama stabil; nama file dan tab menjadi acuan identitas, bukan pengganti deskripsi bisnis.

- Contoh file: Kinerja Layanan Pelanggan KAN Jabung 2026. Contoh tab: Keluhan_Harian, KPI_Layanan_Bulanan, Master_Unit, Master_Indikator, Action_Plan. Hindari Sheet1, Copy of, FINAL_FIX atau nama orang tanpa konteks.
- Draft manual menyarankan Nama bisnis = nama file / nama tab dan kode produk dari gabungan nama tersebut. Nama bisnis maksimal 200 karakter; kode produk huruf ASCII/angka/underscore, diawali huruf, maksimal 63 karakter. Saran bisa ditinjau/diedit; nama serupa setelah normalisasi dapat konflik.
- Nama tabel database merupakan konfigurasi terpisah: draft manual menyarankan nama dasar dari tab, lalu aplikasi menambahkan identitas tab pada tabel fisik. Mengganti nama file/tab tidak otomatis mengganti nama produk atau tabel yang sudah aktif.
- Untuk seri lintas tahun, lebih baik file bisnis stabil dan tahun disimpan sebagai nilai kolom. Jika file terpisah per tahun, jaga grain/header/definisi sama dan rancang penggabungan melalui review; aplikasi tidak otomatis menyatukan file.
- Tulis deskripsi dataset: satu baris mewakili apa, sumber pengukuran, pemilik, periode, satuan, jadwal pembaruan dan batas penggunaan. Tab panduan/kamus data terpisah boleh ada, tetapi jangan diikutkan sebagai data ETL.

## 2. Bentuk tabular: satu header, satu baris per record

- Format ideal: header pada baris 1, data mulai baris 2. Satu kolom mewakili satu field dan satu sel satu nilai. Jangan merge cell, menumpuk header dua tingkat, memakai judul laporan di area data, atau membuat tabel berdampingan.
- Header wajib terisi, unik, jelas dan stabil; periksa juga benturan setelah normalisasi. Contoh Nama Unit dan Nama-Unit dapat menjadi nama target yang sama. Gunakan unit_code, event_date, quantity, amount_idr; jangan hanya Nilai atau Total tanpa definisi.
- Jangan letakkan data pada kolom tanpa header. Gunakan range yang mencakup seluruh field yang dibutuhkan dan mulai dari baris 1. Header_row/data_start_row mengatur lokasi header/data bila sumber lama belum rapi.
- Jangan sisipkan subtotal, grand total, catatan, tanda tangan, chart atau baris pemisah ke dalam tabel fakta. Pisahkan tampilan laporan/dashboard dari tab input; subtotal dapat membuat agregat terhitung dua kali.
- Untuk laporan bulan di kolom Jan/Feb/Mar, ubah ke format panjang: period_start, period_end, unit_code, indicator_code, value. Setiap bulan menjadi baris. Untuk target/realisasi pada grain yang sama, kolom target_value dan actual_value tetap boleh berdampingan.
- Warna, format tebal, komentar, filter tampilan dan posisi sel bukan nilai bisnis. Simpan status, kategori, priority dan flag sebagai kolom eksplisit. Jangan mengandalkan baris yang disembunyikan untuk dikecualikan dari ETL.

## 3. Grain, business key dan hubungan data

Tetapkan grain sebelum memilih key/metrik. Contoh transaksi: satu baris per kejadian keluhan. Contoh KPI: satu baris per unit, indikator dan periode. Jangan mencampur transaksi harian, rekap bulanan dan target tahunan dalam satu grain.

- Sediakan ID stabil dan unik, misalnya complaint_id, kpi_record_id atau action_id. Kode tidak berubah ketika baris disortir/disisipkan; nomor urut tampilan dan nomor baris bukan identitas yang stabil.
- Business key tidak boleh NULL dan harus unik sesuai grain. Untuk KPI, key dapat gabungan unit_code + indicator_code + period_start + period_end. Kolom yang mirip ID hanya kandidat dari profiling; reviewer harus membuktikan keunikannya.
- Master unit/indikator menyediakan rujukan satu record unik. Fakta dapat memiliki banyak baris per satu unit: relasi MANY_TO_ONE. Jika master memakai key gabungan, sediakan satu kode rujukan unik karena resolver mencari satu field master.
- Join antar-produk harus didefinisikan dan disetujui di Governance. Nama kolom sama tidak membuktikan relasi. Uji cardinality dan jumlah baris sebelum/sesudah join agar nilai tidak berlipat.
- Untuk perubahan historis, pilih kebijakan eksplisit: UPSERT memperbarui record dengan key sama; sejarah revisi memerlukan revision_no/as_of_at serta grain/key yang mencakup versi dan filter versi yang dipakai. Jangan menjumlahkan semua versi sebagai kejadian baru.
