---
id: pemecahan-masalah-umum
title: Pemecahan masalah umum
summary: Pemeriksaan awal ketika sumber, konfigurasi, import, akses, atau layanan AI belum siap.
routes: ["/*"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Jika sumber tidak terbaca, periksa URL, akses Viewer service account, credential backend, dan health Google. Untuk konfigurasi/batch yang diblokir, baca kode error, muat ulang state, dan selesaikan dependency sebelum mencoba lagi.

Jika kolom sumber berubah atau fingerprint tidak cocok (`CONFIGURATION_CONFLICT`), perbaiki Sheet lalu profiling ulang sumber yang sama dan buat draft dari profile terbaru. Clone hanya berhasil jika header mapping lama masih ada. Jika target tabel non-master berubah (`SCHEMA_CHANGE_UNSAFE`), minta migrasi manual yang direview; jangan menghapus tabel, registrasi ulang, atau mengulang deploy tanpa penanganan schema. Range/header tab aktif tidak dapat diubah langsung. Untuk periode text `w1`, `w2`, `january`, atau `february`, lengkapi tanggal dan tahun sesuai grain serta kalender bisnis, bukan sekadar mengganti tipe kolom.

Jika NL2SQL tidak bisa membaca data meskipun health database utama sukses, administrator perlu memeriksa koneksi reader yang terpisah, izin akses schema semantic dan SELECT pada view yang diizinkan, serta memastikan reader tidak memiliki hak tulis/superuser. Health database utama bukan bukti kesiapan reader atau keberhasilan panggilan OpenAI.

Jika Hubungkan & profiling tampak tidak bereaksi, lihat pesan di bawah tombol dan lengkapi field wajib. Pendaftaran gagal: periksa daftar sumber sebelum mencoba lagi. Job QUEUED/RUNNING: tunggu worker atau buka monitor. Discovery FAILED: sumber tetap tercatat, baca penyebabnya dan ulangi tahap relevan, bukan pendaftaran.

Dropdown unit/domain/yurisdiksi memakai assignment aktif akun pendaftar pada tenant yang sama. Registry saja tidak memberi assignment; minta admin lain menugaskan atribut melalui Administrasi → Pengguna lalu Muat ulang pilihan. Admin tidak dapat menugaskan diri sendiri. Purpose berasal dari registry aktif; owner/steward dari akun aktif. Pesan gagal memuat pilihan berbeda dari assignment kosong.

Panel Berikan unit/departemen memuat DEPARTMENT; domain/yurisdiksi lewat form Atribut. Centang unit dan pastikan akun tujuan sama dengan pengguna Workspace.

Jika data belum muncul di dashboard, pastikan discovery, profiling, klasifikasi, konfigurasi, deploy, activation, import, dan job terakhir berhasil. Periksa master atau taxonomy binding, pertanyaan batch, data karantina, freshness, metadata sumber, serta policy akses.

Untuk `RELEASE_APPROVAL_REQUIRED`, buka **Persetujuan tayang**. IT harus melengkapi checklist teknis dan setiap unit terkait menyetujui revisi yang sama. Penolakan atau perubahan revisi/snapshot/aturan membatalkan keputusan lama; perbaiki versi/aturan sebelum deploy. Persetujuan ini bukan approval batch atau izin membaca data.

Untuk `DATABASE_PERMISSION_DENIED` (42501), admin memeriksa role DDL: USAGE/CREATE pada schema trusted/semantic serta izin/ownership objek target. `DATABASE_CONNECTION_FAILED` memerlukan pemeriksaan koneksi aplikasi/DDL. Catat ID job agar admin dapat mencari log worker.

Deploy memberi role runtime SELECT/INSERT untuk APPEND (preview membaca target), SELECT/INSERT/UPDATE untuk UPSERT, dan SELECT view semantic. Tabel APPEND lama perlu grant SELECT terarah atau deploy ulang. FULL_REFRESH memerlukan DELETE dari admin; aplikasi tidak menambahkannya otomatis.

Jika AI gagal, periksa health OpenAI, model, kuota, budget/policy, dan request ID sebelum mencoba lagi. Jangan kirim password, token, API key, credential, atau data pribadi ke asisten.

Sumber tidak ada di dropdown? Cari nama/kode melalui **Sumber & tracking**, pagination, lalu **Buka sumber**. Dropdown hanya memilih konteks, bukan daftar lengkap. Kegagalan tahap tidak menghapus sumber; jangan registrasi ulang.

UNLINKED menyembunyikan sumber tanpa menghapus riwayat. Admin dapat memulihkan dengan dua konfirmasi. Unlink perlu sumber utama, alasan, dua konfirmasi; relasi operasional dapat menahannya.

DISCOVERY gagal: periksa akses/tab. PROFILING gagal: periksa header/error. CONFIGURATION belum siap: lengkapi mapping/review. Binding master approved belum memuat record; periksa batch/apply dan Owner/Steward.

Menunggu tindakan (NEEDS_INPUT) berarti berhenti pada temuan, bukan worker masih berjalan; menunggu saja tidak menyelesaikannya. Sedang validasi/diperiksa AI/memuat berarti aktif. IN_PROGRESS berarti belum lengkap; SUCCEEDED per batch berarti pemuatan selesai, bukan hanya job induk.

Lihat detail berikon mata pada tracking, hasil ETL/sync dan audit trail membuka kode, keterangan, baris asli Sheet pada snapshot (termasuk header), kolom serta tautan batch. Audit menyimpan maksimal 20 lokasi tanpa nilai mentah; Muat temuan berikutnya memaginasi pertanyaan. Jika Sheet berubah setelah snapshot, nomor baris dapat bergeser. Riwayat kegagalan lama bukan status terbaru. Membuka modal tidak approve/sync.

Dugaan PII pada kolom non-sensitif masih temuan AI, bukan kepastian: verifikasi nama pribadi/mapping dengan pemilik data, perbaiki klasifikasi jika benar PII. KEEP_ORIGINAL hanya untuk nilai sah terverifikasi, alasan wajib dan diaudit; bukan bypass error teknis. Setelah blocker selesai, sync manual NON_MASTER siap dapat dilanjutkan tanpa approval batch ulang. Master/jadwal/batch biasa tetap preview/approval/Apply.

Aktivasi versi baru membuat konfigurasi lama SUPERSEDED. Inventaris tabel retired hanya mencatat tabel yang masih ada, tidak menghapusnya. REVIEW_REQUIRED meminta pemeriksaan rollback/dependency/retensi; delete_ready tetap false sampai cleanup terkontrol tersedia.


MASTER_RUNTIME_PENDING menolak konfigurasi/sync ETL biasa pada MASTER. Jangan ubah klasifikasi untuk melewatinya. Buka Registry master → Storage & record master, pastikan source binding approved dan storage siap, lalu buat batch dari **Sumber master terikat**. MASTER_BINDING_REQUIRED: atur/review binding. MASTER_STORAGE_REQUIRED: reviewer deploy storage approved. Batch tetap perlu preview, approval, dan apply.
