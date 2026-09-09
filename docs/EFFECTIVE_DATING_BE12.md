# Master dengan versi masa berlaku BE-12

Implementasi 9 September 2026: versi eksplisit immutable pada jalur import review
master. Bukan otomatis SCD Type 2, koreksi periode, atau resolver FK as-of.

## Kontrak konfigurasi master

Contoh body create master: [BE12_EFFECTIVE_MASTER.json](api/BE12_EFFECTIVE_MASTER.json).
Policy memakai field existing `definition.policy.effective_dating`. Tidak ada field
baru pada ETLConfiguration atau template workbook untuk policy master. Daftarkan dan
approve master, deploy storage, lalu bind sumber sesuai workflow master existing.
Kolom ETL tanggal tetap dapat diatur melalui form/XLSX existing.

- Awal/akhir harus field date/timestamp/timestamptz bertipe sama.
- Business key wajib mencakup valid_from dan minimal satu key entitas lain.
- valid_from wajib non-null karena bagian business key; valid_to tidak boleh menjadi key.
- valid_to boleh null jika field nullable: berarti tidak ada batas akhir.
- Interval [awal, akhir): akhir harus setelah awal. Dua periode boleh bersebelahan atau memiliki gap.
- Semua field key selain valid_from membentuk identitas entitas untuk pemeriksaan overlap.

Contoh entitas product_code=P001: versi 2026-01-01 sampai 2026-02-01 dengan harga 10,
lalu versi 2026-02-01 sampai 2026-03-01 dengan harga 12. Dua record memiliki UUID
berbeda; record pertama dan referensi UUID-nya tetap dipertahankan. Tidak ada migrasi
FK otomatis ke versi baru. Resolver existing belum memilih versi berdasarkan tanggal transaksi.

## Preview dan apply

Preview memeriksa seluruh record tenant pada target, termasuk riwayat nonaktif, serta
seluruh kandidat batch. Apply memeriksa ulang setelah advisory transaction lock master
existing diambil. Kandidat di-cast sesuai schema master; payload temporal/numeric
staging tidak ditulis sebagai string yang belum divalidasi.

Versi baru dengan interval valid di-insert. Versi berkey sama dan isi identik adalah
UNCHANGED; apply melewatinya, tidak mengganti UUID, revision, atau lineage. rows_applied
menghitung write baru pada batch versi ini, sehingga bisa 0. Perubahan atribut atau batas akhir lewat overwrite biasa ditolak, termasuk primitive update_attributes internal. Pengecualian terbatas tersedia melalui rencana penutupan periode berapproval di bawah.
Apply versi efektif tidak menggunakan ON CONFLICT DO UPDATE.

Dengan default preview close_open_periods=false, periode terbuka tidak ditutup otomatis ketika versi berikutnya datang. Jika versi
lama valid_to=null, versi selanjutnya pada entitas yang sama akan overlap dan ditolak.
Gunakan periode eksplisit berbatas atau opsi preview penutupan berapproval di bawah. Koreksi riwayat lain tetap memerlukan migrasi yang direview. API koreksi khusus belum tersedia.

| Kode | HTTP | Arti / tindakan frontend |
|---|---|---|
| MASTER_PERIOD_INVALID | 422 | Field/interval invalid; periksa awal, akhir, tipe dan required |
| MASTER_PERIOD_OVERLAP | 409 | Periode bertumpang tindih dengan target atau batch; perbaiki sumber |
| MASTER_VERSION_DUPLICATE | 422 | Key versi muncul dua kali pada batch |
| MASTER_VERSION_IMMUTABLE | 409 | Versi tersimpan berbeda; jangan menawarkan retry overwrite |
| MASTER_SCHEMA_MIGRATION_REQUIRED | 409 | Mengubah key atau policy periode existing memerlukan migrasi |

Preview gagal melalui envelope error, bukan response can_approve=false. Apply
memeriksa ulang meski preview terdahulu berhasil; tampilkan error baru sebagai blocker.
Approval, tenant/role, pertanyaan wajib, snapshot dan token preview mengikuti alur
import review existing. Tidak ada endpoint langsung untuk melewati approval.

## Kompatibilitas dan batas

Definisi lama yang mengaktifkan effective_dating tetapi key-nya hanya entitas tidak
lagi valid: jangan menambahkan tanggal ke key target existing secara diam-diam.
Perlu desain migrasi identity/schema dan review data. Menambah/menghapus/mengganti
policy effective_dating pada master approved juga ditolak jalur evolusi kompatibel.
Tidak ada Alembic baru atau ALTER target otomatis pada perubahan ini.

