# Panduan pengguna: dari Google Sheet sampai dashboard

Panduan ini menjelaskan prosedur umum agar Google Sheet dapat berubah menjadi data yang tervalidasi,
terkendali aksesnya, dan dapat dicari melalui bahasa alami atau ditampilkan sebagai chart. Panduan
interaktif yang sama tersedia pada menu **Panduan penggunaan** (`/guide`) di frontend.

## Peran utama

| Peran | Tanggung jawab umum |
|---|---|
| `PLATFORM_ADMIN` | Membuat akun, atribut organisasi, permission, dan access policy |
| `SOURCE_OWNER` | Mendaftarkan sumber dan memastikan konteks bisnisnya benar |
| `DATA_STEWARD` | Mengelola klasifikasi, master, taxonomy, konfigurasi, dan kualitas |
| `TECHNICAL_APPROVER` | Mereview definisi, binding, konfigurasi, dan batch |
| `ANALYST` / `VIEWER` | Mencari dan memvisualisasikan data yang sudah diizinkan |

Pemisahan editor dan approver diperlukan pada workflow yang dikonfigurasi memakai separate approval.

## Alur sederhana akun, approval gabungan, dan sync

1. **Registrasi akun sekaligus rekomendasi akses.** Admin memilih unit, domain, yurisdiksi
   dan paket izin yang diperlukan, serta alasan bisnis di form Registrasi. Akun dan
   permintaan disimpan atomik; target invalid membatalkan semuanya. Masa akses 366 hari
   sejak pengajuan. Admin lain dapat memilih seluruh rekomendasi akun tersebut dan
   menyetujuinya sekaligus di Permintaan akses; pending belum memberi assignment/izin.
   Policy APPROVED yang cocok digunakan kembali, bukan dibuat ulang untuk setiap akun.
2. **Satu approval konfigurasi dan akses.** Approver konfigurasi sumber membaca ringkasan
   metadata dan memilih policy SOURCE APPROVED yang cocok. Keputusan sekaligus menyetujui
   metadata PENDING dan mengaktifkan akses. Maker-checker selalu berlaku untuk keputusan
   gabungan, termasuk bila separate approval konfigurasi lama dinonaktifkan.
   Metadata incomplete/rejected, editor tidak aktif/assignment sudah berakhir, revisi berubah,
   policy tidak cocok/kedaluwarsa, atau gate yang diwajibkan belum lengkap menghentikan
   transaksi: tidak ada approval sebagian. Dialog menampilkan penyebab dan helper lengkap
   `/guide#approval-gabungan`, serta shortcut ke sumber di Workspace. Reviewer tidak perlu
   punya assignment scope sumber sendiri; assignment editor dan pembaca tetap divalidasi.
3. **Sync manual per sumber.** Setelah deploy, pilih Sync manual di Sumber & tracking
   atau Workspace. Konfirmasi pembacaan Sheet/kuota AI, lalu pantau job dan hasil setiap tab,
   baris valid/dimuat, cakupan AI, temuan, dan link batch. Untuk NON_MASTER dengan konfigurasi
   ACTIVE yang sudah disetujui, sync langsung memuat jika seluruh pemeriksaan lolos.
   Master/konflik/drift/keamanan berhenti tanpa pemuatan. Sync tidak mengubah Sheet.
   Batas pemantauan 10 menit
   bukan pembatalan job; Muat ulang hasil atau monitor job melanjutkan pemantauan tanpa
   enqueue baru. Sumber yang masih mempunyai job QUEUED/RUNNING menolak sync duplikat.
