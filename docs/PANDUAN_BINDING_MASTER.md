# Panduan khusus binding master

Mulai dari Registry master, siapkan storage, hubungkan tab sumber, lalu muat record melalui Batch import. Definisi, binding dan pemuatan adalah persetujuan yang berbeda; binding APPROVED belum berarti record sudah dimuat.

Di aplikasi buka **Panduan penggunaan > Binding master** (`/guide#binding-master`) atau **Bantuan > Panduan khusus binding master**.

## Dua jenis binding

- **Binding tab sumber ke master**: Memuat atau memperbarui record rujukan dari tab MASTER ke master di Registry. Contoh: Tab Master Data berisi daftar bisnis → Master Bisnis.
- **Binding kolom referensi master**: Memvalidasi kode pada tab NON_MASTER terhadap record master yang sudah tersedia. Contoh: Kolom Kode Bisnis pada data marketing → business_code di Master Bisnis.

## Prasyarat

- Sumber Google Sheets sudah terdaftar, bisa dibaca service account sebagai Viewer, discovery dan profiling terbaru berhasil.
- Tab rujukan dikonfirmasi MASTER. Tab transaksi yang memakai rujukan tetap NON_MASTER.
- SOURCE_OWNER, DATA_STEWARD atau PLATFORM_ADMIN menyiapkan definisi dan binding. Reviewer berwenang berbeda pembuat menyetujui definisi, binding dan batch. Deploy storage dilakukan PLATFORM_ADMIN atau TECHNICAL_APPROVER.
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

### 7. Buat batch pemuatan master

Halaman: **Storage & record master → Sumber master terikat**. Pelaksana: Source Owner / Data Steward / Admin.

- Tekan Muat ulang sumber terikat bila tab belum terlihat.
- Cari sumber/tab yang tepat dan pastikan Siap diimpor. Baca blocking_reason jika Belum siap.
- Tekan Buat batch review/import dan pantau proses melalui Batch import atau monitor job.
- Pemuatan MASTER tetap memakai alur batch, bukan jalur sync langsung NON_MASTER.

Hasil sebelum lanjut: **Batch master tersedia untuk pemeriksaan dan keputusan.**.

### 8. Review batch, approve dan Apply

Halaman: **Batch import → batch master yang baru dibuat**. Pelaksana: Editor / steward; reviewer berbeda untuk approval.

- Selesaikan pertanyaan wajib, nilai tidak valid, kandidat record baru dan konflik sesuai policy.
- Jalankan Preview dan periksa record baru/update, konflik, dependency serta dampak pemuatan.
- Reviewer berbeda menyetujui preview yang diperiksa; setelah approval, editor menjalankan Apply.
- Pantau sampai SUCCEEDED dan periksa jumlah record dimuat. Jika data/snapshot berubah, gunakan review terbaru sesuai pesan blocker.

Hasil sebelum lanjut: **Apply sukses; record rujukan benar-benar masuk ke storage master.**.

### 9. Periksa record dan gunakan sebagai rujukan

Halaman: **Storage & record master → Record kanonis**. Pelaksana: Editor / reviewer yang berwenang.

- Cari business key atau label yang baru dimuat; periksa field, status aktif dan jumlah record.
- Untuk dataset NON_MASTER, gunakan Binding kolom referensi master agar kode sumber merujuk record yang tersedia.
- Jika sumber atau definisi master berubah, profiling dan review binding lagi sesuai versi terbaru.

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

