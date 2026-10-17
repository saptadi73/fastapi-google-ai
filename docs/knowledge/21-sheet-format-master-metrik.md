---
id: format-google-sheet-master-metrik
title: Format Google Sheet ideal - Master istilah, taxonomy, dimensi dan metrik analitik
summary: "Rekomendasi data analitik modern, akurat dan presisi: Master istilah, taxonomy, dimensi dan metrik analitik."
routes: ["/masters", "/taxonomies", "/workspace", "/data-catalog", "/guide"]
audiences: ["*"]
source: docs/PANDUAN_FORMAT_GOOGLE_SHEET.md
---
Panduan berdasarkan kemampuan aplikasi Google Sheet AI ini. Tujuannya: data dapat diproses, konsisten lintas sumber dan periode, memiliki ketelitian yang sesuai pengukuran, serta mendukung keputusan yang dapat ditelusuri. Setiap data periodik/berbasis waktu wajib memiliki konteks waktu yang eksplisit.

## 6. Master data, taxonomy dan konsistensi istilah

- Gunakan master untuk entitas/rujukan: unit, produk, pelanggan, indikator. Sediakan kode unik stabil, label bisnis, definisi dan is_active bila diperlukan. Nama manusia bukan pilihan key yang aman bila dapat berubah/berulang.
- Gunakan taxonomy untuk kategori terkendali: jenis keluhan, status, tingkat prioritas dan kelas aktivitas. Term/code baku, alias yang direview dan versi mencegah KAN Jabung/KAN JABUNG/Jabung diperlakukan sebagai kategori berbeda tanpa bukti.
- Di Google Sheet, gunakan dropdown validasi dari daftar kode baku untuk membantu input; proteksi kolom key/formula sesuai kebutuhan pemilik. Dropdown saja tidak menggantikan validasi master/taxonomy di aplikasi.
- Klasifikasikan tab MASTER/NON_MASTER dengan benar. Master memerlukan definisi approved, storage, record yang sudah di-Apply dan source binding approved. Binding approved saja belum memuat record.
- Untuk transaksi, binding referensi master dan binding taxonomy harus sesuai versi approved/profil terbaru. Nilai tidak ditemukan atau ambigu perlu pertanyaan/koreksi; AI/skor tinggi tidak membuktikan relasi dan tidak boleh memilih diam-diam.
- Kamus data menjelaskan tiap header, definisi, tipe, nullability, unit, contoh, daftar nilai, pemilik dan asal field. Perubahan arti indikator/kategori perlu versi, bukan mengganti label lama tanpa jejak.

## 7. Dimensi, metrik dan pengukuran yang tidak menyesatkan

- Dimensi menjawab menurut apa: unit, indikator, kategori dan tanggal/periode. Metrik menjawab berapa: jumlah kejadian, volume, nilai target dan realisasi. Pada konfigurasi NON_MASTER, kolom numerik publik seperti int/integer, bigint, numeric/decimal, real, dan double precision otomatis masuk katalog metrik. Key numerik memakai count_distinct, nama yang mengindikasikan persen/rasio/rate memakai avg, dan kolom numerik lain memakai sum sebagai agregasi awal.
- Tinjau arti bisnis, unit, dan agregasi metrik otomatis sebelum deploy. Kolom sensitif dikecualikan. Tab MASTER tidak mendapat metrik otomatis karena angka sering berfungsi sebagai kode atau atribut identitas.
- Untuk produk NON_MASTER aktif yang dibuat sebelum aturan ini tersedia, operator dapat menjalankan python -m app.cli semantic-numeric-metric-backfill untuk melihat dry-run, lalu python -m app.cli semantic-numeric-metric-backfill --apply setelah memeriksa daftar perubahan. Ini hanya memperbarui semantic catalog dan audit; ETL, tabel fisik, dan baris data tidak dimuat ulang. Perintah idempotent dan mempertahankan definisi metrik yang sudah ada.
- Agregasi yang tersedia: sum, count, avg, min, max, count_distinct. SUM hanya untuk ukuran aditif pada grain yang sama. Saldo/stok/snapshot kondisi tidak otomatis boleh dijumlahkan lintas waktu; pilih definisi/filter periode yang tepat.
- Jangan SUM persen atau AVG persen yang memiliki penyebut berbeda. Rasio total secara bisnis = total pembilang / total penyebut; simpan numerator/denominator atau siapkan rekap rasio pada grain yang benar. Expression rasio bebas belum didukung editor metrik, jadi jangan menjanjikan kalkulasi tersebut otomatis.
- Untuk KPI, simpan target_value, actual_value, unit_code dan indicator_code dengan definisi sama. Jika gap_value/achievement_ratio disiapkan di Sheet, rumus harus direview dan denominasi jelas. Target 0 memerlukan aturan NULL/status, bukan pembagian tak hingga.
- Tetapkan direction HIGHER_IS_BETTER atau LOWER_IS_BETTER dan threshold yang disetujui. Gap target 100, realisasi 90 = kekurangan 10 pada indikator makin tinggi makin baik; keluhan target maksimal 10, realisasi 15 = kelebihan 5 pada indikator makin rendah makin baik.
- Untuk rata-rata/persentase, sertakan sample_count, eligible_count/denominator, cakupan populasi dan metode. Perubahan metode, sampel, definisi atau cutoff dapat menjelaskan tren; korelasi atau perbedaan agregat bukan bukti sebab-akibat.
- Join dan roll-up perlu uji duplikat, cardinality, periode dan filter versi. Jangan mencampur realisasi akumulatif YTD dengan target bulanan atau unit KG dengan liter. Field MEDIUM/HIGH tidak boleh dipakai sebagai dimensi/metrik produk analitik.
- Sertakan ketidakpastian jika memang diukur: ukuran sampel, cakupan, metode, resolusi dan interval/error pengukuran yang sah. Tandai perubahan metode, bias sampel, musim dan kejadian luar biasa. Jangan mengarang tingkat keyakinan statistik atau menyimpulkan sebab-akibat hanya dari chart.
