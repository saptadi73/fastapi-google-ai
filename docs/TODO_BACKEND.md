# TODO implementasi backend

Acuan pengerjaan bertahap `fastapi-googlesheet-ai`, diperbarui 8 September 2026. Dokumen ini adalah checklist pekerjaan, bukan pernyataan bahwa endpoint usulan sudah tersedia. Urutan utama: **klasifikasi → master baku → review import → referensi/FK → validasi AI setiap import → taxonomy → semantic/query lanjutan**.

Gunakan ID `BE-xx` saat meminta implementasi, membuat PR, atau mencatat progres. Centang item hanya setelah kode, migrasi yang diperlukan, pengujian, dan kontrak API selesai. Tandai tahap sedang dikerjakan pada catatan progres; jangan mencentang hanya karena desainnya sudah dibuat.

## Fondasi yang sudah tersedia

- [x] Tenant scoping, autentikasi, role editor/approver, dan audit aplikasi.
- [x] Registrasi Google Sheet, discovery tab, snapshot, profiling, dan antrean job.
- [x] Draft konfigurasi manual/AI, optimistic revision, clone, approval, deployment, dan sync.
- [x] Review konfigurasi dengan snapshot hash, checklist bagian/kolom, jawaban pertanyaan teks, dan preview before/after.
- [x] Export template XLSX, import-preview, diff, serta apply ke draft dengan token preview.
- [x] Transformasi dan DQ dasar, staging/quarantine, serta strategi load dataset mandiri.
- [x] Semantic product dan structured query satu produk, termasuk saved query dasar.
- [x] API Reference, contoh payload, dan exporter schema/OpenAPI.

Verifikasi historis setelah BE-06: **99 tes backend lulus**, Ruff lulus, serta exporter memverifikasi **117 operasi API**. Migrasi BE-06 `6d1305460956`, staging pertanyaan/keputusan, dan Alembic check diuji pada database test; integrasi provider nyata dan production belum dibuktikan oleh tes ini. Review **konfigurasi** yang tersedia belum sama dengan review **setiap batch data**; storage record master, batch/checkpoint, dan pertanyaan/keputusan staging tersedia, sedangkan pemuatan record masih pekerjaan di bawah.

## Urutan implementasi

### BE-01 — Kebijakan data dan kontrak dasar

Selesai pada tahap kontrak dasar. Keputusan dan batas implementasi tercatat di [Kebijakan data BE-01](KEBIJAKAN_DATA_BE01.md). BE-02 sampai BE-07 sudah memiliki implementasi bertahap; resolver referensi dan hardening lanjutan tetap mengikuti BE-08 sampai BE-11.

- [x] Klasifikasi per tab dikonfirmasi pengguna; kontrak hanya menerima SHEET.
- [x] Pengguna memilih update dengan usulan insert yang wajib disetujui; policy dicatat eksplisit.
- [x] Tetapkan sumber otoritatif dan prioritas perubahan ketika beberapa Sheet memperbarui master yang sama.
- [x] Tetapkan arti record hilang dari Sheet, penonaktifan, perubahan business key, serta master dengan masa berlaku.
- [x] Tetapkan policy apply atomik dan apakah partial load diperbolehkan; pertanyaan wajib tetap harus menahan apply.
- [x] Definisikan enum, transisi status, hak akses, dan versi schema kontrak baru.

Selesai jika keputusan tercatat dan contoh produk, karyawan, UOM, struktur gaji, serta transaksi mempunyai aturan yang jelas. Keputusan yang belum ditetapkan tetap ditandai terbuka; pekerjaan desain/test independen dapat berjalan.

### BE-02 — Klasifikasi sumber/tab

Prasyarat: BE-01. Selesai di kode dan database test; detail API/rollout di [Klasifikasi tab BE-02](KLASIFIKASI_TAB_BE02.md).

- [x] Tambahkan `dataset_kind`, status belum diklasifikasi, revision, dan metadata konfirmasi pada tab.
- [x] Tambahkan API baca/simpan klasifikasi dengan optimistic concurrency dan audit.
- [x] Izinkan profiling untuk membantu keputusan; blok approval/deploy/apply yang memerlukan klasifikasi sampai lengkap.
- [x] Siapkan backfill sumber lama ke status perlu konfirmasi; jangan otomatis menganggapnya non-master.
- [x] Uji file dengan tab master dan transaksi, revisi konflik, akses lintas tenant, dan pemanggilan API langsung untuk melewati gate.

Selesai jika setiap tab mempunyai klasifikasi eksplisit dan backend menegakkannya tanpa bergantung pada tombol frontend. Pemilihan master tersedia melalui binding BE-03.

### BE-03 — Registry master dan binding sumber

Prasyarat: BE-01 dan BE-02. Selesai di kode/test; lihat [Registry master BE-03](REGISTRY_MASTER_BE03.md). Pemuatan record tetap menunggu BE-04 dan alur review/apply.

