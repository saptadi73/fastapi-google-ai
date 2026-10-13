---
id: pengguna-role-dan-akses
title: Pengguna, role, dan kontrol akses
summary: Role admin, approval satu kali saat registrasi sumber, akses default berdasarkan domain dan unit, serta policy khusus.
routes: ["/admin", "/admin/*", "/register", "/users/*", "/access-requests", "/release-approvals", "/account", "/configurations/*", "/workspace"]
audiences: ["*"]
source: docs/ACCESS_JURISDICTION_BE16.md
---
**Platform Admin** mengelola akun, role, dan atribut organisasi seperti domain, business unit, yurisdiksi, serta department. Admin adalah superuser platform. Pemilik data mengelola sumber, konfigurasi ETL, validasi, deployment, dan sinkronisasi.

Approver melakukan satu pemeriksaan saat sumber didaftarkan: memeriksa spreadsheet dan tab yang ditemukan, klasifikasi MASTER/NON_MASTER, serta memastikan sumber layak dan tidak membuat dataset ganda/tidak valid. Setelah registrasi disetujui, konfigurasi, perubahan metadata operasional, deployment, dan sync owner-managed dikerjakan oleh data owner/steward tanpa approval rutin kedua. Persetujuan tayang dan approval konfigurasi/batch dapat tetap terlihat pada data atau workflow legacy; ikuti status yang benar-benar tampil untuk item tersebut.

Akses data berbeda dari approval ETL. Secara default, pengguna dengan aksi READ/QUERY yang memenuhi domain bisnis dan business unit pemilik dapat mengakses produk dalam cakupan itu. Kecocokan yurisdiksi tidak diwajibkan oleh fallback default ini. Pemilik data dapat mempersempit akses dengan policy khusus, misalnya yurisdiksi, department, purpose, atau clearance tertentu. Metadata yurisdiksi tetap bagian dari metadata sumber. Explicit DENY, batas tenant, sensitivitas, row/column scope, serta validasi backend tetap berlaku. Default ini tidak memberi EXPORT atau ADMIN.

Jika Katalog data kosong, admin memeriksa status produk, data yang sudah dimuat, role/aksi READ atau QUERY, assignment domain dan unit, policy khusus, serta tenant. Gunakan Preview keputusan pada Access policy untuk menguji akun, tindakan, dan resource yang sama. `DEFAULT_DENY` berarti belum ada izin cocok; `EXPLICIT_DENY` tidak dapat dikalahkan ALLOW. Policy DATA_PRODUCT tidak menggantikan pemeriksaan akses sumber bila sistem meminta keduanya.

Permintaan akun/role dan kebijakan akses khusus masih mengikuti kontrol admin yang tampil pada halaman Administrasi atau Access policy. Pembuat policy tidak menyetujui policy miliknya sendiri bila maker-checker policy diberlakukan. Admin tidak perlu membuat policy per akun bila akses default domain dan unit sudah memadai.

Sumber perlu disetujui sekali oleh approver berbeda dari pendaftar. Penunjukan approver tidak memberi hak membaca data. Penolakan atau perubahan spreadsheet sebelum keputusan memerlukan pemeriksaan sumber terbaru; setelah registrasi lolos, owner/steward menangani proses ETL berikutnya.

Jangan membagikan akun, token, password, credential Google, atau data pribadi melalui form bantuan AI. Role saja tidak melewati scope data dan pemeriksaan tenant.
