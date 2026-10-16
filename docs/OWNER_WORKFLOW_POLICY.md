# Alur pengelolaan sumber dalam unit bisnis

Berlaku ketika `ETL_OWNER_WORKFLOW_ENABLED=true` dan akses unit default aktif. Pengelola menyelesaikan validasi dan eksekusi dalam satu alur tanpa approver manusia terpisah. Aturan ini juga berlaku pada item lama; umur item atau daftar approver lama tidak mengembalikan aturan lama.

| Kegiatan | Siapa yang dapat menjalankan | Pemeriksaan aplikasi |
| --- | --- | --- |
| Membaca data analitik | Pengguna satu unit dengan aksi READ/QUERY | Tenant, assignment aktif, policy khusus, sensitivitas, pembatasan baris/kolom |
| Sumber, konfigurasi, deploy, sync, retry | SOURCE_OWNER / DATA_STEWARD dalam unit sumber; PLATFORM_ADMIN | Unit aktif dan role pengelola, validasi data/schema, snapshot terkini |
| Definisi master dan taxonomy | Pembuat, pengelola satu unit dengan pembuat, atau admin | Versi, business key, dependency dan perubahan storage |
| Binding master / taxonomy | Pengelola unit sumber | Target aktif, mapping, versi, snapshot dan hasil dry-run |
| Aturan formula / action plan dan relasi analitik | Pengelola unit produk yang terkait | Formula/query valid, kontrak semantic terkini, cardinality dan izin data |
| Role, assignment, policy akses khusus | Admin sesuai kontrol administrasi | Tidak memberikan hak admin/ekspor/PII secara otomatis |

## Langkah penggunaan

1. Admin memberikan role SOURCE_OWNER atau DATA_STEWARD dan assignment unit bisnis aktif. Domain, yurisdiksi dan purpose adalah metadata tambahan; tidak wajib untuk akses unit default.
2. Pilih unit pemilik ketika menghubungkan Google Sheet. Owner/steward dapat diisi otomatis oleh aplikasi. Spreadsheet yang sudah terdaftar oleh rekan satu unit dibuka kembali, bukan didaftarkan ulang.
3. Jalankan discovery/profiling, pilih tab dan klasifikasi MASTER atau NON_MASTER. Perubahan header/tab tidak mengulang persetujuan akses sumber.
4. NON_MASTER: siapkan mapping dan cleansing, periksa dry-run serta preview perubahan schema, lalu Validasi & siapkan deploy dan Deploy.
5. MASTER: siapkan definisi, validasi/publikasikan melalui Registry, deploy storage, simpan binding valid, buat batch, periksa Preview lalu Apply. Tidak perlu mengganti akun.
6. Sync manual maupun jadwal menggunakan konfigurasi aktif dan memuat batch yang lolos validasi. Jika ada konflik, key ganda, konversi gagal, atau pertanyaan wajib, aplikasi berhenti pada NEEDS_INPUT dengan tindakan yang harus diselesaikan.

## Menyelesaikan item lama

- Sumber ACCESS_POLICY_REQUIRED/PENDING dengan metadata unit valid: pilih sumber di Workspace dan tekan Validasi akses unit. Sync manual juga menjalankan validasi ini. API: `POST /sources/{source_id}/validate-access`. Tindakan mencatat aktor, waktu dan revisi; tidak memalsukan keputusan reviewer lama.
- Metadata REJECTED: perbaiki metadata lalu simpan kembali sebelum validasi. Unit/akun nonaktif atau assignment kedaluwarsa harus diperbaiki, bukan dilewati.
- Konfigurasi APPROVED lama dapat dideploy pengelola satu unit setelah pemeriksaan runtime. Konfigurasi NEEDS_REVIEW harus divalidasi dan disiapkan oleh pengelola; tidak semua draft historis diaktifkan otomatis.
- Binding/definisi lama yang masih DRAFT/NEEDS_REVIEW dapat dituntaskan pengelola berwenang melalui aksi validasi/publikasi yang tersedia. Mapping/data yang berubah tetap diperiksa kembali.
- Batch READY_FOR_APPROVAL: buat preview terbaru dan Apply pada owner workflow. Label status kompatibilitas bukan syarat orang kedua. Batch stale memakai Revalidate dan batch pengganti dengan dependency terbaru.
- Daftar approver sumber dan approval rilis lama tetap tersimpan untuk audit tetapi tidak menjadi gate pada owner workflow. Role TECHNICAL_APPROVER tetap dapat membaca operasional dalam unitnya; keputusan bisnis pada owner workflow memakai role pengelola. Role ini tidak otomatis menjadi DATA_STEWARD atau mendapat hak PII/admin. Pada mode legacy, hak reviewer lama tetap berlaku.

## Batas yang tetap berlaku

Explicit DENY, isolasi tenant, assignment aktif, pembatasan ekspor, sensitivitas dan validasi teknis tetap berlaku. Kegagalan data atau schema mempertahankan transaksi sebelumnya. Perubahan arti kolom, misalnya memilih saldo awal atau saldo akhir, perlu keputusan bisnis dan tidak diselesaikan dengan melewati validasi.

Jika owner workflow dimatikan secara eksplisit, alur legacy dengan reviewer dan metadata lengkap kembali berlaku. Petunjuk reviewer terpisah hanya berlaku pada mode tersebut.