- [x] Buat model/migrasi `master_definition`: kode, nama, schema bertipe, business key, label, alias dataset, status, revision, dan tenant.
- [x] Implementasikan lifecycle draft/review/approve definisi master dan perubahan schema.
- [x] Buat `master_source_binding` untuk beberapa tab yang memakai master sama; validasi tenant, tipe, dan key.
- [x] Tambahkan API pencarian/list/detail master dengan pagination serta binding klasifikasi tab.
- [x] Cari kandidat master yang sudah ada sebelum menerima usulan master baru; kemiripan nama hanya rekomendasi.
- [x] Uji unique `(tenant_id, code)`, sumber ganda, master nonaktif, konflik schema, dan binding lintas tenant.

Selesai jika dua Sheet dapat diarahkan ke satu definisi master baku tanpa membuat master baru untuk setiap file.

### BE-04 — Penyimpanan master kanonis

Prasyarat: BE-03. Implementasi di [Storage master BE-04](STORAGE_MASTER_BE04.md). Tidak ada Alembic baru; storage per master dibuat lewat deploy-storage. Import tetap menunggu review/apply.

- [x] Perluas compiler untuk menghasilkan target master berdasarkan ID master, bukan UUID tab.
- [x] Tambahkan UUID record stabil, tenant, typed business key, status aktif, revision, dan metadata asal.
- [x] Pasang unique constraint tenant + business key serta tenant + UUID record.
- [x] Sediakan pencarian record terotorisasi untuk kandidat referensi, dengan pagination dan masking sesuai role.
- [x] Pisahkan update atribut biasa dari perubahan key, merge record, penonaktifan, dan penghapusan.
- [x] Tolak FULL_REFRESH destruktif pada master yang dapat dirujuk; tentukan migrasi schema yang kompatibel.
- [x] Uji UUID tetap saat nama berubah, leading zero, composite key, dan constraint pada dua penulisan bersamaan.

Selesai jika master memiliki identitas fisik stabil lintas file dan perubahan label tidak membuat identitas baru. Pemuatan dari import tetap melalui gate BE-05–BE-07.

### BE-05 — Batch review import dan worker yang dapat dilanjutkan

Selesai di kode/test; kontrak implementasi ada di [Batch review BE-05](IMPORT_REVIEW_BE05.md). Pertanyaan/jawaban terstruktur mengikuti BE-06, review AI BE-10, dan apply BE-07.

Prasyarat: BE-02–BE-04.

- [x] Tambahkan `import_review`/batch dengan snapshot, revision konfigurasi, status, dan versi kebijakan.
- [x] Implementasikan state machine VALIDATING, AI_REVIEWING, NEEDS_INPUT, READY_FOR_APPROVAL, APPROVED, APPLYING, SUCCEEDED, FAILED, CANCELLED, dan STALE_REVIEW.
- [x] Simpan checkpoint, temuan, dan blocker sebelum worker berhenti menunggu input; pertanyaan konfigurasi tetap tersimpan dalam konfigurasi batch. Pertanyaan/jawaban per sel mengikuti BE-06.
- [x] Tambahkan create/get/list/cancel/revalidate/resume batch dan penghubung job; list memakai pagination/filter status.
- [x] Bedakan NEEDS_INPUT dari kegagalan teknis yang boleh retry; cegah polling/retry worker tanpa akhir.
- [x] Definisikan kunci idempotency yang mencakup tenant, tab, snapshot, konfigurasi, serta versi dependency yang relevan.
- [x] Uji restart worker, job ganda, cancel, retry, dan batch lama yang menjadi stale.

Selesai jika batch yang menunggu pengguna dapat dilanjutkan tanpa membaca sumber berbeda atau menggandakan pekerjaan.

### BE-06 — Pertanyaan dan keputusan terstruktur per import

Selesai di kode/test; kontrak implementasi ada di [Pertanyaan batch BE-06](IMPORT_QUESTIONS_BE06.md). Proposal master membuat draft registry dan hanya ditutup setelah approval lifecycle master; tidak ada write-back ke Google Sheet.

Prasyarat: BE-05.

- [x] Buat `import_question` dan `import_decision` dengan ID, baris/kolom, kategori masalah, kandidat, alasan, dan evidence.
- [x] Tambahkan API pertanyaan dengan pagination/filter dan API jawaban yang memeriksa revision serta kandidat yang diizinkan.
- [x] Dukung pilih record, pertahankan nilai asli untuk temuan yang sah, perbaiki sumber, dan usulan master baru melalui approval.
- [x] Terapkan koreksi di staging sambil mempertahankan nilai mentah; jangan menulis balik Google Sheet secara implisit.
- [x] Simpan pengguna, waktu, before/after, serta scope keputusan; jawaban per baris bukan alias global otomatis.
- [x] Uji jawaban stale, pertanyaan batch/tenant lain, kandidat palsu, jawaban ulang, dan FK wajib yang belum terselesaikan.

