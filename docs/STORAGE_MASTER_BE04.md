# Storage master kanonis — BE-04

BE-04 menyediakan tabel record bertipe dan pencarian terotorisasi. Registry/binding BE-03 tetap digunakan. Import Google Sheet belum mengisi tabel ini: review batch dan apply masih BE-05–BE-07, kemudian integrasi/validasi lengkap BE-08–BE-11. `execution_ready` tetap `false` dan sync MASTER tetap mendapat `MASTER_RUNTIME_PENDING`.

## Identitas dan schema fisik

Target selalu `trusted.master_<master UUID tanpa tanda hubung>`, terlepas dari tab, kode, atau nama master. Dua tab yang terikat ke master sama memakai target yang sama. Field bisnis disimpan dalam tipe PostgreSQL sesuai versi definisi approved. Kode dengan leading zero harus memakai `text`/`varchar`; `001` tetap berbeda dari `1`. Composite business key mempunyai unique constraint pada kolom-kolom bertipe, bukan string gabungan.

| Kolom internal | Makna |
|---|---|
| `_tenant_id` | Tenant pemilik; NOT NULL dan CHECK terhadap tenant pemilik tabel |
| `_record_id` | UUID stabil yang diberikan penulis internal saat insert; bukan kode atau label |
| `_is_active` | Default true; penonaktifan bukan update atribut |
| `_revision_no` | Positif, default 1; update atribut memeriksa dan menambah revisi |
| `_created_at`, `_updated_at` | Timestamp timezone-aware, default waktu database |
| `_source_sheet_id`, `_source_row` | Asal data; baris harus positif |
| `_source_snapshot_hash` | Hash snapshot asal, maksimal 64 karakter |

Unique constraints: `(_tenant_id, _record_id)` dan `(_tenant_id, <business key...>)`. Seluruh business key NOT NULL. Field bisnis tidak boleh memakai nama internal karena schema hanya menerima nama diawali huruf. Lineage per perubahan dan histori lengkap masih menjadi bagian applier/batch berikutnya; metadata asal belum merupakan FK ke sumber atau bukti approval batch.

## Alur frontend

1. Selesaikan approval definisi master BE-03.
2. Ambil `GET /api/v1/master-definitions/{master_id}/storage-plan` untuk melihat target, versi approved, revisi registry, DDL CREATE, dan kebijakan schema. DDL pada respons merupakan bentuk target lengkap, bukan diff ALTER dari kondisi database saat ini. Endpoint ini tidak membuat tabel.
3. Reviewer memanggil `POST /api/v1/master-definitions/{master_id}/deploy-storage` menggunakan revisi terkini. Dapat diulang dengan aman untuk schema identik. Tidak menaikkan revisi definisi dan tidak memuat data.
4. Ambil `GET /api/v1/master-definitions/{master_id}/records` untuk daftar/pencarian. Tabel yang baru dibuat mengembalikan daftar kosong. Jangan tampilkan keberhasilan import hanya karena `storage_ready=true`.

Role baca: `PLATFORM_ADMIN`, `SOURCE_OWNER`, `DATA_STEWARD`, `TECHNICAL_APPROVER`. Deploy hanya `PLATFORM_ADMIN`/`TECHNICAL_APPROVER`. Viewer/analyst belum mendapat akses katalog record. Tenant lain mendapat 404.

Payload deploy memakai `MasterRevisionRequest` yang sudah tersedia:

```json
{"revision_no":3,"comment":"Siapkan storage untuk master yang telah disetujui"}
```

Contoh respons deploy:

```json
{
  "status":"success",
  "data":{
    "target":"trusted.master_11111111111141118111111111111111",
    "master_version":1,
    "storage_ready":true,
    "execution_ready":false
  },
  "meta":{},
  "errors":[]
}
```

Pencarian: `?search=001&offset=0&limit=50&active_only=true`. `search` maksimal 200 karakter, cocok sebagian pada business key/label yang dapat dilihat pengguna. `%`/`_` diperlakukan literal. `limit` 1–100, `offset` minimal 0. `active_only=false` menyertakan record nonaktif. `record_id=<UUID>` dapat dipakai untuk kandidat tertentu. Urutan berdasarkan UUID stabil; pagination offset tidak menjanjikan snapshot konsisten antar-request jika data berubah.

Contoh respons daftar (contoh record untuk kontrak frontend; BE-04 tidak menyediakan insert publik):

```json
{
  "status":"success",
  "data":{
    "items":[{
      "_tenant_id":"22222222-2222-4222-8222-222222222222",
      "_record_id":"33333333-3333-4333-8333-333333333333",
      "_is_active":true,
      "_revision_no":2,
      "_created_at":"2026-09-08T00:00:00Z",
      "_updated_at":"2026-09-08T01:00:00Z",
      "_source_sheet_id":"44444444-4444-4444-8444-444444444444",
      "_source_row":2,
      "_source_snapshot_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "product_code":"001",
      "product_name":"Produk A",
      "salary":"***"
    }],
    "has_more":false,
    "masked_fields":["salary"]
  },
  "meta":{"offset":0,"limit":50},
  "errors":[]
}
```

