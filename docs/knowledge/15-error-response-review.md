---
id: error-response-review
title: Error response - Review konfigurasi dan deploy schema
summary: Tabel penyebab dan tindakan untuk REVIEW_STALE, CONFIGURATION_CONFLICT, APPROVAL_REQUIRED, RELEASE_APPROVAL_REQUIRED, SCHEMA_REVIEW_REQUIRED, SCHEMA_MIGRATION_STALE, SCHEMA_MIGRATION_BLOCKED, SEMANTIC_SCHEMA_MIGRATION_REQUIRED, SCHEMA_CHANGE_UNSAFE, ARTIFACT_MISSING, ARTIFACT_HASH_MISMATCH, VALIDATION_ERROR, RESOURCE_CONFLICT.
routes: ["/etl-review/*", "/configurations/*", "/release-approvals", "/jobs", "/guide"]
audiences: ["*"]
source: docs/ERROR_RESPONSES.md
---
Cari kode pada pesan error atau monitor job; catat ID job, sumber/tab dan versi konfigurasi. Penyebab di bawah adalah kemungkinan, bukan diagnosis otomatis. Baca detail/log untuk menentukan kasus yang terjadi. DEFAULT_DENY, EXPLICIT_DENY dan ACTION_NOT_GRANTED adalah reason_code keputusan akses; TYPE_OR_NULL_ERROR/DUPLICATE_BUSINESS_KEY adalah temuan validasi; AI_REVIEW_ISSUES/AI_REVIEW_NOT_IMPLEMENTED adalah blocker checkpoint. Kode tersebut tidak selalu muncul sebagai error HTTP. NEEDS_INPUT berarti menunggu tindakan, bukan worker sedang berjalan. Muat ulang halaman hanya membaca status; tidak menjalankan discovery, profiling atau sync. Jangan kirim password, token, API key atau nilai pribadi ke helper.

| Kode / respons | Kemungkinan penyebab | Tindakan yang dilakukan |
| --- | --- | --- |
| `REVIEW_STALE` | Isi atau header Sheet saat deploy berbeda dari snapshot review; formula juga dapat berubah. | Profiling ulang, buat draft terbaru, perbaiki mapping header, Dry-run, review/approval ulang lalu Deploy. Retry versi approved lama tidak memperbarui bukti. |
| `CONFIGURATION_CONFLICT` | Kolom/fingerprint sumber tidak sesuai mapping yang direview. | Temukan tab jika nama tab berubah, lalu Profiling ulang. Clone bila header lama masih ada; jika hilang, buat draft dari profil terbaru dan ajukan ulang. |
| `APPROVAL_REQUIRED` | Status konfigurasi belum memenuhi persyaratan deploy/aktivasi. | Selesaikan review dan approval oleh reviewer berwenang yang berbeda dari pembuat, lalu deploy versi yang benar. |
| `RELEASE_APPROVAL_REQUIRED` | Keputusan IT/unit pada Persetujuan tayang belum lengkap atau sudah tidak berlaku. | Lengkapi checklist dan semua kelompok pada revisi/snapshot sama; perubahan membatalkan keputusan lama. Approval rilis tidak memberi akses baca. |
| `SCHEMA_REVIEW_REQUIRED` | Versi konfigurasi belum memiliki bukti review schema yang diwajibkan. | Buat/clone draft, lihat Preview perubahan schema di langkah 7, konfirmasi, lalu submit dan approval ulang. |
| `SCHEMA_MIGRATION_STALE` | Schema/data target berubah setelah preview schema disetujui. | Muat ulang preview dan review draft terbaru. Jangan mengulangi deploy dengan bukti lama. |
| `SCHEMA_MIGRATION_BLOCKED` | Perubahan schema tidak aman atau bukti konversi tidak cukup. | Baca blocker preview. Bigint ke date wajib Serial Google Sheets hanya jika terbukti serial; periksa contoh/nilai gagal. Rename/drop/key/dependency tidak aman memerlukan rencana migrasi yang direview. |
| `SEMANTIC_SCHEMA_MIGRATION_REQUIRED` | View/proyeksi atau dependency memerlukan perubahan yang harus ditinjau. | Tinjau Preview perubahan schema pada draft terbaru; deploy melalui worker jika didukung. Jika diblokir, admin meninjau dependency/ACL, tanpa DROP CASCADE sembarang. |
| `SCHEMA_CHANGE_UNSAFE` | Error dari alur lama saat perubahan tipe/nullability belum didukung otomatis. | Periksa apakah job lama. Gunakan draft dan preview schema terbaru; selesaikan blocker sebelum approval/deploy. Jangan hapus tabel untuk melewatinya. |
| `ARTIFACT_MISSING` | Runtime artifact yang diperlukan deploy belum tersedia. | Periksa versi konfigurasi dan proses export/generasi artifact; admin memeriksa storage/log. Buat artifact melalui aplikasi pada versi yang benar. |
| `ARTIFACT_HASH_MISMATCH` | Isi artifact berbeda dari registry konfigurasi. | Hentikan deploy versi tersebut. Admin periksa integritas artifact/storage; buat ulang melalui alur aplikasi dan review jika revisi berubah. |
| `VALIDATION_ERROR` | Field permintaan tidak sesuai schema API; parameter wajib, tipe, format atau batas nilai tidak valid. | Baca details.field pada respons atau pesan field di form. Perbaiki nilai sesuai mapping/format yang didukung, lalu kirim ulang; approval tidak melewati validasi. |
| `RESOURCE_CONFLICT` | Data duplikat atau relasi melanggar constraint database. | Periksa kode/nama yang sudah terdaftar dan relasi objek. Muat ulang daftar/detail sebelum mencoba; jangan mendaftarkan ulang sumber yang sama. |
