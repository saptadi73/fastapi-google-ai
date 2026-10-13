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
- Approver IT memeriksa registrasi sumber dan tab; persetujuan itu bukan hak baca otomatis dan tidak mengulang di tiap konfigurasi. Discovery/profiling dijalankan SOURCE_OWNER, DATA_STEWARD atau PLATFORM_ADMIN. Perubahan role/assignment/policy khusus tetap mengikuti kontrol admin yang berlaku.
- Validasi konsumsi memakai akun pembaca yang sebenarnya: katalog terlihat, field yang diizinkan tersedia dan hasil query masuk akal. Jangan menghapus sensitivitas atau memperluas policy hanya agar katalog terisi.

## 11. Strategi load, pembaruan dan perubahan Sheet

- UPSERT cocok untuk KPI periodik/current-state yang dapat dikoreksi: record dengan key sama diperbarui. APPEND cocok untuk kejadian baru yang stabil; keyless APPEND dapat memakai SKIP_IDENTICAL sesuai review, tetapi baris yang berubah bisa menjadi record baru dan menyebabkan hitungan ganda.
- FULL_REFRESH mengganti seluruh isi baris target dari snapshot sumber lengkap setelah validasi; bila ada baris invalid, data lama dipertahankan. Snapshot parsial tidak boleh dipakai seolah mencakup semua data. Perubahan skema tetap diperiksa terpisah.
- Setelah konfigurasi owner-managed aktif dan akses sumber disetujui, Sync manual memvalidasi dan memuat data tanpa approval rutin kedua. Konflik bisnis dan error kualitas tetap perlu ditangani.
- Jika file/tab di-rename, ditambah atau dihapus, pilih sumber yang sama di Workspace dan tekan Temukan tab, tunggu SUCCEEDED, lalu Profiling ulang. Muat ulang data tersimpan tidak membaca ulang daftar tab di Google.
- Perubahan header, mapping, tipe, key atau makna memerlukan profil/draft/validasi terbaru. Preview perubahan schema di langkah 7 dan konfirmasi sebelum worker deploy. Owner workflow tidak memerlukan approval rutin kedua; item legacy mengikuti gate yang tampil. Rename/drop fisik atau dependency tidak aman dapat diblokir; jangan hapus tabel untuk mengakalinya.
- REVIEW_STALE berarti sumber berubah dibanding snapshot review. Contoh starat_date diganti start_date: profil dan review ulang; tidak cukup retry deploy lama. Hindari perubahan selama review/deploy, termasuk formula volatil yang mengubah nilai tiap pembacaan.
- Setelah load, periksa SUCCEEDED per tab/batch, jumlah record, waktu terakhir dimuat, coverage dan akses katalog. Job induk sukses tidak membuktikan semua tab dimuat; NEEDS_INPUT berarti menunggu tindakan. Gunakan tabel error response pada helper untuk penanganan kode.
