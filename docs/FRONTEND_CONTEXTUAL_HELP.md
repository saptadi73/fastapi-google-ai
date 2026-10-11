# Bantuan kontekstual frontend

Frontend menyediakan tombol **Bantuan** tetap pada setiap route, termasuk halaman login. Tombol
membuka dialog yang menjelaskan fungsi halaman, urutan penggunaan, dan catatan yang perlu
diperhatikan. Isi mengikuti `route.path`, sehingga navigasi ke halaman lain langsung mengganti
petunjuk tanpa memuat ulang aplikasi.

Pada halaman Taxonomy, Administrasi, Workspace ETL, Master, binding taxonomy, Dashboard,
Chat data, dan Permintaan akses, dialog juga menampilkan **Contoh pengisian** yang fiktif.
Contohnya meliputi `jenis_biaya`, `jatim`, metadata sumber, business key master, dan
pertanyaan bahasa alami. Konten ini mengikuti [contoh pengisian aplikasi](CONTOH_ISIAN_APLIKASI.md)
dan tetap dapat dibaca tanpa memanggil AI.

Bantuan Administrasi juga menerangkan pilihan multi-unit eksplisit dan reviewer per sumber.
Unit induk tidak otomatis membuka unit bawahan. Reviewer metadata, konfigurasi, dan import
ditunjuk terpisah; penunjukan tidak memberi hak membaca data.

Bantuan Workspace menerangkan mengapa dropdown unit, domain bisnis, dan yurisdiksi bisa
kosong: hanya assignment aktif akun pendaftar yang muncul. Form menampilkan keadaan
assignment kosong, kegagalan request, dan tombol **Muat ulang pilihan** secara terpisah.
Admin lain perlu memberikan assignment melalui Administrasi → Pengguna; atribut registry
tidak otomatis menjadi assignment.

