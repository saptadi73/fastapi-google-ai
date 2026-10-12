---
id: alur-awal-sampai-dashboard
title: Alur awal sampai dashboard
summary: Urutan umum dari administrasi, pendaftaran Google Sheet, validasi, sampai analitik.
routes: ["/guide", "/", "/dashboard", "/chat"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Gunakan urutan berikut agar data dapat dipakai dengan aman:

> Catatan rancangan: workflow sedang dievaluasi untuk mengurangi approval rutin. Sampai rollout perubahan diberitahukan, langkah dan gate yang sedang tampil di aplikasi tetap menjadi acuan. Checklist target, risiko, dan fase pengerjaan ada di `docs/WORKFLOW_SIMPLIFICATION_TODO.md`.

1. Administrator menyiapkan pengguna, role, atribut organisasi, permission, dan kebijakan akses.
2. Pemilik sumber membagikan Google Sheet kepada service account sebagai Viewer, lalu mendaftarkan URL spreadsheet serta metadata pemilikannya.
3. Steward mengonfirmasi setiap tab sebagai MASTER atau NON_MASTER setelah profiling selesai.
4. Jika data memakai rujukan baku, siapkan definisi, storage, record, dan binding master.
5. Jika data memakai kategori baku, siapkan taxonomy, versi, term, alias, dan binding taxonomy.
6. Buat konfigurasi ETL: mapping kolom, transformasi, kualitas, strategi load, business key, produk semantik, dimensi, dan metrik.
7. Pemilik memvalidasi konfigurasi. Approval manusia cukup saat registrasi sumber; konfigurasi, release, dan batch bersih tidak menunggu approver rutin. Sistem tetap memeriksa snapshot, mapping, kualitas, akses, business key, serta rencana perubahan schema.
8. Deploy lalu jalankan sync. FULL_REFRESH mengganti seluruh baris target hanya setelah semua baris lolos validasi; jika ada error, data lama tetap aktif. Konflik bisnis dan perubahan schema destruktif masih perlu ditangani secara eksplisit.
9. Pantau job, kualitas, schedule, dependency, watermark, dan data karantina.
10. Setelah produk data aktif dan dapat diakses, pengguna dapat bertanya dengan bahasa alami dan memilih tabel atau chart.

Master dan taxonomy hanya diperlukan bila dataset membutuhkan rujukan atau kategori baku. Dataset transaksi sederhana tetap melalui klasifikasi, konfigurasi, validasi, pemuatan, dan kontrol akses.

Di halaman konfigurasi, gunakan ikon tanda tanya pada tiap langkah untuk petunjuk singkat. Untuk konfigurasi owner-managed, pemilik menyelesaikan validasi lalu deploy tanpa approval konfigurasi rutin; konfigurasi lama masih menampilkan jalur review jika memang diperlukan. Pada strategi pemuatan, APPEND menambah baris, UPSERT memperbarui berdasarkan key, dan FULL_REFRESH mengganti seluruh isi tabel setelah semua data lolos validasi.

Gunakan menu **Sumber & tracking** sebagai daftar utama untuk mencari sumber dengan pencarian dan pagination, melihat status tiap tahap, serta mengetahui Data Owner dan Data Steward yang bertanggung jawab. Pilih **Buka sumber** untuk melanjutkan proses di Workspace ETL. Dropdown Workspace hanya untuk memilih konteks kerja dan tidak memuat seluruh daftar sumber.

Menunggu tindakan (NEEDS_INPUT) berarti pemuatan berhenti pada temuan, bukan masih berjalan. Lihat detail berikon mata membuka modal kode, keterangan, baris asli Sheet dan kolom. Audit trail menyimpan riwayat dan lokasi tanpa nilai mentah. Periksa hasil per tab dan Baris dimuat, bukan hanya job sync induk.
