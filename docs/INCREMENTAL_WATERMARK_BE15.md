# Incremental watermark BE-15

Watermark dikonfigurasi per tab melalui:

```http
PATCH /api/v1/source-sheets/{sheet_id}/watermark
```

```json
{"revision_no":1,"source_column":"Updated At","kind":"DATETIME"}
```

Kind yang didukung adalah `INTEGER`, `DECIMAL`, `DATE`, dan `DATETIME`. DATETIME wajib
memiliki offset timezone dan dinormalisasi ke UTC. Kolom harus tersedia pada profil tab
terbaru. `source_column=null` dan `kind=null` menonaktifkan serta mereset watermark.
Perubahan kolom/kind juga mereset nilai dan menaikkan revision.

Runtime hanya memproses baris dengan nilai lebih besar dari `watermark_value`. Posisi
baris lama diganti slot kosong agar `_source_row`, evidence, dan koreksi tetap menunjuk
baris Google Sheet asli. Nilai kosong/tidak valid menolak batch; `FULL_REFRESH` tidak
kompatibel karena pemuatan parsial akan menghapus data lama.

Pada ETL langsung, candidate watermark ditulis setelah seluruh load selesai dan hanya
bila tidak ada issue DQ. Pada import review, base, revision, dan candidate dipin saat
batch dibuat. Apply mengunci tab, memeriksa base/revision tetap sama, menjalankan semua
write, lalu memajukan watermark dalam transaksi yang sama. Kegagalan atau rollback tidak
mengubah watermark. Konflik menghasilkan `WATERMARK_STALE`.

Migration `g7c0e3f6b8d5` harus diterapkan sebelum fitur dipakai.
