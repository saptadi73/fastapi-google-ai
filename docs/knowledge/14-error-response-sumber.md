---
id: error-response-sumber
title: Error response - Sumber Google Sheets dan discovery
summary: Tabel penyebab dan tindakan untuk SOURCE_CHANGE_CHECK_DENIED, SOURCE_READ_FAILED, SOURCE_ACCESS_DENIED, DRIVE_API_NOT_ENABLED, SOURCE_NOT_FOUND, INVALID_RANGE, SOURCE_TOO_LARGE, UPSTREAM_RATE_LIMITED, GOOGLE_NOT_CONFIGURED, IMPORT_SOURCE_TAB_MISSING, SOURCE_JOB_RUNNING.
routes: ["/sources", "/workspace", "/jobs", "/guide"]
audiences: ["*"]
source: docs/ERROR_RESPONSES.md
---
Cari kode pada pesan error atau monitor job; catat ID job, sumber/tab dan versi konfigurasi. Penyebab di bawah adalah kemungkinan, bukan diagnosis otomatis. Baca detail/log untuk menentukan kasus yang terjadi. DEFAULT_DENY, EXPLICIT_DENY dan ACTION_NOT_GRANTED adalah reason_code keputusan akses; TYPE_OR_NULL_ERROR/DUPLICATE_BUSINESS_KEY adalah temuan validasi; AI_REVIEW_ISSUES/AI_REVIEW_NOT_IMPLEMENTED adalah blocker checkpoint. Kode tersebut tidak selalu muncul sebagai error HTTP. NEEDS_INPUT berarti menunggu tindakan, bukan worker sedang berjalan. Muat ulang halaman hanya membaca status; tidak menjalankan discovery, profiling atau sync. Jangan kirim password, token, API key atau nilai pribadi ke helper.

| Kode / respons | Kemungkinan penyebab | Tindakan yang dilakukan |
| --- | --- | --- |
| `SOURCE_CHANGE_CHECK_DENIED` | Pemeriksaan perubahan file Google Drive ditolak, biasanya karena API belum aktif atau service account tidak memiliki akses metadata. | Periksa apakah Google Drive API aktif pada project service account. Jika sudah, pastikan service account dapat membaca metadata Drive. Jalankan Temukan tab dan Profiling ulang secara manual sementara itu. |
| `SOURCE_READ_FAILED` | Google menolak range; tab bisa hilang/berganti nama, atau permintaan tidak valid. | Buka monitor job. Source Owner/Steward/Admin: Workspace, pilih sumber, Temukan tab, tunggu SUCCEEDED, lalu Profiling ulang. Jika tetap gagal, admin periksa respons Google. |
| `SOURCE_ACCESS_DENIED` | Service Account tidak mendapat akses atau Google menolak otorisasi. | Pemilik Sheet memberi Service Account akses Viewer; admin memeriksa kredensial. Coba ulang setelah akses benar. |
| `DRIVE_API_NOT_ENABLED` | Google Drive API belum diaktifkan pada Google Cloud project yang dipakai service account. | Minta admin project mengaktifkan Google Drive API pada project service account, lalu tunggu propagasi dan ulangi pemeriksaan. Discovery/profiling manual tetap bisa dipakai. Jangan mengganti sharing Sheet bila akses Sheets sudah benar. |
| `SOURCE_NOT_FOUND` | Spreadsheet/tab tidak ditemukan atau tidak tersedia untuk kredensial server. | Periksa URL/ID, pemulihan file/tab, dan akses Viewer. Temukan tab ulang pada sumber yang sama. |
| `INVALID_RANGE` | Range A1 tidak didukung atau tidak dimulai dari baris 1. | Periksa pengaturan range, misalnya A:CV atau A1:CV1000. Tentukan header_row/data_start_row terpisah; review perubahan konfigurasi. |
| `SOURCE_TOO_LARGE` | Jumlah baris/kolom melebihi batas server. | Persempit range yang diperlukan atau bagi data. Admin meninjau kapasitas/batas sebelum menaikkannya; jangan memotong data diam-diam. |
| `UPSTREAM_RATE_LIMITED` | Google masih membatasi permintaan atau tidak tersedia setelah retry. | Tunggu lalu coba ulang sekali; admin memeriksa kuota dan status layanan. Jangan menumpuk job. |
| `GOOGLE_NOT_CONFIGURED` | File Service Account tidak tersedia atau konfigurasinya tidak valid. | Admin memperbaiki konfigurasi backend dan memeriksa health, lalu ulang proses. Jangan mengirim file key ke helper. |
| `IMPORT_SOURCE_TAB_MISSING` | Tab pada registry tidak lagi ditemukan di Sheet. | Source Owner/Steward/Admin menjalankan Temukan tab lalu Profiling ulang; pulihkan tab jika masih diperlukan. Riwayat lama tetap tersimpan. |
| `SOURCE_JOB_RUNNING` | Sumber memiliki job yang masih QUEUED/RUNNING. | Buka monitor job dan tunggu proses selesai. Jika macet, admin periksa worker sebelum retry. |
