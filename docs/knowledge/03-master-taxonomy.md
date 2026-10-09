---
id: master-dan-taxonomy
title: Master data, referensi, dan taxonomy
summary: Kapan memakai master atau taxonomy dan urutan menyiapkan definisi, versi, storage, record, serta binding.
routes: ["/masters/*", "/taxonomies/*", "/governance", "/sources/*"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/MASTER_DATA_DAN_VALIDASI_IMPORT.md
---
Gunakan master data untuk entitas rujukan yang memiliki identitas dan business key stabil, seperti produk, cabang, pelanggan, atau departemen. Buat definisi dan field, tentukan business key serta label, ajukan review, siapkan storage, isi record rujukan, lalu buat binding dari kolom sumber ke field master. Binding harus approved dan sesuai versi aktif sebelum import dapat menyelesaikan referensi.

Untuk menentukan kolom yang berelasi dengan master, buka **Workspace ETL**, pilih sumber dan tab yang sudah selesai profiling, lalu pilih **Atur referensi master**. Pada halaman **Binding kolom referensi master**, pilih header sumber, master aktif yang sudah approved, dan field master yang berisi nilai rujukannya. Field tujuan sebaiknya unik dan stabil, biasanya business key. Contoh: kolom sumber `Kode Produk` bernilai `SKU-001` dipetakan ke field master `product_code` yang memiliki tepat satu record dengan nilai `SKU-001`. Pengguna tidak perlu menyalin atau memasukkan UUID internal master ke Sheet; sistem akan menyelesaikan nilai bisnis tersebut ke identitas record internal.

Tombol **Muat rekomendasi** membandingkan nama header sumber dengan field master menggunakan normalisasi format dan padanan istilah Indonesia/Inggris umum. Kandidat memperlihatkan master, field, tipe, business key, skor/tingkat kecocokan, dan alasan. Skor tinggi tetap hanya petunjuk berbasis nama: sistem tidak memeriksa isi kolom untuk membuktikan relasi. Cocokkan contoh nilai sumber dengan master dan pilih field unik yang tepat sebelum menggunakan kandidat. Tidak ada binding yang tersimpan otomatis; pengguna tetap meninjau dan reviewer menyetujui draft.

Simpan binding sebagai draft dan minta reviewer menyetujuinya. Centang **Referensi wajib ada** jika setiap baris harus memiliki rujukan; cardinality `MANY_TO_ONE` sesuai ketika banyak transaksi dapat menunjuk produk yang sama. Sesudah binding approved dan storage master siap, buka **Storage & record master**, pilih tab pada bagian **Sumber master terikat**, lalu tekan **Buat batch review/import**. Periksa batch di halaman **Batch import**: selesaikan pertanyaan, buat preview, minta approval reviewer berbeda, lalu apply. Binding approved saja belum memuat record. Nilai yang tidak ditemukan atau cocok ke beberapa record tidak dipilih diam-diam; selesaikan sebagai pertanyaan pada review import. Resolver binding saat ini mencari satu field master, jadi untuk master dengan business key gabungan gunakan satu kode rujukan unik yang juga tersedia di sumber. Tipe dan format harus konsisten; simpan kode berawalan nol sebagai teks.

Gunakan taxonomy untuk daftar istilah atau kategori terkendali, seperti jenis biaya, kategori aktivitas, atau status bisnis. Kelola term, alias, hierarki, versi, dan binding kolom. Versi yang telah diterbitkan tidak diubah langsung; buat draft versi berikutnya, tinjau, lalu aktifkan.

Jika nilai sumber tidak cocok dengan master atau taxonomy, proses import membuat pertanyaan atau kandidat. Steward perlu memilih kandidat, mengoreksi nilai sumber, atau mengusulkan penambahan sesuai policy. Sistem tidak memilih kecocokan ambigu secara otomatis.

