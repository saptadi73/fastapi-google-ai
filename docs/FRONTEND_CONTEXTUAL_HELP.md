# Bantuan kontekstual frontend

Frontend menyediakan tombol **Bantuan** tetap pada setiap route, termasuk halaman login. Tombol
membuka dialog yang menjelaskan fungsi halaman, urutan penggunaan, dan catatan yang perlu
diperhatikan. Isi mengikuti `route.path`, sehingga navigasi ke halaman lain langsung mengganti
petunjuk tanpa memuat ulang aplikasi.

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
- administrasi tenant, pengguna, registrasi akun, akun sendiri, dan access request.

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

## Verifikasi 6 Oktober 2026

- seluruh 26 contoh route memiliki bantuan khusus dan fallback diuji;
- 98 unit test frontend lulus;
- tes browser login ke dashboard membuktikan isi mengikuti halaman, `Escape` bekerja, dan fokus kembali;
- typecheck dan production build lulus.

