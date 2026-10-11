---
id: error-response-akses
title: Error response - Akses pengguna dan katalog data
summary: Tabel penyebab dan tindakan untuk DEFAULT_DENY, EXPLICIT_DENY, ACTION_NOT_GRANTED, DATA_PRODUCT_NOT_FOUND, SELF_ACCESS_CHANGE, FORBIDDEN, STALE_REVISION.
routes: ["/admin", "/admin/users", "/access-requests", "/data-catalog", "/dashboard", "/guide"]
audiences: ["*"]
source: docs/ERROR_RESPONSES.md
---
Cari kode pada pesan error atau monitor job; catat ID job, sumber/tab dan versi konfigurasi. Penyebab di bawah adalah kemungkinan, bukan diagnosis otomatis. Baca detail/log untuk menentukan kasus yang terjadi. DEFAULT_DENY, EXPLICIT_DENY dan ACTION_NOT_GRANTED adalah reason_code keputusan akses; TYPE_OR_NULL_ERROR/DUPLICATE_BUSINESS_KEY adalah temuan validasi; AI_REVIEW_ISSUES/AI_REVIEW_NOT_IMPLEMENTED adalah blocker checkpoint. Kode tersebut tidak selalu muncul sebagai error HTTP. NEEDS_INPUT berarti menunggu tindakan, bukan worker sedang berjalan. Muat ulang halaman hanya membaca status; tidak menjalankan discovery, profiling atau sync. Jangan kirim password, token, API key atau nilai pribadi ke helper.

| Kode / respons | Kemungkinan penyebab | Tindakan yang dilakukan |
| --- | --- | --- |
| `DEFAULT_DENY` | Tidak ada policy ALLOW yang cocok; assignment wajib belum lengkap, kedaluwarsa, atau scope/policy tidak sesuai. | Admin cek Preview keputusan untuk akun/action/resource yang sama. Semua required attributes berlaku AND. Lengkapi assignment lewat approval admin lain atau revisi policy sesuai kewenangan; role admin/IT tidak otomatis lolos. |
| `EXPLICIT_DENY` | Ada policy DENY aktif yang cocok. | Admin meninjau alasan dan scope DENY. Perubahan mengikuti review policy; menambah ALLOW tidak mengalahkan DENY. |
| `ACTION_NOT_GRANTED` | Akun tidak mendapat tindakan yang diminta dari role/paket izin efektif. | Admin meninjau role dan permission grant aktif. Berikan hanya tindakan yang sah melalui alur approval; login ulang bila sesi berubah. |
| `DATA_PRODUCT_NOT_FOUND` | Produk tidak aktif/tidak ada, role tidak diizinkan, atau policy sumber/produk menolak akses. | Pastikan produk ACTIVE dan data dimuat. Periksa allowed_roles, SOURCE DISCOVER/READ/QUERY, lalu policy produk. Policy DATA_PRODUCT saja tidak menggantikan SOURCE; approval ETL bukan izin membaca. |
| `SELF_ACCESS_CHANGE` | Pengguna mencoba mengubah atau menyetujui aksesnya sendiri. | Minta admin berwenang lain memproses assignment/paket izin/approval. Reviewer harus berbeda dari subjek akses sesuai aturan aplikasi. |
| `FORBIDDEN` | Peran atau kepemilikan tidak mengizinkan tindakan. | Gunakan akun berwenang atau ajukan akses. Temukan tab/Profiling ulang tersedia untuk SOURCE_OWNER, DATA_STEWARD, PLATFORM_ADMIN; TECHNICAL_APPROVER mereview sesuai tugas. |
| `STALE_REVISION` | Objek akses berubah sejak halaman dimuat. | Muat ulang detail, tinjau perubahan dan kirim dengan revisi terbaru. Jangan overwrite perubahan pengguna lain. |
