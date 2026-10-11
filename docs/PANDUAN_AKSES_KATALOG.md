# Membuka akses Katalog data: assignment, policy, dan aktivasi sumber

Frontend production: https://google.kanjabung.web.id  
API production: https://api-google.kanjabung.web.id

Panduan ini untuk admin yang memberikan akses baca kepada pengguna. Tidak ada password,
token, atau API key yang perlu ditulis dalam dokumentasi atau policy.

## Jalur sederhana yang disarankan

- Akun baru: isi rekomendasi unit/domain/yurisdiksi dan paket izin pada Registrasi.
  Permintaan berlaku 366 hari sejak pengajuan. Admin lain memilih seluruh rekomendasi
  akun tersebut pada Permintaan akses dan menyetujuinya sekaligus. Tidak perlu membuat
  policy lagi bila policy organisasi APPROVED yang sesuai sudah tersedia.
- Sumber baru/revisi konfigurasi: approver konfigurasi membaca metadata sumber dan
  memilih policy APPROVED pada dialog approval. Satu transaksi menyetujui konfigurasi,
  metadata dan mengaktifkan akses. Jika satu syarat gagal, seluruh approval dibatalkan.
  Klik **Helper lengkap: mengapa approval belum bisa disetujui** untuk rincian dan
  shortcut ke Workspace. Editor metadata/pembuat konfigurasi tidak boleh memutuskan.
- Sesudah deploy, **Sync manual** membaca data dan menampilkan hasil per tab.
  Preview, approval batch dan Apply tetap wajib; struktur ACTIVE belum berarti ada data.
- Katalog menyediakan **Buka Google Sheet**, **Buka sumber di Workspace** bagi role
  operasional, status pembaruan, dan timestamp aktif/pemuatan terakhir.

Langkah review metadata/aktivasi admin terpisah di bawah tetap didukung untuk sumber
yang sudah aktif tanpa revisi konfigurasi. Ini bukan lagi langkah tambahan wajib sesudah
approval gabungan berhasil. Lihat [panduan pengguna](USER_GUIDE_END_TO_END.md) untuk
alur baru serta helper `/guide#approval-gabungan` dan `/guide#sync-manual` pada frontend.

## Mengapa sumber ACTIVE belum muncul?

**ACTIVE adalah status ETL, bukan status akses.** Katalog memerlukan semua syarat berikut:

1. Tab mempunyai Data Product ACTIVE. Tabel storage master tidak otomatis menjadi Data Product.
2. Role pengguna tercantum dalam `allowed_roles` produk.
3. Sumber dengan metadata akses mempunyai review metadata APPROVED dan akses POLICY_APPROVED.
4. Policy ALLOW yang berlaku terikat pada sumber dan memuat aksi DISCOVER untuk katalog,
   serta QUERY untuk analitik.
5. Pengguna memiliki assignment aktif untuk **setiap** atribut wajib policy.
6. Tidak ada policy DENY yang cocok. Kontrol baris/kolom pada policy SOURCE tidak dapat
   dipakai untuk membuka sumber pada runtime saat ini.

Permission bundle bukan pengganti assignment atau policy. Role SOURCE_OWNER dan
TECHNICAL_APPROVER sudah mempunyai DISCOVER/READ/QUERY; jangan memberi ADMIN hanya
untuk membuka katalog.

## Diagnosis kasus 11 Oktober 2026

Pemeriksaan read-only production menemukan:

| Pemeriksaan | Hasil sebelum perbaikan |
|---|---|
| Data Product ACTIVE | 29 |
| Sumber ETL ACTIVE | 10 |
| Status akses 10 sumber | ACCESS_POLICY_REQUIRED |
| Review metadata 10 sumber | PENDING |
| Policy terdaftar untuk tenant kedua akun | Belum ada |
| saptadi1 | SOURCE_OWNER; assignment Marketing, Pemasaran, Holding tersedia |
| saptadi2 | TECHNICAL_APPROVER; belum mempunyai assignment |
| Produk terlihat pada masing-masing akun | 0 |

