---
id: pemecahan-masalah-umum
title: Pemecahan masalah umum
summary: Pemeriksaan awal ketika sumber, konfigurasi, import, akses, atau layanan AI belum siap.
routes: ["/*"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Jika sumber tidak terbaca, periksa URL, akses Viewer service account, credential backend, dan health Google. Untuk konfigurasi/batch yang diblokir, baca kode error, muat ulang state, dan selesaikan dependency sebelum mencoba lagi.

Jika kolom sumber berubah atau fingerprint tidak cocok (`CONFIGURATION_CONFLICT`), perbaiki Sheet lalu profiling ulang sumber sama dan buat draft terbaru. Clone hanya jika header lama masih ada. Periksa Preview perubahan schema di Validasi & persetujuan, konfirmasi sebelum submit; worker menjalankan perubahan aman setelah approval. Jangan hapus tabel/registrasi ulang. Range/header aktif terkunci. Periode text w1/w2/january/february perlu tanggal/tahun sesuai grain/kalender, bukan mengganti tipe saja.

SCHEMA_REVIEW_REQUIRED: clone/review versi tanpa bukti schema. SCHEMA_MIGRATION_STALE: schema/data berubah, review preview baru. SCHEMA_MIGRATION_BLOCKED: selesaikan blocker; rename/drop fisik, key, kolom wajib baru pada tabel berisi data/dependency tidak aman diblokir. Worker: nullable baru, tipe pada tabel kosong, bigint serial menjadi date dengan parse_date_id/serial valid; data dijaga, hash diperbarui. DDL/view/konversi transaksional tanpa DROP CASCADE, ACL dijaga. View mengikuti ID tab. Error lama SCHEMA_CHANGE_UNSAFE/SEMANTIC_SCHEMA_MIGRATION_REQUIRED: gunakan review baru. Cocokkan configuration_id job/versi APPROVED; /guide#review-ulang-tanggal.

NL2SQL gagal meski health utama sukses: periksa koneksi reader terpisah, USAGE schema semantic dan SELECT view; reader tidak boleh menulis/superuser. Health utama bukan bukti reader/OpenAI siap.

Hubungkan & profiling tidak bereaksi: baca pesan/field wajib. Pendaftaran gagal: periksa daftar sebelum retry. QUEUED/RUNNING: tunggu/buka monitor. Discovery FAILED: sumber tetap tercatat; perbaiki tahapnya, bukan pendaftaran.

Dropdown unit/domain/yurisdiksi memakai assignment aktif akun/tenant pendaftar. Registry bukan assignment: admin lain menugaskan lewat Administrasi → Pengguna, lalu Muat ulang pilihan. Admin tidak menugaskan diri sendiri. Purpose dari registry; owner/steward akun aktif. Gagal memuat berbeda dari assignment kosong.

Panel Berikan unit/departemen memuat DEPARTMENT; domain/yurisdiksi lewat form Atribut. Centang unit dan pastikan akun tujuan sama dengan pengguna Workspace.

Data belum muncul: periksa discovery/profiling/klasifikasi/review/deploy/activation/import/job, binding master/taxonomy, pertanyaan, karantina, freshness, metadata dan policy akses.

RELEASE_APPROVAL_REQUIRED: buka Persetujuan tayang, IT melengkapi checklist dan tiap unit menyetujui revisi sama. Penolakan/perubahan revisi/snapshot/aturan membatalkan keputusan; perbaiki sebelum deploy. Bukan approval batch/izin membaca.

Untuk `DATABASE_PERMISSION_DENIED` (42501), admin memeriksa role DDL: USAGE/CREATE pada schema trusted/semantic serta izin/ownership objek target. `DATABASE_CONNECTION_FAILED` memerlukan pemeriksaan koneksi aplikasi/DDL. Catat ID job agar admin dapat mencari log worker.

Deploy memberi role runtime SELECT/INSERT untuk APPEND (preview membaca target), SELECT/INSERT/UPDATE untuk UPSERT, dan SELECT view semantic. Tabel APPEND lama perlu grant SELECT terarah atau deploy ulang. FULL_REFRESH memerlukan DELETE dari admin; aplikasi tidak menambahkannya otomatis.

AI gagal: periksa health/model/kuota/budget/policy/request ID. Jangan kirim password/token/API key/credential/data pribadi ke asisten.

Sumber tidak ada di dropdown? Cari nama/kode melalui **Sumber & tracking**, pagination, lalu **Buka sumber**. Dropdown hanya memilih konteks, bukan daftar lengkap. Kegagalan tahap tidak menghapus sumber; jangan registrasi ulang.

UNLINKED menyembunyikan sumber tanpa menghapus riwayat. Admin dapat memulihkan dengan dua konfirmasi. Unlink perlu sumber utama, alasan, dua konfirmasi; relasi operasional dapat menahannya.

DISCOVERY gagal: periksa akses/tab. PROFILING gagal: periksa header/error. CONFIGURATION belum siap: lengkapi mapping/review. Binding master approved belum memuat record; periksa batch/apply dan Owner/Steward.

Menunggu tindakan (NEEDS_INPUT) berarti berhenti pada temuan, bukan worker masih berjalan; menunggu saja tidak menyelesaikannya. Sedang validasi/diperiksa AI/memuat berarti aktif. IN_PROGRESS berarti belum lengkap; SUCCEEDED per batch berarti pemuatan selesai, bukan hanya job induk.

Lihat detail berikon mata pada tracking, hasil ETL/sync dan audit trail membuka kode, keterangan, baris asli Sheet pada snapshot (termasuk header), kolom serta tautan batch. Audit menyimpan maksimal 20 lokasi tanpa nilai mentah; Muat temuan berikutnya memaginasi pertanyaan. Jika Sheet berubah setelah snapshot, nomor baris dapat bergeser. Riwayat kegagalan lama bukan status terbaru. Membuka modal tidak approve/sync.

Dugaan PII pada kolom non-sensitif masih temuan AI, bukan kepastian: verifikasi nama pribadi/mapping dengan pemilik data, perbaiki klasifikasi jika benar PII. KEEP_ORIGINAL hanya untuk nilai sah terverifikasi, alasan wajib dan diaudit; bukan bypass error teknis. Setelah blocker selesai, sync manual NON_MASTER siap dapat dilanjutkan tanpa approval batch ulang. Master/jadwal/batch biasa tetap preview/approval/Apply.

Aktivasi versi baru membuat konfigurasi lama SUPERSEDED. Inventaris tabel retired hanya mencatat tabel yang masih ada, tidak menghapusnya. REVIEW_REQUIRED meminta pemeriksaan rollback/dependency/retensi; delete_ready tetap false sampai cleanup terkontrol tersedia.


MASTER_RUNTIME_PENDING menolak konfigurasi/sync ETL biasa pada MASTER. Jangan ubah klasifikasi untuk melewatinya. Buka Registry master → Storage & record master, pastikan source binding approved dan storage siap, lalu buat batch dari **Sumber master terikat**. MASTER_BINDING_REQUIRED: atur/review binding. MASTER_STORAGE_REQUIRED: reviewer deploy storage approved. Batch tetap perlu preview, approval, dan apply.

Transaksi migrasi gagal: rollback. Aktivasi gagal setelah commit: schema/audit tetap; retry wajib cocok fingerprint hasil migrasi.
