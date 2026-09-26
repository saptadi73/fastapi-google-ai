# BE14 tahap 1: metadata bisnis produk

PATCH `/api/v1/semantic/data-products/{product_id}` tetap untuk PLATFORM_ADMIN dan
DATA_STEWARD, memakai lookup tenant dan row lock existing. Payload tambahan:

```json
{"name":"Penjualan cabang","description":"Nilai penjualan setelah retur","expected_version":3}
```

`name` opsional, 1..200 karakter, di-trim dan tidak boleh blank/null.
`description` opsional, maksimal 4000 karakter; string kosong menghapus deskripsi,
null ditolak. Pengiriman salah satu field metadata mewajibkan `expected_version`
integer positif. Schema invalid menghasilkan 422. Field omitted tidak diubah.
Request lama yang hanya mengubah allowed_roles/status tetap kompatibel; client baru
dapat mengirim expected_version untuk pemeriksaan konflik pada update tersebut juga.

Backend membandingkan versi setelah lock. Mismatch menghasilkan
`PRODUCT_VERSION_CONFLICT` (409), tanpa perubahan atau audit sukses. Frontend
mempertahankan edit lokal, menahan submit ulang, dan menyediakan reload eksplisit.
Sukses mengembalikan DataProduct, menaikkan version dan mencatat nama field yang
diubah serta versi semantic baru di audit. expected_version tidak disimpan.

Template existing dengan semantic_version lama akan menghasilkan TEMPLATE_STALE
sampai divalidasi dan diaktifkan ulang. Cache query memakai versi produk existing.
Perubahan ini tidak mengubah SQL, dimensi, metrik, tenant scope, row scope atau PII.
Deployment konfigurasi berikutnya tetap mengisi nama/deskripsi dari konfigurasi ETL;
edit katalog ini bukan override permanen terhadap konfigurasi sumber.

Frontend: Dashboard → pilih produk → Edit metadata bisnis produk. Hanya role data
yang melihat editor. Request lama frontend tetap kompatibel; editor baru memerlukan
backend tahap ini terlebih dahulu. Tidak ada migrasi database.

Tahap 1 belum mencakup unit/sinonim (ditambahkan pada tahap 2 di bawah), default periode, approval metrik, expression AST,
template berparameter, atau query join multi-product. BE14 masih berlangsung. Registry join metadata
tersedia melalui API semantic, tetapi belum menjadi izin eksekusi query.
Tes service/schema dan browser memakai mock; bukan bukti konkurensi PostgreSQL nyata.

## Tahap 2: unit dan sinonim metrik

Endpoint PATCH yang sama menerima `metric_metadata`, daftar 1..100 edit berdasarkan
kode metrik existing. expected_version wajib. Contoh:

```json
{"expected_version":4,"metric_metadata":[{"code":"net_sales","unit":"IDR","synonyms":["Pendapatan bersih","Net revenue"]}]}
```

Setiap entri wajib menyertakan unit atau synonyms. Unit nullable maksimal 40 karakter,
di-trim; kosong/null menghapus unit. Synonyms maksimal 20 string nonblank, masing-masing
100 karakter; whitespace dinormalisasi dan duplikasi case-insensitive ditolak.
`synonyms: []` menghapus sinonim. Field omitted dipertahankan. Kode entri tidak boleh
berulang. Column, aggregation, expression, dan kode metrik tidak dapat diedit lewat
payload ini. Unknown code menghasilkan METRIC_NOT_FOUND (422). Sinonim yang sama
dengan kode/label/sinonim metrik lain dalam produk menghasilkan METRIC_SYNONYM_CONFLICT
(422). Seluruh validasi selesai sebelum metadata produk dimutasi.

Metadata tersimpan pada JSON metrics existing, tanpa migrasi. Respons katalog produk
dan `/semantic/metrics` menampilkan unit/synonyms; konteks katalog NL2SQL existing ikut
memuatnya. Tidak ada pemilihan metrik otomatis berdasarkan sinonim: QueryPlan tetap
menerima kode metrik resmi saja. Unit merupakan label, bukan konversi nilai/currency.
Query compiler mengizinkan metadata synonyms tanpa mengubah perhitungan atau scope.

Frontend menyediakan input unit dan sinonim per metrik di editor metadata produk.
Hanya metrik yang berubah dikirim, tanpa column/aggregation. Label unit/sinonim juga
terlihat di katalog dashboard untuk pengguna berizin. Konflik versi memakai recovery
tahap 1. Metadata ini ikut diganti dari konfigurasi ketika redeploy ETL, sehingga
belum menjadi override permanen atau lifecycle approval metrik.

