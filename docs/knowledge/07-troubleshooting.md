---
id: pemecahan-masalah-umum
title: Pemecahan masalah umum
summary: Tindakan awal saat sumber, konfigurasi, import, akses, atau layanan AI terhambat.
routes: ["/*"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Jika sumber tidak terbaca, periksa URL/ID, izin Viewer service account, range, dan status job. Sumber yang gagal tetap tercatat; perbaiki tahapnya, jangan mendaftarkan ulang. **Temukan tab** membaca ulang daftar tab Google Sheet; **Muat ulang** hanya menyegarkan tampilan aplikasi.

Jika tab dihapus/diubah, jalankan Temukan tab, tunggu SUCCEEDED, lalu Profiling ulang. Profil baru dapat membuat draft schema terbaru. Perbaiki mapping dan jalankan validasi. Pada owner workflow, pemilik data melanjutkan deploy setelah validasi tanpa approval konfigurasi rutin. Item legacy mengikuti reviewer yang ditampilkan. `REVIEW_STALE` berarti snapshot berubah; gunakan profil dan validasi terbaru, bukan retry bukti lama.

`DRIVE_API_NOT_ENABLED`: admin mengaktifkan Google Drive API pada Cloud project service account. `SOURCE_CHANGE_CHECK_DENIED`: periksa Drive API dan izin metadata Drive. Temukan tab/profiling manual bisa digunakan sementara. `SOURCE_ACCESS_DENIED`: pemilik Sheet memastikan service account mendapat Viewer.

`CONFIGURATION_INVALID`: buka detail validasi, perbaiki mapping, tipe, key, aturan atau jawaban yang ditunjuk, lalu dry-run ulang. `SCHEMA_MIGRATION_STALE`: muat preview perubahan schema terbaru. `SCHEMA_MIGRATION_BLOCKED`: baca blocker; perubahan key, kolom wajib baru, rename/drop fisik atau dependency berisiko tidak bisa dilewati dengan menghapus tabel.

`MASTER_RUNTIME_PENDING` berarti tab MASTER tidak memakai konfigurasi ETL biasa. Buka Registry master, validasi definisi, deploy storage, atur binding sumber, lalu buat batch master. Pada owner workflow, selesaikan temuan, Preview, dan Apply setelah konfirmasi. Legacy dapat menampilkan approval. Binding valid belum berarti record sudah masuk; periksa Record kanonis.

`NEEDS_INPUT` atau **Menunggu tindakan** berarti batch berhenti untuk jawaban/keputusan, bukan worker masih berjalan. **Lihat detail** berikon mata menampilkan alasan, kode, nomor baris, kolom dan catatan tanpa nilai mentah. `KEEP_ORIGINAL` hanya untuk nilai sah yang sudah diverifikasi pemilik dengan alasan wajib; error teknis, PII, atau salah mapping perlu diperbaiki.

Katalog kosong: periksa produk aktif, apakah data sudah dimuat, aksi READ/QUERY, domain dan unit pengguna, tenant, serta policy khusus. Akses default READ/QUERY berlaku dalam domain dan business unit pemilik; fallback tidak mensyaratkan yurisdiksi. Policy khusus dapat mempersempit akses. `DEFAULT_DENY` berarti tak ada izin yang cocok; `EXPLICIT_DENY` tidak dapat dikalahkan ALLOW.

`RELEASE_APPROVAL_REQUIRED` berlaku pada gate legacy/rilis yang masih aktif; item owner-managed tervalidasi tidak memerlukan approval rilis kedua. Database `DATABASE_PERMISSION_DENIED` perlu admin memeriksa log job dan privilege role; jangan memberi runtime superuser. AI error: catat request ID, cek health, model, budget dan kuota; jangan mengirim key/password ke helper.

Gunakan **Sumber & tracking** sebagai daftar lengkap dengan pencarian dan pagination. Kegagalan tahap tidak menghapus sumber. UNLINKED menyembunyikan sumber dari daftar aktif tetapi menyimpan audit; pemulihan mengikuti dua konfirmasi. Audit menampilkan siapa melakukan tindakan dalam aplikasi; Drive modifiedTime tidak menunjukkan siapa editor eksternal.