Selesai jika ambiguitas memiliki pertanyaan yang bisa dijawab dan diaudit, bukan sekadar teks yang dihapus dari konfigurasi.

### BE-07 — Preview dan apply master

Prasyarat: BE-04–BE-06.

- [x] Bangun diff INSERT, INSERT_PROPOSED, UPDATE, UNCHANGED, DUPLICATE, KEY_CONFLICT, dan INVALID beserta before/after.
- [x] Terapkan policy `UPDATE_ONLY`/`PROPOSE_INSERT` dari BE-01; insert baru diberi status `INSERT_PROPOSED`, sedangkan record lama tetap dipertahankan (`KEEP`).
- [x] Ikat preview/approval ke snapshot dan revision target master; periksa ulang sebelum commit.
- [x] Implementasikan UPSERT atomik, lock/concurrency control, idempotency, dan lineage sumber setiap perubahan.
- [x] Terapkan gate approval dan pertanyaan wajib pada endpoint apply serta worker, termasuk saat dipanggil langsung.
- [x] Tambahkan advisory transaction lock per master/tab pada apply untuk mencegah penulisan paralel.
- [ ] Uji dua import bersamaan, key kosong/duplikat, konflik sumber, retry, dan kegagalan tengah transaksi.

Status BE-07: implementasi inti preview/approval/apply, policy record hilang, dan konflik key tersedia. Pengujian integrasi database berikut masih TERBUKA: dua import bersamaan, key kosong/duplikat, konflik sumber, retry apply, dan kegagalan tengah transaksi dengan verifikasi rollback. Bukti review AI tetap wajib ditambahkan sebelum alur lengkap dinyatakan siap pada BE-10/BE-11.

### BE-08 — Binding kolom dan resolusi referensi master

Prasyarat: BE-03, BE-06, dan BE-07.

- [x] Tambahkan registry relasi kolom → master, required/optional, normalisasi, cardinality, dan versi persetujuan.
- [x] Sediakan rekomendasi binding berdasarkan metadata master dan profiling kolom; pengguna tetap wajib mengonfirmasi mapping.
- [x] Sediakan endpoint resolusi nilai dengan hasil EXACT/CANDIDATE/AMBIGUOUS/NOT_FOUND dan kandidat terotorisasi.
- [x] Resolusi nilai menghasilkan exact/alias/fuzzy candidate dan menandai `requires_question` untuk nilai ambigu/tidak ditemukan.
- [x] Simpan UUID master hasil resolusi ke staging sambil mempertahankan nilai asli; fallback ke nama tampilan ditolak.
- [x] Implementasikan alias berscope tenant/master/kolom, dengan approval dan revision; pencabutan alias masih memerlukan perubahan binding draft.
- [ ] Uji referensi tidak ditemukan, ambigu, master nonaktif, relasi opsional, serta perubahan alias/master setelah preview.

Status BE-08: resolver, registry binding kolom, approval binding, alias approved, penyimpanan UUID exact/alias ke staging, dan rekomendasi binding tersedia. Pengujian perubahan dependency masih terbuka. Confidence AI tidak otomatis menggabungkan entitas berbeda.

### BE-09 — Foreign key fisik dan urutan dependency

Prasyarat: BE-04 dan BE-08.

- [x] Hasilkan FK komposit tenant + UUID master dari binding approved; gunakan ON DELETE RESTRICT sesuai kebijakan.
- [x] Validasi privilege `REFERENCES` role DDL pada target dan master sebelum deployment FK; role operasional/reader tetap tidak diberi DDL.
- [x] Sediakan dependency plan dari binding approved untuk ditampilkan sebelum DDL.
- [x] Deteksi siklus dependency dari binding approved dan tampilkan hasilnya pada dependency plan.
- [x] Tentukan urutan master sebelum transaksi dan tampilkan `load_order` topologis.
- [x] Tampilkan tindakan koreksi dan blokir DDL ketika siklus ditemukan.
- [x] Validasi orphan/type sebelum memasang FK pada target yang sudah berisi data.
- [x] Sediakan pemeriksaan orphan read-only pada target trusted terhadap business key master.
- [x] Tangani retry deployment constraint yang sudah ada dengan hasil `reused`.
- [ ] Uji penolakan FK orphan/lintas tenant langsung di PostgreSQL, dependensi bertingkat, siklus, dan kegagalan DDL.

Status BE-09: dependency plan, load order, deteksi siklus, pemeriksaan orphan/type, dan deployment FK fisik tersedia; tindakan koreksi otomatis dan hardening DDL lintas kegagalan masih terbuka. FK fisik belum berarti query join NL2SQL diaktifkan.

### BE-10 — Review AI pada setiap snapshot baru

Prasyarat: BE-05, BE-06, dan BE-08.

