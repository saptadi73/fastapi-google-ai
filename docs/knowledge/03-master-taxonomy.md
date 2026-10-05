---
id: master-dan-taxonomy
title: Master data, referensi, dan taxonomy
summary: Kapan memakai master atau taxonomy dan urutan menyiapkan definisi, versi, storage, record, serta binding.
routes: ["/masters/*", "/taxonomies/*", "/governance"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/MASTER_DATA_DAN_VALIDASI_IMPORT.md
---
Gunakan master data untuk entitas rujukan yang memiliki identitas dan business key stabil, seperti produk, cabang, pelanggan, atau departemen. Buat definisi dan field, tentukan business key serta label, ajukan review, siapkan storage, isi record rujukan, lalu buat binding dari kolom sumber ke field master. Binding harus approved dan sesuai versi aktif sebelum import dapat menyelesaikan referensi.

Gunakan taxonomy untuk daftar istilah atau kategori terkendali, seperti jenis biaya, kategori aktivitas, atau status bisnis. Kelola term, alias, hierarki, versi, dan binding kolom. Versi yang telah diterbitkan tidak diubah langsung; buat draft versi berikutnya, tinjau, lalu aktifkan.

Jika nilai sumber tidak cocok dengan master atau taxonomy, proses import membuat pertanyaan atau kandidat. Steward perlu memilih kandidat, mengoreksi nilai sumber, atau mengusulkan penambahan sesuai policy. Sistem tidak memilih kecocokan ambigu secara otomatis.

