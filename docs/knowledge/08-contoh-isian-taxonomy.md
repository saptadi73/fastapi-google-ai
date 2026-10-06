---
id: contoh-isian-taxonomy
title: Contoh pengisian taxonomy dan term
summary: Contoh kode, nama, term, label, parent, alias, dan binding taxonomy ke kolom spreadsheet.
routes: ["/taxonomies", "/taxonomies/*", "/sources/*"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/CONTOH_ISIAN_APLIKASI.md
---
Contoh berikut adalah data fiktif untuk menjelaskan form, bukan taxonomy yang otomatis tersedia pada tenant.

Di halaman Registry taxonomy, form "Buat taxonomy" hanya meminta dua isian wajib:

| Isian | Contoh | Arti |
|---|---|---|
| Kode | `jenis_biaya` | Identitas bisnis yang unik dan stabil. Gunakan huruf kecil, angka, dan garis bawah; mulai dengan huruf. |
| Nama | `Jenis Biaya` | Nama yang mudah dibaca pengguna. |

Sesudah draft dibuat, tambahkan term. Contoh term pertama: kode `operasional`, label `Biaya Operasional`, parent `Root`, alias `OPEX` dan `biaya rutin` (satu alias per baris). Contoh term kedua: kode `investasi`, label `Biaya Investasi`, parent `Root`, alias `CAPEX`. Kode dan label term wajib; parent serta alias opsional. Parent dipilih dari term pada taxonomy yang sama untuk membuat hierarki. Jangan membuat alias yang ambigu bagi dua term berbeda.

Kode taxonomy maupun term maksimal 63 karakter dan memakai pola huruf kecil, angka, serta `_`, diawali huruf. Nama dan label maksimal 200 karakter; satu term dapat memiliki sampai 30 alias. UUID taxonomy dan term dibuat oleh sistem, sehingga tidak perlu diketik pengguna.

Urutan kerja: buat taxonomy draft → tambah term → reviewer menyetujui taxonomy → buka binding kolom pada tab yang sudah diprofilkan → pilih header sumber, taxonomy approved, dan opsi "Nilai wajib ada pada taxonomy" → simpan draft binding → reviewer menyetujui binding. Normalisasi yang tersedia pada form adalah `TRIM_CASEFOLD`; versi taxonomy dan ID diambil dari pilihan sistem. Contoh binding: header sumber `Jenis Biaya` dipetakan ke taxonomy `jenis_biaya` versi aktif. Jika nilai sumber `OPEX`, sistem dapat mengenalinya sebagai alias `operasional`; kandidat yang tidak pasti tetap perlu keputusan pengguna.

Setelah taxonomy approved, perubahan term dilakukan melalui draft versi berikutnya dan review, bukan dengan mengedit langsung versi terbit. Jika versi berubah, binding dan konfigurasi yang merujuk versi lama mungkin perlu diperbarui serta disetujui ulang.