4. **Katalog sebagai shortcut perbaikan.** Ikon mata pada Data product membuka
   modal sumber/tab, tabel database, view semantic dan deskripsi. Tabel ringkas
   menggabungkan semantic dengan versi ETL, serta pembaruan dengan waktu dimuat;
   kolom Peluang peningkatan mendapat ruang lebih luas. Pencarian tetap mencakup
   metadata yang dipindahkan ke modal. Membuka detail hanya membaca metadata.
   Buka Google Sheet tepat pada tab asal atau
   Buka sumber di Workspace (role operasional saja). Versi aktif terakhir tetap tampil
   selama revisi bila akses masih valid. Sedang diperbarui menandai job/revisi/drift/data
   snapshot/batch yang belum selesai, bukan berarti versi lama sudah dinonaktifkan.
   Timestamp aktif berasal dari audit aktivasi konfigurasi/pemuatan sukses; timestamp
   masing-masing dan profil terakhir ditampilkan terpisah. Sheet tidak dipantau live:
   perubahan diketahui setelah profiling/sync. Tidak ada pemuatan sukses berarti
   **Belum dimuat**, walaupun struktur konfigurasi ACTIVE.

Policy baru tetap dibuat dan disetujui admin berbeda. Gate IT/unit tetap berlaku;
approval batch tetap diperlukan untuk master, jadwal otomatis, dan batch review biasa,
bukan sync manual NON_MASTER yang lolos seluruh pemeriksaan. Jalur review metadata dan aktivasi admin terpisah tetap tersedia untuk
sumber yang sudah aktif tanpa revisi konfigurasi. Perubahan metadata membatalkan akses;
katalog tidak mempertahankan akses yang sudah dicabut hanya demi menampilkan status.

## Prosedur awal sampai akhir

| Tahap | Tindakan | Hasil minimum sebelum lanjut |
|---|---|---|
| 1. Administrasi | Buat pengguna, role, atribut departemen/domain/yurisdiksi/purpose, assignment multi-unit eksplisit, permission, policy, approver per sumber, dan aturan persetujuan sebelum tayang | Pengguna dapat login, cakupan unit dipilih, dan pemeriksa IT/unit terkait ditunjuk |
| 2. Pendaftaran sumber | Bagikan Sheet ke service account sebagai Viewer, lalu daftarkan URL/ID serta metadata kepemilikan | Discovery dan profiling sukses; tab serta header terbaca |
| 3. Klasifikasi tab | Konfirmasi `MASTER` atau `NON_MASTER` untuk setiap tab | Semua tab yang akan diproses berstatus confirmed |
| 4. Master | Definisikan field, business key, label, policy, storage, dan binding | Definisi/storage/binding approved dan record rujukan siap |
| 5. Taxonomy | Buat term, alias, hierarki, versi, serta binding kolom | Taxonomy dan binding approved |
| 6. Konfigurasi ETL | Map kolom, transformasi, DQ, strategi load, business key, semantic product, dimensi, dan metrik | Konfigurasi valid tanpa blocker |
| 7. Review/deploy | Approver menyetujui konfigurasi sekaligus metadata dan policy sumber; selesaikan gate IT/unit yang diwajibkan, lalu deploy | Konfigurasi `ACTIVE`, metadata `APPROVED`, akses `POLICY_APPROVED` |
| 8. Pemuatan data | Untuk NON_MASTER aktif, jalankan Sync manual; data valid langsung dimuat. Master/jadwal/batch biasa tetap stage, jawab pertanyaan, preview, approve, apply | Batch per tab `SUCCEEDED` dan baris dimuat terisi |
| 9. Operasional | Pantau job, schedule/dependency/watermark, karantina, resolusi, dan reprocess | Job terbaru sukses dan tidak ada blocker kualitas |
| 10. Analitik | Tanyakan data dengan bahasa alami atau gunakan query builder; pilih tabel/chart | Hasil tampil dan dapat ditelusuri ke produk serta sumber approved |

Tahap master dan taxonomy dilakukan bila dataset membutuhkan rujukan atau kategori baku. Dataset
transaksi sederhana tetap harus melewati klasifikasi, konfigurasi, review, deploy, import, dan kontrol
akses sebelum muncul di dashboard.

Tombol **Hubungkan & profiling** mendaftarkan sumber lebih dulu, kemudian membuat job
discovery yang berjalan melalui worker. Status dan tautan monitor job tampil di dekat
tombol. Jika statusnya QUEUED/RUNNING, tunggu atau buka monitor; jangan mendaftarkan
Sheet yang sama lagi. Jika job FAILED, sumber tetap tercatat dan penyebabnya perlu
diperiksa pada monitor job. Jika request pendaftaran gagal, periksa pesan form dan
daftar sumber sebelum mencoba ulang.

