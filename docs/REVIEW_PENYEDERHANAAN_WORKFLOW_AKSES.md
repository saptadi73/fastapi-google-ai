# Review menyeluruh workflow dan akses

Tanggal: 12 Oktober 2026.

Status: hasil pemeriksaan kode dan rancangan perombakan; belum merupakan perilaku runtime yang sudah diterapkan. Dokumen ini tidak menggantikan panduan operasional saat ini sampai implementasi, pengujian dan rollout selesai.

## Tujuan dan keputusan pengguna

Pengguna meminta penghapusan kebutuhan approver, penyederhanaan access policy, serta pengurangan langkah dan pergantian akun. Targetnya satu pengelola dapat menyelesaikan setup dan pemuatan sumber dari awal sampai selesai. Pengguna memilih akses baca otomatis bagi pengguna aktif dalam unit bisnis yang sama. Akses lintas unit bukan default.

Persetujuan orang kedua tidak diperlukan dalam alur target. Validasi, preview, pemeriksaan izin, transaksi dan audit menjadi mekanisme kontrol utama. Memilih hak akses merupakan tindakan pemilik/pengelola sumber, bukan pengajuan policy untuk approver.

## Temuan pada implementasi saat ini

| Area | Implementasi yang ditemukan | Dampak | Perubahan target |
| --- | --- | --- | --- |
| Definisi master | `MasterService.action`: simpan, submit-review, approve; role editor/reviewer dan pemisahan pembuat/pengaju | Pergantian akun sebelum versi dapat dipakai | Simpan draft lalu aktivasi definisi yang valid oleh pengelola |
| Storage master | `MasterStorageService.deploy`: REVIEW_ROLES; UI halaman terpisah | Pengguna harus kembali setelah definisi selesai | Siapkan storage sebagai tahapan setup yang dilacak otomatis |
| Binding tab/kolom master | `save_binding`/`binding_decision` dan `column_binding_decision`: DRAFT lalu APPROVED | Definisi sudah sah tetapi mapping tetap menunggu approval | Simpan dan validasi binding ke versi aktif; tidak ada reviewer |
| Konfigurasi ETL | `submit_review`, `decision`, `deploy`: bukti review, reviewer, assignment, artifact dan deploy terpisah | Banyak langkah dan status, perubahan sumber membuat review berulang | Validasi dan preview menghasilkan rencana eksekusi; pengelola menjalankan langsung |
| Metadata akses sumber | `SourceService` mempunyai review metadata dan aktivasi policy terpisah | Pengisian metadata memicu pekerjaan akses berlapis | Pilih unit bisnis sumber sekali; akses unit berlaku langsung setelah validasi |
| Access policy | `AccessService.transition_policy`: DRAFT, IN_REVIEW, APPROVED, pembuat harus berbeda | Berbagi data memerlukan alur approval tambahan | Pengaturan akses langsung: unit, pengguna/grup tambahan, hak operasi |
| Persetujuan tayang | `require_release_ready`: IT dan kelompok unit harus lengkap bila release policy terpasang | Approval konfigurasi belum cukup untuk deploy | Hapus gate persetujuan IT/unit pada alur target; riwayat tetap tersimpan |
| Batch master/import | `ImportReviewService.approve`: REVIEW_ROLES, assignment sumber, reviewer lain; `apply` memerlukan hasil approval | Editor preview, approver approve, editor apply | Preview lalu Jalankan pemuatan oleh pengelola yang sama |
| Taxonomy/versi/binding | Endpoint reviewer dan pemeriksaan editor terpisah | Koreksi referensi memicu pergantian akun | Simpan/aktifkan hasil validasi dengan versi dan audit |
| Formula/action plan | `AnalyticsRulesService.decide`: assignment reviewer, self-approval selalu ditolak | Aturan bisnis tidak dapat dipakai langsung oleh pengelola | Preview dan aktifkan aturan valid; evaluasi tetap memeriksa akses dan versi |
| Join semantic | Endpoint approve join terpisah | Setup hubungan data membutuhkan langkah tambahan | Pengelola yang berhak atas kedua sumber dapat mengaktifkan join valid |
| Temuan AI | Setiap VALUE_ISSUE AI menghasilkan pertanyaan wajib/AI_REVIEW_ISSUES | Singkatan sah menghentikan batch meskipun seluruh baris lolos validasi | Saran penamaan/istilah menjadi peringatan; ambiguitas identitas dan konflik data tetap blocker |
| Status UI | Ringkasan sumber mencampur konfigurasi/tab dan status import | MASTER siap tetapi sumber terlihat IN_PROGRESS/PENDING_IT_APPROVAL | Kesiapan ditampilkan per tab, dengan satu langkah berikutnya yang tepat |
| Hasil master | Master memiliki storage/record kanonis, berbeda dari data product NON_MASTER | Pengguna mengira master harus ada dalam katalog analitik biasa | Jelaskan output dan berikan tautan record master/produk data yang terkait |

