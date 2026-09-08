# Verifikasi dan persetujuan konfigurasi ETL

Status: **wizard Vue, bukti review, preview before/after, dan round-trip XLSX untuk subset konfigurasi runtime sudah diimplementasikan**. Bagian master/relasi/taxonomy dan parameter lain yang ditandai belum tersedia tetap rancangan. Lihat [panduan implementasi](PANDUAN_REVIEW_ETL.md). Disusun setelah membaca seluruh 14 tab [Template_Parameter_Google_Sheet_AI_ETL.xlsx](Template_Parameter_Google_Sheet_AI_ETL.xlsx). Fitur yang belum tersedia tidak boleh dianggap sudah diimplementasikan oleh API Reference.

## 1. Rekomendasi

Gunakan **wizard/form di Vue sebagai jalur utama**, berisi rekomendasi AI yang dapat diperiksa dan diedit. Gunakan **download/edit/upload XLSX sebagai jalur tambahan** bagi data steward atau reviewer yang perlu mengedit banyak parameter secara offline.

Kedua jalur mengedit draft konfigurasi kanonis yang sama di backend. File Excel bukan sumber persetujuan; approval tetap dilakukan oleh user terautentikasi melalui aplikasi setelah validasi server.

Urutan keseluruhan:

```text
Hubungkan Sheet → klasifikasi master/non-master → profiling
→ AI mengusulkan draft → pengguna memverifikasi
→ dry-run dan penyelesaian pertanyaan → reviewer menyetujui
→ deploy → sync data → pantau hasil
```

BE-01 menetapkan klasifikasi per tab dan usulan kode master baru yang wajib disetujui. [BE-02](KLASIFIKASI_TAB_BE02.md) sudah menyediakan penyimpanan/API klasifikasi dan gate backend; registry/binding metadata tersedia pada [BE-03](REGISTRY_MASTER_BE03.md), storage tersedia pada [BE-04](STORAGE_MASTER_BE04.md), sedangkan runtime import master masih tahap lanjutan. Konfigurasi manual/AI, validate, approval, deploy, dan job polling untuk dataset mandiri tersedia. Form klasifikasi frontend belum ditambahkan; gunakan API/Swagger sementara.

## 2. Wizard yang disarankan

Jangan meminta pengguna mengisi workbook kosong atau menampilkan semua parameter sekaligus. AI mengisi draft berdasarkan profile, business context, master yang tersedia, dan aturan yang disetujui. Parameter yang belum diketahui menjadi pertanyaan, bukan nilai tebakan yang langsung aktif.

| Langkah | Yang ditampilkan | Keputusan pengguna |
|---|---|---|
| 1. Identitas dan tujuan | File/tab, jenis master/non-master, tujuan dataset, arti satu baris | Konfirmasi dataset dan pilih master lama bila ada |
| 2. Struktur kolom | Header asal, arti bisnis, tipe, wajib isi, business key, UOM/currency, sensitivitas | Perbaiki arti kolom, kode identitas, satuan, dan klasifikasi sensitif |
| 3. Pembersihan dan referensi | Transform berurutan, before/after, padanan master/taxonomy | Terima atau ubah aturan; jawab nilai ambigu |
| 4. Kualitas data | Required, uniqueness, rentang, referensi, aksi kegagalan | Tentukan aturan bisnis dan penanganan data gagal |
| 5. Load dan operasional | Preview tambah/update/tetap, jadwal, strategi load, dependensi master | Konfirmasi dampak load dan jadwal |
| 6. Laporan dan akses | Data product, metric, dimensi, intent, relasi yang diizinkan | Konfirmasi definisi hitungan dan siapa yang boleh mengakses |
| 7. Ringkasan dan persetujuan | Diff draft, hasil dry-run, pertanyaan tersisa, coverage pemeriksaan | Ajukan review; reviewer approve/reject; kemudian deploy |

Parameter teknis lanjutan diletakkan pada bagian yang dapat dibuka oleh reviewer terkait. Jangan menyembunyikan kebutuhan verifikasi key, referensi, PII, atau aksi penghapusan di balik tombol “terima semua”. Confidence membantu prioritas review; bukan pengganti approval.