Saat URL Sheet diisi, workspace memeriksa pendaftaran yang sudah ada dan menampilkan peringatan. Jika milik akun sendiri, buka sumber lama; jika milik akun lain, hubungi admin. Saat tombol Hubungkan ditekan, pengecekan diulang sebelum mengirim permintaan. Guard atomik di backend tetap mencegah duplikat ketika dua permintaan datang bersamaan. Workspace juga menampilkan grup sumber duplikat aktif. Admin melihat duplikat tenant; pengguna lain hanya melihat duplikat miliknya. Admin memilih sumber utama dari dropdown, mengisi alasan, lalu menekan **Unlink** pada duplikat yang tidak diperlukan. Sumber yang di-unlink hilang dari pilihan utama dan tidak ditampilkan lagi di panel duplikat. Jika perlu digunakan kembali, tampilkan sumber unlink pada **Sumber & tracking** lalu pulihkan link dengan dua konfirmasi; jangan mendaftarkan ulang Spreadsheet untuk memulihkan sumber yang sama. Sistem menolak unlink jika sumber masih punya konfigurasi, hasil ETL, data product, binding master, dependensi, atau job aktif; periksa keterkaitan tersebut sebelum mencoba lagi. Sumber dengan pemilik berbeda perlu ditinjau tujuan serta hak aksesnya sebelum memilih sumber utama.

Jika dropdown unit, domain bisnis, atau yurisdiksi kosong saat pendaftaran, pastikan
ketiganya sudah menjadi assignment aktif **akun yang sedang login**, pada tenant yang
sama. Atribut yang baru dibuat di Administrasi belum otomatis diberikan ke pengguna.
Minta admin lain menugaskan atribut tersebut melalui Administrasi → Pengguna, lalu
tekan **Muat ulang pilihan** di Workspace. Admin tidak dapat menugaskan akunnya sendiri.
Purpose diambil dari registry aktif, bukan assignment; jika semua pilihan kosong dan
ada pesan gagal memuat, periksa endpoint `/access/registration-options`.

## Memperbarui sumber dan periode waktu

Untuk menambah kolom sumber, ubah Google Sheets dahulu, lalu profiling ulang sumber/tab yang
sama. Workspace ETL hanya mengubah konfigurasi, bukan isi Sheet. Clone konfigurasi lama
menjadi draft bila header lama masih sesuai; jika tidak, buat draft baru dari profile terbaru.
Validate, review, approve, dan deploy. Perubahan kolom target non-master yang sudah deployed
ditampilkan pada Preview perubahan schema di langkah Validasi & persetujuan.
Konfirmasi dan review fingerprint diperlukan; worker memigrasikan perubahan aman saat deploy.