Ini menjelaskan katalog kosong tanpa perlu mengulang ETL, menghapus sumber, atau
mendaftarkan ulang Sheet. Angka di atas adalah hasil pemeriksaan saat itu, bukan
jaminan kondisi terkini. Perbaikan belum selesai sampai policy approved, sumber
diaktifkan, dan katalog diuji dengan login kedua akun.

## Langkah 1: siapkan dua admin berbeda

### Progres konfigurasi production

Pada 11 Oktober 2026, reviewer `adminku@kanjabung.com` terverifikasi sebagai
PLATFORM_ADMIN aktif pada tenant yang sama dengan admin pembuat
`admin_etl@kanjabung.com`.

- Assignment Marketing, Pemasaran, Holding milik saptadi1 dipertahankan.
- Tiga assignment tersebut sudah ditambahkan untuk saptadi2 melalui API.
- Policy `READ_MARKETING_ACTIVE_SOURCES` sudah dibuat dan disubmit oleh admin
  pembuat, dengan status **IN_REVIEW**, belum APPROVED.
- Policy mempunyai 10 binding SOURCE: `new_grd`,
  `analisa_kompetitor_lkms_per_topik_3`, `report_sebaran_juni`,
  `database_crm_konsolidasi`, `database_sales_distribusi_per_unit`,
  `angkutan_per_topik`, `detail_pertanian_per_topik`, `quanti_1`, `pencap_1`,
  dan `realisasi_pencapaian_unit`.
- Aksi hanya DISCOVER, READ, QUERY; tidak ada EXPORT/ADMIN atau kontrol baris/kolom.
  Ketiga atribut wajib berlaku AND. Pemilik tenant menyetujui scope ini:
  pengguna lain yang memiliki semua assignment tersebut juga dapat cocok.
- Form standar dipakai tanpa tanggal akhir, sehingga assignment dan policy
  tetap berlaku sampai dicabut atau diubah sesuai workflow yang tersedia.
- Reviewer harus meninjau dan menyetujui sendiri melalui akunnya. Belum ada
  approval policy, review metadata, atau aktivasi sumber pada tahap ini.

Untuk menemukan policy yang sudah dibuat, buka **Administrasi -> Access policy ->
Daftar policy**, lalu klik **Muat ulang policy**. Cari kartu
`READ_MARKETING_ACTIVE_SOURCES` berstatus IN_REVIEW dan klik **Approve policy**
sebagai reviewer. Daftar berada sebelum **Buat policy baru** pada tampilan terbaru.
Pada tampilan lama, kartu berada setelah form panjang, di bawah tombol
**Buat policy DRAFT**; muat ulang halaman atau gunakan pencarian browser.
Jangan mencari kode policy di pilihan resource: tabel resource berisi sumber/
produk untuk binding policy baru, bukan daftar policy.

Katalog belum dinyatakan berhasil sebelum langkah 4-6 selesai dan hasil login
kedua akun diverifikasi. Perubahan akses ini tidak memerlukan deploy/restart API;
tampilan frontend terbaru sudah dipublikasikan dan diverifikasi di production,
termasuk kartu policy IN_REVIEW sebelum form baru. Dokumen backend terbaru masih
lokal dan perlu dipublikasikan terpisah.

Di Administrasi/Pengguna, siapkan admin pembuat policy dan admin reviewer, keduanya
aktif dalam tenant yang sama. Admin kedua harus akun milik reviewer yang memang
berwenang, bukan akun bersama untuk melewati approval.

- Admin A membuat dan submit policy.
- Admin B membuka policy IN_REVIEW dan memilih **Approve policy**.
- Pembuat policy tidak boleh menyetujui policy sendiri, meskipun PLATFORM_ADMIN.
- Review metadata sumber juga tidak boleh oleh editor metadata terakhir.
- Aktivasi policy sumber dilakukan admin yang bukan editor metadata.

