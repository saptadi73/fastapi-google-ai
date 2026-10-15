# Panduan khusus binding master

Master menyimpan identitas rujukan yang digunakan berulang. Gunakan Registry master dan Batch import untuk tab MASTER; tab transaksi yang merujuk master tetap NON_MASTER. Owner workflow mengurangi approval rutin, tetapi validasi, snapshot terbaru, business key, dan pemeriksaan konflik tetap wajib.

Di aplikasi buka **Panduan penggunaan > Binding master** (`/guide#binding-master`) atau **Bantuan > Panduan khusus binding master**.

## Dua jenis binding

- **Binding tab sumber ke master**: Memuat atau memperbarui record rujukan dari tab MASTER ke master di Registry. Contoh: Tab Master Data berisi daftar bisnis → Master Bisnis.
- **Binding kolom referensi master**: Memvalidasi kode pada tab NON_MASTER terhadap record master yang sudah tersedia. Contoh: Kolom Kode Bisnis pada data marketing → business_code di Master Bisnis.

## Prasyarat

- Sumber Google Sheets sudah terdaftar, bisa dibaca service account sebagai Viewer, discovery dan profiling terbaru berhasil.
- Tab rujukan dikonfirmasi MASTER. Tab transaksi yang memakai rujukan tetap NON_MASTER.
- SOURCE_OWNER, DATA_STEWARD atau PLATFORM_ADMIN menyiapkan definisi dan binding. Jika ETL_OWNER_WORKFLOW_ENABLED aktif, owner/steward menyelesaikan validasi tanpa approval rutin kedua. Workflow legacy tetap dapat meminta reviewer.
- Gunakan master yang sudah ada jika identitas dan arti bisnisnya sesuai. Jangan membuat master duplikat hanya karena sumbernya berbeda.
- Akses sumber, assignment, policy dan gate lain yang diwajibkan tetap dipenuhi; klasifikasi MASTER atau approval binding tidak memberikan izin baca otomatis.

## Langkah dari Registry sampai pemuatan record

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

- Simpan definisi dan jalankan tindakan validasi/pengajuan yang tersedia.
- Owner workflow memeriksa schema, business key, label, sensitivitas, policy dan authority sebelum mengesahkan revisi; tidak ada inbox approval rutin kedua.
- Workflow legacy masih mengirim definisi untuk keputusan reviewer. Gunakan master aktif dengan versi yang sudah disahkan.
- Koreksi field wajib, key atau tipe setelah storage dibuat dapat memerlukan migrasi khusus; baca storage plan dan blocker sebelum melanjutkan.

Hasil sebelum lanjut: **Definisi master aktif memiliki versi yang tervalidasi dan dapat dipakai untuk binding.**.

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

### 7. Buat batch pemuatan master

Halaman: **Storage & record master → Sumber master terikat**. Pelaksana: Source Owner / Data Steward / Admin.

- Tekan Muat ulang sumber terikat bila tab belum terlihat.
- Cari sumber/tab yang tepat dan pastikan Siap diimpor. Baca blocking_reason jika Belum siap.
- Tekan Buat batch review/import dan pantau proses melalui Batch import atau monitor job.
- Pemuatan MASTER tetap memakai alur batch, bukan jalur sync langsung NON_MASTER.

Hasil sebelum lanjut: **Batch master tersedia untuk pemeriksaan dan keputusan.**.

### 8. Validasi batch dan Apply

Halaman: **Batch import → batch master yang baru dibuat**. Pelaksana: Source Owner / Data Steward pada owner workflow; reviewer pada workflow legacy.

- Selesaikan pertanyaan wajib, nilai tidak valid, kandidat record baru dan konflik sesuai policy.
- Jalankan Preview dan periksa record baru/update, konflik, dependency serta dampak pemuatan.
- Owner workflow dapat Apply setelah validasi, preview terbaru, dan konfirmasi konflik yang diwajibkan; legacy mengikuti approval batch yang berlaku.
- Pantau sampai SUCCEEDED dan periksa jumlah record dimuat. Jika data/snapshot berubah, gunakan review terbaru sesuai pesan blocker.

