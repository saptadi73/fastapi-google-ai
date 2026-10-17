---
id: error-response-layanan
title: Error response - Layanan database dan AI
summary: Tabel penyebab dan tindakan untuk DATABASE_PERMISSION_DENIED, DATABASE_CONNECTION_FAILED, OPENAI_NOT_CONFIGURED, AI_UPSTREAM_FAILED, AI_PROVIDER_CREDIT_INSUFFICIENT, AI_BUDGET_EXCEEDED, AI_TASK_BUDGET_EXCEEDED, DATABASE_UNAVAILABLE, INTERNAL_ERROR.
routes: ["/jobs", "/system", "/dashboard", "/chat", "/guide"]
audiences: ["*"]
source: docs/ERROR_RESPONSES.md
---
Cari kode pada pesan error atau monitor job; catat ID job, sumber/tab dan versi konfigurasi. Penyebab di bawah adalah kemungkinan, bukan diagnosis otomatis. Baca detail/log untuk menentukan kasus yang terjadi. DEFAULT_DENY, EXPLICIT_DENY dan ACTION_NOT_GRANTED adalah reason_code keputusan akses; TYPE_OR_NULL_ERROR/DUPLICATE_BUSINESS_KEY adalah temuan validasi; AI_REVIEW_ISSUES/AI_REVIEW_NOT_IMPLEMENTED adalah blocker checkpoint. Kode tersebut tidak selalu muncul sebagai error HTTP. NEEDS_INPUT berarti menunggu tindakan, bukan worker sedang berjalan. Muat ulang halaman hanya membaca status; tidak menjalankan discovery, profiling atau sync. Jangan kirim password, token, API key atau nilai pribadi ke helper.

| Kode / respons | Kemungkinan penyebab | Tindakan yang dilakukan |
| --- | --- | --- |
| `DATABASE_PERMISSION_DENIED` | Role runtime/DDL tidak memiliki izin atau ownership objek PostgreSQL yang diperlukan. | Admin memeriksa log job, role DDL, USAGE/CREATE trusted/semantic serta ownership/ACL target. Jangan memberi runtime hak superuser. |
| `DATABASE_CONNECTION_FAILED` | Aplikasi/worker tidak dapat terhubung ke database. | Admin memeriksa koneksi, host/port, kredensial, pool dan health database; retry setelah koneksi pulih. |
| `OPENAI_NOT_CONFIGURED` | Key atau model AI yang diperlukan belum dikonfigurasi. | Admin melengkapi konfigurasi backend dan memeriksa health/policy model. Jangan menempelkan API key pada helper. |
| `AI_UPSTREAM_FAILED` | Permintaan ke layanan AI gagal. | Admin memeriksa request ID/log, model, key, kuota dan jaringan; coba ulang setelah penyebab diperbaiki. |
| `AI_PROVIDER_CREDIT_INSUFFICIENT` | Provider menolak request karena saldo kredit atau billing project tidak cukup. | Admin memeriksa credit balance dan billing project penyedia AI yang dikonfigurasi di backend. Ini berbeda dari kuota/budget aplikasi; retry atau menaikkan limit aplikasi tidak menambah saldo provider. Ulangi aksi setelah billing pulih. |
| `AI_BUDGET_EXCEEDED` | Budget AI tenant tercapai. | Admin meninjau penggunaan/budget; tunggu periode budget berikutnya atau ubah limit sesuai kewenangan. Retry terus akan tetap ditolak. |
| `AI_TASK_BUDGET_EXCEEDED` | Budget harian policy task AI tercapai. | Admin meninjau policy task dan biaya; lanjutkan saat budget tersedia atau limit disetujui untuk diubah. |
| `DATABASE_UNAVAILABLE` | Operasi database gagal; respons umum tidak menjelaskan penyebab rinci. | Catat request ID/job ID. Admin memeriksa log dan health database untuk membedakan koneksi, izin, constraint atau kegagalan query; retry setelah diperbaiki. |
| `INTERNAL_ERROR` | Aplikasi mengalami kegagalan yang tidak tertangani secara spesifik. | Catat request ID, halaman, waktu dan tindakan terakhir; admin memeriksa log API/worker. Periksa status job sebelum mengulangi tindakan agar tidak membuat proses ganda. |
