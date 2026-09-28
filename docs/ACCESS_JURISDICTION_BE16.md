# Kontrol akses berbasis yurisdiksi bisnis BE-16

## Tujuan

BE-16 menggabungkan role tindakan dengan atribut bisnis. Role menjawab *apa yang boleh
dilakukan*; assignment dan policy menjawab *resource mana yang boleh dikenai tindakan*.
Target akhir memakai default deny pada semua resource. Saat ini default deny berlaku
pada evaluator dan produk dari sumber yang memiliki metadata BE16; sumber legacy tanpa
metadata masih memakai kontrol lama. Kepemilikan, role platform, dan keberadaan
relationship tidak otomatis memberi akses membaca produk BE16.

## Status audit 28 September 2026

Tahap 1–3 dan enforcement SOURCE tahap 4 tersedia di kode, Vue, dan database test.
Migrasi `j0f3b6c9e1a8` sampai `s9i2e5f8a0d7` belum dibuktikan pada database aplikasi
atau deployment production. Status `POLICY_APPROVED` hanya catatan aktivasi sumber;
izin pengguna, policy yang masih berlaku, serta deny diperiksa ulang pada setiap
lookup produk sebelum cache. Implementasi ini **belum memenuhi default-deny penuh**.

Terbuka: policy template sumber, backfill/review semua sumber legacy, kebijakan
baris/kolom dan masking yang benar-benar diterapkan, klasifikasi sensitivitas/clearance,
akses admin/artefak serta resource non-DataProduct,
invalidasi cache lintas jalur, emergency break-glass, dan acceptance security/owner.
Tes browser memakai mock API; tes PostgreSQL memakai database test terpisah.

## Model yang direncanakan

- `organization_unit`: hierarki departemen/unit.
- `business_domain`: kategori/domain bisnis baku.
- `jurisdiction`: wilayah, legal entity, cabang, atau scope operasional.
- `user_assignment`: kumpulan atribut pengguna dengan masa berlaku.
- `resource_classification`: owner/steward, domain, yurisdiksi, sensitivitas, dan purpose.
- `access_policy` dan `access_policy_binding`: aturan berversi dan resource yang diikat.
- `access_request`: permintaan, approval, expiry, revoke, dan delegasi sementara.

Pemetaan implementasi saat ini:

| Konsep rancangan | Penyimpanan aktif | Batas |
|---|---|---|
| Departemen, domain bisnis, yurisdiksi, clearance, purpose | `platform.access_attribute` dengan `kind` dan parent sejenis | Belum lima tabel registry terpisah; hierarki belum menjadi izin turun-temurun otomatis. |
| Penugasan pengguna | `platform.user_assignment` bertanggal efektif dan teraudit | Delegasi admin dan approval assignment berisiko belum ada. |
| Metadata/kepemilikan sumber | `platform.data_source.access_metadata` JSONB + `access_review_status`/`access_revision` | Belum model `resource_classification` terpisah; legacy dapat bernilai null. `owner_user_id` lama adalah pendaftar operasional, bukan otomatis pemilik bisnis. |
| Policy dan binding | `platform.access_policy` dan `platform.access_policy_binding` | Binding baru divalidasi tenant/kode saat dibuat; binding lama belum diaudit ulang. |
| Permintaan akses sementara | `platform.access_request` dan API `/access/requests` | Mendukung atribut/bundle, delegasi admin, approval admin berbeda, expiry, cancel/reject/revoke, serta inbox reviewer terarah. |

## User Access Management

BE-16 memperluas administrasi pengguna yang saat ini hanya mengelola akun, role dasar,
dan `row_scope`. Tanggung jawabnya mencakup:

- lifecycle akun: aktif, suspended, deactivated, serta revoke seluruh sesi;
- role sistem yang stabil untuk kewenangan aplikasi;
- permission bundle/business role untuk paket aksi yang berulang;
- assignment departemen, domain, yurisdiksi, dan clearance dengan effective dating;
- delegasi administratif yang terbatas scope dan waktu;
- separation-of-duties serta approval assignment berisiko;
- tampilan effective access yang menjelaskan role, assignment, allow/deny, masking,
  policy revision, dan expiry yang menghasilkan keputusan akhir.

Role sistem tidak dibuat untuk setiap kombinasi atribut. Contoh `ANALYST_FINANCE_JATIM`
harus direpresentasikan sebagai role `ANALYST` ditambah assignment `FINANCE` dan `JATIM`.
Permission bundle hanya menentukan aksi; bundle tidak otomatis memberikan dataset.

Registry tenant-scoped memakai UUID stabil dan kode unik. Assignment dan policy memakai
`valid_from`, `valid_to`, status, revision, actor, serta audit.