Hasil sebelum lanjut: **Apply sukses; record rujukan benar-benar masuk ke storage master.**.

### 9. Periksa record dan gunakan sebagai rujukan

Halaman: **Storage & record master → Record kanonis**. Pelaksana: Source Owner / Data Steward / pengguna dengan akses baca.

- Cari business key atau label yang baru dimuat; periksa field, status aktif dan jumlah record.
- Untuk dataset NON_MASTER, gunakan Binding kolom referensi master agar kode sumber merujuk record yang tersedia.
- Jika sumber atau definisi master berubah, profiling ulang dan periksa binding terhadap versi terbaru.

Hasil sebelum lanjut: **Record kanonis dapat ditemukan dan digunakan sebagai referensi yang disetujui.**.

## Contoh mapping Master Bisnis

Contoh fiktif yang disarankan: Sheet mempunyai Kode Bisnis, Nama Bisnis dan is_active. Kode disimpan sebagai text agar nol depan tetap utuh. Sesuaikan header dengan Sheet nyata.

| Header sumber | Field master | Tipe | Aturan | Contoh |
| --- | --- | --- | --- | --- |
| Kode Bisnis | business_code | text | Wajib, unik, stabil; business key | BIS-001 |
| Nama Bisnis | business_name | text | Wajib; field label | Unit Contoh |
| is_active | is_active | boolean | Isi sesuai status sebenarnya | TRUE |

Jika Sheet saat ini hanya memiliki BISNIS dan is_active, petakan BISNIS ke field nama bisnis yang sesuai. Menggunakannya sebagai business key hanya layak jika nilainya unik, stabil dan tidak kosong. Jika nama dapat berubah, tambahkan kode bisnis stabil di Google Sheets, profiling ulang, lalu review definisi/binding; jangan membuat kode atau memetakan header yang belum ada.

## Binding kolom referensi pada NON_MASTER

1. Pastikan definisi master aktif/tervalidasi, storage siap dan record rujukan sudah selesai di-Apply.
2. Di Workspace, pilih tab NON_MASTER yang sudah diprofil, lalu Atur referensi master.
3. Pilih kolom sumber berisi kode, master tujuan dan satu field master yang nilainya sama serta unik. Contoh Kode Bisnis bernilai BIS-001 → business_code bernilai BIS-001.
4. Muat rekomendasi hanya membantu kemiripan nama; cocokkan isi sumber dengan record master sebelum memakai kandidat. UUID internal tidak perlu disalin ke Sheet.
5. Pilih MANY_TO_ONE bila banyak transaksi boleh merujuk satu bisnis. Centang Referensi wajib ada jika semua baris harus memiliki rujukan.
6. Simpan binding kolom dan periksa validasinya. Owner workflow tidak memerlukan approval rutin kedua; legacy mengikuti review yang ditampilkan. Lanjutkan konfigurasi/pemuatan NON_MASTER dengan target referensi yang sesuai.
7. Nilai tidak ditemukan/ambigu dihentikan untuk review. Binding referensi tidak membuat record master baru secara otomatis. Master dengan key gabungan memerlukan satu field kode rujukan unik untuk resolver kolom.

Konfigurasi ETL non-master menerima `master_reference` langsung pada mapping kolom. Di Workspace ETL, langkah Kolom menyediakan pilihan master, field kode/nama untuk pencocokan, kardinalitas, dan apakah relasi wajib. Isi Sheet serta kolom target tetap text/varchar: misalnya BISNIS berisi BSP atau BISNIS_CODE berisi BC06. Aplikasi mencari record aktif secara otomatis dan menyimpan identitasnya pada kolom internal terpisah; pengguna tidak perlu mengetik atau mencari UUID. Preview dan analitik tetap menampilkan kode/nama sumber. Nilai tidak ditemukan/ambigu, field sensitif tanpa izin, dan pelanggaran satu-ke-satu ditolak sebelum pemuatan. Binding tab lama yang identik digunakan sebagai relasi yang sama; aturan yang berbeda harus disamakan, bukan dipilih diam-diam. Konfigurasi UUID lama tetap kompatibel. Penambahan relasi tidak menebak isi record historis: kolom internal baru nullable; record lama belum memiliki referensi sampai diproses ulang melalui strategi yang sesuai.

