# Panduan implementasi frontend BE-12

Acuan kode workspace pada 9 September 2026, schema konfigurasi `1.0`. Perubahan belum
berarti sudah terdeploy pada environment frontend. Semua path di bawah relatif
terhadap `/api/v1`; gunakan Bearer token dan envelope API existing.

## Mulai dari sini

1. Ambil `GET /configurations/parameter-catalog` dan konfigurasi/revision dari `GET /configurations/{id}`.
2. Edit objek `configuration_json` lengkap; simpan seluruh field yang tidak diedit.
3. Simpan lewat PATCH, lalu POST validate untuk menampilkan preview dan temuan.
4. Ajukan review memakai revision terbaru dan snapshot_hash hasil validasi; approval/deploy tetap alur existing.
5. Untuk import data per batch gunakan alur `sync-review`/import review existing. Menyimpan konfigurasi atau workbook tidak melakukan apply data.

Bahan yang bisa langsung dipakai:

- [Payload PATCH lengkap: currency, unit, DQ](api/BE12_FRONTEND_PAYLOADS.json). Setiap nilai teratas adalah body PATCH, bukan body wrapper yang dikirim sekaligus. Ganti revision_no dengan nilai aktual.
- [Snapshot respons catalog aktual](api/BE12_PARAMETER_CATALOG.json), diambil dari fungsi endpoint workspace. Environment tujuan tetap harus dicek melalui endpoint.
- [Schema field lengkap dan enum](api/SCHEMAS.md), [OpenAPI](api/openapi.json), [payload endpoint existing](api/PAYLOADS.json).
- [Konfigurasi demo currency + timezone](../examples/be12-currency-configuration.json): objek ETLConfiguration tanpa wrapper PATCH/POST, kurs sintetis.
- [Alur review konfigurasi](PANDUAN_REVIEW_ETL.md), [batch review](IMPORT_REVIEW_BE05.md), [pertanyaan batch](IMPORT_QUESTIONS_BE06.md).

## Endpoint, izin, dan tindakan UI

Editor: PLATFORM_ADMIN, SOURCE_OWNER, DATA_STEWARD. Reviewer: PLATFORM_ADMIN,
TECHNICAL_APPROVER. Endpoint konfigurasi mensyaratkan salah satu kelompok tersebut;
ANALYST/VIEWER tidak dapat mengedit ataupun membaca catalog konfigurasi melalui router ini.

| Metode dan path | Body | Hasil / tindakan |
|---|---|---|
| GET /configurations/parameter-catalog | Tidak ada | `data.parameters`, `data.operations`, `data.capabilities` |
| GET /configurations/{id} | Tidak ada | Record berisi `configuration_json`, `revision_no`, `status` |
| POST /configurations | `source_sheet_id`, `configuration` lengkap | 201, record draft; editor |
| PATCH /configurations/{id} | `revision_no`, `configuration` lengkap, `question_answers` (default `{}`) | 200, record revisi baru; editor |
| POST /configurations/{id}/validate | Tidak ada | 200 dengan objek validasi atau HTTP error |
| GET /configurations/{id}/review | Tidak ada | Konteks konfigurasi, sumber, snapshot/validasi dan capabilities |
| POST /configurations/{id}/submit-review | ReviewSubmission existing | Editor; revision/snapshot/checklist wajib cocok |
| POST /configurations/{id}/approve | `revision_no`, `comment` | Reviewer; tetap tunduk separation of duties |
| POST /configurations/{id}/deploy | Tidak ada | 202, job; reviewer; bukan apply batch data |
| POST /configurations/{id}/clone | Tidak ada | 201, draft baru; editor |
| POST /configurations/{id}/export | `format`: JSON/YAML/XLSX | 201, metadata artifact; lalu download |
| GET /configurations/{id}/artifacts/{artifact_id}/download | Tidak ada | Binary/file, bukan envelope sukses |
| POST /configurations/{id}/workbook-preview | `content_base64` | 200, hasil parse, validation, diff, token; editor |
| POST /configurations/{id}/workbook-apply | `revision_no`, `configuration`, `question_answers`, `preview_token` | Menyimpan draft; editor |

