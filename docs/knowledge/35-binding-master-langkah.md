---
id: "binding-master-langkah"
title: "Binding master: Registry, storage, dan pemetaan"
summary: "Langkah owner-managed untuk definisi, storage, binding tab MASTER, dan validasi; workflow legacy dapat tetap meminta reviewer."
routes: ["/masters", "/masters/*", "/sources/*", "/guide"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: "docs/PANDUAN_BINDING_MASTER.md"
---
Master menyimpan identitas rujukan yang digunakan berulang. Gunakan Registry master dan Batch import untuk tab MASTER; tab transaksi yang merujuk master tetap NON_MASTER. Owner workflow mengurangi approval rutin, tetapi validasi, snapshot terbaru, business key, dan pemeriksaan konflik tetap wajib.

- **Binding tab sumber ke master**: Memuat atau memperbarui record rujukan dari tab MASTER ke master di Registry. Contoh: Tab Master Data berisi daftar bisnis → Master Bisnis.
- **Binding kolom referensi master**: Memvalidasi kode pada tab NON_MASTER terhadap record master yang sudah tersedia. Contoh: Kolom Kode Bisnis pada data marketing → business_code di Master Bisnis.

- Sumber Google Sheets sudah terdaftar, bisa dibaca service account sebagai Viewer, discovery dan profiling terbaru berhasil.
- Tab rujukan dikonfirmasi MASTER. Tab transaksi yang memakai rujukan tetap NON_MASTER.
- SOURCE_OWNER, DATA_STEWARD atau PLATFORM_ADMIN menyiapkan definisi dan binding. Jika ETL_OWNER_WORKFLOW_ENABLED aktif, owner/steward menyelesaikan validasi tanpa approval rutin kedua. Workflow legacy tetap dapat meminta reviewer.
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

### 3. Validasi dan sahkan definisi

Halaman: **Halaman definisi master**. Pelaksana: Source Owner / Data Steward pada owner workflow; reviewer pada workflow legacy.

- Simpan definisi dan jalankan tindakan validasi yang tersedia.
- Owner workflow memeriksa schema, business key, label, sensitivitas, policy dan authority sebelum mengesahkan revisi; tidak ada inbox approval rutin kedua.
- Workflow legacy masih mengirim definisi untuk keputusan reviewer. Gunakan master aktif dengan versi yang sudah disahkan.
- Koreksi field wajib, key atau tipe setelah storage dibuat dapat memerlukan migrasi khusus; baca storage plan dan blocker sebelum melanjutkan.

Hasil sebelum lanjut: **Definisi master aktif memiliki versi tervalidasi yang dapat dipakai untuk binding.**.

### 4. Siapkan storage master

Halaman: **Master terpilih → Storage & record master**. Pelaksana: Source Owner / Data Steward pada owner workflow; role legacy sesuai kebijakan.

- Periksa storage plan dan perubahan yang akan diterapkan.
- Centang konfirmasi rencana, lalu tekan Deploy storage.
- Pastikan storage siap untuk versi definisi aktif. Pembuatan storage belum memasukkan record.

Hasil sebelum lanjut: **Storage siap, meskipun daftar record masih kosong.**.

### 5. Petakan tab sumber ke field master

Halaman: **Workspace → halaman binding master untuk sumber dan tab terpilih**. Pelaksana: Source Owner / Data Steward / Admin.

- Pilih Master tujuan yang aktif dan memakai versi tervalidasi terbaru.
- Pada Mapping terhadap snapshot terkini, pilih header sumber untuk setiap field yang diwajibkan, termasuk business key dan label.
- Tinjau transformasi dan kecocokan tipe; header harus cocok dengan profil terbaru.
- Tekan Simpan binding & dry-run. Owner workflow menyimpan binding setelah validasi; workflow legacy dapat menyimpan DRAFT untuk diperiksa reviewer.

Hasil sebelum lanjut: **Binding tersimpan dan hasil validasi terhadap snapshot tersedia.**.

### 6. Periksa hasil validasi binding

Halaman: **Binding master → Dry-run binding tersimpan → Keputusan binding**. Pelaksana: Source Owner / Data Steward pada owner workflow; reviewer pada workflow legacy.

- Periksa baris valid/bermasalah, error dan Preview data yang sudah disamarkan.
- Jika mapping diubah, tekan Simpan binding & dry-run lagi; preview sebelumnya hanya untuk binding tersimpan.
- Owner workflow dapat lanjut jika binding, klasifikasi, versi master dan snapshot lolos validasi. Legacy memakai keputusan reviewer.
- Jika belum siap, periksa perubahan belum disimpan, hasil dry-run, versi master, klasifikasi dan perubahan sumber.

Hasil sebelum lanjut: **Binding valid dan sesuai versi/snapshot yang diperiksa; record belum dimuat.**.

Panduan utuh: /guide#binding-master atau docs/PANDUAN_BINDING_MASTER.md.