Verifikasi tahap 2: 36 tes backend schema/service/query lulus. Tes browser memakai
mock untuk payload, duplicate input, penghapusan, serta akses viewer; provider NL2SQL
dan konkurensi PostgreSQL nyata belum diverifikasi.

Editor unit/sinonim tahap 2 hanya pada katalog produk; parameter konfigurasi ETL dan
workbook belum diperluas untuk menyimpan metadata tersebut.

## Tahap 3: null handling metrik melalui konfigurasi ETL

`configuration.semantic.metrics[].null_handling` menerima `PRESERVE` (default) atau
`ZERO_RESULT`. Pilihan disimpan lewat PATCH konfigurasi lengkap dan melewati alur
validasi, review/approval serta deployment existing sebelum memengaruhi produk aktif.
Endpoint metadata produk tahap 2 tidak menerima field ini.

PRESERVE mempertahankan perilaku SQL: SUM/AVG/MIN/MAX dari input seluruhnya null atau
tanpa baris menghasilkan null, COUNT tetap 0. ZERO_RESULT membungkus hasil agregat
dengan COALESCE(aggregate(column), 0). Input null tidak diubah menjadi 0 sebelum AVG.
Hanya hasil numeric yang diperbolehkan: sum/avg/min/max atas integer/bigint/numeric,
atau count/count_distinct atas tipe kolom yang didukung. MIN/MAX teks/tanggal dengan
ZERO_RESULT ditolak schema; catalog invalid ditolak SEMANTIC_METRIC_INVALID (422).
GROUP BY tidak menciptakan kelompok yang tidak punya baris. Filter tenant/row scope,
sorting, pagination, dan limit tetap dipakai. Tidak ada SQL atau expression bebas.

Frontend: Konfigurasi ETL → Analitik & akses → Hasil agregat null. Validasi frontend
menahan konfigurasi hasil nonnumeric; backend tetap sumber validasi. Konfigurasi dan
katalog lama tanpa field ini mempertahankan perilaku PRESERVE. Parameter catalog
menandai semantic.metrics.null_handling supported. Tidak ada migrasi database.

Pada tahap 3, workbook belum menyediakan sel editable null handling (editor tersedia mulai tahap 4 di bawah). Export/import lama mempertahankan
policy konfigurasi server untuk kode metrik yang sama; kode baru/yang diganti memakai
PRESERVE. Pengguna mengatur policy melalui editor konfigurasi lalu menyimpan draft
sebelum export XLSX. Perubahan kolom/agregasi di workbook tetap divalidasi terhadap policy.

Tes compiler menjalankan SQL terstruktur di SQLite terisolasi dan memeriksa guard SQL
PostgreSQL, termasuk null/empty, AVG, tenant/row scope dan default lama. Ini bukan bukti
eksekusi atau konkurensi PostgreSQL nyata. Expression AST, default periode, approval
registry metrik terpisah, dan join masih terbuka.

Bukti tahap 3: 42 tes schema/service/query, 12 tes workbook, 3 tes browser mock,
build/type-check frontend, Ruff pada file perubahan, dan exporter --check 152 operasi
lulus. Tidak ada migrasi/deployment atau integrasi provider nyata yang dijalankan.

## Tahap 4: editor null handling di XLSX

Workbook export terbaru mengaktifkan tab **11 Metric Definitions**, kolom **M**
(`null_handling`), baris 5..204. Pilih PRESERVE atau ZERO_RESULT; sel kosong pada
format baru berarti PRESERVE. ZERO_RESULT tetap dibatasi hasil numerik dan melalui
validasi konfigurasi. Tab 12/13, expression bebas, serta approval Excel tetap tidak aktif.

Export menyertakan marker `metric_null_editor=1` dalam token bertanda tangan.
Workbook lama tanpa marker tetap mempertahankan policy konfigurasi berdasarkan
kode metrik. Kolom M yang diisi pada workbook lama ditolak dengan arahan mengunduh
format terbaru. Header saja tidak mengaktifkan fitur. Formula/error Excel, enum
asing, tipe nonnumeric, serta sel M pada baris tanpa definisi lengkap ditolak.

Frontend memakai alur download ? upload preview ? tinjau diff ? simpan draft.
Payload apply tetap memakai configuration dan preview_token dari preview yang sama;
tidak mengirim approval/deployment otomatis. Panduan kolom M tampil di panel Excel.
Untuk mengedit field ini, unduh workbook baru dari backend tahap 4 terlebih dahulu.
Tidak ada perubahan endpoint, payload apply, atau migrasi database.