PATCH bukan partial JSON patch: mengirim hanya kolom yang diedit akan mengganti daftar
kolom keseluruhan. Gunakan record terbaru sebagai dasar. Draft yang dapat diedit
berstatus AI_DRAFT atau NEEDS_REVIEW; konfigurasi immutable harus di-clone.

## Mapping catalog ke payload

Catalog adalah daftar kemampuan, bukan daftar key yang semuanya boleh dikirim.
`parameter_schema` pada conversion adalah JSON Schema; operasi convert_unit/currency
bukan anggota `transformation_codes`. UI harus melakukan mapping berikut.

| Nama catalog | Path payload configuration | Catatan |
|---|---|---|
| number_format | columns[i].number_locale | ID/US; default runtime ID; bukan `number_format` |
| numeric_precision_scale | columns[i].numeric_precision dan numeric_scale | Dua integer terpisah |
| date_format | columns[i].date_format | Pakai pola strptime, bukan literal default catalog `ISO-8601` |
| source_timezone | columns[i].source_timezone | Nama zona IANA, bukan key `timezone` |
| varchar_length | columns[i].varchar_length | Integer nullable |
| unit_conversion | columns[i].unit_conversion | Objek nullable |
| currency_conversion | columns[i].currency_conversion | Objek nullable |
| dq_threshold_percent | data_quality_rules[i].threshold_percent | Persentase per rule |
| dq_format | data_quality_rules[i].rule=`format`, value | UUID/ISO_DATE/ISO_DATETIME |
| dq_domain | data_quality_rules[i].rule=`allowed_values`, value | Array string eksplisit |
| dq_max_age_days | data_quality_rules[i].rule=`max_age_days`, max_age_days | Parameter wajib untuk rule ini saja |
| dq_default_value | data_quality_rules[i].default_value | Scalar target |
| dq_severity_owner | data_quality_rules[i].severity dan owner | Metadata, tidak mengubah action |
| effective_dating | Policy master terpisah | Jangan kirim pada ETLConfiguration; versi eksplisit tersedia; lihat panduan effective dating |

`operations` bukan daftar lengkap semua transform string; daftar string yang valid
ada pada `transformation_codes.allowed`/schema. `capabilities.unsupported` masih
memiliki label umum seperti master/taxonomy yang tidak mewakili seluruh endpoint
registry saat ini. Untuk form BE-12 gunakan mapping di atas, schema, dan scope
parameter; jangan menjadikan label capability umum sebagai izin mengirim field baru.

## Field kolom dan validasi form

Field opsional berikut default null. Kirim null untuk mematikan parameter; jangan
mengirim string kosong pada input angka atau objek conversion.

| Field | Batas/ketergantungan |
|---|---|
| numeric_precision | Integer 1..100; hanya numeric |
| numeric_scale | Integer 0..50, wajib precision, tidak boleh lebih besar dari precision; precision tanpa scale berarti 0 |
| varchar_length | Integer 1..10485760; hanya text/varchar; jumlah karakter, bukan byte |
| date_format | String maksimal 40; memerlukan parse_date_id; contoh `%d/%m/%Y` |
| number_locale | ID atau US; memerlukan parse_decimal_id |
| source_timezone | String 1..100, zona IANA valid; hanya timestamptz, tidak boleh parse_date_id |
| unit_conversion | Hanya numeric non-business-key/non-primary-key; tidak bersama currency_conversion |
| currency_conversion | Hanya numeric non-business-key/non-primary-key; tidak bersama unit_conversion |

Transform berjalan berurutan sesuai array. `parse_date_id` default mencoba
`%d/%m/%Y`, `%d-%m-%Y`, `%Y-%m-%d`; angka serial tanggal juga diterima. Pola invalid
atau tidak cocok terlihat sebagai masalah runtime, tidak selalu ditolak saat menyimpan
schema. Locale ID menerima `1.234,56`; locale US saat ini menerima `1234.56`,
belum menerima grouping `1,234.56`. Ini bukan currency autodetection.

