---
id: "binding-master-langkah"
title: "Binding master: Registry, storage, mapping dan approval"
summary: "Panduan step by step binding tab MASTER, Simpan binding & dry-run, Setujui binding dan prasyarat."
routes: ["/masters", "/masters/*", "/sources/*", "/guide"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: "docs/PANDUAN_BINDING_MASTER.md"
---
Mulai dari Registry master, siapkan storage, hubungkan tab sumber, lalu muat record melalui Batch import. Definisi, binding dan pemuatan adalah persetujuan yang berbeda; binding APPROVED belum berarti record sudah dimuat.

- **Binding tab sumber ke master**: Memuat atau memperbarui record rujukan dari tab MASTER ke master di Registry. Contoh: Tab Master Data berisi daftar bisnis → Master Bisnis.
- **Binding kolom referensi master**: Memvalidasi kode pada tab NON_MASTER terhadap record master yang sudah tersedia. Contoh: Kolom Kode Bisnis pada data marketing → business_code di Master Bisnis.

- Sumber Google Sheets sudah terdaftar, bisa dibaca service account sebagai Viewer, discovery dan profiling terbaru berhasil.
- Tab rujukan dikonfirmasi MASTER. Tab transaksi yang memakai rujukan tetap NON_MASTER.
- SOURCE_OWNER, DATA_STEWARD atau PLATFORM_ADMIN menyiapkan definisi dan binding. Reviewer berwenang berbeda pembuat menyetujui definisi, binding dan batch. Deploy storage dilakukan PLATFORM_ADMIN atau TECHNICAL_APPROVER.
- Gunakan master yang sudah ada jika identitas dan arti bisnisnya sesuai. Jangan membuat master duplikat hanya karena sumbernya berbeda.
- Akses sumber, assignment, policy dan gate lain yang diwajibkan tetap dipenuhi; klasifikasi MASTER atau approval binding tidak memberikan izin baca otomatis.

### 1. Periksa sumber dan klasifikasi

Halaman: **Sumber & tracking → Buka sumber → Workspace**. Pelaksana: Source Owner / Data Steward / Admin.

- Pilih sumber dan tab rujukan yang benar; periksa profil, header, tipe dan key.
- Jika ada tab baru atau rename, jalankan Temukan tab lalu Profiling ulang pada sumber yang sama.
- Konfirmasi MASTER untuk tab rujukan. Buka binding master, bukan approval konfigurasi ETL biasa.

Hasil sebelum lanjut: **Tab MASTER terkonfirmasi dan profil terbaru tersedia.**.

### 2. Pilih atau buat definisi di Registry master

Halaman: **Registry master → Buat master baru atau buka master yang sesuai**. Pelaksana: Source Owner / Data Steward / Admin.

- Cari berdasarkan kode/nama; periksa kandidat serupa sebelum membuat master baru.
- Tentukan kode, nama, deskripsi, field, tipe, sensitivitas, business key dan field label.
- Business key harus unik, stabil dan tidak kosong. Kolom is_active memakai boolean jika isinya TRUE/FALSE.
- Periksa policy record baru, konflik dan masa berlaku sesuai kebutuhan; jangan menebak arti field dari nama saja.

Hasil sebelum lanjut: **Draft definisi master dengan arti field dan identitas record yang jelas.**.

### 3. Ajukan dan setujui definisi

Halaman: **Halaman definisi / review master**. Pelaksana: Editor mengajukan; reviewer berbeda memutuskan.

- Simpan draft dan ajukan review definisi.
- Reviewer memeriksa field, business key, label, sensitivitas dan policy, lalu approve atau reject dengan catatan.
- Gunakan versi approved terbaru dari master aktif. Definisi yang belum approved tidak dapat dipilih sebagai tujuan binding.
- Sebelum storage pertama dibuat, koreksi key/tipe/field wajib dapat direview dan disetujui reviewer berbeda. Backend memeriksa storage fisik dan riwayat deployment; binding lama perlu review ulang.

Hasil sebelum lanjut: **Definisi master aktif memiliki versi APPROVED.**.

### 4. Siapkan storage master

Halaman: **Master terpilih → Storage & record master**. Pelaksana: Platform Admin / Technical Approver.

- Periksa storage plan dan perubahan yang akan diterapkan.
- Centang konfirmasi rencana, lalu tekan Deploy storage.
- Pastikan storage siap untuk versi approved. Pembuatan storage belum memasukkan record.

Hasil sebelum lanjut: **Storage siap, meskipun daftar record masih kosong.**.

### 5. Petakan tab sumber ke field master

Halaman: **Workspace → halaman binding master untuk sumber dan tab terpilih**. Pelaksana: Source Owner / Data Steward / Admin.

- Pilih Master tujuan yang aktif dan memakai versi approved terbaru.
- Pada Mapping terhadap snapshot approved, pilih header sumber untuk setiap field yang diwajibkan, termasuk business key dan label.
- Tinjau transformasi dan kecocokan tipe; header harus cocok dengan profil terbaru.
- Tekan Simpan binding & dry-run. Binding disimpan sebagai DRAFT; tidak ada langkah submit terpisah untuk binding tab.

Hasil sebelum lanjut: **Binding DRAFT tersimpan dan hasil dry-run tersedia.**.

### 6. Periksa dry-run dan setujui binding

Halaman: **Binding master → Dry-run binding tersimpan → Keputusan binding**. Pelaksana: Editor memperbaiki; reviewer berbeda menyetujui.

- Periksa baris valid/bermasalah, error dan Preview data yang sudah disamarkan.
- Jika mapping diubah, tekan Simpan binding & dry-run lagi; preview sebelumnya hanya untuk binding tersimpan.
- Reviewer memeriksa snapshot, versi master dan revisi klasifikasi, mengisi catatan, lalu menekan Setujui binding atau Tolak binding.
- Jika tombol tidak aktif, periksa perubahan belum disimpan, dry-run, reviewer sama pembuat, versi master, klasifikasi dan perubahan sumber.

Hasil sebelum lanjut: **Binding APPROVED dan sesuai versi/snapshot yang diperiksa; record belum dimuat.**.

Panduan utuh: /guide#binding-master atau docs/PANDUAN_BINDING_MASTER.md.
