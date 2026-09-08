# BE-02 — Klasifikasi master/non-master per tab

Status: implementasi backend tersedia. Policy mengikuti keputusan [BE-01](KEBIJAKAN_DATA_BE01.md): klasifikasi per tab dan kode master baru diusulkan untuk ditambahkan dengan persetujuan. BE-02 menyimpan jenis tab dan menegakkan gate eksekusi. Registry, binding, serta pemuatan master kanonis baru dilanjutkan pada BE-03 dan seterusnya.

Pembaruan setelah BE-03: registry/binding metadata sudah tersedia. Blocker eksekusi MASTER kini `MASTER_RUNTIME_PENDING`; `MASTER_BINDING_REQUIRED` hanya dipakai pada GET binding yang belum ada. GET klasifikasi MASTER menambah ringkasan master_binding. Detail terbaru ada di [Registry master BE-03](REGISTRY_MASTER_BE03.md). Penjelasan implementasi awal BE-02 di bawah tetap menjadi riwayat tahap tersebut.

## Perilaku

- Tab hasil discovery dan tab lama dari migrasi dimulai dengan `dataset_kind: null`, `classification_status: CLASSIFICATION_REQUIRED`, dan `classification_revision: 1`.
- Editor mengonfirmasi `MASTER` atau `NON_MASTER`. Status menjadi `CONFIRMED`; revision naik dan actor/time dicatat.
- Konfirmasi `MASTER` berhasil disimpan, tetapi `execution_ready` tetap false dengan alasan `MASTER_BINDING_REQUIRED`. Master tidak dialihkan diam-diam ke tabel dataset mandiri.
- `NON_MASTER` yang sudah dikonfirmasi dapat melanjutkan alur konfigurasi yang tersedia. `execution_ready` hanya menunjukkan kelulusan gate klasifikasi, bukan bukti bahwa DQ, approval, atau konfigurasi aktif sudah lengkap.
- Discovery ulang mempertahankan klasifikasi tab yang sama. Sheet baru yang ditemukan tetap meminta konfirmasi.
- Profiling, draft manual/AI, edit, export/import draft, dan dry-run tetap tersedia sebelum klasifikasi untuk membantu keputusan.
- Submit-review, approve, deploy/activate/rollback, dan sync memeriksa klasifikasi di server. Penolakan konfigurasi tetap diperbolehkan walaupun klasifikasi belum lengkap.
- Sync satu sumber memeriksa **seluruh tab enabled**. Satu tab yang belum dikonfirmasi atau masih master tanpa binding menahan sync sumber tersebut; tab disabled tidak ikut pemuatan.
- Worker memeriksa kembali gate sebelum membaca Google dan menulis data. Job lama, scheduler, atau retry yang melewati endpoint sync tidak melewati gate tersebut.

## API aktif

Path relatif terhadap `/api/v1`. Bearer authentication dan envelope `{status,data,meta,errors}` mengikuti [API Reference](API_REFERENCE.md).

| Method dan path | Hak akses | Fungsi |
|---|---|---|
| `GET /source-sheets/{sheet_id}/classification` | Editor dan technical approver | Baca pilihan, revision, status, metadata konfirmasi, dan blocker |
| `PUT /source-sheets/{sheet_id}/classification` | PLATFORM_ADMIN, SOURCE_OWNER, DATA_STEWARD | Konfirmasi atau ubah jenis tab |

`sheet_id` adalah UUID tab internal dari `GET /sources/{source_id}/sheets`, bukan ID numerik Google. Klasifikasi tidak dikirim melalui `POST /sources/google-sheets`, `PATCH /source-sheets/{sheet_id}`, `ETLConfiguration`, atau Excel. Field `master_definition_id` belum diterima pada BE-02.

Payload PUT:

```json
{"revision_no":1,"dataset_kind":"NON_MASTER"}
```

