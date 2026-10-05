---
id: sumber-dan-klasifikasi
title: Mendaftarkan sumber dan mengklasifikasikan tab
summary: Cara menghubungkan Google Sheet, melengkapi metadata bisnis, profiling, dan menentukan MASTER atau NON_MASTER.
routes: ["/workspace", "/sources/*"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/KLASIFIKASI_TAB_BE02.md
---
Sebelum mendaftarkan sumber, bagikan spreadsheet kepada email service account backend dengan akses Viewer. Pada Workspace ETL, masukkan URL atau ID spreadsheet dan nama yang mudah dikenali. Kode teknis dan UUID dibuat sistem; pengguna hanya mengisi kode bisnis bila form memang menyediakannya.

Lengkapi unit pemilik, domain bisnis, yurisdiksi, purpose, data owner, data steward, sensitivitas, dan deskripsi. Metadata ini dipakai untuk kepemilikan, pencarian, serta keputusan akses. Hubungkan sumber untuk menjalankan discovery dan profiling. Pastikan daftar tab dan header berhasil terbaca.

Setiap tab harus dikonfirmasi sebagai MASTER atau NON_MASTER. MASTER berisi rujukan yang relatif stabil dan dipakai dataset lain, misalnya cabang, produk, atau departemen. NON_MASTER berisi transaksi, pengukuran, atau data dinamis. Jika ragu, tinjau business key, frekuensi perubahan, pemilik resmi, dan pemakaian kolom sebagai rujukan. Perubahan klasifikasi yang sudah aktif dapat memerlukan migrasi dan review ulang.

