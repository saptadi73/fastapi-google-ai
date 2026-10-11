---
id: error-response-import
title: Error response - Validasi data dan batch import
summary: Tabel penyebab dan tindakan untuk TYPE_OR_NULL_ERROR, DUPLICATE_BUSINESS_KEY, AI_REVIEW_ISSUES, AI_REVIEW_NOT_IMPLEMENTED, IMPORT_INPUT_PENDING, IMPORT_STALE_REVIEW, IMPORT_PREVIEW_STALE, IMPORT_ACTIVE_APPROVAL_REQUIRED, MASTER_BINDING_REQUIRED, MASTER_STORAGE_REQUIRED.
routes: ["/import-reviews", "/import-reviews/*", "/workspace", "/quality", "/guide"]
audiences: ["*"]
source: docs/ERROR_RESPONSES.md
---
Cari kode pada pesan error atau monitor job; catat ID job, sumber/tab dan versi konfigurasi. Penyebab di bawah adalah kemungkinan, bukan diagnosis otomatis. Baca detail/log untuk menentukan kasus yang terjadi. DEFAULT_DENY, EXPLICIT_DENY dan ACTION_NOT_GRANTED adalah reason_code keputusan akses; TYPE_OR_NULL_ERROR/DUPLICATE_BUSINESS_KEY adalah temuan validasi; AI_REVIEW_ISSUES/AI_REVIEW_NOT_IMPLEMENTED adalah blocker checkpoint. Kode tersebut tidak selalu muncul sebagai error HTTP. NEEDS_INPUT berarti menunggu tindakan, bukan worker sedang berjalan. Muat ulang halaman hanya membaca status; tidak menjalankan discovery, profiling atau sync. Jangan kirim password, token, API key atau nilai pribadi ke helper.

| Kode / respons | Kemungkinan penyebab | Tindakan yang dilakukan |
| --- | --- | --- |
| `TYPE_OR_NULL_ERROR` | Nilai gagal konversi tipe, melebihi batas, atau kosong pada kolom wajib. | Lihat detail baris/kolom. Periksa parser/format tanggal dan angka. Text/varchar di-trim otomatis; spasi saja menjadi NULL. Nullable hanya jika sah, bukan untuk menutupi format salah. |
| `DUPLICATE_BUSINESS_KEY` | Business key berulang dalam batch, termasuk setelah trim. | Periksa grain dan key di baris yang ditunjuk; perbaiki duplikat sumber atau mapping, kemudian validasi ulang. Jangan menghapus key hanya agar lolos. |
| `AI_REVIEW_ISSUES` | AI menemukan nilai yang perlu diverifikasi atau coverage belum lengkap. | Buka Lihat detail dan batch. KEEP_ORIGINAL hanya untuk nilai sah dengan alasan; koreksi sumber bila perlu. Sync manual dapat recheck batch AI-only tanpa keputusan; blocker nyata tetap berlaku. |
| `AI_REVIEW_NOT_IMPLEMENTED` | Pemeriksaan AI wajib belum dapat dijalankan karena konfigurasi/capability tidak tersedia. | Admin memeriksa key/model, health dan dukungan AI; lanjutkan batch melalui alur aplikasi setelah capability tersedia. Menunggu saja tidak menyelesaikan blocker. |
| `IMPORT_INPUT_PENDING` | Pertanyaan, keputusan, atau blocker batch belum selesai. | Buka batch dan selesaikan semua temuan wajib. Keputusan pengguna tidak dihapus oleh sync ulang; master/batch biasa tetap perlu preview, approval, Apply. |
| `IMPORT_STALE_REVIEW` | Snapshot, konfigurasi, atau dependency batch berubah. | Perbarui profil/dependency dan buat batch sesuai sumber terbaru; jangan menerapkan preview/approval lama. |
| `IMPORT_PREVIEW_STALE` | Revisi atau rencana pemuatan berubah setelah preview/approval. | Buat preview ulang pada revisi terbaru; revalidate dan approval ulang bila diperlukan, lalu Apply dengan token terbaru. |
| `IMPORT_ACTIVE_APPROVAL_REQUIRED` | Sync langsung tidak memenuhi syarat konfigurasi ACTIVE, approval terpisah, akses/rilis, atau strategi load. | Pastikan deploy selesai dan akses/rilis siap. FULL_REFRESH/master memakai alur review batch yang sesuai; jangan bypass approval. |
| `MASTER_BINDING_REQUIRED` | Sumber master belum memiliki binding yang diwajibkan. | Buka Registry master, lengkapi/review source binding pada versi/profil terbaru, lalu buat batch master. |
| `MASTER_STORAGE_REQUIRED` | Storage master belum tersedia atau siap. | Reviewer deploy storage definisi approved melalui Registry master; periksa binding lalu ulang batch master. |