- [x] Tentukan masking field MEDIUM/HIGH dan simpan daftar field yang dimasking pada checkpoint batch.
- [x] Tambahkan task review batch dengan output terstruktur tervalidasi (`AIImportReviewResult`).
- [x] Proses baris dalam chunk maksimal 100 dan gabungkan coverage/metadata seluruh chunk.
- [x] Catat coverage, baris diperiksa, model/prompt metadata, policy version, waktu selesai, dan evidence issue; biaya tetap tersedia pada `audit.ai_usage_log`.
- [x] Terapkan timeout, quota/budget dari OpenAIService, retry worker terbatas, serta pemakaian ulang hasil chunk yang hash-nya masih sama.
- [x] Jika review AI menghasilkan issue atau coverage belum lengkap, tahan batch dan buat pertanyaan terstruktur dengan evidence.
- [x] Perlakukan isi Sheet sebagai data tidak tepercaya pada konteks AI; output tetap divalidasi schema dan issue masuk pertanyaan. Pengujian provider nyata/injeksi masih diperlukan.
- [x] Pastikan snapshot baru diperiksa walaupun fingerprint schema tetap sama; dependency check memakai snapshot hash, bukan fingerprint saja. Tercakup pada test snapshot replacement.

Status BE-10: worker sudah memanggil review terstruktur ketika OpenAI dikonfigurasi, menyimpan coverage, metadata model/prompt, findings, blocker, masking field sensitif, chunk cache, dan pertanyaan per issue. Pengujian provider nyata/injeksi serta validasi snapshot baru dengan fingerprint schema sama masih terbuka. Label “semua diperiksa AI” tidak dipakai untuk hasil sampling atau pengecualian.

### BE-11 — Integrasi alur lengkap dan migrasi data lama

Prasyarat: BE-07–BE-10.

- [x] Sediakan jalur `sync-review` yang membuat batch review per tab dan mengembalikan tab yang belum siap sebagai `BLOCKED`.
- [x] Pertahankan idempotency batch saat sync-review diulang pada snapshot/configuration yang sama.
- [ ] Hubungkan sync manual dan terjadwal sepenuhnya ke validasi deterministik, resolusi referensi, AI review, pertanyaan, approval, dan apply.
- [x] Revalidasi batch ketika snapshot, konfigurasi, master, binding/alias, atau policy yang relevan berubah melalui dependency hash.
- [x] Tandai response `/sync` sebagai `LEGACY_ETL` dan arahkan frontend ke `/sync-review`; kompatibilitas legacy tetap dipertahankan sementara migrasi penuh belum selesai.
- [x] Siapkan preview migrasi target per tab ke master kanonis beserta binding dan validation gate; deduplikasi, mapping ID lama-baru, dan apply migrasi tetap memerlukan tahap berikutnya.
- [x] Sertakan rollback plan dan snapshot reference pada preview migrasi; eksekusi backup/restore fisik tetap wajib dilakukan oleh job migrasi terpisah.
- [ ] Uji end-to-end master UOM → produk → transaksi, lalu karyawan → pangkat/grade → penilaian dengan mock provider dan PostgreSQL test.

Selesai jika kebutuhan inti master/non-master berjalan dari pendaftaran sampai trusted, termasuk kasus ambigu dan restart. **Ini milestone utama sebelum memperluas taxonomy dan query.**

### BE-12 — Lengkapi kamus parameter dan runtime ETL

Acuan implementasi frontend paralel: [Panduan frontend BE-12](FRONTEND_BE12.md), termasuk mapping catalog/payload, batas runtime, error, dan contoh request lengkap.

Prasyarat: BE-11; inventaris field dapat disiapkan lebih awal.

Status: dukungan runtime bertahap tersedia untuk numeric precision/scale, format tanggal, locale angka ID/US, panjang varchar, dan allowlist transformasi. Multi-target dan schema evolution masih terbuka; currency conversion dengan kurs tetap eksplisit kini tersedia; timezone sumber timestamptz kini tersedia; DQ format/domain, umur maksimum, default bertipe, metadata severity/owner, dan threshold per rule kini tersedia.