Pemeriksaan overlap berada pada service; belum ada exclusion constraint PostgreSQL
untuk mencegah SQL langsung di luar aplikasi. Lock berlaku pada jalur import master
aplikasi, bukan penulis eksternal. Preview memuat riwayat tenant ke memori; belum
optimasi untuk master sangat besar. Alur legacy per-tab tidak menjadi jalur versi
master kanonis. XLSX mengatur kolom ETL, bukan policy registry master.

Tes mencakup interval, immutable history, idempotence, tipe, key versi, penolakan
perubahan policy, serta mock apply yang memeriksa urutan lock dan ketiadaan INSERT
pada overlap/UNCHANGED. Concurrency/rollback PostgreSQL nyata dan alur FK as-of
belum diverifikasi; milestone versi historis penuh tetap parsial.


## Pencarian versi yang berlaku (as_of)

Frontend dapat memakai endpoint existing:

```http
GET /api/v1/master-definitions/{master_id}/records?as_of=2026-02-01&search=P001&limit=50&offset=0
```

`as_of` string opsional, panjang 1..64; jika dikirim harus sesuai tipe field periode:

| Tipe periode | Format as_of | Contoh |
|---|---|---|
| date | YYYY-MM-DD, tanggal kalender valid | 2026-02-01 |
| timestamp | ISO dengan T dan detik, tanpa offset | 2026-02-01T12:00:00 |
| timestamptz | ISO dengan T dan detik, offset wajib | 2026-02-01T12:00:00+07:00 |

Gunakan URLSearchParams/params client HTTP agar `+` pada offset menjadi `%2B`, bukan
spasi. Timestamptz dinormalisasi ke UTC; tidak mengasumsikan timezone browser atau
source_timezone ETL. Tanpa as_of, endpoint tetap mengembalikan riwayat sesuai filter
existing. Filter menguji `valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of)`
di SQL sebelum pagination, dan nilai waktu menjadi bind parameter.

`active_only=true` tetap default dan mengacu `_is_active`, bukan tanggal masa berlaku.
Untuk menyertakan versi nonaktif gunakan false sesuai akses existing; master sendiri
harus tetap aktif/approved agar target bisa diakses. record_id dan search dapat
digabung dengan as_of. search tetap pencarian substring key/label, bukan exact entity
resolver. Endpoint dapat mengembalikan versi dari banyak entitas; jangan menganggap
item pertama sebagai jawaban tunggal atau otomatis mengisi FK.

Response tetap envelope dengan data `{items, has_more, masked_fields}` dan
meta `{offset, limit}`. Daftar kosong berarti tidak ada record yang cocok; tidak
fallback ke versi terbaru. Batas mulai inklusif, akhir eksklusif; tepat pada pergantian
periode versi yang berakhir tidak lagi muncul. Periode akhir null tidak berbatas.

| Error | HTTP | Penanganan frontend |
|---|---|---|
| MASTER_AS_OF_INVALID | 422 | Format/tanggal/offset tidak sesuai tipe periode |
| MASTER_EFFECTIVE_DATING_REQUIRED | 409 | Master tidak mempunyai policy masa berlaku; sembunyikan filter |
| MASTER_PERIOD_FILTER_FORBIDDEN | 403 | Role tidak boleh melihat salah satu field periode; filter ditolak untuk mencegah inferensi |
| VALIDATION_ERROR | 422 | Parameter kosong/lebih dari 64 karakter ditolak schema endpoint |

Role endpoint tetap editor/reviewer. Scope tenant, masking SELECT-time, dan pembatasan
pencarian pada field sensitif tetap berlaku. Penutupan periode melalui batch berapproval dijelaskan di bawah. Koreksi bebas serta resolver
FK berdasarkan tanggal transaksi masih pekerjaan terpisah. Tidak ada write atau
migrasi pada fitur baca ini.


## Penutupan periode terbuka melalui preview berapproval

Opsi baru pada body POST `/import-reviews/{review_id}/preview`:

```json
{"revision_no": 1, "close_open_periods": true}
```

