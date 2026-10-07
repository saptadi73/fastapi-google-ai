---
id: pemecahan-masalah-umum
title: Pemecahan masalah umum
summary: Pemeriksaan awal ketika sumber, konfigurasi, import, akses, atau layanan AI belum siap.
routes: ["/*"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Jika sumber tidak terbaca, pastikan spreadsheet dibagikan kepada service account yang benar, URL valid, file credential Google tersedia di server, dan health check Google berstatus ready. Jika konfigurasi atau batch diblokir, baca kode serta pesan error, muat ulang state terbaru, dan selesaikan dependency yang disebutkan sebelum mengulang aksi.

Jika dropdown unit, domain bisnis, atau yurisdiksi kosong saat mendaftarkan Google Sheet, periksa assignment aktif pada akun yang sedang login dan tenant yang benar. Membuat atribut di Administrasi saja belum memberi assignment. Minta admin lain membuka Administrasi → Pengguna untuk menugaskan ketiga atribut tersebut, lalu tekan Muat ulang pilihan di Workspace. Admin tidak dapat memberi assignment kepada akunnya sendiri. Purpose berasal dari registry atribut aktif, sedangkan owner/steward dari akun aktif. Jika formulir menampilkan pesan pilihan gagal dimuat, periksa request registration-options atau hubungi administrator.

Di Administrasi, panel Berikan unit/departemen hanya menampilkan atribut DEPARTMENT. Jika yang tampil cuma Marketing, periksa Registry akses: domain bisnis dan yurisdiksi wilayah memiliki jenis atribut berbeda dan diberikan melalui form Atribut di bawah panel unit. Centang Marketing terlebih dahulu; tombol menunjukkan jumlah unit yang akan diberikan. Sesudah berhasil, pilihan centang dikosongkan kembali, tetapi assignment aktif terlihat pada ringkasan dan riwayat. Periksa nama pengguna yang dipilih dan nama akun yang login ke Workspace; dua nama akun berbeda tidak berbagi assignment.

Jika data belum muncul di dashboard, pastikan discovery, profiling, klasifikasi, konfigurasi, deploy, activation, import, dan job terakhir berhasil. Periksa master atau taxonomy binding, pertanyaan batch, data karantina, freshness, metadata sumber, serta policy akses.

Jika deploy atau rollback ditolak dengan `RELEASE_APPROVAL_REQUIRED`, buka status **Persetujuan tayang** pada review konfigurasi. Pastikan akun IT dan setiap unit yang ditunjuk telah memutuskan revisi yang sama; IT harus menyelesaikan checklist teknis. Jika status ditolak atau keputusan lama tidak berlaku setelah revisi konfigurasi, snapshot, atau aturan rilis berubah, minta editor memperbaiki versi konfigurasi atau admin meninjau ulang aturan. Jangan mengulangi deploy sebelum status siap tayang. Persetujuan ini berbeda dari approval batch import dan tidak otomatis memberikan akses membaca data.

Jika AI tidak menjawab, periksa health OpenAI, konfigurasi model, kuota pengguna, budget tenant atau policy, lalu coba sekali lagi dengan pertanyaan yang lebih spesifik. Jangan mengirim password, token, API key, isi credential, atau data pribadi ke asisten. Catat request ID dari respons error untuk pemeriksaan administrator.

