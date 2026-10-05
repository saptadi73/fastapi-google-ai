---
id: konfigurasi-import-dan-operasi
title: Konfigurasi ETL, batch import, dan operasi
summary: Menyusun konfigurasi, menjalankan review, mengimpor data, dan menangani job atau kualitas.
routes: ["/workspace", "/etl-review/*", "/imports/*", "/jobs", "/quality"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/PANDUAN_REVIEW_ETL.md
---
Konfigurasi ETL memetakan kolom sumber ke target, menetapkan tipe data dan transformasi, aturan kualitas, business key, strategi APPEND atau UPSERT, serta metadata produk semantik. Untuk data yang berubah menurut waktu, tetapkan field periode atau watermark yang benar. Jalankan validasi sampai tidak ada blocker.

Submit konfigurasi untuk review. Pada workflow separate approval, pembuat tidak boleh menjadi approver. Setelah approved, deploy dan activate konfigurasi. Perubahan pada profil sumber, taxonomy, master, atau binding dapat membuat konfigurasi lama stale dan perlu direview ulang.

Saat import, buat batch dari snapshot terbaru, selesaikan pertanyaan wajib, lalu lakukan revalidate. Periksa preview karena preview menjelaskan insert, update, konflik, dan penutupan periode yang akan terjadi. Reviewer menyetujui preview yang sama sebelum apply. Pantau hasil pada Jobs dan Quality. Perbaiki penyebab kegagalan atau data karantina, kemudian reprocess melalui aksi yang disediakan; hindari mengulang permintaan tanpa memahami statusnya.