## Jika proses belum bisa dilanjutkan

| Pesan / kondisi | Penyebab | Tindakan |
| --- | --- | --- |
| MASTER_RUNTIME_PENDING pada konfigurasi ETL | Tab MASTER sedang dibuka melalui alur ETL biasa. | Blocker ini hanya untuk konfigurasi/sync ETL biasa. Buka Registry master, pastikan binding dan storage siap, lalu lanjutkan lewat Batch Import master. Owner workflow Apply setelah preview bersih; legacy mengikuti review yang ditampilkan. |
| MASTER_BINDING_REQUIRED | Tab belum mempunyai binding sumber ke definisi master. | Pilih master aktif/tervalidasi, petakan field, Simpan binding & dry-run. Owner workflow lanjut setelah validasi; legacy mengikuti review yang ditampilkan. |
| Master tujuan tidak dapat dipilih | Master belum disahkan, tidak aktif atau versi sudah berubah. | Pada owner workflow, selesaikan validasi definisi; pada legacy, selesaikan review. Pilih versi terbaru dari master aktif. |
| Binding belum siap | Ada perubahan belum disimpan, dry-run gagal, atau snapshot/versi/klasifikasi berubah. | Baca hasil validasi dan simpan ulang binding terhadap snapshot terbaru. Legacy juga memerlukan reviewer berbeda yang berwenang. |
| Sumber terikat Belum siap | Binding, storage, metadata atau gate pemuatan belum siap. | Baca blocking_reason; siapkan versi storage/binding serta akses yang diwajibkan, lalu muat ulang sumber terikat. |
| Binding APPROVED tetapi record kosong | Pemetaan sudah valid; batch belum selesai di-Apply. | Buat batch import, selesaikan temuan, jalankan Preview lalu Apply. Owner workflow tidak memakai approval batch rutin; legacy mengikuti approval yang berlaku. Cek hasil per batch. |
| is_active menjadi text atau nilai ditolak | Definisi/mapping tipe belum sesuai nilai TRUE/FALSE. | Siapkan boolean sejak definisi awal. Jika storage belum dibuat, koreksi lalu validasi definisi. Jika storage sudah ada atau pernah dideploy, perubahan tipe memerlukan migrasi khusus; baca blocker dan jangan hapus/buat ulang tabel. |
| Referensi kode tidak ditemukan atau ambigu | Record master belum dimuat atau field pencarian tidak cocok/unik. | Periksa Record kanonis, tipe/format kode dan field unik; selesaikan review tanpa memilih kecocokan secara diam-diam. |
| Perubahan field / header / versi master | Binding lama mengacu snapshot atau definisi lama. | Profiling ulang bila header berubah; validasi ulang mapping sesuai versi terbaru. Sebelum storage pertama, koreksi definisi lalu validasi. Setelah storage pernah dideploy, perubahan schema harus mengikuti storage plan dan migrasi yang tersedia; perubahan tidak kompatibel perlu penanganan khusus. |

## Checklist selesai

- Definisi master aktif dan versi tervalidasi jelas.
- Storage siap untuk versi yang disetujui.
- Binding tab valid dan hasil validasi sesuai snapshot terbaru.
- Batch pemuatan sudah SUCCEEDED setelah Apply.
- Record kanonis ditemukan dengan business key / label yang benar.
- Binding kolom referensi dibuat dan tervalidasi bila dipakai dataset lain.

Master tersimpan sebagai rujukan di Registry, bukan otomatis data product di Katalog data. Periksa record melalui Storage & record master. Dataset NON_MASTER yang menggunakannya memerlukan konfigurasi semantic dan akses tersendiri.
