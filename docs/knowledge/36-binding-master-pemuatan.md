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

- Definisi master aktif dan versi approved jelas.
- Storage siap untuk versi yang disetujui.
- Binding tab APPROVED dan hasil validasi sesuai snapshot terbaru.
- Batch pemuatan sudah SUCCEEDED setelah Apply.
- Record kanonis ditemukan dengan business key / label yang benar.
- Binding kolom referensi dibuat dan disetujui bila dipakai dataset lain.

Panduan utuh: /guide#binding-master atau docs/PANDUAN_BINDING_MASTER.md.
