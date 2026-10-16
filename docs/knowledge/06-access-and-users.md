---
id: pengguna-role-dan-akses
title: Pengguna, role, dan kontrol akses
summary: Role pengelola unit tanpa approver terpisah, akses default unit dan policy khusus.
routes: ["/admin", "/admin/*", "/register", "/users/*", "/access-requests", "/release-approvals", "/account", "/configurations/*", "/workspace"]
audiences: ["*"]
source: docs/ACCESS_JURISDICTION_BE16.md
---
**Platform Admin** mengelola akun, role, dan atribut organisasi seperti domain, business unit, yurisdiksi, serta department. Admin adalah superuser platform. Pemilik data mengelola sumber, konfigurasi ETL, validasi, deployment, dan sinkronisasi.

SOURCE_OWNER dan DATA_STEWARD dengan assignment aktif pada unit sumber dapat mengelola sumber milik rekan satu unit, termasuk konfigurasi, deploy dan sync. Registrasi sumber tidak memerlukan orang kedua pada owner workflow.

Akses data berbeda dari approval ETL. Secara default, pengguna dengan aksi READ/QUERY yang memenuhi unit bisnis pemilik pada owner workflow dapat mengakses produk dalam cakupan itu. Kecocokan yurisdiksi tidak diwajibkan oleh fallback default ini. Pemilik data dapat mempersempit akses dengan policy khusus, misalnya yurisdiksi, department, purpose, atau clearance tertentu. Metadata yurisdiksi tetap bagian dari metadata sumber. Explicit DENY, batas tenant, sensitivitas, row/column scope, serta validasi backend tetap berlaku. Default ini tidak memberi EXPORT atau ADMIN.

Jika Katalog data kosong, admin memeriksa status produk, data yang sudah dimuat, role/aksi READ atau QUERY, assignment unit aktif, policy khusus, serta tenant. Gunakan Preview keputusan pada Access policy untuk menguji akun, tindakan, dan resource yang sama. `DEFAULT_DENY` berarti belum ada izin cocok; `EXPLICIT_DENY` tidak dapat dikalahkan ALLOW. Policy DATA_PRODUCT tidak menggantikan pemeriksaan akses sumber bila sistem meminta keduanya.

Permintaan akun/role dan kebijakan akses khusus masih mengikuti kontrol admin yang tampil pada halaman Administrasi atau Access policy. Pembuat policy tidak menyetujui policy miliknya sendiri bila maker-checker policy diberlakukan. Admin tidak perlu membuat policy per akun bila akses default unit sudah memadai.

Sumber lama yang pending akses dapat diselesaikan melalui Validasi akses unit atau Sync manual. Metadata ditolak harus diperbaiki sebelum validasi. Daftar approver dan approval rilis lama hanya merupakan histori pada owner workflow.

Jangan membagikan akun, token, password, credential Google, atau data pribadi melalui form bantuan AI. Role saja tidak melewati scope data dan pemeriksaan tenant.
