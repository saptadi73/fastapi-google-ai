---
id: cleansing-text-dan-review-ai
title: Cleansing text otomatis dan review AI
summary: Trim text/varchar, nilai kosong, perlindungan masking, bukti duplikat dan recheck sync manual.
routes: ["/workspace", "/etl-review/*", "/import-reviews/*", "/sources", "/quality"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/PANDUAN_REVIEW_ETL.md
---
Kolom `text` dan `varchar` selalu mendapat `trim` otomatis pada nilai sumber sebelum transformasi tambahan, validasi DQ/key, pemeriksaan AI, dan pemuatan. `"  KAN  Jabung  "` menjadi `"KAN  Jabung"`: spasi di tengah, huruf, dan nol depan tetap dipertahankan. Nilai berisi spasi saja menjadi kosong/NULL; nullable mengizinkannya, kolom wajib tetap menghasilkan TYPE_OR_NULL_ERROR. Transformasi tambahan seperti normalize_whitespace, prefix/suffix, atau koreksi ejaan perlu aturan yang direview; trim dasar tidak perlu ditambahkan satu per satu. Nilai sumber di Sheet tidak ditulis ulang.

AI tidak boleh menganggap `[REDACTED]` sebagai data rusak atau menyimpulkan duplikat dari nilai yang disamarkan. Temuan duplikat memakai `issue_kind=EXACT_DUPLICATE` dan `related_source_row`; server membandingkan seluruh data asli di staging. Temuan pada nilai tersembunyi atau duplikat yang tidak terbukti dicatat sebagai temuan yang diabaikan pada checkpoint/audit tanpa membocorkan nilai. `VALUE_ISSUE` seperti dugaan typo, istilah, atau label hanya menjadi peringatan; hasil AI yang parsial atau tidak tersedia juga tidak menahan batch. Validasi tipe/null, business key, referensi, aturan kualitas, exact duplicate yang terbukti, serta `PRIVACY_RISK` pada kolom terbuka tetap memerlukan penyelesaian sebelum pemuatan.

Sync manual pada konfigurasi NON_MASTER aktif yang telah disetujui dapat memeriksa ulang batch NEEDS_INPUT dengan blocker AI saja dan seluruh pertanyaan masih terbuka tanpa keputusan pengguna. Worker mengulang cleansing/validasi lalu review AI, mempertahankan identitas staging dan audit pertanyaan lama. Batch dengan keputusan, blocker teknis, konflik, atau gate akses/rilis belum selesai tidak dilompati. Muat ulang halaman tidak menjalankan sync.

Pada batch lama yang menunggu `AI_REVIEW_ISSUES`, pemilik dapat menandai semua pertanyaan `VALUE_ISSUE` terbuka sebagai telah ditinjau melalui `POST /api/v1/import-reviews/{id}/dismiss-ai-suggestions`. Kirim `revision_no` terbaru dan alasan minimal 10 karakter. Tindakan ini menutup saran saja, menyimpan audit, dan tidak mengubah nilai staging atau Sheet. Pertanyaan exact duplicate, privacy risk, error kualitas, dan blocker lain tetap terbuka.