Timestamptz naive memakai source_timezone; ber-offset memakai offset input. Hasil
UTC. DST gap/overlap ditolak, arahkan pengguna memperbaiki timestamp sumber dengan
offset eksplisit. Tanpa source_timezone, timestamptz naive ditolak. Timestamp biasa
tetap tanpa zona. Tidak ada endpoint daftar timezone baru: validasi server tetap otoritatif.

## Form konversi

| Parameter | Unit | Currency |
|---|---|---|
| Asal/tujuan | from_unit / to_unit | from_currency / to_currency |
| Pengali | factor, decimal positif, max_digits 20 / decimal_places 12 | rate, decimal positif finite, max_digits 30 / decimal_places 18 |
| Referensi | Faktor harus sama dengan rasio unit server | rate_date YYYY-MM-DD dan rate_reference nonblank, maksimal 500 |
| output_scale | Wajib integer 0..50 | Wajib integer 0..50 |
| rounding | Wajib HALF_UP/HALF_EVEN/DOWN | Sama |
| on_error | REJECT_ROW saja; default REJECT_ROW | Sama |

Kirim factor/rate sebagai string decimal agar tidak kehilangan presisi JavaScript.
Response konfigurasi juga menyerialisasi Decimal sebagai string. Jangan otomatis
menghitung nominal dengan Number untuk menggantikan preview backend.

Unit: massa T/KG/G/MG, volume L/ML, panjang M/CM/MM. Asal/tujuan berbeda dan satu
dimensi; contoh KG ke G factor `1000`, G ke KG `0.001`. Currency: IDR/USD/EUR/SGD/JPY/THB,
pasangan berbeda. `1 from_currency * rate = to_currency`. Kurs tidak dicek ke provider;
rate_date hanya metadata, bukan filter transaksi atau pemilih kurs otomatis. Semua
baris pada kolom diasumsikan satu currency asal.

Jika numeric_precision diisi, numeric_scale efektif harus sama dengan output_scale.
HALF_UP membulatkan tie menjauhi nol, HALF_EVEN ke digit genap, DOWN menuju nol.
Tidak ada asumsi minor unit otomatis per currency. Perubahan pasangan unit/currency
pada target berisi data perlu keputusan migrasi bisnis; parameter ini tidak mengubah
ulang record yang sudah tersimpan.

## DQ dan urutan eksekusi

Urutan: transform sumber -> default untuk nilai kosong/null yang tersisa -> cast /
timezone -> conversion dan rounding -> batas precision/varchar/nullability -> DQ ->
cek duplicate key. Default adalah nilai target: tidak ditransform atau dikonversi lagi.
Default timestamptz wajib ber-offset. Bila transform parse sudah gagal pada string
kosong, default tidak dijalankan: susun `null_if_empty` sebelum transform parsing
untuk kasus tersebut. Default berbeda untuk kolom yang sama ditolak.

| Rule | Parameter value | Null / kegagalan |
|---|---|---|
| not_null | Tidak diperlukan | Null gagal |
| unique | Tidak diperlukan | Nilai berulang gagal; null kedua juga gagal |
| min / max | Angka | Null dilewati; nilai nonnumeric gagal pemeriksaan |
| allowed_values | Array string | Membandingkan representasi string runtime; null tidak otomatis dilewati |
| format | UUID/ISO_DATE/ISO_DATETIME | Null dilewati; gunakan not_null bila wajib |
| max_age_days | Pakai field max_age_days 0..36500, bukan value | Kolom date/timestamp/timestamptz saja; null dilewati |

Field lintas rule: action_on_fail default REJECT_ROW; severity INFO/WARN/ERROR/CRITICAL
(default ERROR); owner string nullable max 100; threshold_percent nullable 0..100;
default_value string/number/boolean/null. Owner belum memiliki lookup/assignment atau
notifikasi otomatis. Severity tidak menggantikan action_on_fail.