Login tersedia untuk seluruh akun aktif. Registrasi akun bersifat internal dan hanya
dapat dilakukan `PLATFORM_ADMIN` melalui `POST /users` atau halaman frontend `/register`;
pengaturan role/status/row scope tersedia di `/admin/users`. Tidak ada registrasi publik
yang dapat memilih role sendiri. Instalasi awal membuat admin dari
`BOOTSTRAP_TENANT`, `BOOTSTRAP_USERNAME`, `BOOTSTRAP_FULL_NAME`, dan
`BOOTSTRAP_PASSWORD` melalui `python -m app.cli bootstrap`. Perintah ini idempotent,
memastikan akun aktif dan ber-role `PLATFORM_ADMIN`, serta tidak mengubah password akun
yang sudah ada kecuali operator menambahkan `--reset-existing-password`. Reset tersebut
menaikkan `token_version`, sehingga seluruh token akun lama tidak dapat dipakai lagi.

## Evaluasi

Target evaluator memakai `subject`, `action`, `resource`, dan `context`. Respons
preview yang tersedia saat ini berbentuk:

```json
{
  "allowed": true,
  "reason_code": "POLICY_MATCH",
  "policy_ids": ["UUID"],
  "policy_revisions": [{"id": "UUID", "revision": 3}],
  "row_scope": {},
  "columns": {},
  "export_allowed": false
}
```

Preview dapat menghasilkan `row_scope` dan `columns` dari policy. Compiler structured
query produk/join BE16 menerapkan row scope secara parameterized dan menghasilkan
placeholder `[MASKED]` untuk dimension masked; field hidden/non-visible ditolak pada
metric, filter, sort, dan join key. Kolom klasifikasi PII `MEDIUM/HIGH` default hidden
pada produk BE16 kecuali policy memberi visibility eksplisit. Policy tidak menerima SQL
mentah. Hasil memakai `policy_ids` dan pasangan
`policy_revisions` agar perubahan policy dapat ditelusuri. Export limit belum tersedia.
Masking di preview,
error, filter, sort, join, lineage, artefak, dan export masih target berikutnya.
Join produk yang diizinkan memakai lookup setiap sisi; policy kolom paling ketat belum
diterapkan.

## Permintaan akses sementara

Migration `q7g0c3d6e8b5` menambahkan permintaan atribut yurisdiksi atau permission bundle;
`r8h1d4e7f9c6` menambah `subject_user_id` untuk delegasi oleh admin. Pengguna biasa hanya
dapat meminta untuk dirinya sendiri. Pemohon wajib memberi alasan bisnis dan periode maksimum 366 hari.
Status awal `PENDING` tidak memberi akses. `PLATFORM_ADMIN` lain dapat approve/reject;
approval membuat `user_assignment` atau `user_permission_grant` dalam transaksi yang
sama. Permintaan dapat dibatalkan sebelum keputusan, dan akses approved dapat dicabut
oleh pemohon atau admin. Revoke mencabut grant terkait dan menaikkan `token_version`.
Semua lookup tenant-scoped, revision conflict menghasilkan 409, serta target lintas
tenant/tidak ada tetap 404. Request delegasi tetap harus diputuskan admin kedua.
Migration `s9i2e5f8a0d7` menambahkan penerima spesifik pada notifikasi operasional. Setiap
admin aktif yang boleh mereview, selain admin pemohon, memperoleh notifikasi
`ACCESS_REQUEST_PENDING`. Notifikasi tidak terlihat dan tidak dapat diakui pengguna lain,
lalu diselesaikan otomatis ketika request di-approve, reject, atau cancel.

## Registrasi Google Sheet

Registrasi sumber baru meminta unit pemilik, domain bisnis, owner, steward,
yurisdiksi, sensitivitas, dan purpose dari registry. Policy template belum tersedia.
Backend memvalidasi tiga scope terhadap assignment aktif pendaftar. Sumber baru dan
legacy tanpa metadata sama-sama berstatus `ACCESS_POLICY_REQUIRED`, tetapi **status
ini belum membatasi query sumber legacy**. Sumber baru dengan metadata tidak muncul
di katalog/query bisnis sampai aktivasi SOURCE, lalu hak setiap pengguna diperiksa.

## AI, cache, dan audit

Untuk produk BE16, katalog dan template/relationship yang dikirim ke NL2SQL dibatasi
berdasarkan SOURCE yang dapat diakses; plan model diperiksa ulang oleh compiler.
Lookup otorisasi dilakukan sebelum membaca cache hasil query, sehingga revoke dan
expiry menolak akses meskipun hasil lama masih ada di cache. Cache query memasukkan
`token_version` serta pasangan policy/revision SOURCE untuk produk dan join; cache
lintas jalur lain masih memerlukan invalidasi terpusat. Audit keputusan menyimpan
reason code aman tanpa nilai baris/PII mentah.