- [x] Sediakan parameter catalog runtime untuk field yang sudah didukung dan menandai field unsupported beserta tahap pemiliknya.
- [x] Inventaris awal locale/timezone/format tanggal/angka, currency, dan UOM pada parameter catalog sebagai unsupported; precision/scale numeric sudah didukung compiler.
- [x] Publikasikan allowlist transformasi runtime; DQ threshold dan konversi unit/currency eksplisit kini didukung. Transform expression/kondisi dinamis tetap unsupported.
- [x] Inventaris effective dating policy master, unit conversion, multi-target, dan schema evolution; unit conversion massa/volume/panjang kini didukung, multi-target/schema evolution tetap unsupported.
- [~] Lengkapi locale/timezone, entity/domain, dan unit/currency (timezone IANA sumber timestamptz tersedia, normalisasi UTC dan penolakan DST ambigu/gap; unit dan currency kurs tetap eksplisit tersedia); format tanggal, numeric precision/scale, locale angka, dan panjang varchar sudah didukung bertahap.
- [x] Sediakan registry operasi allowlist beserta parameter schema dan `on_error`; eksekusi transform berparameter, kondisi, dan urutan dinamis tetap diblokir sampai compiler siap.
- [~] Lengkapi DQ format/domain, threshold persen, severity/owner, max_age_days, serta default value dengan semantics yang disetujui (runtime format allowlist/domain allowed_values, threshold per rule, default bertipe, umur UTC, dan round-trip XLSX tersedia; severity/owner menjadi metadata, action_on_fail mengendalikan routing; notifikasi owner otomatis belum tersedia).
- [~] Implementasikan versi/master bermasa berlaku: versi eksplisit immutable, key entitas + valid_from, validasi overlap preview/apply dan skip UNCHANGED tersedia. Penutupan periode terbuka tersedia melalui preview opt-in dan approval; rollback, dua apply bersamaan, retry, batas as_of, dan isolasi tenant telah diuji PostgreSQL. Koreksi bebas dan FK as-of masih terbuka. Lihat [panduan](EFFECTIVE_DATING_BE12.md).
- [x] Implementasikan konversi satuan eksplisit untuk massa/volume/panjang, faktor tervalidasi dan pembulatan HALF_UP/HALF_EVEN/DOWN; alias ejaan dan satuan custom tetap unsupported; currency memakai parameter terpisah.
- [x] Rancang split grain/multi-target, schema evolution, default/update condition, serta kebijakan append event identik. [Rancangan dan batas runtime](LOAD_POLICIES_BE12.md); payload multi-target/evolution/kondisi dinamis tetap unsupported.
- [~] Tambahkan dukungan bertahap ke schema, compiler, dry-run, artifact, API, dan XLSX secara bersamaan; numeric/date/locale, DQ, unit/currency/timezone, dan policy APPEND tanpa key tersedia; unsupported tetap ditolak sampai runtime tersedia.

Progres DQ BE-12 (9 September 2026): format allowlist `UUID`/`ISO_DATE`/`ISO_DATETIME`, domain `allowed_values`, umur maksimum UTC, threshold per indeks rule (batas inklusif), default sebelum cast/nullability, dan metadata severity/owner telah terhubung compiler serta XLSX. Tab 05 memakai G/J/K/O/P untuk parameter tambahan. Tidak memerlukan migrasi database. Bukti: 23 tes DQ/ETL/XLSX lulus dalam pengujian terarah (19 tes awal + 4 kasus tambahan); 14 tes query security lulus setelah memperbaiki allowlist `label` metric. Ruff pada file perubahan tahap ini lulus; Ruff global masih memiliki 20 temuan di file lain. Exporter `--check` memverifikasi 145 operasi. Integrasi PostgreSQL/provider nyata belum dijalankan pada tahap ini. Severity/owner belum mengirim notifikasi atau assignment otomatis.

Progres konversi satuan BE-12 (9 September 2026): `columns.unit_conversion` terhubung schema, compiler bersama dry-run/load, artifact konfigurasi, catalog API, dan XLSX tab 02 kolom Z. Faktor harus cocok dengan satuan dan dimensi allowlist; konversi key/currency/custom ditolak. Batas precision/scale dan panjang varchar kini diperiksa runtime sebelum penulisan. XLSX U-Y juga menampilkan parameter numeric/varchar/date/locale yang sebelumnya hanya tersimpan di konfigurasi. Tidak ada migrasi model; perubahan tipe target terdeploy tetap melalui gate migrasi existing. Pengujian unit/runtime dan round-trip XLSX lulus; PostgreSQL/provider nyata belum diuji pada tahap ini.

Progres timezone BE-12 (9 September 2026): `columns.source_timezone` mendukung zona IANA untuk input naive timestamptz, normalisasi UTC, offset eksplisit, dan penolakan DST overlap/gap. Schema, compiler dry-run/load, API catalog, artifact, dan XLSX AA terhubung. tzdata ditambahkan sebagai dependency langsung memakai versi lock existing. Tidak ada migrasi database. Timezone scheduler/query, konversi date-only, serta pin tzdb per konfigurasi tetap di luar cakupan ini. Bukti: suite non-integrasi 126 tes lulus (35 tes integrasi tidak dijalankan), termasuk 18 tes timezone dan round-trip/edit XLSX; Ruff file perubahan lulus dan exporter --check memverifikasi 145 operasi API. PostgreSQL/provider nyata belum diverifikasi.

