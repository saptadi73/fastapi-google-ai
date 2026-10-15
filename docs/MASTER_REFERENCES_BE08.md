# BE-08: resolver referensi dan perubahan dependency

Hardening 10 September 2026 membatasi resolusi ke binding approved milik tenant,
tab batch, kolom sumber, dan master yang diminta. Binding harus menunjuk versi
master aktif yang sesuai. Target UUID pada konfigurasi lama tetap kompatibel.
Mapping baru mempertahankan kode/nama sebagai text/varchar dan menyiapkan identitas
relasi internal otomatis (lihat pembaruan 15 Oktober 2026 di bawah).

## Rekomendasi binding dari nama kolom

GET `/source-sheets/{sheet_id}/column-bindings/recommendations` membandingkan header
profil terbaru dengan field pada master tenant yang aktif dan berstatus APPROVED.
Nama dinormalisasi terhadap kapitalisasi, tanda baca, separator, serta padanan umum
Indonesia/Inggris (misalnya `Kode Produk` dan `product_code`). Kandidat dengan
skor minimal 0,55 dikembalikan dengan skor, confidence HIGH/MEDIUM/LOW, alasan,
master dan versi, tipe field, serta penanda business key. Business key diprioritaskan
bila skornya sama.

Ini hanya pencocokan nama; endpoint tidak membaca nilai baris untuk membuktikan relasi.
Frontend tidak menyimpan relasi otomatis. Pemilik memeriksa field tujuan dan memilih
relasi pada langkah Kolom di Workspace ETL. Owner workflow melanjutkan tanpa approval
rutin; jalur legacy mengikuti status review yang sudah ada. Nilai yang tidak ditemukan
atau ambigu tetap harus ditangani pada batch. Header profil memakai field
`source_column`; payload lama yang menggunakan `name` masih diterima.

## Resolver

Kolom pada konfigurasi NON_MASTER kini dapat menyertakan pemetaan `master_reference`:

```json
{
  "master_definition_id": "55555555-5555-4555-8555-555555555555",
  "master_field": "business_code",
  "required": false,
  "cardinality": "MANY_TO_ONE",
  "normalization": "TRIM_CASEFOLD",
  "aliases": {"Kode lama": "66666666-6666-4666-8666-666666666666"}
}
```

Letakkan objek ini pada kolom mapping yang `target_type`-nya `uuid`. Editor langkah
Kolom Workspace ETL menyediakan pemilihan master dan field master. Relasi wajib juga
memerlukan `nullable=false`. Pemetaan disimpan bersama revisi konfigurasi dan masuk
ke hash preview; perubahan master atau konfigurasi membatalkan preview lama. Binding
tab-per-kolom yang sudah tersimpan tetap dibaca untuk kompatibilitas, tetapi kolom
yang sama tidak boleh memakai kedua bentuk sekaligus.

POST `/import-reviews/{review_id}/resolve-reference` kini mewajibkan `source_column`.
Contoh penulisan staging:

```json
{
  "revision_no": 5,
  "master_definition_id": "55555555-5555-4555-8555-555555555555",
  "source_column": "Kode Produk",
  "value": "SKU-001",
  "staging_row_id": "66666666-6666-4666-8666-666666666666",
  "target_column": "product_id"
}
```

Untuk pencarian tanpa perubahan staging, hilangkan kedua field staging/target.
Mengirim hanya salah satunya menghasilkan 422. Request lama tanpa kolom sumber
harus diperbarui; pencarian master bebas tetap melalui endpoint records master.

| Hasil | Makna | Penulisan staging |
|---|---|---|
| EXACT | Satu record aktif cocok pada `master_field` binding | UUID record jika diminta |
| ALIAS | Alias approved menunjuk satu record aktif tanpa benturan exact | UUID record jika diminta |
| EMPTY | Nilai kosong pada binding opsional | null jika diminta |
| CANDIDATE | Saran berdasarkan label, belum dikonfirmasi | Tidak ada |
| AMBIGUOUS | Beberapa exact/alias atau kandidat | Tidak ada |
| NOT_FOUND | Tidak ada record aktif cocok, atau nilai wajib kosong | Tidak ada |

CANDIDATE, AMBIGUOUS, dan NOT_FOUND selalu mengembalikan `requires_question: true`.
EMPTY mengembalikan false. Normalisasi yang didukung adalah TRIM_CASEFOLD; text
mempertahankan leading zero, sedangkan tipe non-text memakai konversi tipe field.
Lookup memakai satu field binding, sehingga composite business key tidak lagi
dibandingkan dengan satu nilai yang diulang untuk seluruh komponennya. Field yang
tidak unik menghasilkan AMBIGUOUS. Resolusi FK as-of tetap di luar cakupan ini.

Record nonaktif tidak menjadi kandidat. Field sensitif dimasking untuk role non-data;
field tersebut tidak dapat dipakai untuk lookup atau pencarian label. Alias dari tab
lain tidak berlaku, sekalipun nama kolom dan master sama. Benturan alias/exact
menghasilkan AMBIGUOUS dan tidak memilih salah satu diam-diam.

