---
id: sumber-dan-klasifikasi
title: Mendaftarkan sumber dan mengklasifikasikan tab
summary: Cara menghubungkan Google Sheet, melengkapi metadata bisnis, profiling, dan menentukan MASTER atau NON_MASTER.
routes: ["/workspace", "/sources", "/sources/*"]
audiences: ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"]
source: docs/KLASIFIKASI_TAB_BE02.md
---
Sebelum mendaftarkan sumber, bagikan spreadsheet kepada email service account backend dengan akses Viewer. Pada Workspace ETL, masukkan URL atau ID spreadsheet dan nama yang mudah dikenali. Kode teknis dan UUID dibuat sistem; pengguna hanya mengisi kode bisnis bila form memang menyediakannya.

Lengkapi unit pemilik, domain bisnis, yurisdiksi, purpose, data owner, data steward, sensitivitas, dan deskripsi. Metadata ini dipakai untuk kepemilikan, pencarian, serta keputusan akses. Tekan Hubungkan & profiling sekali. API lebih dulu mendaftarkan sumber dan membuat job discovery; pembacaan Google Sheet berlangsung di worker setelahnya. Status pendaftaran, status job, dan tautan monitor tampil di dekat tombol. Jika job gagal, sumber sudah tercatat: buka monitor job, periksa penyebabnya, dan jangan mendaftarkan Sheet yang sama lagi.

Gunakan menu **Sumber & tracking** sebagai daftar utama. Halaman ini menyediakan pencarian dan pagination; dropdown Workspace hanya menampilkan sebagian hasil untuk memilih konteks kerja. Tekan **Buka sumber** pada tabel untuk melanjutkan di Workspace ETL. Kolom progres merangkum discovery, profiling, konfigurasi atau binding master, approval IT, pemuatan/import, Data Owner, dan Data Steward. Status **Menunggu IT_APPROVER** muncul setelah konfigurasi diajukan dan masih menunggu keputusan reviewer teknis; buka detail Tab untuk melihat tab yang menunggu. **Belum diajukan** berarti steward masih perlu mengajukan review. Status gagal menandai tahap yang perlu diperbaiki; sumbernya tetap ada dan tidak perlu didaftarkan ulang. Tab yang diklasifikasikan MASTER memerlukan binding dan batch import master yang dapat dipantau terpisah.

Pada setiap kolom tahap, tekan ikon **?** untuk membaca petunjuk dan urutan kerja. Ikon **!** muncul bila ada kegagalan terakhir; buka untuk membaca kode, pesan, dan waktunya. Tombol **Riwayat** membuka audit trail sumber yang mencatat aktivitas, waktu, pelaku, serta awal/hasil job. Riwayat dapat dimuat bertahap dari aktivitas terbaru ke yang lebih lama. Audit trail adalah kronologi aktivitas yang tercatat; ia tidak menggantikan pemeriksaan akses atau persetujuan.

Jika tab dihapus dari Google Sheet, tombol **Muat ulang data tersimpan** hanya membaca ulang status yang sudah tersimpan di aplikasi. Jalankan **Temukan tab** untuk meminta backend memeriksa ulang Google Sheet. Tab yang tidak lagi ditemukan akan dinonaktifkan dan disembunyikan dari pilihan Workspace; rekam tab, konfigurasi, dan audit tetap disimpan. Jika tab dikembalikan, jalankan discovery lagi lalu aktifkan tab secara manual bila ingin memprosesnya kembali.

Jika spreadsheet yang sama terdaftar lebih dari sekali, pendaftaran aktif ditampilkan bersama sebagai duplikat. Admin meninjau sumber utama dan relasinya sebelum menjalankan **Unlink**. Tindakan ini membutuhkan alasan serta dua konfirmasi; riwayat tetap disimpan, tetapi entri tidak lagi tampil pada daftar aktif dan grup duplikat aktif. Admin dapat menampilkan sumber yang sudah di-unlink dan memulihkannya dengan dua konfirmasi, atau memakai sumber yang sesuai lalu mengatur binding ulang. Unlink ditolak bila masih ada konfigurasi, hasil ETL, data product, binding master, dependensi, atau job aktif. Jangan membuat registrasi baru untuk memperbaiki kegagalan profiling atau discovery.

Untuk menghapus registrasi setup gagal dan mengulang dari awal, admin gunakan ikon **Hapus permanen** pada tabel sumber. Preview akan menyebutkan jumlah tab, hasil profiling, dan job terminal yang dihapus. Sumber tidak dapat dihapus bila sudah memiliki konfigurasi, snapshot/ETL, data product, binding master/taxonomy, review import, kebijakan akses/AI terkait, dependensi, atau job aktif. Admin harus mengetik kode sumber, memberi alasan, dan mengonfirmasi dua kali. Data setup yang dihapus tidak dapat dipulihkan; audit penghapusan tetap tercatat. Untuk sumber yang telah menghasilkan data operasional, jangan hapus; tinjau relasinya dan ikuti proses perubahan yang berlaku.

Setiap tab harus dikonfirmasi sebagai MASTER atau NON_MASTER. MASTER berisi rujukan yang relatif stabil dan dipakai dataset lain, misalnya cabang, produk, atau departemen. NON_MASTER berisi transaksi, pengukuran, atau data dinamis. Jika ragu, tinjau business key, frekuensi perubahan, pemilik resmi, dan pemakaian kolom sebagai rujukan. Perubahan klasifikasi yang sudah aktif dapat memerlukan migrasi dan review ulang.

