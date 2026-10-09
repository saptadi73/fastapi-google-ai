---
id: konfigurasi-import-dan-operasi
title: Konfigurasi ETL, batch import, dan operasi
summary: Menyusun konfigurasi, menjalankan review, mengimpor data, dan menangani job atau kualitas.
routes: ["/workspace", "/etl-review/*", "/import-reviews", "/release-approvals", "/imports/*", "/jobs", "/quality"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/PANDUAN_REVIEW_ETL.md
---
Konfigurasi ETL memetakan kolom sumber ke target, menetapkan tipe data dan transformasi, aturan kualitas, business key, strategi APPEND atau UPSERT, serta metadata produk semantik. Untuk data yang berubah menurut waktu, tetapkan field periode atau watermark yang benar. Jalankan validasi sampai tidak ada blocker.

Submit konfigurasi untuk review. Pada workflow separate approval, pembuat tidak boleh menjadi approver. Setelah approved, periksa status **Persetujuan tayang** pada halaman review konfigurasi. Bila admin telah mengaktifkan aturan rilis pada sumber, pemeriksa IT dan satu approver dari setiap unit terkait harus menyetujui revisi serta snapshot review yang sama sebelum deploy. Pemeriksa IT melengkapi checklist skema/mapping, kualitas data, dan keamanan/akses. Setelah semua kelompok setuju, editor dapat deploy dan activate. Sumber lama tanpa aturan rilis tetap memakai review konfigurasi biasa. Perubahan revisi, snapshot, atau aturan rilis membatalkan keputusan lama; penolakan perlu ditangani lewat versi konfigurasi baru atau revisi aturan yang diaudit. Rollback ke versi lama juga diperiksa terhadap aturan rilis saat ini. Perubahan pada profil sumber, taxonomy, master, atau binding dapat membuat konfigurasi lama stale dan perlu direview ulang.

Saat import, buat batch dari snapshot terbaru, selesaikan pertanyaan wajib, lalu lakukan revalidate. Periksa preview karena preview menjelaskan insert, update, konflik, dan penutupan periode yang akan terjadi. Reviewer batch menyetujui preview yang sama sebelum apply; persetujuan tayang konfigurasi tidak menggantikan review batch dan saat ini tidak diulang untuk setiap batch. Pantau hasil pada Jobs dan Quality. Perbaiki penyebab kegagalan atau data karantina, kemudian reprocess melalui aksi yang disediakan; hindari mengulang permintaan tanpa memahami statusnya.

Halaman **Batch import** menampilkan daftar sumber dengan pencarian dan pagination, termasuk status discovery, profiling, konfigurasi atau binding master, approval IT, serta database. Pilih sumber dari daftar tersebut, lalu pilih tab yang sudah diklasifikasikan. Halaman **Persetujuan tayang** hanya menampilkan konfigurasi yang ditugaskan kepada akun approver; gunakan pencarian sumber, produk, status, revisi, atau kelompok, lalu pilih baris untuk memeriksa detail dan memberi keputusan. Daftar memakai komponen reusable `PagedDataTable` agar sumber dan konfigurasi mudah dicari tanpa dropdown panjang.