### Mengapa satu perubahan konfigurasi tidak menyelesaikan masalah

`REQUIRE_SEPARATE_APPROVER=false` hanya mematikan sebagian pengecekan identitas reviewer. Pembatasan endpoint REVIEW_ROLES, assignment approver sumber, release policy, status APPROVED, pemeriksaan frontend dan beberapa konflik editor tetap berjalan. Analytics rules dan policy akses memiliki konflik pembuat yang tidak bergantung pada flag ini. Menggabungkan seluruh role editor ke REVIEW_ROLES juga tidak cukup: pergantian status, submit dan tombol approval tetap ada, dan perluasan role akan membuka operasi lain yang tidak diminta.

## Alur target untuk pengguna

### Sumber dan ETL biasa

1. Tambahkan Google Sheet dan pilih unit bisnis. Sistem melakukan discovery/profiling serta menawarkan klasifikasi tab.
2. Periksa mapping, key, tipe, periode, semantic dan aturan kualitas pada satu workspace. Simpan draft kapan saja.
3. Klik **Validasi & preview**. Tampilkan jumlah record, perubahan struktur, contoh hasil konversi, konflik dan output yang akan dibuat.
4. Jika tidak ada blocker, klik **Jalankan**. Backend mengaktifkan versi, menyiapkan tabel/view dan memuat data lewat job yang terpantau. Tahapan ini bukan transaksi tunggal lintas semua job; setiap tahap memiliki transaksi sendiri, checkpoint dan retry aman.
5. Tampilkan hasil: data dimuat, jumlah baris aktual, produk di katalog dan siapa yang dapat mengaksesnya.

Sync rutin dengan konfigurasi aktif berjalan langsung jika data lolos validasi. Konfigurasi tidak dibuat ulang hanya karena nilai sumber berubah. Struktur/key/aturan yang berubah memerlukan preview baru; tidak memerlukan orang kedua.

### Tab MASTER

1. Pilih atau buat definisi master dan periksa business key serta label.
2. Periksa mapping terhadap versi aktif. Definisi dan binding disimpan sebagai draft sampai validasi berhasil.
3. Klik **Validasi & preview**. Bila storage belum ada, tampilkan rencana pembuatan bersama rencana record.
4. Klik **Jalankan**. Sistem mengaktifkan versi, menyiapkan storage yang kompatibel, mengaktifkan binding dan memuat record. Kegagalan tahap tertentu ditampilkan pada workspace yang sama; tahap sukses sebelumnya tidak digambarkan sebagai rollback keseluruhan.
5. Tampilkan **Record master**, jumlah INSERT/UPDATE/UNCHANGED dan referensi yang tersedia untuk dataset lain.

Pemilihan versi aktif menampilkan nomor yang sama pada dropdown, ringkasan binding dan payload tersimpan. Perubahan versi menampilkan perbandingan mapping; jangan mengosongkan mapping lama yang masih cocok secara otomatis.

### Formula, action plan dan taxonomy

Simpan draft, lakukan validasi/preview, lalu aktifkan. Pengelola tidak perlu submit review atau berpindah akun. Formula tetap memakai parser terbatas, angka presisi, pembuktian semantic/periode dan data yang boleh dibaca. Action plan tetap usulan dengan bukti; menjalankan tindakan bisnis di luar aplikasi bukan akibat otomatis aktivasi formula.

## Akses sederhana: otomatis dalam unit bisnis yang sama

### Model izin

| Hak | Penerima default | Kewenangan |
| --- | --- | --- |
| Baca dan analitik | Pengguna aktif dengan keanggotaan aktif pada business domain **dan** unit pemilik sumber, tenant sama | Lihat katalog, baca data yang diizinkan, chart, query, analitik/action plan |
| Kelola sumber | Pemilik/pengelola sumber yang tercatat | Edit setup, aktivasi, sync/import, pengaturan akses sumber |
| Kelola platform | Admin tenant | Kelola akun/unit, pemilik sumber, pemulihan dan konfigurasi platform |
| Ekspor | Izin tersendiri | Unduh data; hak baca tidak otomatis berarti hak ekspor |
| Akses lintas unit | Pengguna/grup yang dipilih pemilik/pengelola atau admin | Baca atau kelola sesuai hak eksplisit; tidak ada approval policy |

