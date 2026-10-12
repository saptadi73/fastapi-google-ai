---
id: "binding-master-referensi"
title: "Binding master: contoh mapping bisnis dan rujukan"
summary: "Contoh BISNIS/is_active, business key stabil dan rujukan NON_MASTER yang berbeda dari binding tab."
routes: ["/masters", "/masters/*", "/sources/*", "/guide"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: "docs/PANDUAN_BINDING_MASTER.md"
---
- **Binding tab sumber ke master**: Memuat atau memperbarui record rujukan dari tab MASTER ke master di Registry. Contoh: Tab Master Data berisi daftar bisnis → Master Bisnis.
- **Binding kolom referensi master**: Memvalidasi kode pada tab NON_MASTER terhadap record master yang sudah tersedia. Contoh: Kolom Kode Bisnis pada data marketing → business_code di Master Bisnis.

Contoh fiktif yang disarankan: Sheet mempunyai Kode Bisnis, Nama Bisnis dan is_active. Kode disimpan sebagai text agar nol depan tetap utuh. Sesuaikan header dengan Sheet nyata.

| Header sumber | Field master | Tipe | Aturan | Contoh |
| --- | --- | --- | --- | --- |
| Kode Bisnis | business_code | text | Wajib, unik, stabil; business key | BIS-001 |
| Nama Bisnis | business_name | text | Wajib; field label | Unit Contoh |
| is_active | is_active | boolean | Isi sesuai status sebenarnya | TRUE |

Jika Sheet saat ini hanya memiliki BISNIS dan is_active, petakan BISNIS ke field nama bisnis yang sesuai. Menggunakannya sebagai business key hanya layak jika nilainya unik, stabil dan tidak kosong. Jika nama dapat berubah, tambahkan kode bisnis stabil di Google Sheets, profiling ulang, lalu review definisi/binding; jangan membuat kode atau memetakan header yang belum ada.

Binding kolom referensi:

1. Pastikan definisi master aktif/tervalidasi, storage siap dan record rujukan sudah selesai di-Apply.
2. Di Workspace, pilih tab NON_MASTER yang sudah diprofil, lalu Atur referensi master.
3. Pilih kolom sumber berisi kode, master tujuan dan satu field master yang nilainya sama serta unik. Contoh Kode Bisnis bernilai BIS-001 → business_code bernilai BIS-001.
4. Muat rekomendasi hanya membantu kemiripan nama; cocokkan isi sumber dengan record master sebelum memakai kandidat. UUID internal tidak perlu disalin ke Sheet.
5. Pilih MANY_TO_ONE bila banyak transaksi boleh merujuk satu bisnis. Centang Referensi wajib ada jika semua baris harus memiliki rujukan.
6. Simpan binding kolom dan periksa validasinya. Owner workflow tidak memerlukan approval rutin kedua; legacy mengikuti review yang ditampilkan. Lanjutkan konfigurasi/pemuatan NON_MASTER dengan target referensi yang sesuai.
7. Nilai tidak ditemukan/ambigu dihentikan untuk review. Binding referensi tidak membuat record master baru secara otomatis. Master dengan key gabungan memerlukan satu field kode rujukan unik untuk resolver kolom.

Panduan utuh: /guide#binding-master atau docs/PANDUAN_BINDING_MASTER.md.
