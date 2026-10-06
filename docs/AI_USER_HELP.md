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

Contoh isian bisnis terdapat pada [Contoh pengisian aplikasi](CONTOH_ISIAN_APLIKASI.md) dan
artikel `08` sampai `11` dalam `docs/knowledge`. Isinya mencakup taxonomy/term, atribut
DEPARTMENT/BUSINESS_DOMAIN/JURISDICTION/CLEARANCE/PURPOSE, metadata Google Sheet, master,
dan pertanyaan dashboard. Contoh bersifat fiktif; retrieval tidak boleh menyatakannya sebagai
registry yang sudah ada pada tenant pengguna.

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
