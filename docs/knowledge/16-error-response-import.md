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
| `AI_REVIEW_NOT_IMPLEMENTED` | Kode lama untuk capability review AI yang belum tersedia. | Periksa status batch terkini. Konfigurasi tanpa AI kini dapat melewati pemeriksaan AI dengan status SKIPPED setelah validasi deterministik; kode lama ini bukan alasan untuk mengabaikan blocker data. |
| `IMPORT_INPUT_PENDING` | Pertanyaan, keputusan, atau blocker batch belum selesai. | Buka batch dan selesaikan semua temuan wajib. Keputusan pengguna tidak dihapus oleh sync ulang. Owner workflow: Preview lalu Apply setelah validasi; legacy dapat meminta approval sebelum Apply. |
| `IMPORT_STALE_REVIEW` | Snapshot, konfigurasi, atau dependency batch berubah. | Klik Validasi ulang untuk membuat atau membuka batch pengganti dengan snapshot profiling terakhir dan konfigurasi aktif. Jika header berubah, perbarui profil dan mapping dahulu. Periksa preview baru lalu Apply oleh pemilik; jangan gunakan preview lama. |
| `IMPORT_PREVIEW_STALE` | Revisi atau rencana pemuatan berubah setelah preview/approval. | Buat preview ulang pada revisi terbaru dan Apply dengan token terbaru. Workflow legacy dapat meminta approval jika status batch menampilkannya. |
| `IMPORT_ACTIVE_APPROVAL_REQUIRED` | Sync langsung tidak memenuhi syarat konfigurasi ACTIVE, approval terpisah, akses/rilis, atau strategi load. | Pastikan konfigurasi tervalidasi/aktif dan akses siap. Owner workflow dapat menjalankan FULL_REFRESH setelah preview valid dan konfirmasi. Master memakai batch import dengan preview dan Apply; legacy mengikuti gate approval yang tampil. |
| `MASTER_BINDING_REQUIRED` | Sumber master belum memiliki binding yang diwajibkan. | Buka Registry master, lengkapi binding pada definisi/profil terbaru dan jalankan validasi. Pada owner workflow, lanjutkan ke batch master tanpa approval binding rutin; legacy mengikuti status yang tampil. |
| `MASTER_STORAGE_REQUIRED` | Storage master belum tersedia atau siap. | Pemilik data deploy storage setelah meninjau rencana schema dan konfirmasi. Legacy mengikuti alur review yang tampil; periksa binding lalu ulang batch master. |
