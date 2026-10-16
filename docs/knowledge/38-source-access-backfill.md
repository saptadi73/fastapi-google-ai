---
id: source-access-backfill
title: Pemeriksaan sumber lama sebelum penyederhanaan akses
summary: Cara membaca laporan dry-run metadata akses legacy tanpa mengubah policy atau membuka akses.
routes: ["/sources", "/access", "/guide"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD"]
source: docs/ACCESS_BACKFILL_REPORT.md
---
Sebelum mengaktifkan workflow akses pemilik, administrator dapat menjalankan `python -m app.cli source-access-backfill-report` di environment backend. Perintah ini read-only, mencakup sumber yang masih terhubung, dan tidak menampilkan spreadsheet ID atau nilai metadata. Kategori `OWNER_METADATA_REQUIRED` berarti pemilik perlu melengkapi metadata; `SOURCE_REVIEW_REQUIRED` atau `SOURCE_REVIEW_REJECTED` perlu pemeriksaan registrasi; `OWNER_ACCESS_ACTIVATION_REQUIRED` berarti metadata sudah direview tetapi pemilik belum mengaktifkan akses; `READY_NO_BACKFILL` berarti sumber sudah dalam status akses yang siap. Jangan menandai sumber lama approved secara massal. Periksa tab, assignment aktif, tenant, scope domain/unit, dan audit melalui alur aplikasi.

Pada owner workflow, `OWNER_ACCESS_VALIDATION_REQUIRED` berarti pengelola menjalankan Validasi akses unit melalui Workspace atau `POST /sources/{id}/validate-access`. API memeriksa metadata, unit aktif, assignment dan aktor serta mencatat audit. Tidak perlu approver terpisah atau mengubah status langsung di database. Domain/yurisdiksi/purpose opsional; metadata REJECTED tetap harus diperbaiki dahulu.