Tidak perlu mengubah role saptadi1 atau saptadi2 menjadi admin.

## Langkah 2: berikan assignment sesuai sumber

Login sebagai admin. Buka **Administrasi**, pilih pengguna tujuan, lalu berikan:

| Jenis atribut | Contoh scope sumber pada kasus ini |
|---|---|
| DEPARTMENT | MARKETING |
| BUSINESS_DOMAIN | PEMASARAN |
| JURISDICTION | HOLDING |

Nama/label yang ditampilkan dapat berbeda dari kode; cocokkan dengan metadata
sumber di Workspace. Ketiga atribut harus diberikan kepada setiap pengguna
yang diberi akses ke sumber ini. saptadi1 sudah memilikinya saat pemeriksaan;
jangan membuat assignment tumpang tindih. saptadi2 perlu assignment yang belum ada.

Jika policy juga mewajibkan PURPOSE atau CLEARANCE, pengguna harus memiliki
assignment tambahan tersebut. Purpose pendaftaran sumber bukan otomatis
assignment untuk semua pembaca. Pilih masa berlaku sesuai kebijakan organisasi.
Unit induk tidak otomatis memberikan assignment semua anak.

## Langkah 3: buat policy SOURCE, bukan hanya DATA_PRODUCT

Pada **Administrasi → Access policy**:

1. Isi kode unik, misalnya `READ_MARKETING_NEW_GRD`, dan nama bisnis yang jelas.
2. Pilih **Efek ALLOW**.
3. Pilih **Jenis resource SOURCE**.
4. Cari sumber yang dituju di tabel resource, lalu klik **Pilih**.
   Resource memakai kode sumber, bukan nama tabel PostgreSQL atau UUID yang diketik.
5. Centang **DISCOVER**, **READ**, dan **QUERY**.
6. Pada **Atribut subject wajib**, centang unit, domain bisnis, dan yurisdiksi
   yang tepat dari metadata sumber. Semua centang berarti **AND**, bukan OR.
7. Jangan centang EXPORT atau Izinkan ekspor jika kebutuhannya hanya katalog/query.
8. Klik **Buat policy DRAFT**, lalu **Submit review**.
9. Login sebagai admin berbeda, temukan policy IN_REVIEW, lalu **Approve policy**.

Form saat ini membuat satu binding sumber per policy. Ulangi untuk setiap sumber
yang memang boleh diakses. API dapat mengikat beberapa sumber pada satu policy DRAFT
sebelum submit, tetapi hanya gabungkan sumber dengan scope dan aturan yang sama.
Jangan menggabungkan semua atribut berbagai sumber menjadi satu daftar wajib:
itu justru mengharuskan pengguna memiliki seluruh atribut sekaligus.

Policy tidak menarget username langsung; ia berlaku bagi pengguna yang memenuhi
seluruh atribut dan aksi. Jika akses harus khusus individu, desain atribut/assignment
yang resmi untuk kelompok tersebut, bukan membuat policy tanpa scope sumber.

## Langkah 4: review metadata sumber

Pada **Sumber & tracking**, cari sumber lalu **Buka** untuk masuk Workspace.

1. Periksa unit, domain, yurisdiksi, owner, steward, purpose, dan sensitivitas.
2. Reviewer yang ditunjuk membuka **Review metadata sumber → Tinjau metadata**.
3. Setelah benar, klik **Setujui metadata** menggunakan akun berbeda dari editor.
4. Jika akun tidak ditunjuk, admin mengatur **Approver per sumber data → Review
   metadata sumber** terlebih dahulu.

Approval metadata hanya mengubah review menjadi APPROVED. Status akses masih
ACCESS_POLICY_REQUIRED sampai langkah aktivasi berikut.

## Langkah 5: aktifkan policy pada sumber

Login sebagai admin yang bukan editor metadata. Pada Workspace sumber yang sama:

