---
id: konfigurasi-import-dan-operasi
title: Konfigurasi ETL, batch import, dan operasi
summary: Approval metadata sumber gabungan, sync manual langsung, lokasi temuan, audit trail, dan perubahan schema.
routes: ["/sources", "/workspace", "/etl-review/*", "/configurations/*", "/import-reviews", "/import-reviews/*", "/release-approvals", "/imports/*", "/jobs", "/quality", "/data-catalog"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/PANDUAN_REVIEW_ETL.md
---
Konfigurasi ETL menetapkan mapping, tipe, transformasi, DQ, key, strategi load dan semantic. Tetapkan periode/watermark sesuai sumber dan validasi sampai tanpa blocker.

Tambah/rename kolom di Google Sheets, lalu profiling ulang sumber/tab yang sama. Workspace tidak menulis data ke Sheet. APPROVED/ACTIVE/REJECTED immutable: clone jika header lama ada, atau buat draft dari profil terkini. Tambah mapping lewat form, bukan struktur workbook. Fingerprint berubah membuat draft lama stale. Perubahan kolom/tipe/nullability/key target existing perlu migrasi manual yang direview; approval bukan migrasi otomatis. Jangan hapus tabel atau registrasi ulang.

Label `w1`, `w2`, `january`, `february` tidak cukup untuk query waktu: lengkapi tahun/kalender minggu. Transaksi memakai tanggal kejadian; rekap memakai periode mulai dan selesai sambil menyimpan label asal. Contoh Januari 2026: 2026-01-01 sampai 2026-01-31, bukan tanggal transaksi. Map date/dimensi waktu dan uji parser. Jangan menebak tanggal dari nama bulan atau minggu. Default periode metrik memakai dimensi waktu/jumlah hari; overlap periode tidak otomatis tersedia.

Master memakai definisi/binding, bukan ETL biasa. Tambah field nullable: approve, deploy-storage ulang, record lama null; review binding versi master/profil terbaru sebelum import. Field wajib baru atau perubahan key/tipe/nullability/rename/drop perlu migrasi khusus.

Review ulang start_date/end_date: tanggal native Sheets berupa angka serial (46023 = 2026-01-01, 46053 = 2026-01-31). Map target date dan tambahkan parse_date_id pada Cleansing untuk kedua kolom; pola tanggal boleh kosong untuk serial, text tanggal memakai pola strptime sesuai sumber. Simpan draft, Dry-run ulang, baca kolom/baris TYPE_OR_NULL_ERROR, isi checklist lalu Ajukan review. Jangan nullable/hapus record untuk menutupi format salah. Jaga nama target lama untuk revisi dataset yang sama kecuali perpindahan direview; draft manual baru bukan clone seluruh konfigurasi lama.

SEMANTIC_SCHEMA_MIGRATION_REQUIRED: nama view mengikuti ID tab, bukan tabel. Mengganti target tidak menghindari konflik tipe bigint menjadi date atau nama/urutan/penghapusan kolom view. Tim teknis memigrasikan dalam transaksi sambil menjaga data, dependency, owner dan grant; tidak DROP CASCADE. Dry-run lulus bukan bukti schema database cocok. Cocokkan configuration_id payload job DEPLOY dengan versi APPROVED, bukan URL draft lama. Setelah deploy SUCCEEDED baru sync memuat data. Helper /guide#review-ulang-tanggal.

Submit untuk reviewer berbeda dari pembuat. Jika aturan rilis aktif, IT dan approver tiap unit menyetujui revisi/snapshot yang sama pada Persetujuan tayang. IT memeriksa skema/mapping, DQ, keamanan/akses. Semua kelompok setuju sebelum deploy. Tanpa aturan rilis, review konfigurasi biasa berlaku. Revisi/snapshot/aturan berubah membatalkan keputusan lama; penolakan perlu versi baru/revisi aturan diaudit. Rollback tetap memeriksa aturan rilis kini. Profil/taxonomy/master/binding berubah dapat membuat konfigurasi stale.

Approver konfigurasi sumber yang bukan maker/editor metadata membaca ringkasan, memilih policy SOURCE APPROVED, lalu menyetujui konfigurasi, metadata PENDING dan aktivasi akses dalam satu transaksi. Tidak perlu approval metadata terpisah setelah berhasil. Gate rilis dan akses pembaca tetap berlaku. Helper /guide#approval-gabungan.

Pilih sumber di Sumber & tracking atau Workspace, tekan Sync manual / Sync manual data, lalu Jalankan sync sekarang. NON_MASTER ACTIVE dengan approval terpisah, akses POLICY_APPROVED dan rilis siap langsung dimuat jika validasi teknis/AI/preview konflik lolos, tanpa approval batch ulang. Master, FULL_REFRESH, konflik, drift, PII atau error berhenti. Konfirmasi mencakup database/biaya AI; Sheet tidak diubah. Periksa SUCCEEDED dan Baris dimuat per tab, bukan hanya job induk. Reload tidak mengantre ulang; batas monitor 10 menit bukan pembatalan. Jadwal, endpoint sync-review lama dan batch biasa tetap preview/approval/Apply.

Katalog menyediakan tombol Buka Google Sheet dan Buka sumber di Workspace bagi role operasional. Versi aktif terakhir tetap tampil selama revisi jika masih lolos akses; Sedang diperbarui menandai job/revisi/drift/snapshot/batch belum selesai. Terakhir aktif berasal dari audit aktivasi atau pemuatan sukses, dengan timestamp keduanya ditampilkan terpisah. Perubahan Sheet diketahui setelah profil/sync, bukan live push.

**Batch import** menyediakan pencarian sumber dan status proses; pilih sumber lalu tab terklasifikasi. **Persetujuan tayang** hanya menampilkan konfigurasi yang ditugaskan kepada approver, dengan pencarian dan detail keputusan.
# Konfirmasi temuan AI

NEEDS_INPUT = Menunggu tindakan, bukan worker berjalan. Lihat detail berikon mata pada tracking/hasil ETL/sync/audit membuka keterangan, kode, baris asli Sheet saat snapshot (termasuk header), kolom dan tautan batch. Audit menyimpan maksimal 20 lokasi tanpa nilai mentah; Muat temuan berikutnya memaginasi pertanyaan. Riwayat kegagalan lama bukan hasil terbaru. Membuka detail tidak sync/approve.

Temuan AI_REVIEW, termasuk batch lama, dapat dijawab KEEP_ORIGINAL dengan alasan verifikasi yang diaudit. Dugaan PII/salah mapping perlu pemilik data; error teknis tidak bisa dilewati. CORRECT_SOURCE meminta perbaikan Sheet dan snapshot baru. Setelah semua jawaban, AI COMPLETE dan validasi selesai tanpa blocker, batch siap. Sync manual kembali dapat memuat batch NON_MASTER siap berdasarkan approval konfigurasi aktif; batch biasa/master tetap preview, approval, Apply. Jawaban saja tidak memuat record.
