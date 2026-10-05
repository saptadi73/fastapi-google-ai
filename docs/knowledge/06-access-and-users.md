---
id: pengguna-role-dan-akses
title: Pengguna, role, dan kontrol akses
summary: Tanggung jawab role, atribut organisasi, kebijakan akses, dan access request.
routes: ["/admin/*", "/users/*", "/access-requests", "/account"]
audiences: ["*"]
source: docs/ACCESS_JURISDICTION_BE16.md
---
PLATFORM_ADMIN mengelola pengguna, role, atribut organisasi, permission, dan policy. SOURCE_OWNER mendaftarkan dan menjaga konteks sumber. DATA_STEWARD mengelola klasifikasi, master, taxonomy, konfigurasi, dan kualitas. TECHNICAL_APPROVER mereview perubahan. ANALYST dan VIEWER memakai data yang sudah dipublikasikan dan diizinkan.

Akses tidak hanya ditentukan oleh role. Sistem dapat mempertimbangkan departemen, domain bisnis, yurisdiksi, clearance, purpose, assignment pengguna, scope sumber, row scope, dan sensitivitas kolom. Backend mengambil identitas tenant dan pengguna dari token; pengguna tidak memasukkan UUID tenant atau resource secara manual.

Jika halaman atau data tidak tersedia, ajukan access request dengan alasan bisnis dan scope yang diperlukan. Persetujuan harus diberikan oleh pihak yang berwenang. Jangan membagikan akun, token, password, credential Google, atau informasi sensitif melalui form bantuan AI.