## Tahapan rollout

1. Registry dan assignment tersedia; keputusan akses legacy tetap tidak berubah.
2. Metadata wajib sumber baru dan status pending sumber legacy tersedia; antrean
  backfill/review seluruh legacy belum selesai.
3. Evaluator preview tersedia; perbandingan shadow-mode sistematis belum dilakukan.
4. Gate katalog/detail/query/export/join produk BE16 tersedia; operasi admin,
  artefak, dan resource lain belum memakai evaluator menyeluruh.
5. Default deny penuh menunggu acceptance data owner dan security.

### Status tahap 1

Tahap 1 tersedia melalui migration `j0f3b6c9e1a8`. Implementasi memakai registry generik
`access_attribute` dengan jenis `DEPARTMENT`, `BUSINESS_DOMAIN`, `JURISDICTION`, dan
`CLEARANCE`, serta `user_assignment` bertanggal efektif. Endpoint `/access` menyediakan
pengelolaan registry, histori assignment, revoke, dan effective access. Revoke assignment
menaikkan `token_version` pengguna agar sesi lama tidak dapat terus dipakai. Seluruh lookup
dibatasi tenant dan relasi lintas tenant juga ditolak constraint PostgreSQL.

Tahap ini berjalan berdampingan dengan role dan `row_scope` lama. Enforcement produk
SOURCE terbatas datang pada tahap 4; purpose enforcement, access request, masking,
dan default deny seluruh resource masih terbuka.

### Status tahap 2

Migration `k1a4c7d0f2b9` menambah `permission_bundle` dan `user_permission_grant`.
Bundle hanya berisi kombinasi aksi `DISCOVER`, `READ`, `QUERY`, `EXPORT`, `EDIT`,
`APPROVE`, `OPERATE`, dan `ADMIN`. Grant mempunyai periode berlaku, revision, actor,
alasan, revoke, audit, dan tenant constraint. Pemberian maupun pencabutan merotasi sesi
target. Admin tidak boleh memberi atau mencabut bundle miliknya sendiri.

Effective access menggabungkan aksi role sistem dan seluruh bundle aktif pada waktu yang
diminta. Bundle tidak menyebut dataset, department, atau wilayah, sehingga pemberian aksi
tidak memperluas scope data tanpa assignment dan policy resource yang sesuai.

### Status tahap 3

Migration `l2b5d8e1a3c0` menambah `access_policy` dan `access_policy_binding`. Policy
memiliki effect ALLOW/DENY, aksi, atribut subject wajib, effective dating, row scope,
aturan kolom, izin export, revision, alasan, dan lifecycle
`DRAFT -> IN_REVIEW -> APPROVED -> REVOKED`. Minimal satu binding wajib sebelum submit,
dan pembuat policy tidak boleh menjadi approver.

Binding baru memakai kode resource (`DATA_PRODUCT.code`, `SOURCE.source_code`,
`MASTER.code`, atau `TAXONOMY.code`). Service menolak kode yang tidak ditemukan pada
tenant aktif dengan 404. Admin dapat memakai `GET /access/resources?resource_type=...`
dengan filter `search` pada kode, `offset`, dan `limit` (maksimum 100); respons hanya
memuat `id`, `code`, `name`, dan `status`. Status terdaftar tidak berarti policy telah
approved. Binding lama sebelum validasi ini belum diaudit ulang. Evaluator preview
kemudian dipakai pada lookup DataProduct dari SOURCE BE16; resource lain belum
memakainya sebagai enforcement menyeluruh.

`POST /access/evaluate` menyediakan preview keputusan untuk user, aksi, resource, dan
waktu tertentu. Urutannya adalah explicit deny, pemeriksaan aksi role/bundle, lalu ALLOW;
tanpa ALLOW yang cocok hasilnya `DEFAULT_DENY`. Keputusan diaudit tanpa nilai data mentah.
Evaluator ini dipakai untuk DISCOVER/QUERY/EXPORT DataProduct dari SOURCE BE16 yang
telah diaktifkan; endpoint sumber administratif, artefak, dan resource lain belum
memakainya secara menyeluruh.
Subjek nonaktif menghasilkan `USER_INACTIVE` dengan effective actions kosong, terlepas
dari role maupun policy yang cocok. Untuk aksi `EXPORT`, setiap policy ALLOW yang cocok
harus mengaktifkan `export_allowed`; jika tidak, keputusan `EXPORT_NOT_ALLOWED` dan
`allowed=false`. Aksi selain EXPORT tetap mengembalikan `export_allowed=false`.
Tes PostgreSQL access mencakup kedua hasil ekspor serta penonaktifan akun.