`dataset_kind` wajib tepat `MASTER` atau `NON_MASTER`; null/string lain ditolak. `revision_no` wajib integer minimal 1 dan berasal dari GET klasifikasi, bukan revision konfigurasi ETL.

Contoh respons setelah konfirmasi:

```json
{
  "status":"success",
  "data":{
    "schema_version":"1.0",
    "classification_scope":"SHEET",
    "source_sheet_id":"22222222-2222-4222-8222-222222222222",
    "dataset_kind":"NON_MASTER",
    "status":"CONFIRMED",
    "revision_no":2,
    "confirmed_by":"11111111-1111-4111-8111-111111111111",
    "confirmed_at":"2026-09-08T08:00:00Z",
    "execution_ready":true,
    "blocking_reason":null
  },
  "meta":{},
  "errors":[]
}
```

Pada tab belum dikonfirmasi, `confirmed_by/at` dan `dataset_kind` null; `blocking_reason` berisi `{code: "CLASSIFICATION_REQUIRED", message: "..."}`. Pada MASTER yang dikonfirmasi, status tetap CONFIRMED, tetapi blocker menjadi `MASTER_BINDING_REQUIRED`.

Mengirim jenis yang sama dengan revision terkini merupakan no-op: revision, actor/time, dan audit tidak digandakan. Request dengan revision lama tetap 409, termasuk retry payload lama setelah konfirmasi berhasil. Dua update bersamaan diserialisasi dengan row lock; satu sukses dan satu perlu memuat ulang.

Record `SourceSheet` pada list sumber dan review konfigurasi juga mempunyai `dataset_kind`, `classification_status`, `classification_revision`, `classification_confirmed_by`, dan `classification_confirmed_at`. `GET /configurations/{id}/review` menambah objek `classification` dengan bentuk yang sama seperti GET klasifikasi.

## Hubungan dengan validasi dan persetujuan konfigurasi

Hasil `/validate` menambah `classification` dan `ready_for_review`. Field `valid` tetap menyatakan hasil validasi data/pertanyaan; ia dapat true sementara `ready_for_review` false karena tab belum diklasifikasi.

Frontend harus memakai `ready_for_review` sebelum menawarkan submit. Checklist dan snapshot_hash masih wajib dikirim sebagaimana [panduan review ETL](PANDUAN_REVIEW_ETL.md). Revisi klasifikasi tidak perlu dikirim pada body submit; server membaca dan menguncinya sendiri.

Submission menyimpan `classification_revision` dan `dataset_kind` dalam `Configuration.review_state`. Approve dan deployment memeriksa bukti tersebut terhadap tab saat ini. Mengubah jenis tab lalu mengembalikannya ke pilihan awal tetap menaikkan revision; submission lama tidak berlaku kembali.

- Draft NEEDS_REVIEW: lakukan submit ulang setelah validasi dan pemeriksaan pengguna.
- APPROVED/SUPERSEDED tanpa bukti klasifikasi yang sesuai: clone ke draft, review, approve, lalu deploy versi baru.
- Tab dengan konfigurasi ACTIVE: perubahan ke MASTER ditolak dengan `CLASSIFICATION_ACTIVE_CONFLICT`, karena perpindahan target memerlukan migrasi. Clone konfigurasi saja tidak mengubah target aktif menjadi master.
- Tab ACTIVE lama yang belum diklasifikasi boleh dikonfirmasi NON_MASTER agar sync yang sudah aktif dapat berjalan kembali. Konfirmasi ini tidak membuat runtime artifact baru. Jika tab sebenarnya master, jangan memilih NON_MASTER untuk melewati gate; tunggu migrasi master di tahap lanjutan.

Gate runtime merupakan pemeriksaan server, bukan jaminan bahwa jenis yang dipilih pengguna benar secara bisnis. BE-02 juga belum menjalankan review AI untuk seluruh nilai pada setiap sync; itu BE-10/BE-11.

## Error

