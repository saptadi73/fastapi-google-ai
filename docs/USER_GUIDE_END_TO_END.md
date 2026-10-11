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

## Prosedur awal sampai akhir

| Tahap | Tindakan | Hasil minimum sebelum lanjut |
|---|---|---|
| 1. Administrasi | Buat pengguna, role, atribut departemen/domain/yurisdiksi/purpose, assignment multi-unit eksplisit, permission, policy, approver per sumber, dan aturan persetujuan sebelum tayang | Pengguna dapat login, cakupan unit dipilih, dan pemeriksa IT/unit terkait ditunjuk |
| 2. Pendaftaran sumber | Bagikan Sheet ke service account sebagai Viewer, lalu daftarkan URL/ID serta metadata kepemilikan | Discovery dan profiling sukses; tab serta header terbaca |
| 3. Klasifikasi tab | Konfirmasi `MASTER` atau `NON_MASTER` untuk setiap tab | Semua tab yang akan diproses berstatus confirmed |
| 4. Master | Definisikan field, business key, label, policy, storage, dan binding | Definisi/storage/binding approved dan record rujukan siap |
| 5. Taxonomy | Buat term, alias, hierarki, versi, serta binding kolom | Taxonomy dan binding approved |
| 6. Konfigurasi ETL | Map kolom, transformasi, DQ, strategi load, business key, semantic product, dimensi, dan metrik | Konfigurasi valid tanpa blocker |
| 7. Review/deploy | Submit dan approve konfigurasi; jika aturan rilis aktif, IT dan setiap unit terkait menyetujui revisi yang sama di Persetujuan tayang; lalu deploy, activate, dan selesaikan policy sumber | Konfigurasi `ACTIVE` dan produk lolos kontrol akses |
| 8. Batch import | Stage data, jawab pertanyaan, resolve referensi, preview, approve, lalu apply | Batch `SUCCEEDED` sesuai preview |
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
memerlukan migrasi schema yang direview; persetujuan di form bukan migrasi otomatis.

Label `w1`, `w2`, `january`, atau `february` tidak cukup untuk query tanggal. Lengkapi tahun
dan kalender minggu. Gunakan tanggal kejadian untuk transaksi, atau batas mulai/selesai
untuk rekap periode, sambil mempertahankan label asal. Map sebagai `date` dan dimensi semantic,
lalu periksa dry-run; jangan mengarang tanggal dari label yang ambigu. Panduan lengkap:
[perubahan sumber, kolom, dan periode waktu](PANDUAN_REVIEW_ETL.md#perubahan-sumber-kolom-dan-periode-waktu).

## Contoh pertanyaan dashboard

- `Tampilkan total penjualan per cabang bulan ini.`
- `Bandingkan nilai penjualan dan jumlah transaksi per bulan selama satu tahun.`
- `Tampilkan 10 produk dengan penjualan tertinggi.`
- `Berapa jumlah record gagal berdasarkan jenis masalah kualitas?`

Sebutkan ukuran, dimensi, periode, lokasi, dan produk data bila pertanyaan masih ambigu. Backend
menyusun structured plan dan SQL aman berdasarkan semantic catalog; pengguna tidak memasukkan SQL.

## Jika data belum muncul

Untuk katalog kosong meskipun ETL ACTIVE, ikuti
[panduan assignment, policy SOURCE, review metadata, dan aktivasi sumber](PANDUAN_AKSES_KATALOG.md).
Approval konfigurasi/IT tidak menggantikan aktivasi akses POLICY_APPROVED.

1. Pastikan job discovery/sync/import terakhir berhasil.
2. Pastikan tab sudah diklasifikasikan dan konfigurasi berstatus approved, deployed, serta active.
   Jika gate siap tayang aktif, periksa apakah IT dan semua unit terkait sudah menyetujui revisi yang sama.
3. Periksa batch import: seluruh pertanyaan wajib harus selesai dan preview yang sama harus approved
   sebelum apply.
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