Threshold = gagal/terevaluasi per indeks rule, hanya baris yang lolos tipe/null.
Melebihi batas menghentikan batch, termasuk rule WARN; sama dengan batas diterima.
Nol baris terevaluasi tidak melanggar. Threshold tidak memberi toleransi agar baris
REJECT_ROW masuk target. STOP_BATCH/REQUIRE_REVIEW menghentikan segera, sebelum
perhitungan akhir threshold. Umur memakai waktu UTC evaluasi; batas inklusif;
tanggal masa depan tidak gagal max_age_days. Timestamp tanpa zona dianggap UTC.

## Preview, error, dan state UI

POST validate menghasilkan `data.valid`, `ready_for_review`, `sample_rows_valid`,
`sample_rows_invalid`, `warnings` (maksimal 20), `issues` (maksimal 50),
`row_previews` (maksimal 10 baris valid), `snapshot_hash`, `snapshot_id`,
`unresolved_questions`, `classification`, `deployment_plan`. Angka sample menghitung
snapshot yang dievaluasi; array temuan/preview dibatasi. Jangan menyimpulkan tidak ada
masalah hanya dari preview valid. Field sensitif bisa berisi `[REDACTED]`.

Temuan DQ dalam warnings/errors menyertakan column, code, rule_index (zero-based),
severity, owner. Error tipe hanya column/code, tanpa jaminan metadata rule. Normalisasi
angka/timestamp pada preview dapat berbeda dari input mentah; gunakan nilai backend.

| Kondisi/kode | Lokasi | Tindakan frontend |
|---|---|---|
| VALIDATION_ERROR, HTTP 422 | errors[].details[].field/message | Tampilkan error field atau form; validasi lintas field bisa muncul di root |
| TYPE_OR_NULL_ERROR | data.issues[].errors[] pada validate sukses | Tampilkan baris/kolom; mencakup parse, timezone, overflow, null, panjang teks |
| DQ_THRESHOLD_EXCEEDED | HTTP 422 pada validate | Blok submit dan tampilkan pesan; bukan sekadar warning |
| DQ_STOP_BATCH / DQ_REQUIRE_REVIEW | HTTP 422 pada validate | Tampilkan blocker; jangan menganggap otomatis ada pertanyaan batch dari validate konfigurasi |
| CONFIGURATION_CONFLICT, HTTP 409 | Envelope error | Reload revision/state; jangan retry PATCH revision lama |
| PROFILE_REQUIRED / REVIEW_STALE, HTTP 409 | Envelope error | Profile/validate ulang dan perbarui snapshot review |
| CONFIGURATION_IMMUTABLE, HTTP 409 | Workbook pada non-draft | Clone draft |
| WORKBOOK_PREVIEW_STALE / WORKBOOK_TOKEN_INVALID, HTTP 409 | Workbook apply | Preview ulang, termasuk saat token kedaluwarsa |
| SCHEMA_CHANGE_UNSAFE | Deployment/job | Tampilkan kebutuhan migrasi; jangan menyatakan ukuran kolom berubah hanya karena draft tersimpan |

`data.valid` dapat false pada HTTP 200. `ready_for_review` juga memeriksa klasifikasi.
Pada GET review, kegagalan validasi dapat dibungkus dalam `data.validation.errors`.
Pada workbook-preview, parse/validasi error ada di `data.errors` dengan location/message
(dan kadang code), bukan harus HTTP error. `can_apply=true` berarti kandidat boleh
disimpan menjadi draft, bukan `validation.valid=true`, approved, deployed, atau data loaded.

## Workbook dan artifact

| Tab | Kolom editable tambahan BE-12 |
|---|---|
| 02 Struktur Kolom | U numeric_precision; V numeric_scale; W varchar_length; X date_format; Y number_locale; Z unit_conversion_json; AA source_timezone; AB currency_conversion_json |
| 05 Data Quality | G severity; J threshold_percent; K owner; O max_age_days; P default_value_json |

