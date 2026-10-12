# Istilah teknis dalam bahasa sederhana

<!-- Generated from docs/technical-glossary.json by scripts/export_technical_glossary.py. -->

Bayangkan Google Sheet sebagai buku pencatatan bisnis. Istilah berikut menjelaskan isi buku, aturan pencatatan dan cara aplikasi mengolahnya. Contoh memakai keluhan pelanggan dan rekap KPI.

## Dasar pencatatan data

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

## Rujukan dan persiapan data

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

## Analitik, ketelitian dan konteks waktu

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

## Proses aplikasi dan pemuatan

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

Contoh terpadu: satu baris adalah rekap penyelesaian keluhan satu unit untuk satu indikator dalam satu bulan. Itu grain. Unit + indikator + periode dapat menjadi business key. Unit dan periode menjadi dimensi; target serta realisasi adalah metrik dengan definisi/agregasi yang direview. Jika angka periode yang sama dikoreksi, UPSERT memperbarui key yang sama. APPEND tanpa key yang tepat dapat membuat record awal dan koreksi ikut dihitung sehingga hasil berlipat. Master menyimpan entitas rujukan seperti unit; taxonomy mengatur kategori seperti jenis keluhan.

Di aplikasi: **Bantuan > Istilah teknis dalam bahasa sederhana** atau **Panduan lengkap > Istilah teknis dalam bahasa sederhana**. Cari istilah, arti atau contoh. Lihat juga [Format Google Sheet ideal](PANDUAN_FORMAT_GOOGLE_SHEET.md) dan [Tabel error response](ERROR_RESPONSES.md).
