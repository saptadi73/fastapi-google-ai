---
id: format-google-sheet-operasi
title: Format Google Sheet ideal - Akses, load dan perubahan sumber analitik
summary: "Rekomendasi data analitik modern, akurat dan presisi: Akses, load dan perubahan sumber analitik."
routes: ["/sources", "/workspace", "/jobs", "/admin", "/guide"]
audiences: ["*"]
source: docs/PANDUAN_FORMAT_GOOGLE_SHEET.md
---
Panduan berdasarkan kemampuan aplikasi Google Sheet AI ini. Tujuannya: data dapat diproses, konsisten lintas sumber dan periode, memiliki ketelitian yang sesuai pengukuran, serta mendukung keputusan yang dapat ditelusuri. Setiap data periodik/berbasis waktu wajib memiliki konteks waktu yang eksplisit.

## 10. Kepemilikan, keamanan dan hak konsumsi

- Tetapkan Data Owner, Data Steward, unit pemilik, domain bisnis, yurisdiksi, purpose dan sensitivitas yang sesuai isi sumber. Bagikan Sheet ke Service Account backend sebagai Viewer; aplikasi tidak menulis ulang sel sumber.
- Klasifikasikan PII per kolom berdasarkan isi, bukan nama header saja. Hindari NIK, kontak, alamat atau nama pribadi jika analisis cukup memakai kode anonim/agregat. Kontrol akses berlaku juga pada narasi action plan dan evidence_ref.
- Konfigurasi ACTIVE dan sync SUCCEEDED tidak otomatis membuat produk terlihat bagi semua pengguna. Allowed_roles produk serta policy SOURCE/DATA_PRODUCT dan assignment aktif pembaca harus cocok; semua required attributes pada policy berlaku AND.
- Approval IT/TECHNICAL_APPROVER adalah persetujuan proses, bukan hak baca otomatis. Discovery/profiling dijalankan SOURCE_OWNER, DATA_STEWARD atau PLATFORM_ADMIN. Perubahan assignment/policy mengikuti approval terpisah yang diwajibkan.
- Validasi konsumsi memakai akun pembaca yang sebenarnya: katalog terlihat, field yang diizinkan tersedia dan hasil query masuk akal. Jangan menghapus sensitivitas atau memperluas policy hanya agar katalog terisi.

## 11. Strategi load, pembaruan dan perubahan Sheet

- UPSERT cocok untuk KPI periodik/current-state yang dapat dikoreksi: record dengan key sama diperbarui. APPEND cocok untuk kejadian baru yang stabil; keyless APPEND dapat memakai SKIP_IDENTICAL sesuai review, tetapi baris yang berubah bisa menjadi record baru dan menyebabkan hitungan ganda.
- FULL_REFRESH mengganti isi target dengan snapshot lengkap dan memerlukan alur review yang sesuai; snapshot parsial tidak boleh dipakai seolah mencakup semua data. Master memakai definisi/storage/source binding dan batch master, bukan ETL biasa.
- Sepakati jadwal, cutoff, target freshness dan petugas. Setelah deploy ACTIVE dengan approval terpisah, akses/rilis siap, Sync manual memuat NON_MASTER yang valid; master/FULL_REFRESH/batch biasa tetap memakai preview, approval dan Apply sesuai alurnya.
- Jika file/tab di-rename, ditambah atau dihapus, pilih sumber yang sama di Workspace dan tekan Temukan tab, tunggu SUCCEEDED, lalu Profiling ulang. Muat ulang data tersimpan tidak membaca ulang daftar tab di Google.
- Perubahan header, mapping, tipe, key atau makna memerlukan profil/draft/review terbaru. Preview perubahan schema di langkah 7, konfirmasi dan approval sebelum worker deploy. Rename/drop fisik atau dependency tidak aman dapat diblokir; jangan hapus tabel untuk mengakalinya.
- REVIEW_STALE berarti sumber berubah dibanding snapshot review. Contoh starat_date diganti start_date: profil dan review ulang; tidak cukup retry deploy lama. Hindari perubahan selama review/deploy, termasuk formula volatil yang mengubah nilai tiap pembacaan.
- Setelah load, periksa SUCCEEDED per tab/batch, jumlah record, waktu terakhir dimuat, coverage dan akses katalog. Job induk sukses tidak membuktikan semua tab dimuat; NEEDS_INPUT berarti menunggu tindakan. Gunakan tabel error response pada helper untuk penanganan kode.
