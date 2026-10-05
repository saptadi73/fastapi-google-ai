---
id: pemecahan-masalah-umum
title: Pemecahan masalah umum
summary: Pemeriksaan awal ketika sumber, konfigurasi, import, akses, atau layanan AI belum siap.
routes: ["/*"]
audiences: ["*"]
source: docs/USER_GUIDE_END_TO_END.md
---
Jika sumber tidak terbaca, pastikan spreadsheet dibagikan kepada service account yang benar, URL valid, file credential Google tersedia di server, dan health check Google berstatus ready. Jika konfigurasi atau batch diblokir, baca kode serta pesan error, muat ulang state terbaru, dan selesaikan dependency yang disebutkan sebelum mengulang aksi.

Jika data belum muncul di dashboard, pastikan discovery, profiling, klasifikasi, konfigurasi, deploy, activation, import, dan job terakhir berhasil. Periksa master atau taxonomy binding, pertanyaan batch, data karantina, freshness, metadata sumber, serta policy akses.

Jika AI tidak menjawab, periksa health OpenAI, konfigurasi model, kuota pengguna, budget tenant atau policy, lalu coba sekali lagi dengan pertanyaan yang lebih spesifik. Jangan mengirim password, token, API key, isi credential, atau data pribadi ke asisten. Catat request ID dari respons error untuk pemeriksaan administrator.

