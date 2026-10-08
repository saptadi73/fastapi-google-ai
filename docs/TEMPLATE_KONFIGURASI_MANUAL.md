# Template konfigurasi ETL manual

Gunakan template manual setelah profiling selesai. Template mengambil nama kolom dan perkiraan tipe dari sumber, lalu pengguna memeriksa empat hal sebelum membuat draft:

1. **Grain**: arti satu baris, misalnya `satu baris per transaksi` atau `satu baris per produk`.
2. **Tipe tujuan**: `bigint` untuk bilangan bulat, `numeric` untuk nilai desimal/uang, `date` atau `timestamp` untuk waktu, `boolean` untuk ya/tidak, dan `text` untuk kode atau uraian.
3. **Business key**: kolom yang mengidentifikasi baris secara unik. Key wajib terisi dan dipakai pada template **Upsert**. Contoh: `product_code`, `customer_id`, atau gabungan `unit_code` dan `period`.
4. **Sensitivitas**: tandai `HIGH` untuk identitas, kontak, atau informasi rahasia; tandai `NONE` untuk atribut umum yang boleh dipakai sebagai dimensi analitik.

## Pilihan template

| Template | Gunakan saat | Contoh |
| --- | --- | --- |
| Append | Setiap sinkronisasi menambah catatan baru | transaksi harian, log aktivitas |
| Full refresh | Isi tabel selalu merupakan snapshot terbaru | stok, daftar unit, saldo saat ini |
| Upsert | Baris lama diperbarui berdasarkan key | master produk, master pelanggan |

Setelah draft dibuat, buka halaman review untuk menambah transformasi, aturan kualitas, taxonomy, metric, dan approval. Draft manual tetap mengikuti validasi, review, dan approval yang sama dengan draft AI.

## Contoh pemetaan

| Header sumber | Nama tujuan | Tipe | Key | Sensitivitas |
| --- | --- | --- | --- | --- |
| `PRODUCT_CODE` | `product_code` | text | Ya | NONE |
| `PRODUCT_NAME` | `product_name` | text | Tidak | NONE |
| `QTY` | `quantity` | bigint | Tidak | NONE |
| `PRICE` | `price` | numeric | Tidak | NONE |
| `UPDATED_AT` | `updated_at` | timestamp | Tidak | NONE |

Jika belum yakin, pilih `APPEND`, biarkan key tidak dicentang, lalu minta pemeriksaan steward. Jangan memilih `UPSERT` sebelum key benar-benar unik dan tidak nullable.
