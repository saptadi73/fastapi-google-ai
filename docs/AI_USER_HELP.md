# Asisten AI dan knowledge base pengguna

Asisten tersedia melalui `POST /api/v1/help/ask` untuk pengguna yang sudah login. Backend mencari
artikel lokal yang boleh dibaca role pengguna, mengirim hanya artikel terpilih ke OpenAI, lalu
memvalidasi kembali ID sumber pada jawaban. Source code, filesystem, database, dan credential tidak
diberikan kepada model.

Artikel berada di `docs/knowledge/*.md` dengan front matter `id`, `title`, `summary`, `routes`,
`audiences`, dan `source`. `audiences: ["*"]` berarti seluruh role. Gunakan daftar role eksplisit
untuk prosedur terbatas. Konten harus menjelaskan fungsi dan proses pengguna tanpa SQL, UUID,
credential, atau detail kontrol keamanan. Perubahan artikel langsung digunakan pada request berikutnya
dan tidak memerlukan migration database.

Artikel akses menjelaskan pilihan beberapa unit secara eksplisit dan penunjukan approver
per sumber untuk review metadata, konfigurasi ETL, dan batch import. Asisten harus
menegaskan bahwa unit induk tidak otomatis membuka unit bawahan dan penunjukan approver
tidak otomatis memberi akses membaca data.

Artikel akses, alur awal, operasi ETL, dan pemecahan masalah menerangkan gate siap tayang: admin menunjuk pemeriksa IT dan
approver bernama pada setiap unit terkait; satu keputusan IT serta satu keputusan dari
setiap unit diperlukan pada revisi konfigurasi yang sama sebelum deploy. Asisten harus
membedakan ini dari reviewer konfigurasi awal, approval batch import, dan assignment untuk membaca data. Jawaban tentang deploy yang tertahan perlu mengarahkan pengguna ke status **Persetujuan tayang**, serta menjelaskan bahwa perubahan revisi/snapshot/aturan atau penolakan memerlukan tindak lanjut sebelum mencoba lagi.

Contoh isian bisnis terdapat pada [Contoh pengisian aplikasi](CONTOH_ISIAN_APLIKASI.md) dan
artikel `08` sampai `11` dalam `docs/knowledge`. Isinya mencakup taxonomy/term, atribut
DEPARTMENT/BUSINESS_DOMAIN/JURISDICTION/CLEARANCE/PURPOSE, metadata Google Sheet, master,
dan pertanyaan dashboard. Contoh bersifat fiktif; retrieval tidak boleh menyatakannya sebagai
registry yang sudah ada pada tenant pengguna.

Panduan kontekstual pada halaman **Binding kolom referensi master** dan artikel knowledge
`master-dan-taxonomy`/`contoh-isian-master-dan-analitik` menjelaskan cara memilih header sumber,
master approved, serta field master unik (biasanya business key). Jawaban harus menegaskan bahwa
UUID internal dibuat/dipakai sistem, nilai tidak ditemukan atau ambigu diselesaikan pada review
batch, binding hanya mencari satu field master, dan perubahan binding memerlukan approval serta
batch import baru.

## API

- `GET /api/v1/help/articles?route=/dashboard` menampilkan metadata artikel yang dapat diakses.
- `GET /api/v1/help/articles?query=kata` mencari metadata artikel.
- `POST /api/v1/help/ask` menerima `question` dan `route` opsional.

Respons jawaban berisi `answer`, `citations`, `suggested_questions`, dan `insufficient_context`.
Metadata envelope mencantumkan model dan versi prompt bila OpenAI dipanggil. Jika retrieval tidak
menemukan konteks, backend mengembalikan petunjuk aman tanpa memanggil OpenAI.

Konfigurasi memakai `OPENAI_MODEL_HELP`; jika kosong, model `OPENAI_MODEL_NL2SQL` digunakan. Respons
provider mengikuti `OPENAI_STORE_RESPONSES=false`. Pemakaian dicatat dengan purpose `USER_HELP` pada
ledger AI dan dibatasi `AI_HELP_DAILY_USER_LIMIT` per pengguna; budget tenant tetap berlaku. Administrator dapat membuat policy global
`USER_HELP` dengan prompt version `user_help_v1.md` bila memerlukan model, fallback, batas konteks,
atau budget khusus.

Saat menambah artikel, uji pertanyaan umum, pertanyaan ambigu, pembatasan audience, dan sitasi. Jangan
memasukkan data tenant, isi spreadsheet, token, password, API key, atau file service account ke
knowledge base.

Jalankan `alembic upgrade head` saat deployment agar check constraint policy menerima purpose
`USER_HELP`. Migration tidak membuat tabel knowledge base karena artikel dibaca dari file terkurasi.

Knowledge base menjelaskan menu **Sumber & tracking** sebagai daftar lengkap sumber dengan
pencarian, pagination, status discovery/profiling/configuration atau binding master/pemuatan,
serta Data Owner dan Data Steward. Asisten mengarahkan pengguna ke halaman ini bila sumber
lama tidak tampak pada dropdown Workspace dan menyarankan **Buka sumber** untuk melanjutkan.
Sumber yang gagal pada satu tahap tetap tercatat; perbaiki lalu ulangi tahap relevan tanpa
registrasi ulang. Unlink menyimpan riwayat dan mengeluarkan entri dari daftar aktif serta
duplikat aktif. Unlink meminta alasan dan dua konfirmasi; pemulihan juga membutuhkan dua
konfirmasi. Asisten tidak boleh menyatakan bahwa status tracking menjamin hak akses atau
bahwa binding master saja berarti data sudah dimuat.

Admin dapat menghapus permanen registrasi setup yang gagal dari tabel tracking. UI menampilkan
preview dampak terlebih dahulu, meminta kode sumber dan alasan, lalu dua konfirmasi. Penghapusan
hanya tersedia bila belum ada konfigurasi, snapshot/ETL, data product, binding, review import,
kebijakan terikat, dependensi, atau job aktif; bila ada, arahkan admin untuk menyelesaikan
ketergantungan atau memakai unlink jika memang sumber duplikat. Penghapusan membersihkan tab,
hasil profiling, dan job terminal sumber tersebut, sementara event audit penghapusan tetap ada.
Jangan menghapus sumber yang sudah menghasilkan data operasional hanya untuk mengulang profiling.

Halaman **Katalog data** menggunakan `GET /api/v1/semantic/data-product-inventory` untuk
menampilkan Data Product aktif yang memang boleh dilihat pengguna, bersama tabel fisik, semantic
view, sumber spreadsheet/tab, versi ETL, dan metadata semantic. Katalog membantu menemukan metadata
yang belum lengkap; sarannya bukan perubahan otomatis. Untuk NL2SQL, lengkapi deskripsi dataset,
nama bisnis kolom, dimensi, definisi metrik beserta unit dan sinonim. Perbaiki data/header di sumber,
struktur/mapping lewat revisi ETL, dan semantic melalui Governance. Relasi lintas dataset dibuat
hanya bila diperlukan dan kolom kunci serta kardinalitasnya telah diverifikasi.