Keanggotaan domain dan unit adalah pemberian hak oleh admin, bukan hasil membaca kolom `bisnis` atau klaim pengguna sendiri. Kesamaan tenant saja tidak memberi akses. Default memerlukan kecocokan kedua atribut tersebut. Pemilik dapat memakai yurisdiksi/department sebagai pembatas tambahan atau memilih beberapa grup tambahan; hak kelola tetap eksplisit dan anggota unit biasa tidak dapat mengganti business key, memuat data atau membagikan ulang sumber.

Sumber baru wajib mempunyai unit bisnis. Sumber lama yang belum memiliki unit tetap ditandai perlu penetapan unit; jangan menebak dari nama file/tab atau menyebarkan akses seluruh tenant. Unit sumber yang sudah valid dapat dimigrasikan dari `owner_unit_id`; tampilkan hasil pemetaan.

UI **Akses data** cukup menampilkan unit default, pengelola, pengguna/grup tambahan dan hak ekspor. Domain bisnis, yurisdiksi dan PIC menjadi metadata pendukung, bukan prasyarat pembacaan biasa. Pembatasan khusus baris/kolom tetap tersedia pada konfigurasi lanjutan untuk sumber yang membutuhkannya.

### Konsistensi seluruh jalur baca

Pengecekan yang sama wajib digunakan oleh katalog, records, query SQL terkontrol, chat, dashboard, hasil cache, export, formula, join dan resolver referensi. Pencabutan keanggotaan/akses langsung memengaruhi request berikutnya dan cache berdasarkan revisi akses. Hak mengelola konfigurasi platform tidak otomatis menyingkap kolom sensitif.

Explicit DENY, batas baris, masking/hide kolom, masa berlaku dan kontrol ekspor lama tidak boleh hilang diam-diam saat migrasi. Tampilkan pembatasan khusus yang masih berlaku. Aturan akses lama tidak dipakai lagi sebagai gate approval, tetapi kontrol data yang sah tetap dipertahankan sampai dikonversi.

## Kontrol otomatis yang tetap diperlukan

- Tenant, akun aktif, kepemilikan/pemberian hak kelola dan keanggotaan unit diperiksa di backend, termasuk worker yang menjalankan perintah pengguna.
- Header kosong/duplikat, tipe tidak valid, business key duplikat, nilai wajib kosong, referensi ambigu dan konflik periode tetap menghentikan pemuatan.
- Konversi tanggal dari angka tetap memerlukan format eksplisit dan bukti hasil. Menghapus approver tidak membenarkan tebakan serial Sheets.
- DDL tetap menjaga data, dependency dan izin akses; migrasi destruktif yang belum didukung tetap ditolak dengan alasan tindakan yang jelas.
- Rencana eksekusi mengikat revision konfigurasi, hash schema/staging/dependency, target dan izin pengguna. Perubahan setelah preview menghasilkan perbandingan baru di halaman yang sama.
- Apply memeriksa ulang target dan hak akses setelah memperoleh lock, menggunakan idempotency key, transaksi per tahap dan checkpoint. Klik ganda, retry atau dua pengelola serentak tidak menulis dua kali.
- Audit mencatat actor nyata, versi, alasan koreksi, hash rencana dan hasil. Aktivasi oleh pengelola tidak dicatat sebagai persetujuan reviewer lain.
- Temuan AI nonteknis seperti kepanjangan singkatan menjadi saran, bukan blocker. Ketidakjelasan yang menentukan identitas/key/referensi tetap harus diselesaikan.

## Kontrak dan status target

Untuk UI gunakan **Draft → Perlu perbaikan / Siap dijalankan → Memproses → Selesai / Gagal**. Kesiapan struktur, validasi data dan ketersediaan akses dibedakan; status seluruh sumber tidak menggantikan status tab.

Gunakan satu layanan otorisasi per resource dengan tindakan `read`, `manage`, `share`, `export`. Layanan workflow menghasilkan receipt/rencana tervalidasi yang dapat dijalankan pengelola. Hindari frontend memanggil approve milik pengguna sendiri secara tersembunyi: ini masih mewarisi gate/semantik reviewer dan mudah gagal sebagian.

