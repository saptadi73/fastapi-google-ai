---
id: "binding-master-pemuatan"
title: "Binding master: pemuatan record dan troubleshooting"
summary: "Buat batch review/import, Preview, approval, Apply, Record kanonis; MASTER_BINDING_REQUIRED dan tombol tidak aktif."
routes: ["/masters", "/masters/*", "/sources/*", "/guide"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: "docs/PANDUAN_BINDING_MASTER.md"
---
Binding APPROVED belum memuat record. Tab MASTER tidak diproses lewat approval konfigurasi ETL biasa.

### 7. Buat batch pemuatan master

Halaman: **Storage & record master → Sumber master terikat**. Pelaksana: Source Owner / Data Steward / Admin.

- Tekan Muat ulang sumber terikat bila tab belum terlihat.
- Cari sumber/tab yang tepat dan pastikan Siap diimpor. Baca blocking_reason jika Belum siap.
- Tekan Buat batch review/import dan pantau proses melalui Batch import atau monitor job.
- Pemuatan MASTER tetap memakai alur batch, bukan jalur sync langsung NON_MASTER.

Hasil sebelum lanjut: **Batch master tersedia untuk pemeriksaan dan keputusan.**.

### 8. Review batch, approve dan Apply

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

- Definisi master aktif dan versi tervalidasi jelas.
- Storage siap untuk versi yang disetujui.
- Binding tab valid dan hasil validasi sesuai snapshot terbaru.
- Batch pemuatan sudah SUCCEEDED setelah Apply.
- Record kanonis ditemukan dengan business key / label yang benar.
- Binding kolom referensi dibuat dan tervalidasi bila dipakai dataset lain.

Panduan utuh: /guide#binding-master atau docs/PANDUAN_BINDING_MASTER.md.
