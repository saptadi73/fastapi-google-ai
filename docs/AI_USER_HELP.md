# Asisten AI dan knowledge base pengguna

## Arah penyederhanaan workflow ETL

Mode owner-managed aktif secara default lewat `ETL_OWNER_WORKFLOW_ENABLED=true`; administrator dapat menonaktifkannya sementara untuk kompatibilitas. Nilai environment production mengesampingkan default aplikasi, jadi verifikasi nilai di server sebelum menyimpulkan alur sudah aktif. Approval satu kali saat registrasi sumber tetap terpisah dari pemeriksaan teknis konfigurasi.

Targetnya adalah satu pemeriksaan saat registrasi/klasifikasi tab, lalu pemilik data menyelesaikan validasi konfigurasi dan deploy tanpa approval rutin. Pemeriksaan snapshot terbaru, dry-run, integritas business key, keamanan tenant, pembatasan akses, serta audit tetap wajib. Hak baca default mengikuti domain dan business unit yang sama untuk sumber yang sudah disetujui; pembatas yurisdiksi/department dapat ditambahkan oleh pemilik. Role tetap memerlukan capability baca/query, dan DENY eksplisit tetap berlaku.

Approver sumber meninjau inventory tab yang ditemukan, klasifikasi, status profiling, dan ringkasan kolom tanpa nilai data. Perubahan tab/profil membatalkan bukti review sumber. Untuk konfigurasi, pemilik membuat draft dan menjalankan validasi deterministic; tidak perlu checklist kolom/bagian berulang atau approval reviewer. Data owner/steward dapat men-deploy serta rollback versi owner-managed. Snapshot, dry-run, schema plan, klasifikasi, tenant checks, pemeriksaan identitas owner, konfirmasi rollback, dan audit tetap berlaku. Perubahan skema yang tidak aman tetap dihentikan dengan alasan dan tindakan yang jelas.

Dalam mode pemilik yang sama, definisi master, binding tab, binding kolom referensi, dan deploy storage memakai validasi business key/schema, snapshot, versi master, normalisasi, dan pemeriksaan referensi. Batch import yang bersih dapat langsung di-Apply pemilik setelah preview hash terbaru diperiksa. Konflik bisnis yang nyata memerlukan konfirmasi dan alasan; duplicate/key conflict, pertanyaan terbuka, referensi ambigu, atau baris invalid tetap menghentikan apply. Sinkronisasi aktif mendukung `FULL_REFRESH`: seluruh sumber divalidasi lebih dulu, lalu data target diganti atomik; jika ada baris invalid, data aktif lama dipertahankan. Full refresh mengganti isi baris, bukan memberikan izin untuk migrasi skema destruktif. Akses sumber harus tetap aktif. Jalur batch master memakai pipeline apply bersama ini, tetapi blocker `MASTER_RUNTIME_PENDING` pada konfigurasi ETL umum masih perlu dituntaskan.

Setelah sumber lolos pemeriksaan awal, pemilik data dapat memperbarui metadata akses tanpa meminta approver lagi pada workflow target. Backend memeriksa domain/unit aktif dan assignment pemilik, membatasi fallback ke DISCOVER/READ/QUERY, serta mencatat perubahan. Untuk produk dari sumber bermetadata yang sudah disetujui, `allowed_roles` tidak menjadi pembatas tambahan bila role memiliki capability DISCOVER/READ/QUERY dan assignment domain serta unitnya cocok. EXPORT tidak termasuk. Mode ini default ON, tetapi nilai environment production dapat menimpanya. Sumber tanpa review/metadata tetap mengikuti kebijakan lama; jangan menganggap status review lama otomatis disetujui.

Sebelum merencanakan migrasi sumber lama, administrator dapat menjalankan `python -m app.cli source-access-backfill-report` pada environment backend. Perintah ini hanya membaca dan mengelompokkan sumber aktif; ia tidak mengubah metadata, review, policy, atau hak akses. Lihat [laporan dry-run metadata akses](ACCESS_BACKFILL_REPORT.md) untuk arti setiap kategori. Sumber legacy tidak boleh otomatis dianggap telah direview.

Asisten tersedia melalui `POST /api/v1/help/ask` untuk pengguna yang sudah login. Backend mencari
artikel lokal yang boleh dibaca role pengguna, mengirim hanya artikel terpilih ke OpenAI, lalu
memvalidasi kembali ID sumber pada jawaban. Source code, filesystem, database, dan credential tidak
diberikan kepada model.