Endpoint lama dapat dipertahankan selama transisi untuk klien lama, tetapi wajib memakai pengecekan hak baru yang sama. Pemetaan status internal APPROVED sebagai kompatibilitas harus eksplisit; status/kolom audit lama tidak dihapus atau ditulis ulang. Endpoint submit/approve lama diberi keterangan deprecated setelah API baru siap.

Role TECHNICAL_APPROVER yang ada tidak otomatis diberi hak mengubah semua sumber. Admin memetakan pengguna tersebut menjadi pengelola untuk sumber/unit yang sesuai. Role ini tidak lagi menjadi prasyarat proses, dan tidak perlu menciptakan akun kedua.

## Rencana implementasi

| Paket | Pekerjaan wajib | Bukti selesai |
| --- | --- | --- |
| Otorisasi | Resource grants/pemilik, unit default, hak kelola terpusat, query/cache/export konsisten | Tes lintas unit/tenant, pencabutan akses dan masking lulus |
| Migrasi kompatibilitas | Backfill unit/pemilik valid, pertahankan audit dan kontrol khusus, tandai sumber belum jelas | Laporan dry-run per sumber; tidak ada akses baru ke tenant/unit lain |
| Aktivasi | Ganti gate approver pada konfigurasi, master, binding, taxonomy, join dan analytics rules | Satu pengelola dapat mengaktifkan versi valid; pengguna baca ditolak |
| Orkestrasi | Setup/storage/import menjadi tahapan satu operasi, idempotency/retry dan progress | Gagal tahap menampilkan checkpoint benar; retry tidak menggandakan data |
| Pemuatan | Preview dan Jalankan tanpa endpoint approval manusia wajib | MASTER/NON_MASTER, konflik, stale dan concurrency lulus |
| Frontend | Workspace per tab, satu CTA berikutnya, Akses data sederhana, role/capability server | Skenario lengkap tanpa logout/ganti akun, keyboard dan error jelas |
| Pengetahuan | Panduan ETL/master, KB, helper, tabel error, API reference, templates dan PPT | Tidak ada petunjuk aktif yang meminta approver/gate lama pada mode baru |
| Rollout | Backup DB, migration dry-run, staging test, deploy backend/worker/frontend sesuai kontrak | Verifikasi production memakai resource uji; rollback akses/workflow terdokumentasi |

Frontend perlu menerima capability dari backend untuk resource yang sedang dibuka, bukan hanya array `editRoles`/`reviewRoles`. Role global tetap relevan untuk administrasi, tetapi tidak cukup menentukan siapa yang dapat mengelola satu sumber.

## Skenario penerimaan wajib

1. Pemilik sumber menyelesaikan setup NON_MASTER sampai produk/record tersedia tanpa akun kedua.
2. Pemilik menyelesaikan definisi MASTER, storage, binding, preview dan pemuatan tanpa akun kedua.
3. Anggota unit yang sama dapat melihat hasil dengan hak baca; tidak bisa mengubah setup atau membagikan ulang.
4. Unit berbeda, tenant berbeda, pengguna nonaktif dan membership kedaluwarsa tidak mendapat data.
5. Ekspor dan kolom sensitif tetap sesuai hak eksplisit, termasuk chat, formula dan cache.
6. Pencabutan izin sebelum job/Apply membatalkan eksekusi yang belum berhak, tanpa mengandalkan tombol UI.
7. LKMS/BSP yang lolos validasi menjadi warning; key duplikat/konversi tanggal gagal/referensi ambigu tetap blocker.
8. Perubahan target/schema/staging setelah preview menampilkan perubahan dan meminta preview baru; tidak meminta approval orang lain.
9. Klik ganda, dua pengelola, rollback dan retry menjaga idempotency, data lama serta audit.
10. Batch DRAFT/NEEDS_INPUT/READY_FOR_APPROVAL/APPROVED lama mempunyai jalur lanjut yang sah tanpa memalsukan riwayat persetujuan.
11. Sumber tanpa unit, dengan DENY atau kontrol khusus tidak dibuka lebih luas hanya karena migrasi.
12. Rumus/action plan/taxonomy/join dapat diaktifkan pengelola, tetapi tidak melewati akses produk, validasi versi atau pembatasan query.

## Batas pemeriksaan ini

Review berdasarkan kode backend/frontend dan rangkaian masalah production yang sudah diverifikasi. Dokumen ini bukan bukti perubahan runtime. Tidak ada flag production, hak pengguna, approval lama, record master atau policy yang diubah untuk menyelesaikan review. Implementasi harus menguji jalur di atas sebelum menyatakan aplikasi bebas approver.