## Penulisan, role, dan lifecycle

Pencarian tersedia untuk role editor/reviewer. Penulisan membutuhkan role editor,
revision batch terbaru, serta status NEEDS_INPUT, READY_FOR_APPROVAL, atau FAILED.
APPROVED dan status terminal tidak menerima perubahan staging. Kolom target harus
sesuai konfigurasi binding; row harus berasal dari batch dan tenant yang sama.

Penulisan mempertahankan raw/transformed data, mengubah `corrected_data`, menaikkan
revision batch, mencabut preview sebelumnya, serta mencatat before/after dan hash
binding/dependency di audit. Respons menyertakan revision terbaru. Endpoint ini tidak
menutup pertanyaan DQ/AI atau menghapus blocker worker; gunakan alur jawaban existing
untuk menyelesaikan pertanyaan wajib. Tidak ada write-back ke Google Sheet.

Save binding selalu mengembalikannya ke DRAFT dan menghapus metadata approval.
Alias wajib unik setelah normalisasi serta menunjuk UUID aktif pada master/tenant
yang tepat. Target alias diperiksa lagi saat approval. Lock tab menserialisasi
pembuatan pertama, edit, dan approval; request dengan revision lama menerima 409.

## Preview, approval, dan apply

Capture batch menyimpan hash binding, alias, versi/definisi master, dan record master.
Perubahan dependency membuat `is_current` false. Preview juga memvalidasi UUID staging:
nilai label, UUID asing/nonaktif, dan referensi wajib kosong ditolak. Binding opsional
hanya mengizinkan kosong, bukan nilai asing. ONE_TO_ONE menolak UUID berulang dalam
batch; unique constraint terhadap seluruh target tetap mengikuti deployment BE-09.

Hash preview mencakup dependency referensi. Approval menghitung ulang preview dan
apply memeriksa ulang setelah lock, sehingga UUID yang sudah tersimpan tidak dapat
melewati perubahan alias/master setelah review. Bukti resolusi per baris juga
diperiksa terhadap binding terbaru. Read preview tidak mengubah staging.

Batch yang dependency-nya berubah perlu dibuat ulang berdasarkan dependency terbaru;
revalidate tidak mengganti snapshot/dependency batch lama secara implisit. Batch
lama yang dibuat sebelum capture referensi ini menjadi stale ketika mempunyai
binding referensi, dan harus dibuat ulang. Alur NON_MASTER tanpa binding tetap memakai
kontrak hash sebelumnya.

| Error | HTTP | Tindakan |
|---|---|---|
| REFERENCE_BINDING_REQUIRED | 409 | Simpan/approve binding tab dan kolom yang benar |
| REFERENCE_BINDING_STALE | 409 | Perbarui binding ke versi master terbaru |
| REFERENCE_MAPPING_INVALID | 409 pada context, 422 pada target request salah | Pilih master dan field pencocokan pada mapping; kode/nama tetap text/varchar |
| MASTER_ALIAS_INVALID | 422 pada lifecycle, 409 pada context | Koreksi alias/target dan approve ulang |
| REFERENCE_REQUIRED / REFERENCE_UNRESOLVED / REFERENCE_RECORD_UNAVAILABLE | 409 | Selesaikan referensi ke UUID aktif atau kosong opsional |
| REFERENCE_CARDINALITY_CONFLICT | 409 | Hilangkan referensi berulang dalam batch ONE_TO_ONE |
| REFERENCE_RESOLUTION_STALE / IMPORT_STALE_REVIEW / IMPORT_PREVIEW_STALE | 409 | Buat batch/preview baru sesuai dependency terbaru |
| MASTER_NOT_APPROVED | 409 | Gunakan master aktif yang memiliki versi approved |
| REFERENCE_SEARCH_FORBIDDEN | 403 | Gunakan role data untuk pencarian field sensitif |

## Bukti dan batasan

Hasil: **28 tes PostgreSQL BE-08** (26 resolver/lifecycle dan 2 capture asli) serta
**8 tes lookup bertipe** lulus. Termasuk regresi policy BE-07, transaksi master,
effective dating, APPEND, dan import/preview: **84 tes integrasi** lulus pada run
terpisah. **214 tes non-integrasi di luar workbook**, ditambah 8 tes tipe baru
(total **222**), lulus. Workbook tidak dijalankan ulang pada perubahan ini.
Ruff file perubahan, exporter `--check` **152 operasi**, dan `git diff --check` lulus.

Tes PostgreSQL meliputi missing/ambiguity/candidate, optional, alias lintas tab, UUID
asing/nonaktif, masking, lifecycle binding, concurrent create/approve, revision,
staging salah/terminal, kontrak HTTP, serta perubahan alias/master sebelum approval
dan setelah approval. Suite resolver men-seed batch siap review dan men-stub freshness
upstream. Dua tes `test_reference_capture.py` memakai `capture` dan `is_current` asli
untuk membuktikan invalidasi alias dan perubahan record; Google Sheets tetap fixture.

