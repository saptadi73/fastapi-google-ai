---
id: error-response-analitik
title: Error response - Formula analitik dan aturan action plan
summary: Tabel penyebab dan tindakan untuk ANALYTICS_RULES_INVALID, ANALYTICS_PERIOD_REQUIRED, ANALYTICS_SELF_APPROVAL, ANALYTICS_APPROVAL_REQUIRED, ANALYTICS_RULES_STALE, ANALYTICS_RESULT_TRUNCATED.
routes: ["/guide", "/workspace", "/jobs", "/guide"]
audiences: ["*"]
source: docs/ERROR_RESPONSES.md
---
Cari kode pada pesan error atau monitor job; catat ID job, sumber/tab dan versi konfigurasi. Penyebab di bawah adalah kemungkinan, bukan diagnosis otomatis. Baca detail/log untuk menentukan kasus yang terjadi. DEFAULT_DENY, EXPLICIT_DENY dan ACTION_NOT_GRANTED adalah reason_code keputusan akses; TYPE_OR_NULL_ERROR/DUPLICATE_BUSINESS_KEY adalah temuan validasi; AI_REVIEW_ISSUES/AI_REVIEW_NOT_IMPLEMENTED adalah blocker checkpoint. Kode tersebut tidak selalu muncul sebagai error HTTP. NEEDS_INPUT berarti menunggu tindakan, bukan worker sedang berjalan. Muat ulang halaman hanya membaca status; tidak menjalankan discovery, profiling atau sync. Jangan kirim password, token, API key atau nilai pribadi ke helper.

| Kode / respons | Kemungkinan penyebab | Tindakan yang dilakukan |
| --- | --- | --- |
| `ANALYTICS_RULES_INVALID` | Header, kode formula atau metrik numerik tidak sesuai kontrak. | Sesuaikan tab kontrol dengan template dan kode metrik produk aktif; impor ulang. |
| `ANALYTICS_PERIOD_REQUIRED` | Query aturan tidak memiliki periode between yang valid. | Pilih dimension waktu dan batas awal/akhir eksplisit, lalu buat draft baru. |
| `ANALYTICS_SELF_APPROVAL` | Pembuat mencoba menyetujui aturan sendiri. | Reviewer konfigurasi sumber yang berbeda memeriksa preview dan memutuskan. |
| `ANALYTICS_APPROVAL_REQUIRED` | Aturan masih DRAFT atau REJECTED. | Preview lalu minta approval; aturan ditolak perlu dibuat ulang. |
| `ANALYTICS_RULES_STALE` | Tab kontrol atau semantic berubah, sumber paused/unlinked, hash/status tidak cocok. | Muat ulang status, aktifkan sumber yang sah bila perlu; impor/buat draft dan review ulang. |
| `ANALYTICS_RESULT_TRUNCATED` | Hasil mencapai batas query/server sehingga dapat terpotong. | Persempit periode atau kelompok dimension; review draft baru sebelum evaluasi. |