Artikel berada di `docs/knowledge/*.md` dengan front matter `id`, `title`, `summary`, `routes`,
`audiences`, dan `source`. `audiences: ["*"]` berarti seluruh role. Gunakan daftar role eksplisit
untuk prosedur terbatas. Konten harus menjelaskan fungsi dan proses pengguna tanpa SQL, UUID,
credential, atau detail kontrol keamanan. Perubahan artikel langsung digunakan pada request berikutnya
dan tidak memerlukan migration database.

Ini adalah retrieval artikel lokal pada setiap pertanyaan, bukan fine-tuning model. Hanya
artikel terpilih yang dikirim; backend membatasi isi setiap artikel menjadi 6.000 karakter.
Letakkan panduan penting sebelum batas tersebut dan uji pertanyaan serta konteks yang benar-benar
diterima provider. Mengubah dokumentasi di luar `docs/knowledge` tidak otomatis memperbarui
jawaban model. Helper halaman frontend adalah konten statis terpisah yang perlu diselaraskan.
Perubahan lokal baru tersedia di production setelah file terkait dideploy; perubahan prompt
mengikuti pemuatan/version policy runtime, bukan perubahan izin database.

Artikel sumber, operasi ETL, master, dashboard, contoh analitik, dan pemecahan masalah
membedakan penambahan kolom Google Sheets dari revisi konfigurasi Workspace. Asisten harus
menjelaskan profiling ulang pada sumber yang sama, draft dari profile terbaru, serta migrasi
schema non-master yang sudah deployed. Field master nullable memiliki alur approval dan
deploy-storage tersendiri. Label periode text seperti `w1` atau `january` perlu tahun,
grain, dan kalender bisnis; jangan menjanjikan konversi tanggal atau analisis overlap otomatis.
Lihat [panduan perubahan sumber dan waktu](PANDUAN_REVIEW_ETL.md#perubahan-sumber-kolom-dan-periode-waktu).

Dalam workflow target, pemeriksaan manusia hanya dilakukan saat registrasi sumber untuk memeriksa inventory seluruh tab dan klasifikasinya. Sesudah itu pemilik/steward melakukan metadata, konfigurasi, preview, validasi, deploy, dan sync. Untuk flag OFF atau konfigurasi lama, UI dapat tetap menampilkan gate lama; bantu pengguna melihat status backend dan jangan menyuruh mereka menganggap review tersebut sudah dihapus.

Contoh isian bisnis terdapat pada [Contoh pengisian aplikasi](CONTOH_ISIAN_APLIKASI.md) dan
artikel `08` sampai `11` dalam `docs/knowledge`. Isinya mencakup taxonomy/term, atribut
DEPARTMENT/BUSINESS_DOMAIN/JURISDICTION/CLEARANCE/PURPOSE, metadata Google Sheet, master,
dan pertanyaan dashboard. Contoh bersifat fiktif; retrieval tidak boleh menyatakannya sebagai
registry yang sudah ada pada tenant pengguna.

Panduan kontekstual pada halaman **Binding kolom referensi master** dan artikel knowledge
`master-dan-taxonomy`/`contoh-isian-master-dan-analitik` menjelaskan cara memilih header sumber,
master approved, serta field master unik (biasanya business key). Jawaban harus menegaskan bahwa
UUID internal dibuat/dipakai sistem, nilai tidak ditemukan atau ambigu harus diselesaikan sebelum apply. Pada owner workflow, binding yang tervalidasi tidak memerlukan approver kedua; perubahan tetap memerlukan preview/validasi terbaru dan audit.

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

Pada halaman **Batch import**, pengguna mencari sumber pada tabel dengan status discovery,
profiling, konfigurasi/binding, approval IT, dan database sebelum memilih sumber serta tab. Pada
**Persetujuan tayang**, approver mencari konfigurasi menurut sumber, produk, status, revisi, atau
kelompok approval, lalu memilih baris untuk membuka detail. Daftar hanya memuat konfigurasi yang
ditugaskan kepada approver. Kedua halaman menggunakan pencarian dan pagination tabel reusable;
tidak perlu memilih sumber dari dropdown panjang.

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
yang belum lengkap. Jika struktur tabel dan isi data sudah benar, perbaiki nama/deskripsi dataset,
arti/deskripsi/sinonim kolom, dimensi, dan definisi metrik melalui **detail produk → Edit metadata
semantik untuk NL2SQL**. Cara ini memperbarui semantic catalog, versi, dan audit tanpa profiling,
konfigurasi ulang, ETL, atau pemuatan ulang data. Gunakan Workspace ETL dan profiling ulang hanya
ketika struktur/header sumber berubah atau memang perlu memperbaiki mapping, tipe, transformasi,
aturan kualitas, atau strategi pemuatan. Perubahan nilai di Google Sheet saja memerlukan koreksi
sumber dan sync ulang bila data target harus diperbarui; tidak otomatis memerlukan profiling bila
struktur dan mapping tetap sama. Relasi lintas dataset dibuat hanya bila diperlukan dan kolom kunci
serta kardinalitasnya telah diverifikasi.


### Tabel error response

Lihat [Error response: kemungkinan penyebab dan tindakan](ERROR_RESPONSES.md). Tabel mencakup error sumber, review/deploy schema, validasi/import, akses katalog serta layanan database/AI. Di aplikasi: **Bantuan > Tabel error response** atau **Panduan lengkap > Tabel error response**; gunakan pencarian kode. Alasan keputusan akses dan blocker batch dibedakan dari error HTTP.


### Format Google Sheet ideal untuk analitik dan action plan

Baca [Panduan lengkap format Google Sheet](PANDUAN_FORMAT_GOOGLE_SHEET.md): penamaan file/tab dan produk, header tabular, grain/key, master/taxonomy, tipe/satuan/presisi, waktu/periode wajib untuk data periodik, metrik, kualitas, provenance, action plan berbasis bukti dan contoh tabel. Di aplikasi buka **Bantuan > Format Google Sheet ideal** atau **Panduan lengkap > Format Google Sheet ideal**. Waktu kejadian/pengukuran, periode data dan waktu pengambilan dibedakan; tanggal sync bukan pengganti waktu bisnis. Kolom angka publik pada konfigurasi NON_MASTER kini otomatis menjadi metrik awal; pemilik tetap perlu memeriksa arti, satuan dan agregasinya.


### Istilah teknis untuk pengguna non teknis

[Tabel istilah teknis dalam bahasa sederhana](ISTILAH_TEKNIS.md) menjelaskan grain, business/primary key, master, taxonomy, mapping, tipe, nullable, dimensi/metrik, snapshot, ETL, periode, waktu pengambilan serta proses pemuatan dengan contoh bisnis. Buka **Bantuan > Istilah teknis dalam bahasa sederhana** atau **Panduan lengkap > Istilah teknis dalam bahasa sederhana**; cari istilah, arti atau contoh.

Pada draft konfigurasi `NON_MASTER` yang baru, kolom publik bertipe `int`/`integer`, `bigint`, `numeric`/`decimal`, serta tipe numerik lain otomatis didaftarkan sebagai metrik agar tidak perlu menambahkannya satu per satu. Key numerik memakai `count_distinct`, kolom bernama persen/rasio/rate memakai `avg`, dan kolom numerik lain memakai `sum` sebagai nilai awal. Tinjau agregasi dan satuan sesuai arti bisnis sebelum deploy; kolom `MEDIUM/HIGH` dikecualikan. Tab `MASTER` tidak mendapat metrik otomatis karena angka pada master sering merupakan kode atau atribut identitas.

Produk NON_MASTER aktif yang sudah ada dapat diperbarui tanpa profiling, konfigurasi ulang, atau sinkronisasi ulang. Jalankan `python -m app.cli semantic-numeric-metric-backfill` untuk laporan dry-run; setelah memeriksa hasilnya, jalankan `python -m app.cli semantic-numeric-metric-backfill --apply`. Perintah hanya menambah definisi metrik katalog yang belum ada, mempertahankan definisi manual, mengecualikan MASTER dan kolom sensitif, menaikkan versi semantic produk yang berubah, serta mencatat audit sistem. Pengulangan perintah aman.


### Lima contoh Excel untuk analitik dan action plan

Lihat [Contoh data analitik](CONTOH_DATA_ANALITIK.md): keluhan pelanggan, sebaran marketing ATL/BTL, kepuasan berbasis produk, competitiveness harga/layanan dan plan/goal/KPI. File dapat diunduh dari **Bantuan > Contoh Excel untuk analitik dan action plan** atau **Panduan lengkap > Contoh Excel**. Data fiktif dilengkapi master, waktu/periode, kamus, rencana ETL, formula dan baseline tindakan; target/bobot/hipotesis tetap perlu verifikasi bisnis.