Ini bukan acceptance provider nyata, rollout production, pengujian semua penulis SQL
eksternal, atau implementasi FK fisik BE-09. Fingerprint membaca seluruh record master
yang dirujuk; benchmark/optimasi dataset besar masih BE-17. Otomatisasi pemilihan
kandidat/pertanyaan dan alur ETL legacy tidak diperluas oleh perubahan ini.

## Relasi dari kode/nama tanpa input UUID (15 Oktober 2026)

### Melepas relasi dan mengarsipkan binding

Pada langkah Kolom, klik **Hapus relasi** atau pilih **Tidak berelasi dengan master**, lalu Simpan draft, Validasi dan Deploy. `master_reference_disabled=true` dengan `master_reference=null` menyimpan keputusan eksplisit untuk mengabaikan binding lama pada versi konfigurasi tersebut. Relasi tidak dimuat kembali saat reload. Mengaktifkan relasi kembali menghapus penanda disabled dan memakai pencocokan yang dipilih.

Konfigurasi aktif tidak diubah oleh penyimpanan draft. Kolom text/varchar, record master, data lama dan kolom `_ref_` historis dipertahankan. Baris baru pada konfigurasi yang telah melepas relasi mendapat identitas internal null; tidak ada lookup ke master. Pelepasan tidak menghapus kolom fisik. Konversi target UUID legacy ke teks tetap tunduk pada pemeriksaan migrasi; tabel berisi data tidak dikonversi secara spekulatif.

Pada halaman Binding kolom referensi, **Hapus relasi** membuka draft terbaru, atau membuat clone dari versi aktif bila diperlukan. Pengguna meninjau dan menyimpan perubahan sebelum deployment. Binding tanpa pemakaian aktif, atau yang telah dilepas melalui konfigurasi aktif, dapat diarsipkan melalui `POST /column-bindings/{binding_id}/remove` dengan `MasterRevisionRequest`. Pengelola sumber/admin dan tenant/revisi binding diperiksa. Endpoint mempertahankan record binding sebagai REVOKED beserta audit; tidak menghapus record master. `REFERENCE_IN_USE` meminta pelepasan melalui draft dahulu. Binding REVOKED diabaikan resolver, dan perubahan dependency membatalkan batch/preview yang tidak lagi sesuai.

Pada mapping NON_MASTER pilih master aktif dan field pencocokan, misalnya `BISNIS` → `master_business.bisnis` atau `BISNIS_CODE` → `bisnis_code`. Kode stabil lebih disarankan bila nama dapat berubah. `master_reference` menerima target text/varchar dan mempertahankan teks hasil cleansing. Identitas master disimpan otomatis pada `_ref_<target_column>` di tabel trusted; kolom internal tidak dimasukkan ke semantic view/kolom publik. Target UUID lama tetap didukung untuk kompatibilitas, tanpa mewajibkan pengguna menulis UUID pada Sheet.

Dry-run, deploy, worker dan final apply memakai resolver yang sama: exact/alias unik atau kosong opsional diterima; nilai tidak ditemukan, ambigu, required kosong, pelanggaran kardinalitas dan pencarian field sensitif tanpa izin tetap diblokir. Pesan validasi menunjuk kolom sumber. Apply menghitung ulang identitas dari teks terkoreksi dan memeriksa dependency/hash master; UUID staging tidak dipercaya begitu saja. Preview baca tidak mengubah staging.

Binding lama dan mapping embedded yang identik mewakili satu relasi, bukan konflik ganda. Jika master, field, required, kardinalitas, normalisasi atau alias berbeda, sistem meminta penyamaan aturan. Binding lama yang masih menunjuk target text tanpa deklarasi relasi ditandai saat validasi; form draft memuat binding tersebut agar dapat disimpan sebagai mapping terintegrasi.

Penambahan kolom internal memakai migrasi nullable yang direview. Record historis tidak diubah diam-diam dan belum memiliki referensi sampai diproses ulang dengan strategi yang sesuai; APPEND SKIP_IDENTICAL tidak memperbarui record lama. Konfigurasi perlu divalidasi dan dideploy sebelum batch baru memakai struktur referensi. Pengguna cukup menyimpan mapping, menjalankan validasi dan memeriksa hasil pemuatan, tanpa mengelola tipe UUID manual.

Verifikasi perubahan 15 Oktober: 114 tes schema/resolver/workflow, 32 tes integrasi referensi PostgreSQL (termasuk kode teks + identitas internal dan binding legacy identik), 7 tes preview baca, 5 tes panduan, 125 unit frontend dan satu skenario browser pemilihan/simpan relasi lulus. Typecheck/build, Ruff dan exporter dokumen lulus. Regresi lebih luas menemukan `test_import_idempotency_checkpoint_and_blocked_resume` mengharapkan satu audit notifikasi tetapi mendapat nol; kegagalan yang sama direproduksi pada baseline `e4fe537` di worktree terpisah, sehingga bukan akibat perubahan relasi ini. Pengujian tidak menyatakan seluruh suite aplikasi lulus.