1. Pastikan review metadata APPROVED.
2. Klik **Muat policy SOURCE**.
3. Pilih policy APPROVED yang terikat ke sumber dan scope-nya cocok.
4. Klik **Aktifkan policy sumber**.
5. Pastikan status akses menjadi **POLICY_APPROVED**.

Dropdown kosong berarti belum ada policy yang memenuhi syarat: SOURCE binding,
ALLOW, APPROVED, sedang berlaku, aksi DISCOVER + QUERY, tiga scope sumber, serta
tanpa kontrol baris/kolom SOURCE. Membuat policy DATA_PRODUCT saja tidak memenuhi
aktivasi sumber induk.

Jika aturan persetujuan tayang aktif, backend juga memeriksa keputusan rilis
konfigurasi aktif. Jangan menghapus atau mematikan aturan untuk melewati blocker.

## Langkah 6: uji akun tujuan, bukan akun admin

1. Di Administrasi, pilih saptadi1 dan gunakan **Access policy → Preview keputusan**.
2. Pilih resource SOURCE, sumber yang sama, dan aksi DISCOVER; hasil harus
   `allowed: true`, `reason_code: POLICY_MATCH`.
3. Ulangi untuk QUERY dan akun saptadi2.
4. Keluar dari sesi admin, login masing-masing akun pada production.
5. Buka **Katalog data** dan muat ulang. Pastikan produk yang diharapkan muncul.

Preview ALLOW saja belum cukup bila sumber belum POLICY_APPROVED atau role
pengguna tidak ada di allowed_roles produk. Policy tambahan tidak dapat meniadakan
DENY yang cocok. Tidak perlu restart API untuk perubahan akses yang tersimpan.

## Kesalahan yang sering membuat percobaan gagal

| Gejala/kode | Penyebab | Tindakan |
|---|---|---|
| Katalog kosong, ETL ACTIVE | Akses sumber belum POLICY_APPROVED | Review metadata, approve policy SOURCE, lalu aktifkan sumber |
| DEFAULT_DENY | Tidak ada policy ALLOW yang cocok atau assignment kurang | Cocokkan binding, aksi, waktu berlaku, dan semua atribut |
| EXPLICIT_DENY | Ada DENY yang cocok | Minta pemilik kebijakan meninjau; jangan menambah ALLOW untuk menimpanya |
| POLICY_APPROVER_CONFLICT | Pembuat meng-approve policy sendiri | Gunakan admin reviewer lain |
| SOURCE_METADATA_SELF_REVIEW | Editor metadata mereview dirinya sendiri | Gunakan reviewer yang berbeda dan ditunjuk |
| SOURCE_ACCESS_APPROVER_CONFLICT | Editor metadata mencoba aktivasi | Admin berbeda mengaktifkan |
| SOURCE_METADATA_REVIEW_REQUIRED | Metadata belum APPROVED | Review metadata dahulu |
| SOURCE_POLICY_SCOPE_REQUIRED | Unit/domain/yurisdiksi sumber tidak lengkap pada policy | Perbaiki DRAFT atau buat policy baru, lalu review |
| Policy tidak ada di dropdown | Salah resource/status/scope/aksi atau masa berlaku | Gunakan checklist langkah 5 |
| ASSIGNMENT_PERIOD_OVERLAP | Assignment aktif sudah ada | Pakai assignment existing; jangan duplikasi |
| Preview ALLOW tetapi produk tersembunyi | Gate sumber atau allowed_roles produk belum cocok | Periksa status sumber dan role produk |
| STALE_REVISION / SOURCE_ACCESS_REVISION_CONFLICT | Data berubah sejak form dimuat | Muat ulang, periksa lagi, gunakan revisi terbaru |

Referensi teknis: [kontrol akses BE16](ACCESS_JURISDICTION_BE16.md),
[API Reference](API_REFERENCE.md), dan [panduan pengguna](USER_GUIDE_END_TO_END.md).