Contoh tabel review kolom, ilustrasi rekomendasi yang harus dikonfirmasi:

| Kolom sumber | Rekomendasi | Alasan | Kontrol pengguna |
|---|---|---|---|
| Kode Produk | Text, business key jika dataset benar-benar master produk | Kode perlu mempertahankan nol di depan | Pilih key/tipe dan konfirmasi keunikan |
| Nama Produk | Text, trim dan normalize whitespace | Ada spasi berlebih pada contoh yang diizinkan untuk diperiksa | Lihat before/after dan ubah aturan |
| Satuan | Referensi ke master UOM | Nilai tampak seperti kode satuan | Pilih master dan jawab padanan yang ambigu |
| Nilai | Numeric, format Indonesia jika bukti mendukung | Pemisah ribuan/desimal perlu ditafsirkan | Konfirmasi format, satuan, dan batas nilai |

Tampilkan status setiap rekomendasi: belum diperiksa, diterima, diubah pengguna, atau perlu jawaban. Nilai mentah dan rekomendasi harus dapat dibedakan. Sel sensitif tidak otomatis dikirim ke AI atau ditampilkan kepada reviewer tanpa hak akses.

## 3. Hubungan dengan semua tab template

| Tab workbook | Penempatan pada UI | Ketersediaan backend saat ini |
|---|---|---|
| 00 Petunjuk | Bantuan, ringkasan progres, indikator kelengkapan | Perlu UI; formula workbook bukan validasi server |
| 01 Sumber Sheet | Identitas file/tab dan pengaturan baca | Source/tab/range/header tersedia; timezone/locale/owner bisnis per dataset belum lengkap |
| 02 Struktur Kolom | Tabel pemetaan dan arti bisnis | Mapping, tipe dasar, nullable, key, PII, confidence/reason tersedia; domain/entity/unit/currency/format detail belum lengkap |
| 03 Aturan Cleansing | Tabel transform berurutan dengan contoh | Daftar transform terbatas tersedia; priority/condition/on_error/parameter bebas belum tersedia |
| 04 Taxonomy Mapping | Padanan nilai dan kategori baku | Registry taxonomy dan approval mapping belum tersedia |
| 05 Data Quality | Form aturan dan hasil uji | not_null/unique/min/max/allowed_values tersedia; threshold persen, in_taxonomy, max_age_days, severity/owner belum lengkap |
| 06 Target Database | Preview target/load dan panel teknis | Satu tabel trusted per tab, strategi load tersedia; multi-target, FK master, ekspresi/default/update_condition belum tersedia |
| 07 OpenAI Config | Kebijakan AI, masking, pertanyaan ambigu | Model/prompt global dan draft AI tersedia; registry task/prompt, trigger/threshold per task belum tersedia |
| 08 Operasional | Jadwal, sync, status job, audit | Cron UTC, antrean, pause/resume, audit tersedia; watermark incremental, timezone per job, notifikasi/retention per job belum tersedia |
| 09 Kamus Parameter | Help text, validasi input, daftar enum | Perlu kamus pemetaan template ke schema API |
| 10 Data Product Catalog | Ringkasan dataset untuk laporan | Product, dimensi, metric, allowed_roles tersedia; beberapa field bisnis/default periode belum tersedia |
| 11 Metric Definitions | Editor definisi hitungan | Kolom, agregasi, code/label tersedia; expression/filter/null handling/unit/sinonim/approval metric terpisah belum tersedia |
| 12 Intent Query Mapping | Contoh pertanyaan dan rencana query | Saved query dan pencocokan contoh teks tersedia; periode relatif dinamis/output type/priority/ambiguity policy belum lengkap |
| 13 Join Relationships | Review relasi dan kardinalitas | Registry join allowlist dan query multi-product belum tersedia |

Template tidak dapat diperlakukan sebagai payload API saat ini. Contoh perbedaan yang harus ditangani adapter:

- `collapse_whitespace` perlu dipetakan ke `normalize_whitespace`.
- `parse_date` dengan format bebas tidak identik dengan `parse_date_id`; hanya petakan jika semantiknya sesuai.
- `varchar(200)` dan `numeric(18,2)` tidak diterima sebagai enum `target_type` saat ini; panjang/precision tidak boleh hilang diam-diam ketika diterjemahkan.
- `analytics`/`staging` target di contoh workbook tidak sama dengan target `trusted` yang diizinkan ETLConfiguration sekarang.
- Label PII workbook `Personal`/`Financial` tidak sama dengan klasifikasi tingkat risiko NONE/LOW/MEDIUM/HIGH; minta pemetaan kebijakan, jangan konversi otomatis tanpa definisi.
- Workbook memuat status Ya/Aktif/Disetujui, sedangkan API memakai boolean/enum yang berbeda.
- `source_id` workbook seperti SRC_SALES_01 adalah kode bisnis, bukan UUID SourceSheet/Source internal.

Catat field yang tidak didukung sebagai error/pekerjaan lanjutan. Jangan membuang field saat upload lalu menampilkan pesan “semua konfigurasi tersimpan”.

## 4. Verifikasi, validasi, approval, dan deploy berbeda

**Verifikasi pengguna:** pengguna memeriksa makna rekomendasi AI. Pertanyaan seperti “Apakah kode pelanggan unik per cabang?” harus dijawab karena mengubah business key dan relasi.

**Validasi server/dry-run:** cek schema konfigurasi, referensi, versi, dan data sumber. Tampilkan jumlah baris valid/invalid, before/after, serta perubahan yang akan terjadi. Preview sampel harus diberi label sampel; jangan mengklaim seluruh baris telah diperiksa jika hanya sebagian.

**Approval:** reviewer menyetujui satu revision dengan bukti validasi tertentu. Default backend memerlukan approver terpisah dari pembuat/editor terakhir. AI tidak boleh menyetujui hasilnya sendiri. Perubahan draft setelah approval harus kembali menjadi draft/revision yang ditinjau.

**Deploy dan sync:** deploy membangun struktur/konfigurasi aktif; sync memuat data. Approval tidak boleh langsung dianggap data selesai dimuat. Kedua pekerjaan dipantau dengan job ID.

Review konfigurasi saat ini terikat revision konfigurasi, snapshot hash, serta revision/jenis klasifikasi melalui `review_state`. Perubahan draft membatalkan submission; perubahan klasifikasi membuat bukti review tidak sesuai lagi. Deployment memeriksa ulang isi sumber. Rancangan review setiap import memperluas evidence ke versi master, alias, dan policy. Pertanyaan per sel, coverage AI per snapshot baru, serta binding ke versi master belum diimplementasikan.

Tampilan akhir yang disarankan:

```text
Status: Siap diajukan review
Konfigurasi: versi 2, revision 5
Kolom: 12 sudah diperiksa
Pertanyaan wajib: 0
Dry-run: 1.000 baris valid, 0 invalid
Perubahan master: 20 penambahan diusulkan, 15 update, 965 tetap
Relasi: Produk → Master Product, Satuan → Master UOM

[Kembali mengedit] [Unduh konfigurasi] [Ajukan review]
```

Angka dan fitur pada contoh di atas adalah rancangan UI, bukan output API yang sudah tersedia. Pada akun reviewer, tampilkan approve/reject disertai komentar; setelah approve, tampilkan aksi deploy dengan status job.

## 5. Jalur Excel opsional

Jalur offline yang direkomendasikan adalah **XLSX**, mengikuti workbook pengguna:

1. Pengguna mengunduh template yang **sudah terisi draft AI**, termasuk data/aturan lama yang relevan dan daftar pertanyaan.
2. Pengguna mengedit field konfigurasi yang diperbolehkan. Metadata seperti tenant, source/tab ID, config ID, revision, schema version, dan snapshot reference dipertahankan sebagai identitas dokumen.
3. Upload masuk tahap **parse dan preview perubahan**, belum mengubah konfigurasi aktif.
4. Server mencocokkan identitas terhadap user/tenant dan registry; metadata tersembunyi/protected cell tidak dianggap bukti keaslian atau izin.
5. Server menolak struktur tidak dikenal, field unsupported, formula pada sel input parameter, atau nilai yang tidak lolos schema. Formula ringkasan bawaan hanya untuk tampilan; server menghitung ulang hasil validasinya sendiri.
6. Tampilkan diff Excel terhadap draft backend, error per tab/baris/kolom, dan pertanyaan yang masih terbuka.
7. Pengguna menerima perubahan yang valid ke draft, lalu menjalani dry-run dan approval aplikasi seperti jalur form.