Panduan Workspace/review, sumber, master, katalog/dashboard, serta topik periode harus
membedakan isi Sheet dari konfigurasi ETL: kolom sumber ditambah di Google Sheets,
profiling ulang pada sumber yang sama, dan draft versi baru sebelum review/deploy.
Approval form tidak memigrasikan schema target non-master yang sudah ada. Field master
nullable memakai approval definisi dan deploy-storage ulang; perubahan yang tidak kompatibel
memerlukan migrasi khusus. Label bulan/minggu tanpa tahun bukan tanggal transaksi.
Tanggal kejadian dan batas rekap periode harus dijelaskan terpisah dengan kalender bisnis
yang eksplisit. Detail: [perubahan sumber dan periode](PANDUAN_REVIEW_ETL.md#perubahan-sumber-kolom-dan-periode-waktu).

Bantuan **Persetujuan tayang** menjelaskan keputusan IT dan setiap unit terkait untuk
revisi konfigurasi approved. Administrasi menyediakan pilihan akun/unit bernama;
halaman approver menampilkan status, ringkasan data, dan catatan sebelum keputusan.
Contoh yang ditampilkan: IT, Penjualan Malang, dan Keuangan masing-masing menyetujui
revisi yang sama dengan akun berbeda. IT wajib melengkapi checklist skema/mapping,
kualitas, dan keamanan/akses. Bantuan review ETL mengingatkan editor untuk memeriksa
status seluruh kelompok sebelum deploy/rollback; penolakan meminta revisi atau
peninjauan aturan, dan review batch import tetap terpisah.

Dialog menyediakan tautan **Panduan lengkap** ke `/guide`. Halaman ini memuat workflow 10 tahap dari
administrasi dan pendaftaran Google Sheet sampai batch berhasil, dashboard, serta chart. Versi
dokumentasinya tersedia di [panduan pengguna awal sampai akhir](USER_GUIDE_END_TO_END.md). Panduan
dapat dibuka sebelum login; tautan ke modul operasional tetap meminta autentikasi dan role yang sesuai.

Setelah login, tombol **Tanya AI** tersedia di atas tombol Bantuan. Panel ini menerima pertanyaan
bebas, menyertakan route aktif sebagai konteks, dan menampilkan sumber knowledge base serta saran
pertanyaan lanjutan. Riwayat hanya disimpan dalam memori browser dan dibersihkan ketika sesi berakhir.
Frontend tidak mengirim isi halaman, role, tenant, token, atau riwayat percakapan ke endpoint bantuan.
Rincian integrasi tersedia di `docs/AI_USER_HELP.md` pada repository frontend.

## Cakupan

Bantuan khusus tersedia untuk:

- login, beranda, dashboard NL2SQL/query builder, dan Chat data;
- Workspace ETL dan review konfigurasi;
- registry, definisi, storage, source binding, reference binding, dan taxonomy binding master;
- registry taxonomy dan semantic/AI governance;
- daftar serta detail batch import;
- job/schedule, kualitas/karantina, dan operasi retry;
- administrasi tenant, pengguna, registrasi akun, akun sendiri, access request, dan Persetujuan tayang.

Route detail menggunakan pola path dan tidak menampilkan UUID kepada pengguna. Route baru yang belum
memiliki entri tetap mendapat bantuan fallback yang menyarankan pengguna membaca status, melengkapi
field wajib, meninjau tindakan sensitif, dan menghubungi administrator atau data steward.

## Perilaku dan aksesibilitas

- tombol selalu dapat diakses dengan keyboard dan memiliki label `Buka bantuan halaman`;
- dialog menggunakan `role=dialog`, `aria-modal`, dan judul terhubung;
- tombol tutup menerima fokus saat dialog dibuka;
- `Escape`, tombol tutup, klik backdrop, atau **Saya mengerti** menutup dialog;
- fokus kembali ke tombol Bantuan setelah dialog ditutup;
- pada layar kecil label teks disembunyikan, tetapi nama aksesibel tetap tersedia;
- membuka route lain menutup dialog lama secara otomatis.

Registry konten berada di `src/lib/pageHelp.ts`, renderer global di
`src/components/PageHelp.vue`, dan pemasangannya di `src/App.vue`. Saat menambah route, tambahkan
petunjuk khusus beserta contoh path ke `tests/unit/pageHelp.test.ts`.

## Verifikasi 7 Oktober 2026

- route operasional, termasuk Persetujuan tayang, memiliki bantuan khusus dan fallback diuji;
- 99 unit test frontend lulus;
- tes browser login ke dashboard membuktikan isi mengikuti halaman, `Escape` bekerja, dan fokus kembali;
- typecheck dan production build lulus.


## Halaman Sumber & tracking

Route `/sources` memiliki bantuan khusus untuk pencarian dan pagination sumber, pembacaan status discovery/profiling/configuration atau binding master/pemuatan, penanggung jawab Data Owner/Data Steward, serta navigasi Buka sumber. Panduan mengarahkan pengguna ke daftar ini jika sumber tidak ada di dropdown Workspace. Kegagalan tahap tidak menghapus sumber. Admin memerlukan alasan dan dua konfirmasi untuk unlink; pemulihan juga memerlukan dua konfirmasi. Status progres bukan bukti hak akses, dan binding master approved belum membuktikan record telah dimuat.

## Alur sederhana dan detail temuan

Helper Workspace/review menerangkan approval gabungan konfigurasi, metadata sumber PENDING,
dan aktivasi policy SOURCE APPROVED tanpa approval sebagian. Reviewer tidak boleh menjadi
pembuat konfigurasi/editor metadata. Gate IT/unit dan kontrol akses pembaca tetap berlaku.

Helper Sumber/Workspace/import membedakan Sync manual langsung NON_MASTER ACTIVE dari master,
FULL_REFRESH, jadwal dan batch review biasa. Jalur langsung tidak meminta approval batch
tambahan jika validasi teknis, AI dan preview konflik lolos; jalur biasa tetap approval/Apply.
Setelah jawaban temuan selesai, sync manual kembali dapat memuat batch siap sesuai prasyarat.

`NEEDS_INPUT` berarti Menunggu tindakan, bukan proses aktif. **Lihat detail** berikon mata
membuka modal keterangan, kode, baris asli Sheet pada snapshot (termasuk header), kolom,
pagination temuan dan tautan batch. Audit menyimpan ringkasan lokasi tanpa nilai mentah.
Membuka detail tidak menjalankan sync/approval. Kegagalan lama bukan status pemuatan terbaru.