Z/AB adalah JSON object atau null; P JSON scalar (contoh `0`, `false`, `"0"`, `null`).
J dan O harus menjaga angka nol, jangan diubah menjadi null dengan pemeriksaan falsy.
Download XLSX baru dari backend; jangan memakai template lama untuk menambahkan kolom
secara manual karena sel identitas/read-only ditandatangani. Formula di sel editable
juga ditolak. Upload base64 tanpa prefix data URL, maksimum file 2 MB; token preview
berlaku 15 menit dan terikat pengguna, konfigurasi, snapshot, serta kandidat.

Simpan hasil `configuration`, `question_answers`, `revision_no`, `preview_token` dari
preview; kirim kandidat yang sama pada workbook-apply. Jika pengguna mengubah kandidat,
lakukan preview lagi. Setelah apply, gunakan revision pada respons. Export JSON/YAML
atau XLSX tidak mengubah status approval.

## Batas yang masih perlu ditampilkan

- Belum ada currency provider live, kurs historis otomatis, currency campuran per baris, custom unit atau konversi lintas dimensi.
- Belum ada general locale, metadata entity/domain baru pada ColumnMapping, transform expression bebas, kondisi dinamis, multi-target atau schema evolution otomatis.
- Effective dating mendukung versi eksplisit immutable; penutupan periode terbuka tersedia lewat preview batch opt-in dan approval; koreksi bebas dan resolver FK as-of belum tersedia. Lihat [panduan effective dating](EFFECTIVE_DATING_BE12.md).
- Timezone scheduler/query dan pin versi tzdb per konfigurasi belum termasuk source_timezone ETL.
- DDL target existing tetap CREATE_ONLY_OR_IDENTICAL. Mengubah precision/scale/varchar dalam form tidak melakukan migrasi target otomatis.
- Kontrak BE-12 schema/versi tetap 1.0; strict schema menolak field tambahan. Jangan menyimpan key UI (expanded, label tampilan, dsb.) dalam payload.

## Checklist acceptance frontend

- Load/edit/save tidak kehilangan kolom, semantic, taxonomy, atau parameter lain yang tidak disentuh.
- Uji revision stale, validasi HTTP 200 dengan valid=false, dan HTTP 422 DQ blocker.
- Uji number_locale ID/US, precision overflow, text terlalu panjang, timezone DST ambiguous, dan default sebelum parsing dengan null_if_empty.
- Uji pengalih unit/currency agar hanya satu aktif, string decimal tetap utuh, metadata kurs wajib, dan skala konsisten.
- Uji export/import XLSX termasuk nilai 0, false, null; preview token stale; can_apply tidak dipakai sebagai indikator siap deploy.
- Gunakan rate sintetis berlabel pada demo. Contoh currency + timezone sudah dijalankan lokal.

Bukti backend terakhir: 150 tes non-integrasi lulus, 35 tes integrasi tidak dijalankan;
exporter memverifikasi 145 operasi API. Bukan verifikasi PostgreSQL/provider nyata
atau bukti deployment environment tujuan.


Pembaruan berikutnya: [Master versi masa berlaku](EFFECTIVE_DATING_BE12.md) mencakup key versi, error preview/apply baru, dan payload registry master.


Pembaruan pencarian riwayat: endpoint GET master records kini menerima `as_of`.
Gunakan [kontrak format, error, dan interval](EFFECTIVE_DATING_BE12.md#pencarian-versi-yang-berlaku-as_of)
untuk date/time picker frontend. As-of lookup tidak mengganti pemilihan record/FK.


Preview import kini menerima close_open_periods (default false), mengembalikan period_closures, dan apply menambahkan periods_closed. Lihat [alur penutupan berapproval](EFFECTIVE_DATING_BE12.md#penutupan-periode-terbuka-melalui-preview-berapproval), termasuk revalidate untuk mencabut approval lama.