Verifikasi tahap 4: 4 tes backend terarah (termasuk round-trip XLSX serialized dan
kompatibilitas lama), 2 tes browser mock, build/type-check, Ruff, serta pemeriksaan
152 operasi API lulus. Tes browser tidak menjalankan backend atau provider nyata.

## Tahap 5: klarifikasi template yang ambigu

Jika pertanyaan cocok persis setelah normalisasi dengan lebih dari satu contoh
query template ACTIVE, backend mengembalikan klarifikasi tanpa memanggil AI atau
mengeksekusi query. Pencarian dilakukan di database, dengan tenant scope, status
ACTIVE dan izin role pada template serta produk. Tidak dibatasi daftar awal 1000
registry template. Hasil diurutkan menurut kode, maksimal 20 kandidat:

```json
{"data":[],"meta":{"query_id":"uuid","clarification_required":true,"question":"Pilih template yang dimaksud.","route":"CLARIFICATION","openai_called":false,"template_candidates":[{"code":"daily_sales","data_product_code":"SALES"},{"code":"monthly_sales","data_product_code":"SALES"}],"template_candidates_more":false}}
```

`template_candidates_more=true` berarti daftar dipotong; pilih produk atau perjelas
pertanyaan. Kandidat hanya memuat kode template/produk, tanpa plan, examples atau data.
Policy tahap ini selalu meminta pilihan, belum mendukung prioritas otomatis.

Frontend Chat menampilkan tombol pilihan. Memilih mengisi pertanyaan asli, produk dan
saved_query_code; belum mengirim query. Tombol Kirim klarifikasi mengirim QuestionRequest
lengkap ke `/nl2sql/clarifications/{query_id}`. Perubahan pertanyaan/produk membuang
pilihan template; response baru/sesi baru juga membuang pilihan. Klarifikasi generik
existing tetap bekerja tanpa saved_query_code.

Pilihan eksplisit diperiksa ulang lewat saved-query lookup: template/produk harus
masih aktif dan diizinkan, semantic_version harus current. TEMPLATE_STALE tetap
memerlukan validasi/aktivasi ulang; kandidat bukan jaminan kesiapan eksekusi. Jika
saved_query_code dan data_product_code berbeda produk, respons
SAVED_QUERY_PRODUCT_MISMATCH (422), tanpa eksekusi. Satu template cocok tetap memakai
INTENT_TEMPLATE; tidak ada kecocokan tetap mengikuti alur AI existing.

Tidak ada migrasi atau endpoint baru pada tahap klarifikasi. Periode relatif, parameter template, prioritas,
expression AST, dan query join multi-product masih terbuka. Registry relationship tersedia
terpisah dari compiler. Tes service/SQL compilation dan
browser menggunakan mock; bukan bukti integrasi PostgreSQL/provider nyata.

## Tahap 6: metadata metrik dalam konfigurasi dan workbook

`configuration.semantic.metrics[]` sekarang menerima `description` (default string
kosong, maksimal 1000 karakter), `unit` (nullable, maksimal 40 karakter), dan
`synonyms` (maksimal 20 string, masing-masing 1..100 karakter). Label dibatasi 200
karakter. Whitespace label, description, dan sinonim dinormalisasi; unit di-trim dan
string kosong menjadi null. Sinonim harus unik tanpa membedakan kapital. Kode, label,
atau sinonim yang sama dengan istilah milik metrik lain dalam satu produk ditolak.

Field tersebut disimpan lewat PATCH konfigurasi lengkap sehingga ikut revision,
validasi, review/approval, deployment, audit, dan semantic version existing. Deployment
mengisi JSON metrics pada DataProduct; perubahan katalog langsung dari tahap 2 dapat
ditimpa oleh deployment konfigurasi berikutnya. Tidak ada migrasi database dan tidak
ada perubahan cara perhitungan SQL. Unit tetap metadata tampilan, bukan konversi.

Frontend Konfigurasi ETL â†’ Analitik & akses menyediakan definisi bisnis, unit, dan
sinonim satu per baris. Normalisasi dan konflik diperiksa sebelum PATCH; backend tetap
sumber validasi. Metrik lama memperoleh default kompatibel saat konfigurasi dimuat.

Workbook baru mengaktifkan tab **11 Metric Definitions** kolom C (`business_definition`),
D (`synonyms` sebagai array JSON), dan K (`unit`) pada baris 5..204. Token export
menyertakan marker `metric_metadata_editor=1`. Workbook lama tanpa marker mempertahankan
metadata konfigurasi berdasarkan kode; isi baru pada C/D/K ditolak dan pengguna harus
mengunduh ulang workbook. Preview/apply tetap hanya menyimpan draft dan tidak memberi
approval otomatis.

