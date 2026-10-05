# Identifier internal dan kode bisnis

Antarmuka aplikasi tidak meminta pengguna mengetik UUID. UUID tetap dipakai oleh database dan API
untuk primary key, foreign key, route, concurrency, dan audit, tetapi nilainya selalu berasal dari
record yang dibuat sistem atau pilihan yang dimuat dari API.

Aturan implementasi:

- pengguna memilih sumber, sheet, master, taxonomy, user, atribut, permission, job, pertanyaan, dan
  resource policy melalui nama atau kode bisnis;
- komponen frontend menyimpan UUID pilihan sebagai nilai internal lalu mengirimkannya ke API;
- route detail membawa UUID dari tombol atau tautan record yang dipilih, bukan dari input teks;
- kode sumber dibuat otomatis. Kode master, taxonomy, term, metric, product, policy, atribut, dan
  permission tetap dapat diisi karena merupakan identifier bisnis yang dapat dibaca manusia;
- workbook konfigurasi mengunci referensi taxonomy internal. Pemilihan taxonomy dilakukan melalui
  aplikasi, sedangkan workbook hanya dapat mengubah versi dan status wajib;
- API tetap memvalidasi UUID untuk relasi internal agar referensi lintas tenant, salah format, dan
  record yang tidak ada ditolak.

Halaman yang menggunakan pilihan bernama mencakup workspace sumber, jadwal dan dependency, master
otoritatif, binding master/taxonomy, batch import, resolver referensi, proposal master, pengaturan
akses, evaluasi policy, serta pemantauan job. Filter storage master memakai pencarian nilai bisnis
dan periode, tanpa input UUID record.

Jika fitur baru membutuhkan relasi, sediakan endpoint daftar atau pencarian yang terscope tenant dan
akses pengguna. Jangan menambahkan input teks UUID sebagai jalan pintas di frontend atau workbook.