Default false mempertahankan penolakan overlap sebelumnya. Opsi true hanya berlaku
untuk MASTER dengan effective_dating dan policy PROPOSE_INSERT. Ini pilihan batch,
bukan perubahan policy atau kolom XLSX. Semua gate review/approval existing tetap berlaku.

Backend memeriksa versi lama valid_to=null dan kandidat versi baru entitas yang sama.
Penutupan hanya ke valid_from paling awal dari versi baru yang lebih kemudian; tidak
menutup record nonaktif, tidak mengubah end yang sudah terisi, tidak mengubah atribut,
dan tidak memotong awal versi. Interval existing yang sudah rusak tetap ditolak.

Kirim kandidat versi baru yang periodenya tidak saling overlap. Batch yang menyertakan
salinan versi lama terbuka bersama versi baru masih dapat ditolak karena interval
kandidat overlap; gunakan sumber delta versi baru atau periode eksplisit yang konsisten.
Beberapa versi baru dalam batch harus berbatas jelas, kecuali versi terakhir.

Preview menambahkan `data.period_closures` (array, kosong bila tidak ada penutupan):

```json
[{"record_id":"11111111-1111-4111-8111-111111111111","revision_no":3,"column":"valid_to","before":null,"after":"2026-02-01"}]
```

UI wajib menampilkan penutupan berdampingan dengan changes insert. `summary` existing
menghitung kandidat rows, tidak memasukkan penutupan sebagai UPDATE; gunakan panjang
period_closures untuk jumlah penutupan. Jangan menganggap array ini sebagai daftar
record sumber baru. Timestamp output memakai serialisasi backend; tampilkan tanpa
mengubah nilai yang terikat preview.

Hash preview/token mencakup mode dan rencana penutupan. Checkpoint menyimpan
close_open_periods, effective_plan_hash, periods_to_close. Hash target memakai seluruh
record tenant pada target: perubahan record lain pun dapat menyebabkan stale. Rencana
approved tidak boleh diganti lewat preview ulang dengan isi berbeda.

Apply memakai mode yang tersimpan, bukan flag baru dari request apply. Setelah lock,
backend membandingkan ulang isi staging dan snapshot target dengan hash preview. Jika
berubah, IMPORT_PREVIEW_STALE (409), tanpa update. Jika cocok, UPDATE akhir periode
memeriksa tenant + UUID + revision + end IS NULL + active, menaikkan revision, dan
memperbarui _updated_at. UUID, atribut bisnis, dan lineage sumber lama dipertahankan.
Audit `master.period_closed` menyimpan record/revision, sebelum/sesudah akhir periode,
pengguna, dan import_review_id. INSERT versi baru menggunakan UUID baru.

Response apply menambahkan `periods_closed`; `rows_applied` tetap jumlah INSERT row.
Keduanya ditulis ke checkpoint. Penutupan dan INSERT memakai transaksi API yang sama;
kegagalan dipropagasikan agar session rollback. Belum ada bukti rollback/concurrency
PostgreSQL nyata pada tahap ini; tes mock memeriksa urutan dan guard SQL.

| Error | HTTP | Tindakan |
|---|---|---|
| MASTER_PERIOD_CLOSURE_INVALID | 409 | Policy insert/record target tidak memenuhi syarat penutupan |
| IMPORT_PREVIEW_STALE | 409 | Rencana/target berubah; revalidate, preview dan approve ulang |
| MASTER_RECORD_REVISION_CONFLICT | 409 | Guard UPDATE tidak cocok; transaksi gagal, jangan lanjut INSERT |
| MASTER_PERIOD_FILTER_FORBIDDEN | 403 | Preview/approval/apply penutupan periode sensitif memerlukan role data yang berizin |

Recovery: POST `/import-reviews/{id}/revalidate` kini dapat dipanggil editor pada
READY_FOR_APPROVAL atau APPROVED. Backend mencabut approval/preview lama, meningkatkan
revision/generation, lalu mengantrekan validasi ulang jika dependencies masih current.
Ambil state/revision terbaru sebelum preview dengan close_open_periods=true lagi.
Jika dependencies berubah, hasil bisa STALE_REVIEW mengikuti alur existing; sumber
baru tetap memerlukan batch/snapshot yang sesuai. Apply token lama tidak boleh dicoba
ulang untuk melewati proses review.

Tidak ada migrasi database. Ini penutupan otomatis yang diusulkan dalam batch dan
memerlukan approval; bukan koreksi bebas riwayat atau perubahan diam-diam saat insert.