Jika revision backend berubah sejak download, jangan menimpa draft terbaru. Tampilkan konflik dan minta pengguna memuat ulang atau menggabungkan perubahan dengan preview yang eksplisit. Upload file yang sama tidak boleh menggandakan konfigurasi/aturan.

Tulisan `Approved`, `Aktif`, atau nama approver di Excel tidak boleh mengaktifkan konfigurasi; keputusan approval berasal dari akun aplikasi yang mempunyai hak. Import tidak boleh mengeksekusi SQL/regex/ekspresi bebas dari workbook sebagai kode. Operasi transform harus berasal dari registry yang diizinkan.

Semua tab, hubungan ID, serta bagian task dan prompt pada tab 07 harus dipertahankan saat ekspor template. Jangan mengganti workbook lengkap dengan satu sheet JSON lalu menyebutnya kompatibel dengan template.

## 6. API yang tersedia dan tambahan yang diperlukan

### Dapat dipakai sekarang untuk form subset konfigurasi

- `POST /sources/{source_id}/ai-configurations` → antrekan draft AI.
- `GET /jobs/{job_id}` → pantau hasil dan ambil configuration_id.
- `GET /configurations/{id}` → isi form dari configuration_json.
- `GET /configurations/{id}/questions` → daftar pertanyaan berupa teks.
- `PATCH /configurations/{id}` → kirim revision_no dan objek configuration lengkap.
- `POST /configurations/{id}/validate` → hasil dry-run.
- `POST /configurations/{id}/submit-review` → ajukan review.
- `POST /configurations/{id}/approve` atau `/reject` → revision_no dan komentar.
- `POST /configurations/{id}/deploy` → antrekan aktivasi.
- `POST /sources/{source_id}/sync` → antrekan pemuatan data.

Path di atas relatif terhadap `/api/v1`; detail payload dan respons ada di [API Reference](API_REFERENCE.md).

### Belum tersedia

- Seluruh parameter template yang ditandai belum tersedia pada tabel pemetaan.
- Status penerimaan rekomendasi dan pertanyaan/jawaban terstruktur per field/baris.

Export XLSX sekarang mempertahankan seluruh tab template dan mengisi parameter runtime yang didukung. `workbook-preview` memvalidasi perubahan tanpa menyimpan; `workbook-apply` menyimpan draft setelah preview diterima. Konflik revision/snapshot meminta unduh atau preview ulang; tidak ada merge otomatis. Bukti review per bagian/kolom dan jawaban pertanyaan tersimpan pada `review_state`.

## 7. Urutan pengembangan

1. Sepakati kamus parameter kanonis dengan mempertahankan seluruh cakupan template; nyatakan field yang belum didukung secara eksplisit.
2. Bangun wizard Vue menggunakan subset endpoint yang sudah ada; lengkapi registry master dan reference sebelum menjanjikan FK/padanan master.
3. Perluas schema dan service secara bertahap untuk taxonomy, kebijakan AI, operasional, metric, dan relationships; setiap bagian memiliki validasi dan status review.
4. Tambahkan preview before/after dan pertanyaan terstruktur dengan revision/evidence.
5. Tambahkan export template terisi serta import-preview XLSX yang memakai schema dan validator yang sama dengan form.
6. Uji kesetaraan form ↔ XLSX, tidak ada parameter hilang, konflik revision, tenant isolation, formula input, dan approval tidak bisa dipalsukan melalui workbook.

Jalur form utama dan XLSX tambahan sudah tersedia untuk subset runtime. Urutan di atas tetap menjadi acuan perluasan parameter; registry master, taxonomy, dan relasi belum termasuk implementasi ini.