### Status sumber tahap 4 (fondasi)

Migration `m3c6e9f2b4d1` menambah `data_source.access_status` terpisah dari status
discovery/ETL. Sumber baru dan sumber legacy dibackfill ke `ACCESS_POLICY_REQUIRED`
melalui default database; profiling tidak menghapus status akses ini. GET sumber/detail
serta respons registrasi memuat field tersebut, dan workspace Vue menampilkannya untuk
sumber yang dipilih. Downgrade menghapus kolom (dan informasi statusnya), tanpa mengubah
status ETL atau data sumber. Tes PostgreSQL onboarding membuktikan status bertahan setelah
discovery/profiling.

Saat migrasi ini diperkenalkan, field baru hanya penanda. Setelah aktivasi SOURCE
ditambahkan, produk dari sumber dengan metadata ditahan saat pending dan dicek terhadap
policy aktif. Query/export sumber legacy tetap berjalan sesuai kontrol lama. Jangan
mengartikan status database saja sebagai izin pengguna atau bukti rollout production.

### Metadata registrasi tahap 4

Migration `n4d7f0a3c5e2` menambah `data_source.access_metadata` nullable untuk sumber
legacy (tetap null dan memerlukan review), serta atribut registry `PURPOSE`. Pendaftaran
baru wajib mengirim unit pemilik, domain bisnis, yurisdiksi, purpose, data owner, data
steward, dan sensitivitas. Tiga scope diverifikasi sebagai assignment aktif pendaftar
pada saat POST; semua atribut harus aktif dan tenant-scoped, owner/steward user aktif
tenant yang sama. `GET /access/registration-options` untuk editor mengembalikan scope
yang saat ini ter-assign, PURPOSE tenant aktif, sensitivitas baku, serta akun aktif
pendaftar dan calon owner/steward ber-role `SOURCE_OWNER`/`DATA_STEWARD`. Respons ini
hanya pilihan UI, bukan grant atau otorisasi baca data. Backend mengulang validasi pada
POST, termasuk saat assignment sudah dicabut setelah opsi diambil. `owner_user_id`
existing tetap akun pendaftar operasional; `data_owner_user_id` dalam metadata adalah
pemilik bisnis. Downgrade menolak bila masih ada atribut PURPOSE agar registry tidak
terhapus diam-diam; penghapusan kolom metadata pada downgrade tetap menghilangkan isi
metadata, sehingga backup wajib.

Migration `o5e8a1b4d6f3` memberi `access_revision=1` pada sumber baru dan legacy.
`PATCH /sources/{source_id}/access-metadata` menerima metadata lengkap dan revision,
mengunci sumber tenant sebelum memeriksa revision, lalu menjalankan validasi yang sama
dengan registrasi. Revisi stale ditolak 409; payload identik saat pending tidak menulis
ulang. Perubahan nyata menambah revision, mengaudit actor serta nama field yang berubah
tanpa menyalin nilai user/PII, dan mengembalikan status akses ke
`ACCESS_POLICY_REQUIRED` bahkan bila sebelumnya approved. Status ETL tidak berubah.
Downgrade menghapus revision metadata dan tidak memulihkan approval lama.

Migration `p6f9b2c5d7a4` menambah status review metadata `PENDING/APPROVED/REJECTED`,
editor terakhir, reviewer tenant-scoped, waktu dan alasan kode. Sumber lama/default
PENDING; sumber dengan metadata tetapi editor belum tercatat harus PATCH ulang, walau
nilainya identik, agar actor tercatat. GET access-review-context admin meresolusikan
label atribut dan username tanpa mengambil data bisnis. POST access-review hanya admin
lain, memakai revision sumber dan reason allowlist. APPROVE memvalidasi ulang metadata
termasuk assignment editor yang masih aktif; REJECT dapat menyatakan alasan saat scope
sudah tidak valid. Re-edit atau pembukaan ulang setelah reject menghapus keputusan
lama dan kembali PENDING. Tes PostgreSQL mencakup tenant, role, SoD, stale revision,
revoke sebelum approval, audit tanpa raw PII, dan reset saat edit. Downgrade menghapus
riwayat review pada kolom ini; backup wajib sebelum rollback.