1. Pastikan definisi master approved/aktif, storage siap dan record rujukan sudah selesai di-Apply.
2. Di Workspace, pilih tab NON_MASTER yang sudah diprofil, lalu Atur referensi master.
3. Pilih kolom sumber berisi kode, master tujuan dan satu field master yang nilainya sama serta unik. Contoh Kode Bisnis bernilai BIS-001 → business_code bernilai BIS-001.
4. Muat rekomendasi hanya membantu kemiripan nama; cocokkan isi sumber dengan record master sebelum memakai kandidat. UUID internal tidak perlu disalin ke Sheet.
5. Pilih MANY_TO_ONE bila banyak transaksi boleh merujuk satu bisnis. Centang Referensi wajib ada jika semua baris harus memiliki rujukan.
6. Simpan draft binding kolom dan minta reviewer menyetujuinya. Lanjutkan konfigurasi/pemuatan NON_MASTER dengan mapping referensi target UUID yang sesuai.
7. Nilai tidak ditemukan/ambigu dihentikan untuk review. Binding referensi tidak membuat record master baru secara otomatis. Master dengan key gabungan memerlukan satu field kode rujukan unik untuk resolver kolom.

## Jika proses belum bisa dilanjutkan

| Pesan / kondisi | Penyebab | Tindakan |
| --- | --- | --- |
| MASTER_RUNTIME_PENDING pada konfigurasi ETL | Tab MASTER sedang dibuka melalui alur ETL biasa. | Buka Registry master dan binding tab; lanjutkan melalui batch master. |
| MASTER_BINDING_REQUIRED | Tab belum mempunyai binding sumber ke definisi master. | Pilih master approved, petakan field, Simpan binding & dry-run, lalu minta approval. |
| Master tujuan tidak dapat dipilih | Master belum approved, tidak aktif atau versi sudah berubah. | Selesaikan review definisi; pilih versi approved terbaru dari master aktif. |
| Setujui binding tidak aktif | Ada perubahan belum disimpan, dry-run gagal, reviewer sama pembuat, atau snapshot/versi/klasifikasi berubah. | Baca hasil validasi; simpan dry-run terbaru dan gunakan reviewer berbeda yang berwenang. |
| Sumber terikat Belum siap | Binding, storage, metadata atau gate pemuatan belum siap. | Baca blocking_reason; siapkan versi storage/binding serta akses yang diwajibkan, lalu muat ulang sumber terikat. |
| Binding APPROVED tetapi record kosong | Pemetaan sudah disetujui; batch belum selesai di-Apply. | Buat batch review/import, selesaikan temuan, Preview, approval, Apply; cek hasil per batch. |
| is_active menjadi text atau nilai ditolak | Definisi/mapping tipe belum sesuai nilai TRUE/FALSE. | Siapkan boolean sejak definisi awal. Jika storage belum dibuat dan belum pernah dideploy, koreksi definisi melalui review/approval reviewer berbeda. Jika storage sudah ada atau pernah dideploy, perubahan tipe memerlukan migrasi yang direview; jangan hapus/buat ulang tabel. |
| Referensi kode tidak ditemukan atau ambigu | Record master belum dimuat atau field pencarian tidak cocok/unik. | Periksa Record kanonis, tipe/format kode dan field unik; selesaikan review tanpa memilih kecocokan secara diam-diam. |
| Perubahan field / header / versi master | Binding lama mengacu snapshot atau definisi lama. | Profiling ulang bila header berubah; review mapping dan approve binding sesuai versi terbaru. Sebelum storage pertama, koreksi definisi direview. Setelah storage pernah dideploy, field nullable baru perlu approval/redeploy; perubahan tidak kompatibel perlu migrasi khusus. |

## Checklist selesai

- Definisi master aktif dan versi approved jelas.
- Storage siap untuk versi yang disetujui.
- Binding tab APPROVED dan hasil validasi sesuai snapshot terbaru.
- Batch pemuatan sudah SUCCEEDED setelah Apply.
- Record kanonis ditemukan dengan business key / label yang benar.
- Binding kolom referensi dibuat dan disetujui bila dipakai dataset lain.

Master tersimpan sebagai rujukan di Registry, bukan otomatis data product di Katalog data. Periksa record melalui Storage & record master. Dataset NON_MASTER yang menggunakannya memerlukan konfigurasi semantic dan akses tersendiri.