`PLATFORM_ADMIN`/`DATA_STEWARD` boleh melihat field MEDIUM/HIGH. Untuk SOURCE_OWNER/TECHNICAL_APPROVER field tersebut tidak diambil dari database dan respons memakai `***`, termasuk bila nilainya null. Pencarian juga tidak memakai field tersembunyi agar hasil pencarian tidak membocorkan nilainya. UUID dan metadata asal tetap terlihat bagi role baca. Gunakan `masked_fields` untuk membedakan placeholder dari nilai asli.

## Perubahan schema dan record

Approval versi berikutnya hanya mendukung perubahan metadata (nama, label, alias, klasifikasi PII/policy) serta penambahan field nullable. Setelah penambahan field disetujui, baca record ditahan dengan `MASTER_STORAGE_STALE` sampai reviewer menjalankan deploy-storage lagi. Deploy menjalankan ADD COLUMN dalam transaksi; record lama bernilai null pada field baru.

Perubahan business key, tipe, nullability, penghapusan/rename field, atau field baru wajib ditolak dengan `MASTER_SCHEMA_MIGRATION_REQUIRED`. Belum tersedia endpoint migrasi khusus untuk perubahan tersebut. Jangan menghapus tabel lalu membuat ulang karena UUID record harus dipertahankan. Penyimpangan kolom, tipe, unique constraint, atau tenant CHECK pada tabel fisik juga ditolak, tanpa otomatis menghapus data.

Compiler menolak strategi selain UPSERT, termasuk FULL_REFRESH. Primitive internal update atribut memeriksa tenant, UUID, status aktif, dan revisi, serta menolak perubahan key/UUID/status/metadata. Primitive ini tidak dipanggil endpoint publik; integrasi approval, lineage perubahan, dan insert atomik lengkap masih BE-07. Merge, ganti key, penonaktifan record, DELETE dan TRUNCATE tidak disediakan lewat API BE-04. Pengguna database yang memiliki izin langsung tetap harus dibatasi melalui pengaturan role deployment.

## Error penting

| HTTP | Code | Tindakan frontend |
|---|---|---|
| 403 | FORBIDDEN | Periksa role |
| 404 | RESOURCE_NOT_FOUND | Master tidak tersedia dalam tenant |
| 409 | MASTER_NOT_APPROVED | Master harus aktif dan memiliki versi approved |
| 409 | MASTER_REVISION_CONFLICT | Muat ulang revisi sebelum deploy |
| 409 | MASTER_STORAGE_REQUIRED | Jalankan deploy-storage |
| 409 | MASTER_STORAGE_STALE | Deploy storage setelah perubahan versi approved |
| 409 | MASTER_SCHEMA_MIGRATION_REQUIRED | Perlu penanganan migrasi khusus; jangan retry otomatis |
| 409 | MASTER_RUNTIME_PENDING | Review/apply import belum tersedia |
| 422 | VALIDATION_ERROR | Koreksi parameter/payload |

## Rollout dan batas transaksi

Tidak ada migrasi Alembic baru BE-04: tabel dinamis dibuat per master melalui deploy-storage setelah migrasi registry BE-03 tersedia. Pengguna telah melaporkan migrasi sebelumnya selesai; sesi ini tidak menjalankan DDL pada database aplikasi.

DDL memakai `DATABASE_DDL_URL` dengan fallback `DATABASE_URL`. Role DDL memerlukan CREATE pada schema trusted serta ownership untuk ALTER/GRANT target. Deploy memberikan SELECT/INSERT/UPDATE pada tabel kepada role DATABASE_URL; tidak menambahkan DELETE/TRUNCATE atau akses ke role NL2SQL. Hak schema USAGE tetap bagian setup role lingkungan.

Lock registry menserialisasi deployment terhadap perubahan definisi; advisory lock melindungi target DDL. DDL berada dalam transaksi tersendiri dari audit registry. Jika DDL berhasil tetapi commit audit gagal, tabel dapat sudah tersedia: retry memeriksa schema dan membuat audit kembali. Kegagalan satu transaksi ALTER akan rollback seluruh ALTER di transaksi tersebut. Tidak ada cleanup DROP otomatis terhadap tabel yang sudah dibuat. Pemulihan lintas transaksi lengkap tetap bagian hardening operasional BE-09/BE-16.

Lihat [API Reference](API_REFERENCE.md), [Registry BE-03](REGISTRY_MASTER_BE03.md), dan [TODO backend](TODO_BACKEND.md). Frontend belum diubah pada tahap ini.

Verifikasi 8 September 2026: **87 tes backend lulus**, Ruff lulus, dan exporter memverifikasi **107 operasi API**. Tes PostgreSQL mencakup UUID stabil saat label diubah, leading zero, composite key, dua insert bersamaan, tenant CHECK, unique UUID, revisi stale, role/tenant, masking tanpa kebocoran pencarian, pagination, deployment berulang, penambahan nullable, dan penolakan schema yang tidak sesuai. Pemeriksaan tambahan offline memverifikasi perubahan key/tipe/nullability/penghapusan/field wajib ditolak serta nama target tetap saat master berganti nama. Provider nyata dan role DDL terpisah pada lingkungan production belum diverifikasi.