Progres currency BE-12 (9 September 2026): `columns.currency_conversion` memuat pasangan currency allowlist, kurs positif finite, tanggal/referensi wajib, dan pembulatan Decimal. Runtime mendukung kurs tetap per revisi konfigurasi, DQ/precision setelah konversi, serta default dalam mata uang target. Metadata kurs ikut artifact dan dependency hash existing; XLSX tab 02 AB mendukung edit/round-trip. Tidak ada migrasi database. Currency campuran per baris, provider live, dan historical rate otomatis tetap unsupported; tanggal kurs adalah metadata eksplisit, bukan pemilih/filter tanggal transaksi. Verifikasi: 150 tes non-integrasi lulus, 35 tes integrasi tidak dijalankan; Ruff file perubahan lulus, exporter --check memverifikasi 145 operasi. Contoh examples/be12-currency-configuration.json dijalankan dengan hasil 100 USD sintetis menjadi 1234550.00 IDR dan timestamp UTC yang sesuai. PostgreSQL/provider nyata belum diuji.

Progres versi eksplisit BE-12: pemeriksaan interval immutable dipakai preview dan apply master setelah lock, update atribut versi diblokir, perubahan policy masa berlaku memerlukan migrasi, dan versi identik dilewati. Bukti: 159 tes non-integrasi di luar workbook lulus; 19 tes effective dating terarah lulus termasuk dua kasus tambahan normalisasi offset/field asing. Lint file perubahan dan exporter 145 operasi lulus. Workbook tidak berubah pada tahap ini; concurrency/rollback PostgreSQL nyata, penutupan periode otomatis, serta FK as-of masih terbuka. Payload/panduan frontend ada di [effective dating](EFFECTIVE_DATING_BE12.md).

Progres pencarian riwayat BE-12: GET master records mendukung as_of dengan filter interval SQL sebelum pagination, validasi sesuai tipe periode, dan penolakan filter periode sensitif. Schema/OpenAPI dan handoff frontend diperbarui. Bukan resolver FK as-of; penutupan periode otomatis masih terbuka. Verifikasi: 176 tes regresi non-integrasi di luar workbook lulus; 35 tes effective dating/as_of terarah lulus, termasuk kontrak HTTP dan pembatasan role. Lint file perubahan dan exporter --check 145 operasi lulus. Tes interval SQL in-memory dan mock scope/masking tidak menggantikan integrasi PostgreSQL.

Progres penutupan periode BE-12: preview close_open_periods=true mengusulkan penutupan null ke awal versi baru, terikat hash target/staging dan approval. Apply memeriksa ulang setelah lock, guarded UPDATE + INSERT dalam transaksi, mempertahankan UUID/lineage lama, menambah revision dan audit. Revalidate batch approved mencabut approval/token lama. Default tetap reject overlap; koreksi periode bebas dan hardening PostgreSQL masih terbuka. Lihat kontrak frontend pada panduan effective dating. Verifikasi: 191 tes regresi non-integrasi di luar workbook lulus dan 50 tes effective dating/closure terarah lulus, termasuk token preview nyata dalam alur service mock preview-approve-apply. Lint file perubahan dan exporter --check 145 operasi lulus; rollback/concurrency PostgreSQL nyata belum diuji.