Bukti tahap 6: schema/normalisasi/konflik dan kompatibilitas workbook diuji di backend;
editor, persistensi, serta konflik diuji di browser mock. Typecheck dan build produksi
frontend lulus. Integrasi PostgreSQL/provider nyata dan rollout tetap terpisah.

## Tahap 7: default periode metrik

`configuration.semantic.metrics[].default_period` menerima object
`{"dimension":"transaction_date","days":30}` atau null. Dimension wajib termasuk
semantic dimensions, berasal dari kolom publik bertipe date/timestamp/timestamptz;
days wajib integer 1..3660. Field mengikuti revision, review/approval dan deployment.

Saat sebuah metrik dipilih dan QueryPlan tidak mempunyai filter pada dimension tersebut,
compiler menambahkan rentang inklusif sejumlah hari sampai tanggal UTC saat query.
Untuk timestamp/timestamptz, batas akhir memakai awal hari UTC berikutnya secara
eksklusif agar seluruh hari terakhir tercakup. Filter eksplisit pada dimension yang sama
menonaktifkan default. Default berbeda dari beberapa metrik menghasilkan
`QUERY_DEFAULT_PERIOD_CONFLICT` (422) dan meminta filter tanggal eksplisit. Nilai
resolved masuk cache key serta `meta.default_period_applied`; null berarti tidak dipakai.

Frontend menyediakan pilihan dimensi periode dan jumlah hari pada editor metrik.
Workbook baru memakai tab 11 kolom I (`date_column`) dan J (`default_period`, integer
hari), dengan marker signed `metric_default_period_editor=1`. Workbook lama tanpa marker
mempertahankan konfigurasi server dan menolak isian I/J baru. Tidak ada migrasi.

## Tahap 8: filter tetap metrik

`configuration.semantic.metrics[].filters` menerima maksimal 10 predicate terstruktur:
`field`, operator `eq|in|between|gte|lte|gt|lt`, dan value scalar atau array sesuai
operator. `in` menerima 1..100 nilai dan `between` tepat dua. Field wajib mapped public;
nilai dicast terhadap tipe kolom saat validasi konfigurasi. Key tambahan, operator asing,
field sensitif/tidak dikenal, tipe salah, serta SQL/expression bebas ditolak.

Compiler menerapkan setiap predicate sebagai SQL aggregate `FILTER (WHERE ...)`.
Artinya filter hanya memengaruhi agregat metrik tersebut; tenant scope, row scope, filter
QueryPlan, grouping, pagination, dan limit tetap diterapkan pada query utama. Filter
tersimpan melalui revision, review/approval dan deployment existing.

Frontend menyediakan editor field/operator/value. Nilai string dapat ditulis langsung;
angka, boolean, `in`, dan `between` memakai JSON scalar/array. Workbook terbaru memakai
tab 11 kolom H (`filter_expression`) berupa array JSON dan marker signed
`metric_filter_editor=1`. Workbook lama mempertahankan filter server dan menolak isian
H baru. Tidak ada migrasi; AST arithmetic/expression metrik masih belum tersedia.

## Tahap 9: spesifikasi visualisasi tervalidasi

QueryPlan menerima `visualization` nullable dengan type allowlist `table`, `kpi`, `bar`,
`line`, `area`, `pie`, `donut`, `combo`, `scatter`, atau `heatmap`; title maksimal 200,
`x_field`/`y_field`, dan maksimal 10 series `{field,type,axis}`. Series hanya boleh
memakai metric yang dipilih QueryPlan, sedangkan axis field hanya boleh memakai
dimension yang dipilih. Key opsi library, formatter, HTML, script, warna, dan field
di luar output ditolak oleh strict schema.

Aturan bentuk: KPI satu metric tanpa dimension; pie/donut satu metric dan satu
dimension; bar/line/area minimal satu metric dan satu dimension; combo minimal dua
metric dan satu dimension; scatter tepat dua metric; heatmap satu metric dan dua
dimension berbeda; table tidak menerima field chart. Visualisasi tidak ikut kompilasi
SQL dan dikeluarkan dari cache key hasil data, sehingga pergantian chart tidak mengubah
query, scope, biaya database, atau cache result. Respons query mengembalikan spec pada
`meta.visualization`; saved query menyimpannya bersama plan.

Dashboard dan Chat merender spec serta menyediakan override manual. Renderer membatasi
grafik ke 100 baris halaman hasil dan tabel tetap ditampilkan sebagai sumber detail.
Pilihan manual dapat disimpan bersama template. AI boleh memilih spec allowlist dalam
plan, tetapi tidak dapat mengirim opsi ApexCharts bebas. Tidak ada migrasi database.
