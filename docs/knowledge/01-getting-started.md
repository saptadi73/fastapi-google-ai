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
7. Ajukan konfigurasi dan minta reviewer berbeda menyetujui. Jika aturan persetujuan tayang aktif, tunggu pemeriksaan IT dan persetujuan dari setiap unit terkait pada revisi yang sama. Setelah status siap tayang, deploy dan aktifkan. Aturan ini ditetapkan admin per sumber; sumber lama tanpa aturan tetap mengikuti alur review konfigurasi biasa.
8. Stage data, jawab pertanyaan import, periksa preview, approve, lalu apply batch.
9. Pantau job, kualitas, schedule, dependency, watermark, dan data karantina.
10. Setelah produk data aktif dan dapat diakses, pengguna dapat bertanya dengan bahasa alami dan memilih tabel atau chart.

Master dan taxonomy hanya diperlukan bila dataset membutuhkan rujukan atau kategori baku. Dataset transaksi sederhana tetap harus melalui klasifikasi, konfigurasi, review, import, dan kontrol akses.