Progres hardening PostgreSQL BE-12 (9 September 2026): 7 tes integrasi baru membuktikan commit UUID/lineage/audit, rollback setelah kegagalan INSERT termasuk status/revision batch, retry, penolakan target stale, serialisasi dua apply dengan bukti `pg_blocking_pids`, skip versi identik, batas interval as_of, serta penolakan lintas tenant pada service dan constraint fisik. Bersama 50 tes effective dating existing: **57 tes lulus**. Ruff file baru dan exporter `--check` 145 operasi lulus. Tidak ada perubahan API/migrasi. Dependency freshness `is_current` distub pada suite ini; bukan bukti onboarding/provider end-to-end atau penulis SQL eksternal. Detail dan perintah pengujian: [verifikasi PostgreSQL](EFFECTIVE_DATING_BE12.md#verifikasi-postgresql-penutupan-periode). BE-12 tetap parsial untuk koreksi riwayat, FK as-of, multi-target/schema evolution, dan parameter lanjutan lainnya.

Regresi setelah hardening: **200 tes non-integrasi lulus**, termasuk workbook XLSX (42 tes integrasi dikecualikan dari perintah regresi; 7 tes baru dijalankan terpisah di atas).

Progres APPEND BE-12 (9 September 2026): `append_duplicate_policy` SKIP_IDENTICAL/REJECT_IDENTICAL khusus APPEND tanpa business/primary key terhubung schema, dry-run, preview/approval/apply, ETL legacy, catalog/artifact, serta XLSX 14 Review B8. Default null menyamakan apply batch dengan skip duplikat legacy; rows_applied menghitung INSERT aktual. Staging JSON dikembalikan ke tipe target tanpa transform ulang. Rancangan multi-target/schema evolution/update condition selesai didokumentasikan, runtime fitur tersebut tetap unsupported. Bukti: **208 tes non-integrasi, 6 tes PostgreSQL APPEND, dan 7 tes PostgreSQL effective dating lulus**; Ruff file kode perubahan dan exporter 145 operasi lulus. Tidak ada migrasi baru; database test menjalankan migrasi existing sampai head, sedangkan `alembic check` menemukan drift existing master_column_binding/taxonomy yang masih harus diperbaiki. [Kontrak, rancangan, dan batas bukti](LOAD_POLICIES_BE12.md).

Selesai per field/fitur jika konfigurasi benar-benar memengaruhi runtime dan export–import tidak kehilangan maknanya. Pecah tahap ini menjadi PR per kemampuan, bukan satu perubahan besar.

### BE-13 — Taxonomy dan mapping kategori

Prasyarat: BE-08, BE-11, dan kamus parameter BE-12.

Status: registry taxonomy berversi, term hierarkis, dan binding kolom tersedia; AI suggestion, validasi term, dan DQ `in_taxonomy` masih terbuka.

- [x] Buat registry taxonomy/version/hierarchy dan term, terpisah dari identitas record master; tersedia endpoint CRUD term dan approval version.
- [x] Sediakan binding taxonomy ke kolom sumber dengan optimistic revision dan approval/rejection.
- [x] Sediakan resolver term exact/alias/kandidat/ambigu dengan flag `requires_question`.
- [~] Tambahkan usulan AI, approval mapping, alias terkontrol, serta pertanyaan untuk nilai ambigu (resolver, ranking rekomendasi, dan `ImportQuestion` tersedia; rekomendasi generatif dan alias approval terpisah masih terbuka).
- [x] Implementasikan DQ `in_taxonomy` dan dampak perubahan versi mapping pada review lama; preview kini menolak taxonomy stale dan nilai invalid jika `taxonomy_required=true`.
- [x] Aktifkan field taxonomy pada mapping kolom ETL (`taxonomy_id`, `taxonomy_version`, `taxonomy_required`) sehingga tab 04/XLSX dapat diekspor; resolusi nilai tetap memakai endpoint DQ sebelum apply.
- [~] Uji hierarki, kode tidak ditemukan, mapping konflik, versioning, dan isolasi tenant (kontrak schema taxonomy/ETL sudah diuji; pengujian integrasi PostgreSQL lintas tenant masih perlu environment test database).

Selesai jika nilai kategori dinormalisasi melalui aturan approved tanpa mengubah identitas master secara keliru.

### BE-14 — Semantic catalog, metrik, intent, dan join

Prasyarat: BE-09, BE-11; gunakan BE-12/BE-13 jika memakai unit/domain/taxonomy.

- [ ] Lengkapi metadata bisnis produk, default periode, unit, sinonim, dan lifecycle approval metrik.
- [~] Tambahkan expression/filter/null handling metrik melalui AST/operasi allowlist yang tervalidasi (aggregation dan kolom metric kini divalidasi; expression AST lanjutan belum).
- [ ] Tambahkan query template berparameter dan periode relatif, timezone, output type, priority, serta ambiguity policy.
- [ ] Buat registry join allowlist, kardinalitas, arah join, dan kebijakan penanganan agregasi ganda.
- [ ] Perluas structured query compiler multi-product dengan tenant scope, row scope, PII, serta akses tiap sisi join.
- [ ] Aktifkan field lanjutan tab 10–13 setelah compiler dan validasinya siap.
- [ ] Uji total agregasi pada one-to-many, relasi ambigu, unauthorized join, filter waktu, dan saved query versi lama.

Selesai jika laporan/join menghasilkan angka yang benar dan tidak memperluas akses data pengguna.

### BE-15 — Kebijakan AI dan operasional per dataset/task

Prasyarat: BE-10 dan BE-11; kontrak parameter mengikuti BE-12.

- [ ] Buat registry task/prompt/version dan assignment model melalui allowlist server; jangan simpan API key dalam workbook.
- [ ] Tambahkan trigger, threshold, masking, budget, dan fallback policy per task dengan approval/audit perubahan.
- [ ] Tambahkan edit jadwal, timezone, dependency job, concurrency policy, dan incremental watermark yang commit hanya setelah load sukses.
- [ ] Implementasikan retention snapshot/artifact/audit sesuai kebutuhan, statistik proses, dan notifikasi NEEDS_INPUT/FAILED.
- [ ] Pertimbangkan SSE untuk progres serta similarity/embedding/query cache hanya dengan kebutuhan dan invalidation yang jelas.
- [ ] Aktifkan parameter tab 07/08 bertahap; uji jadwal, retry, perubahan policy, batas biaya, dan pergantian kredensial.

Selesai jika operasi berulang dapat dikonfigurasi, diamati, dan dipulihkan tanpa menghilangkan bukti review.

### BE-16 — Kesiapan deployment production

Prasyarat: tahap yang akan dirilis sudah selesai. Pemeriksaan lingkungan dasar boleh dilakukan sejak awal.

- [ ] Review lalu terapkan migrasi `9c32a61d740e` dan migrasi berikutnya pada lingkungan tujuan; migrasi test bukan rollout aplikasi.
- [ ] Verifikasi role PostgreSQL operasional/DDL/reader, Redis/broker/backend, worker, storage, dan health readiness.
- [ ] Uji akses Google Sheet nyata, OpenAI nyata, kuota/pricing/budget, dan rotasi key/service account sesuai panduan kredensial.
- [ ] Benchmark dataset besar; tambahkan batch/COPY dan object storage jika dibutuhkan oleh ukuran/retention data.
- [ ] Lengkapi monitoring/metrik/alert, distributed login rate limiting, kebijakan RLS, dan proteksi audit sesuai model deployment.
- [ ] Evaluasi OIDC, secret management, TLS, pembatasan akses master sensitif, dan masa simpan data berdasarkan kebutuhan lingkungan.
- [ ] Uji backup/restore, disaster recovery, failure recovery, serta keamanan akses lintas tenant pada deployment sebenarnya.
- [ ] Dokumentasikan rollout, kompatibilitas frontend/backend, rollback, dan hasil acceptance test; bedakan restore data dari rollback konfigurasi.

Selesai jika release checklist untuk lingkungan tujuan mempunyai bukti verifikasi nyata, bukan hanya hasil mock/unit test.

## Checklist wajib pada setiap tahap

- [ ] Model/migrasi dan strategi backfill/rollback ditinjau bila schema berubah.
- [ ] Validasi server, izin role/tenant, revision, idempotency, dan failure handling sesuai dampak perubahan.
- [ ] Pengujian perilaku sukses serta kasus gagal penting lulus di database test terpisah.
- [ ] API Reference menjelaskan payload, respons, error, role, status, dan mekanisme polling/resume yang baru.
- [ ] Contoh payload serta OpenAPI/schema diperbarui; `scripts/export_api_reference.py --check` lulus.
- [ ] Parameter yang belum didukung tetap disebutkan pada capabilities dan tidak dibuang diam-diam saat import Excel.
- [ ] Bukti pengujian dan batasan dicatat; status TODO diperbarui setelah kriteria selesai terpenuhi.

## Catatan progres

| Tahap | Status awal | Bukti penyelesaian / pekerjaan berikutnya |
|---|---|---|
| Fondasi review konfigurasi | Selesai di kode/test | [Panduan review ETL](PANDUAN_REVIEW_ETL.md); rollout aplikasi ada pada BE-16 |
| BE-01 | Selesai: kontrak dasar | Keputusan pengguna, schema policy, guard lifecycle/role, dan tes; belum terhubung runtime import |
| BE-02 | Selesai di kode/test | Migrasi, GET/PUT klasifikasi, gate runtime dan worker; migrasi dilaporkan selesai oleh pengguna |
| BE-03 | Selesai di kode/test | Registry berversi, candidate review, binding/dry-run/approval; belum memuat record master |
| BE-04 | Selesai di kode/test | Target per master, UUID stabil, constraint, storage deployment, pencarian/masking; import belum aktif |
| BE-05 | Selesai di kode/test | Snapshot/policy tetap, idempotency, checkpoint, temuan, cancel/revalidate/resume dan recovery; AI/apply belum aktif |
| BE-06 | Selesai di kode/test | Staging, pertanyaan/keputusan berversi, koreksi, kandidat allowlist, proposal registry approved; import/apply belum aktif |
| BE-07 | Implementasi inti tersedia | Preview token, approval reviewer, apply UPSERT; hardening policy/conflict masih terbuka |
| BE-08 sampai BE-11 | Berikutnya; belum mulai | Referensi/FK, review AI, dan integrasi alur lengkap |
| BE-12 | Sebagian selesai | DQ, precision/varchar, locale angka, unit, timezone sumber, currency kurs tetap; lihat [handoff frontend](FRONTEND_BE12.md). Effective dating lanjutan, multi-target, dan schema evolution masih pending |
| BE-13 sampai BE-15 | Bertahap | Taxonomy/semantic memiliki implementasi parsial sesuai checklist; parameter operasional lanjutan belum selesai |
| BE-16 | Belum selesai | Verifikasi integrasi nyata serta rollout per release |

Referensi: [Spesifikasi master data](MASTER_DATA_DAN_VALIDASI_IMPORT.md), [cakupan template ETL](REVIEW_KONFIGURASI_ETL.md), [API Reference aktif](API_REFERENCE.md), [batasan implementasi](IMPLEMENTASI.md), dan [konfigurasi/rotasi kredensial](KONFIGURASI_DAN_ROTASI_KREDENSIAL.md).
