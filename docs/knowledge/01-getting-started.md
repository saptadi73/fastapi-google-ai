---
id: alur-awal-sampai-dashboard
title: Alur awal sampai dashboard
summary: Urutan umum dari administrasi, pendaftaran Google Sheet, validasi, sampai analitik.
routes: ["/guide", "/", "/dashboard", "/chat"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Gunakan urutan berikut agar data dapat dipakai dengan aman:

1. Administrator menyiapkan pengguna, role, atribut organisasi, permission, dan kebijakan akses.
2. Pemilik sumber membagikan Google Sheet kepada service account sebagai Viewer, lalu mendaftarkan URL spreadsheet serta metadata pemilikannya.
3. Steward mengonfirmasi setiap tab sebagai MASTER atau NON_MASTER setelah profiling selesai.
4. Jika data memakai rujukan baku, siapkan definisi, storage, record, dan binding master.
5. Jika data memakai kategori baku, siapkan taxonomy, versi, term, alias, dan binding taxonomy.
6. Buat konfigurasi ETL: mapping kolom, transformasi, kualitas, strategi load, business key, produk semantik, dimensi, dan metrik.
7. Ajukan konfigurasi. Approver sumber yang bukan pembuat/editor metadata membaca ringkasan dan memilih policy SOURCE APPROVED: satu approval menyetujui konfigurasi, metadata PENDING, dan aktivasi akses. Jika satu syarat gagal, tidak ada approval sebagian. Selesaikan gate IT/unit yang diwajibkan pada revisi sama, lalu deploy sampai ACTIVE.
8. Jalankan Sync manual NON_MASTER aktif: validasi teknis, AI dan preview konflik lolos berarti langsung dimuat tanpa approval batch tambahan. Master, FULL_REFRESH, jadwal dan batch biasa tidak memakai jalur langsung; batch biasa tetap preview, approve, Apply.
9. Pantau job, kualitas, schedule, dependency, watermark, dan data karantina.
10. Setelah produk data aktif dan dapat diakses, pengguna dapat bertanya dengan bahasa alami dan memilih tabel atau chart.

Master dan taxonomy hanya diperlukan bila dataset membutuhkan rujukan atau kategori baku. Dataset transaksi sederhana tetap harus melalui klasifikasi, konfigurasi, review, import, dan kontrol akses.

Gunakan menu **Sumber & tracking** sebagai daftar utama untuk mencari sumber dengan pencarian dan pagination, melihat status tiap tahap, serta mengetahui Data Owner dan Data Steward yang bertanggung jawab. Pilih **Buka sumber** untuk melanjutkan proses di Workspace ETL. Dropdown Workspace hanya untuk memilih konteks kerja dan tidak memuat seluruh daftar sumber.

Menunggu tindakan (NEEDS_INPUT) berarti pemuatan berhenti pada temuan, bukan masih berjalan. Lihat detail berikon mata membuka modal kode, keterangan, baris asli Sheet dan kolom. Audit trail menyimpan riwayat dan lokasi tanpa nilai mentah. Periksa hasil per tab dan Baris dimuat, bukan hanya job sync induk.