Review metadata APPROVED sendiri tidak mengubah `access_status`. Lanjutan enforcement
terbatas mengaktifkan sumber lewat `POST /sources/{id}/access-activate` setelah admin
lain memilih policy SOURCE ALLOW approved dari `GET /sources/{id}/access-policy-options`.
Policy wajib mencakup DISCOVER dan QUERY, berlaku pada saat aktivasi, dan tidak boleh
mengandung row/column control yang belum didukung. ALLOW harus mensyaratkan ketiga
atribut sumber (unit, domain bisnis, dan yurisdiksi); policy broad tidak dapat
diaktifkan dan tidak cocok saat runtime. Source.status ETL tetap terpisah.

Untuk sumber baru yang memiliki metadata, repository produk memeriksa status sumber,
role produk, serta keputusan policy SOURCE pada setiap lookup. Catalog, metadata
produk, join, query, export, report berbasis produk, saved query, dan konteks/template
NL2SQL memakai filter tersebut. QUERY dan EXPORT dievaluasi terpisah, sebelum cache;
explicit deny, pencabutan assignment/policy, dan expiry langsung menolak akses. Hasil
evaluator dengan row_scope atau column_rules belum diterapkan compiler dan **ditolak**,
tidak diabaikan. Status `POLICY_APPROVED` yang tersimpan bukan jaminan policy masih
aktif: runtime selalu mengecek ulang. Sumber legacy dengan metadata null masih
mengikuti akses lama untuk kompatibilitas; default-deny penuh dan jalur admin/artefak,
metadata field sensitif, masking, serta kontrol baris/kolom tetap terbuka. Tes
PostgreSQL memeriksa bypass query/export langsung, katalog/NL2SQL, SoD aktivasi,
perubahan assignment, ketiga scope, DENY override, row-scope, dan revoke. Klasifikasi
sensitivitas belum otomatis memberi masking/clearance. Rollout production dan
acceptance security tetap terpisah.

Guard SoD assignment kini konsisten dengan permission grant: admin tidak dapat membuat
atau mencabut assignment miliknya sendiri. Backend mengembalikan `422
SELF_ACCESS_CHANGE`; UI Vue menonaktifkan aksi yang sama untuk menghindari request yang
jelas akan ditolak, tetapi validasi server tetap wajib untuk direct API.

### Matriks enforcement saat ini

| Jalur | Sumber dengan metadata BE16 | Sumber legacy `access_metadata=null` |
|---|---|---|
| Katalog/detail/metric DataProduct dan daftar template/relationship | Ditahan saat pending; DISCOVER SOURCE saat aktif | Role/allowlist produk lama |
| Structured query, saved query, laporan berbasis DataProduct dan join | QUERY SOURCE diperiksa tiap produk sebelum cache; row/column control yang belum didukung ditolak | Query/row_scope lama |
| CSV export DataProduct | EXPORT SOURCE dan `export_allowed` diperiksa terpisah; deny/revoke/expiry berlaku | Export lama |
| NL2SQL katalog, kandidat template dan eksekusi plan | Hanya produk/relationship yang lolos katalog; plan dikompilasi ulang dengan gate QUERY | Katalog/kontrol lama |
| Administrasi sumber/tab/configuration, batch, job, artifact, master, taxonomy | Belum memakai evaluator BE16 menyeluruh | Kontrol role/tenant lama |

Katalog yang terfilter tidak menggantikan otorisasi runtime. Policy dengan aturan
baris/kolom belum boleh dipakai untuk membuka produk BE16; `READ`, `EDIT`, dan aksi
admin belum ditegakkan secara menyeluruh di semua resource. Profiling administratif
masih terpisah dari izin query, tetapi nilai profil/error/artefak belum seluruhnya
melewati masking BE16. Policy/assignment baru dicek pada lookup; session/query cache
lintas jalur dan klasifikasi ulang sumber masih memerlukan strategi invalidasi penuh.

### Gate rollout berikutnya

1. Audit binding policy lama dan isi/review metadata sumber legacy; jangan mengubah
  null menjadi public atau menandai semua sumber approved secara massal.
2. Evaluasi sumber PII/HIGH, owner/steward dan policy kolom/baris bersama security;
  jangan aktifkan data sensitif sebelum masking serta jalur admin/artefak tertutup.
3. Uji migrasi pada database tujuan dengan backup, verifikasi role reader/DDL,
  rollback metadata/review, dan acceptance pemilik data. Migrasi database test bukan
  rollout production.
4. Selesaikan access request, delegasi, break-glass ber-expiry/audit, dan default-deny
  seluruh resource sebelum menandai BE16 selesai.

Migration harus menyediakan backfill/rollback yang tidak menjadikan data lama publik.
Break-glass memerlukan actor khusus, alasan, expiry pendek, notifikasi, dan audit.