| HTTP | Kode | Tindakan |
|---|---|---|
| 409 | CLASSIFICATION_REQUIRED | Buka klasifikasi tab dan konfirmasi jenisnya |
| 409 | MASTER_BINDING_REQUIRED | Klasifikasi tersimpan; lanjut implementasi registry/binding master sebelum memuat master |
| 409 | CLASSIFICATION_CONFLICT | Muat ulang revision klasifikasi; jangan retry dengan revision lama |
| 409 | CLASSIFICATION_ACTIVE_CONFLICT | Perubahan jenis membutuhkan migrasi target aktif |
| 409 | CLASSIFICATION_REVIEW_STALE | Review klasifikasi terbaru; clone konfigurasi immutable bila diperlukan |
| 403 | FORBIDDEN | Gunakan role editor untuk PUT; viewer/analyst tidak dapat membaca metadata sumber ini |
| 404 | RESOURCE_NOT_FOUND | Tab tidak ada atau berada pada tenant lain |
| 422 | VALIDATION_ERROR | Periksa enum, revision, dan field tambahan yang tidak didukung |

`POST /sources/{source_id}/sync` kini dapat mengembalikan 409 sebelum membuat job. Job yang sebelumnya sudah diantrekan dapat berakhir FAILED dengan kode yang sama ketika worker melakukan pemeriksaan ulang. Tidak ada tab enabled menghasilkan SOURCE_NOT_FOUND (404).

## Migrasi dan rollout

Migrasi: [b762af03e219_sheet_classification.py](../alembic/versions/b762af03e219_sheet_classification.py), setelah `9c32a61d740e`.

Migrasi menambah lima field klasifikasi, constraint konsistensi status/jenis/actor/waktu, constraint revision positif, serta composite FK `(tenant_id, classification_confirmed_by)` ke user tenant yang sama. Seluruh tab lama mendapat status perlu konfirmasi; nama, range, data, dan referensi konfigurasi aktif tetap dipertahankan.

Jalankan pada lingkungan tujuan saat rollout backend:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
```

Migrasi telah dicoba pada database `_test` terpisah. Database aplikasi/production belum diubah. Koordinasikan rollout dengan frontend: halaman Vue yang ada belum mempunyai form klasifikasi BE-02, sehingga konfirmasi sementara dilakukan melalui API/Swagger oleh editor. Setelah migrasi, sync lama tertahan sampai semua tab enabled dikonfirmasi NON_MASTER atau dinonaktifkan dari pemuatan secara sengaja.

Downgrade menghapus field/constraint klasifikasi sehingga pilihan konfirmasi hilang; ia tidak menghapus tabel data atau konfigurasi aktif. Backup metadata dan gunakan versi backend yang cocok bila melakukan rollback. Jangan melakukan downgrade schema sambil backend BE-02 masih mengakses kolom baru.

## Bukti pengujian

Hasil akhir: **77 tes backend lulus**, Ruff lulus, pemeriksaan Alembic terhadap database test tidak menemukan perbedaan model/schema, dan exporter memverifikasi **91 operasi API** beserta seluruh contoh payload. Upgrade migrasi hanya diterapkan pada database test terpisah.

- Tes migrasi menjalankan upgrade/downgrade pada tabel PostgreSQL dalam schema test terisolasi: tab lama tetap ada, konfigurasi aktif tidak berubah, dan klasifikasi tidak ditebak.
- Tes integrasi mencakup hak akses/tenant, enum/payload, revision/no-op, dua update bersamaan, metadata konfirmasi, dan constraint database.
- Gate diuji pada submit/approve, deploy yang diantrekan sebelum klasifikasi berubah, sync langsung, serta job worker yang dibuat tanpa endpoint sync.
- File campuran diuji dengan tab NON_MASTER dan MASTER; discovery ulang mempertahankan keputusan sebelumnya dan tab disabled tidak memblokir pemuatan tab lain.
- Provider Google/OpenAI pada tes memakai mock. Hasil pengujian tidak membuktikan akses atau kuota akun provider nyata.