Label `w1`, `w2`, `january`, atau `february` tidak cukup untuk query tanggal. Lengkapi tahun
dan kalender minggu. Gunakan tanggal kejadian untuk transaksi, atau batas mulai/selesai
untuk rekap periode, sambil mempertahankan label asal. Map sebagai `date` dan dimensi semantic,
lalu periksa dry-run; jangan mengarang tanggal dari label yang ambigu. Panduan lengkap:
[perubahan sumber, kolom, dan periode waktu](PANDUAN_REVIEW_ETL.md#perubahan-sumber-kolom-dan-periode-waktu).

### Review ulang start_date/end_date

Tanggal native Google Sheets dibaca sebagai angka serial, misalnya `46023` =
`2026-01-01`. Target `date` saja tidak cukup: tambahkan `parse_date_id` pada
**Cleansing** dan pilih **Format nilai tanggal = Serial Google Sheets** untuk kedua kolom; pola tanggal boleh kosong untuk serial.
Text tanggal menggunakan pola strptime sesuai sumber jika diperlukan.
**Simpan draft**, **Dry-run ulang**, periksa kolom/baris `TYPE_OR_NULL_ERROR`,
lengkapi checklist lalu **Ajukan review**. Jangan mengubah nullable atau menghapus
record hanya untuk menutupi kegagalan parsing.

Untuk revisi dataset yang sama, jaga target tabel lama kecuali perpindahan memang
direncanakan. Draft manual dari profil bukan clone seluruh konfigurasi lama.
Nama view semantic mengikuti ID tab; target baru tidak menghindari perubahan
tipe view. Periksa preview schema, jumlah record lama, contoh serial menjadi tanggal,
dan blocker; centang konfirmasi schema sebelum Ajukan review. Tabel kosong dapat berubah
tipe; tabel berisi data mendukung serial bigint menjadi date dengan parse_date_id dan
kolom nullable baru (record lama null). Worker menjaga data/dependency/grant tanpa CASCADE,
memperbarui hash. DDL, view, konversi, hash, aktivasi konfigurasi, audit sukses dan status job SUCCEEDED berada dalam satu transaksi. Kegagalan sebelum commit mempertahankan schema/data serta konfigurasi aktif sebelumnya. Audit kegagalan dan alasan UI dicatat setelah rollback; retry memeriksa fingerprint review kembali.
Rename/drop fisik, key dan perubahan berisiko lain tetap diblokir. Jika fingerprint stale,
review ulang dengan preview terkini; versi approved lama tanpa bukti schema perlu clone/review.
Cocokkan `configuration_id` pada payload job DEPLOY dengan versi APPROVED
yang dimaksud; URL draft lama dapat menunjuk versi berbeda. Setelah deploy
SUCCEEDED, jalankan sync untuk memuat data. Helper frontend: `/guide#review-ulang-tanggal`.

## Contoh pertanyaan dashboard

- `Tampilkan total penjualan per cabang bulan ini.`
- `Bandingkan nilai penjualan dan jumlah transaksi per bulan selama satu tahun.`
- `Tampilkan 10 produk dengan penjualan tertinggi.`
- `Berapa jumlah record gagal berdasarkan jenis masalah kualitas?`

Sebutkan ukuran, dimensi, periode, lokasi, dan produk data bila pertanyaan masih ambigu. Backend
menyusun structured plan dan SQL aman berdasarkan semantic catalog; pengguna tidak memasukkan SQL.

## Jika data belum muncul

### Tabel aktif belum berarti data sudah dimuat

Deploy konfigurasi menyiapkan struktur tabel dan produk semantic; pemuatan data adalah
proses terpisah. Di Workspace, **Status database** dan **Baris dimuat** berasal dari
riwayat ETL/import terakhir melalui `/sources/tracking`, bukan `COUNT(*)` tabel saat ini.
**Belum dimuat** berarti belum ada riwayat pemuatan. Jika tracking gagal dimuat, tampilkan
pesan error dan nilai tidak tersedia, bukan angka 0 yang seolah-olah sudah diverifikasi.

Untuk pemuatan awal NON_MASTER, pilih **Sync manual** di Sumber & tracking atau
**Sync manual data** di tabel hasil ETL Workspace, lalu **Jalankan sync sekarang**.
Konfigurasi harus ACTIVE dengan approval reviewer berbeda, akses sumber POLICY_APPROVED,
dan gate rilis lengkap. Validasi teknis, AI dan preview konflik berjalan sebelum pemuatan
otomatis; data yang lolos tidak meminta approval batch tambahan. FULL_REFRESH dan master
tidak memakai jalur langsung. Master, jadwal, endpoint sync-review lama dan batch biasa
tetap memerlukan review pertanyaan, preview, approval serta Apply.

Job induk SYNC_REVIEW SUCCEEDED tidak membuktikan setiap tab sudah dimuat.
Periksa status batch per tab, **Baris dimuat**, dan waktu pemuatan. Tab dengan blocker
berhenti sementara tab lain yang valid dapat berhasil. Jangan menonaktifkan tab yang
dibutuhkan hanya untuk menghilangkan blocker.

Jadwal otomatis juga membuat sync review, tidak otomatis menyetujui/apply batch.
Cron mengikuti zona waktu sumber. Contoh `0 0 * * 1` dengan zona UTC berjalan setiap
Senin 00.00 UTC, yaitu 07.00 WIB; bukan segera setelah deploy atau setiap hari.
Untuk mengetahui mengapa belum ada pemuatan, periksa job SYNC_REVIEW/IMPORT_REVIEW,
jadwal dan zona waktu, status pause, kesiapan dependency, serta status worker/beat.

Jika batch gagal pada review AI dengan `AI_UPSTREAM_FAILED`, jangan langsung retry berulang
atau Apply. Administrator perlu memeriksa respons provider. HTTP 400 `invalid_json_schema`
berarti kontrak Structured Outputs ditolak, bukan database kosong atau approval akses kurang.
Review AI menggunakan schema `AIImportReviewResult` (issues bertipe, reviewed_rows, coverage);
parser konfigurasi ETL tidak boleh dipakai untuk hasil review. Setelah perbaikan backend,
gunakan **Revalidate** pada batch FAILED melalui workflow resmi agar tidak membuat batch
duplikat. **Resume** hanya untuk NEEDS_INPUT setelah blocker diselesaikan.

Untuk katalog kosong meskipun ETL ACTIVE, ikuti
[panduan assignment, policy SOURCE, review metadata, dan aktivasi sumber](PANDUAN_AKSES_KATALOG.md).
Approval konfigurasi/IT tidak menggantikan aktivasi akses POLICY_APPROVED.

1. Pastikan job discovery/sync/import terakhir berhasil.
2. Pastikan tab sudah diklasifikasikan dan konfigurasi berstatus approved, deployed, serta active.
   Jika gate siap tayang aktif, periksa apakah IT dan semua unit terkait sudah menyetujui revisi yang sama.
3. Periksa batch per tab dan Baris dimuat, bukan hanya job induk. Pada sync manual langsung,
   approval konfigurasi aktif menjadi dasar; pada master/batch biasa, preview tetap harus approved sebelum Apply.
4. Periksa master/taxonomy binding dan dependency freshness.
5. Periksa masalah karantina dan aturan kualitas yang menahan batch.
6. Periksa metadata sumber, policy `SOURCE`, assignment pengguna, row scope, serta kolom sensitif.
7. Pastikan produk memiliki dimensi/metrik dan freshness terbaru.
8. Perjelas pertanyaan NL2SQL atau pilih ruang data secara eksplisit.

## Bantuan dalam aplikasi

Tombol **Bantuan** tersedia pada semua halaman dan menjelaskan fungsi serta operasi halaman aktif.
Pilih **Panduan lengkap** dari dialog tersebut untuk membuka workflow `/guide`. Panduan route dan
aksesibilitas dijelaskan di [bantuan kontekstual frontend](FRONTEND_CONTEXTUAL_HELP.md).

Pengguna yang sudah login juga dapat membuka **Tanya AI** dari tombol bantuan global. Asisten mencari
jawaban pada knowledge base pengguna yang dikurasi, menampilkan sumber rujukan, dan tidak mempunyai
akses langsung ke source code, database, filesystem, atau credential. Jangan masukkan password,
token, API key, data pribadi, atau isi spreadsheet sensitif ke pertanyaan.

Contoh nilai yang dapat dipakai saat menjelaskan form taxonomy, yurisdiksi, metadata sumber,
dan master tersedia di [Contoh pengisian aplikasi](CONTOH_ISIAN_APLIKASI.md).
### Konfirmasi nilai asli pada temuan AI

**Sync manual langsung:** untuk NON_MASTER, tombol Sync manual membaca data terbaru,
memeriksa konfigurasi ACTIVE/approval terpisah, rilis/akses sumber, validasi teknis,
AI dan preview konflik. Jika semuanya lolos, data langsung dimuat memakai approval
konfigurasi sebagai dasar; tidak meminta approval batch ulang. Konfirmasi tombol
mencakup perubahan database dan biaya AI. Master, FULL_REFRESH, drift, konflik,
atau temuan keamanan/PII berhenti. Jadwal dan batch review biasa tetap memakai
alur preview/approval/Apply. Batch lama tanpa keputusan dapat diperiksa ulang
bila blocker seluruhnya AI; tidak otomatis menerima temuan lama.

Batch yang `NEEDS_INPUT` belum memuat data ke database. Buka batch dan baca temuan setiap baris/kolom. Untuk kategori `AI_REVIEW`, bila nilai asli sudah diverifikasi sah, pilih **Konfirmasi nilai asli sah** (`KEEP_ORIGINAL`) lalu isi alasan. Ini berlaku juga untuk pertanyaan batch lama. Semua temuan tetap wajib ditinjau; alasan dan aktor disimpan dalam keputusan/audit, tanpa mengganti nilai staging.

Jangan menerima dugaan data pribadi, salah mapping, atau aturan persentase yang belum jelas tanpa verifikasi pemilik data. Error teknis wajib (tipe, nullability, referensi, dan sejenisnya) tidak dapat dilewati dengan konfirmasi. Bila perlu mengubah Sheet, pilih `CORRECT_SOURCE`, perbaiki Sheet, lalu gunakan snapshot/batch baru.

Setelah semua pertanyaan selesai, cakupan AI `COMPLETE`, dan validasi teknis selesai tanpa
blocker, batch masuk `READY_FOR_APPROVAL`. Untuk batch sync manual NON_MASTER dengan
konfigurasi/akses yang masih berlaku, jalankan **Sync manual** kembali agar batch siap
tersebut dipreview dan dimuat berdasarkan approval konfigurasi aktif. Jika masih ada
konflik atau prasyarat berubah, sistem tetap berhenti. Master/batch biasa memakai
**Preview → approval reviewer terpisah → Apply**. Menjawab pertanyaan saja tidak memuat record.

### Membaca status dan lokasi temuan

- **Sedang berjalan / validasi / diperiksa AI / memuat:** worker masih memproses.
- **Menunggu tindakan (`NEEDS_INPUT`):** berhenti pada temuan; menunggu saja tidak menyelesaikannya.
- **Belum lengkap (`IN_PROGRESS`):** ringkasan belum seluruhnya selesai, bukan bukti worker aktif.
- **Gagal (`FAILED`):** perbaiki penyebab teknis lalu Revalidate melalui batch resmi.
- **Berhasil (`SUCCEEDED`):** batch pemuatan selesai; periksa jumlah baris dan timestamp.

Tekan **Lihat detail** berikon mata pada tracking, tabel hasil ETL, hasil sync atau audit
trail. Modal menampilkan keterangan, kode penghambat, nomor baris dan kolom temuan,
serta **Buka batch untuk tindak lanjut**. Nomor baris adalah baris asli Google Sheet
pada snapshot, termasuk header; penyisipan baris setelah snapshot dapat menggeser lokasi.
Daftar pertanyaan dipaginasi dengan **Muat temuan berikutnya**.

Audit mencatat aktor, waktu, keputusan/alasan dan ringkasan maksimal 20 lokasi tanpa
nilai mentah. Riwayat kegagalan lama tidak berarti pemuatan terbaru gagal. Membuka
detail tidak menyetujui temuan, mengubah Sheet, atau menjalankan sync. Dugaan PII
perlu verifikasi pemilik data; jangan menerima nama pribadi pada kolom non-PII tanpa
memperbaiki klasifikasi/mapping yang sesuai.

### Review perubahan schema NON_MASTER

Langkah 7 menampilkan `deployment_plan.migration.comparison`: kolom lama/baru beserta tipe dan nullability, key sebelum/sesudah, target/proyeksi view dan dependency. Operasi, jumlah record lama, contoh konversi dan blocker tersedia sebelum submit/approval/deploy. Reviewer menyetujui schema dan mapping pada revisi serta fingerprint schema/data yang sama. Perubahan setelah review meminta review ulang (`SCHEMA_MIGRATION_STALE`).

Untuk `bigint menjadi date` pada tabel berisi data, pilih **Format nilai tanggal = Serial Google Sheets** (`date_input_format: "GOOGLE_SHEETS_SERIAL"`) bersama `parse_date_id`. Tipe bigint atau angka dalam rentang valid saja tidak membuktikan bahwa nilainya tanggal. Konfirmasi makna sumber melalui mapping; backend memeriksa seluruh nilai non-null dan menampilkan `validation.checked`, `convertible`, `invalid`, serta contoh. Nilai di luar rentang 1..2958465 menghentikan migrasi. Mode serial eksplisit menolak text, pecahan dan nilai non-finite; mode `TEXT` memakai pola strptime dan menolak angka. Default null mempertahankan parser konfigurasi lama, tetapi tidak mengizinkan migrasi berisiko tanpa deklarasi format. Workbook menyimpan pilihan ini di `02 Struktur Kolom`, kolom AD.

Worker mendukung kolom nullable baru dan perubahan tipe pada tabel kosong. View yang perlu dibuat ulang mempertahankan ACL/komentar; dependency yang tidak aman, rename/drop fisik, perubahan key dan backfill wajib diblokir. DDL, view, konversi, hash, aktivasi konfigurasi, audit sukses dan status job SUCCEEDED berada dalam satu transaksi. Kegagalan sebelum commit mempertahankan schema/data serta konfigurasi aktif sebelumnya. Audit kegagalan dan alasan UI dicatat setelah rollback; retry memeriksa fingerprint review kembali.

`DATABASE_RETRY_REQUIRED`: database sibuk/timeout/konflik; tunggu lalu retry. `DATABASE_PERMISSION_DENIED`: admin memeriksa role DDL, ownership dan izin SET ke role aplikasi. Catat ID job; jangan mengubah SQL atau menghapus data untuk melewati blocker. Migrasi platform saat rollout berbeda dari perubahan schema dataset melalui aplikasi.


### Cleansing text otomatis dan bukti temuan AI

Kolom `text` dan `varchar` selalu mendapat `trim` otomatis pada nilai sumber sebelum transformasi tambahan, validasi DQ/key, pemeriksaan AI, dan pemuatan. `"  KAN  Jabung  "` menjadi `"KAN  Jabung"`: spasi di tengah, huruf, dan nol depan tetap dipertahankan. Nilai berisi spasi saja menjadi kosong/NULL; nullable mengizinkannya, kolom wajib tetap menghasilkan TYPE_OR_NULL_ERROR. Transformasi tambahan seperti normalize_whitespace, prefix/suffix, atau koreksi ejaan perlu aturan yang direview; trim dasar tidak perlu ditambahkan satu per satu. Nilai sumber di Sheet tidak ditulis ulang.

AI tidak boleh menganggap `[REDACTED]` sebagai data rusak atau menyimpulkan duplikat dari nilai yang disamarkan. Temuan duplikat memakai `issue_kind=EXACT_DUPLICATE` dan `related_source_row`; server membandingkan seluruh data asli di staging. Temuan pada nilai tersembunyi atau duplikat yang tidak terbukti dicatat sebagai temuan yang diabaikan pada checkpoint/audit tanpa membocorkan nilai. Masalah nyata pada kolom terbuka, dugaan PII, dan coverage tidak lengkap tetap menghentikan batch.

Sync manual pada konfigurasi NON_MASTER aktif yang telah disetujui dapat memeriksa ulang batch NEEDS_INPUT dengan blocker AI saja dan seluruh pertanyaan masih terbuka tanpa keputusan pengguna. Worker mengulang cleansing/validasi lalu review AI, mempertahankan identitas staging dan audit pertanyaan lama. Batch dengan keputusan, blocker teknis, konflik, atau gate akses/rilis belum selesai tidak dilompati. Muat ulang halaman tidak menjalankan sync.


### Tabel error response

Lihat [Error response: kemungkinan penyebab dan tindakan](ERROR_RESPONSES.md). Tabel mencakup error sumber, review/deploy schema, validasi/import, akses katalog serta layanan database/AI. Di aplikasi: **Bantuan > Tabel error response** atau **Panduan lengkap > Tabel error response**; gunakan pencarian kode. Alasan keputusan akses dan blocker batch dibedakan dari error HTTP.


### Format Google Sheet ideal untuk analitik dan action plan

Baca [Panduan lengkap format Google Sheet](PANDUAN_FORMAT_GOOGLE_SHEET.md): penamaan file/tab dan produk, header tabular, grain/key, master/taxonomy, tipe/satuan/presisi, waktu/periode wajib untuk data periodik, metrik, kualitas, provenance, action plan berbasis bukti dan contoh tabel. Di aplikasi buka **Bantuan > Format Google Sheet ideal** atau **Panduan lengkap > Format Google Sheet ideal**. Waktu kejadian/pengukuran, periode data dan waktu pengambilan dibedakan; tanggal sync bukan pengganti waktu bisnis. Definisi metrik dan tindakan tetap perlu review, bukan asumsi otomatis dari nama kolom.


### Istilah teknis untuk pengguna non teknis

[Tabel istilah teknis dalam bahasa sederhana](ISTILAH_TEKNIS.md) menjelaskan grain, business/primary key, master, taxonomy, mapping, tipe, nullable, dimensi/metrik, snapshot, ETL, periode, waktu pengambilan serta proses pemuatan dengan contoh bisnis. Buka **Bantuan > Istilah teknis dalam bahasa sederhana** atau **Panduan lengkap > Istilah teknis dalam bahasa sederhana**; cari istilah, arti atau contoh.


### Lima contoh Excel untuk analitik dan action plan

Lihat [Contoh data analitik](CONTOH_DATA_ANALITIK.md): keluhan pelanggan, sebaran marketing ATL/BTL, kepuasan berbasis produk, competitiveness harga/layanan dan plan/goal/KPI. File dapat diunduh dari **Bantuan > Contoh Excel untuk analitik dan action plan** atau **Panduan lengkap > Contoh Excel**. Data fiktif dilengkapi master, waktu/periode, kamus, rencana ETL, formula dan baseline tindakan; target/bobot/hipotesis tetap perlu verifikasi bisnis.


## Formula analitik dan aturan action plan

Lima contoh Excel memuat Formula_Analitik dan Aturan_Action_Plan. Kedua tab kontrol Dikecualikan dari ETL; produk data utamanya harus ACTIVE. Backend menerima impor melalui API analytics-rules/import-sheet, menyediakan preview, approval reviewer berbeda, evaluate berbasis metrik yang diizinkan dan REVOKE untuk menghentikan aturan. Hasil berupa usulan PROPOSED dengan bukti angka, periode dan versi; unit, sampel serta hipotesis diperiksa manusia. Workflow aturan saat ini melalui API, belum terhubung otomatis ke wizard ETL atau chat AI.

Lihat [panduan aturan dan formula](PANDUAN_ATURAN_ANALITIK.md) serta [lima template Excel](CONTOH_DATA_ANALITIK.md).


## Panduan khusus binding master

Baca [Panduan khusus binding master](PANDUAN_BINDING_MASTER.md): Registry, approval definisi, deploy storage, mapping tab MASTER, Simpan binding & dry-run, approval binding, batch import, Preview, approval dan Apply. Panduan membedakan binding tab dengan binding kolom referensi serta menyediakan contoh BISNIS/is_active, troubleshooting dan checklist record kanonis. Di aplikasi: Panduan penggunaan > Binding master (/guide#binding-master) atau Bantuan > Panduan khusus binding master.


## Koreksi sebelum storage pertama

Definisi approved dapat dikoreksi sebelum storage pertama dibuat melalui revisi dan approval reviewer berbeda. Backend memeriksa bahwa tabel/relation belum ada dan audit tidak mencatat deployment storage sebelumnya. Key, tipe atau field wajib baru pada fase ini tidak memigrasikan data. Approval menyimpan versi lama dan menandai initial_schema_correction; binding versi lama perlu review ulang. Jika storage sudah ada atau pernah dideploy, perubahan tidak kompatibel tetap memerlukan migrasi yang direview, termasuk pada tabel kosong atau tabel yang pernah dihapus. Jangan hapus/buat ulang storage untuk melewati pemeriksaan.
