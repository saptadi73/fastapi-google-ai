# TODO implementasi backend

Acuan pengerjaan bertahap `fastapi-googlesheet-ai`, ditinjau ulang 30 September 2026. Dokumen ini adalah checklist pekerjaan, bukan pernyataan bahwa endpoint usulan sudah tersedia. Urutan utama: **klasifikasi → master baku → review import → referensi/FK → validasi AI setiap import → taxonomy → semantic/query lanjutan**.

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

Verifikasi historis setelah BE-06: **99 tes backend lulus**, Ruff lulus, serta exporter memverifikasi **117 operasi API**. Migrasi BE-06 `6d1305460956`, staging pertanyaan/keputusan, dan Alembic check diuji pada database test; integrasi provider nyata dan production belum dibuktikan oleh tes ini. Catatan ini dilanjutkan oleh BE-07: preview, approval, dan apply record master sekarang tersedia pada kode dan pengujian.

## Sinkronisasi frontend

Audit awal 26 September 2026 dengan addendum BE16 27 September tersedia di
[audit kesesuaian backend dan frontend](AUDIT_FRONTEND_BACKEND_2026-09-26.md).
Frontend sudah mencakup BE-02 sampai BE-10, cakupan aktif BE-13, BE-14 tahap 1–9,
serta endpoint aktif registry join BE-14, AI task policy BE-15, dan BE16 tahap 1–4
parsial. BE-11/BE-12 tetap mengikuti status parsial backend; editor
`transform_parameters` BE-12 tersedia. Baseline sebelum BE16: **54 unit test dan
62 skenario browser lulus**. Regresi terkini 27 September 2026: **54 unit test,
68 skenario browser, dan build/typecheck frontend lulus**; tes browser memakai mock
API dan bukan acceptance deployment.

Addendum 6 Oktober 2026: frontend menyediakan bantuan kontekstual global untuk 26 pola route,
termasuk login, analitik NL2SQL, ETL, governance, import, operasional, dan administrasi. Dialog
menjelaskan fungsi serta langkah penggunaan, mendukung keyboard/focus, dan mempunyai fallback untuk
route baru. Menu `/guide` memberikan workflow 10 tahap dari administrasi, onboarding Google Sheet,
master/taxonomy, ETL/import, sampai dashboard/chart. Bukti: **98 unit test**, tes browser bantuan,
panduan dan navigasi viewer, typecheck, serta production build lulus. Lihat
[bantuan kontekstual frontend](FRONTEND_CONTEXTUAL_HELP.md) dan
[panduan pengguna](USER_GUIDE_END_TO_END.md).

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
- [x] Tegakkan UPDATE_ONLY pada preview/approval/apply, tampilkan INSERT_PROPOSED untuk PROPOSE_INSERT, dan pertahankan record hilang (KEEP).
- [x] Ikat preview/approval ke snapshot dan revision target master; periksa ulang sebelum commit.
- [x] Implementasikan UPSERT atomik, lock/concurrency control, idempotency, dan lineage sumber setiap perubahan.
- [x] Terapkan gate approval dan pertanyaan wajib pada endpoint apply serta worker, termasuk saat dipanggil langsung.
- [x] Tambahkan advisory transaction lock per master/tab pada apply untuk mencegah penulisan paralel.
- [x] Uji dua import master bersamaan, key kosong/duplikat, retry, dan kegagalan tengah transaksi dengan rollback PostgreSQL.
- [x] Uji REQUIRE_REVIEW dengan konfirmasi reviewer terikat hash/alasan/audit serta AUTHORITATIVE_SOURCE dengan binding approved dan isolasi tenant, termasuk penutupan periode.

Status BE-07: preview/approval/apply, policy insert, konflik sumber, record hilang, dan konflik key tersedia pada kode/test. Hardening 10 September 2026 memeriksa ulang preview setelah lock, menaikkan revision UPDATE, dan melewati UNCHANGED. Tes PostgreSQL membuktikan konkurensi dengan `pg_blocking_pids`, penolakan target/staging stale, key kosong/duplikat, rollback UPDATE sebelum INSERT gagal, retry, UUID/lineage, serta KEEP. Freshness upstream/provider di-seed pada suite ini; bukan bukti BE-10/BE-11 atau production. Detail: [hardening transaksi BE-07](MASTER_APPLY_HARDENING_BE07.md).

Lanjutan policy 10 September: celah UPDATE_ONLY dan konflik sumber di atas sudah
ditutup. Recheck preview kini mencakup effective dating. Konflik sumber memerlukan
konfirmasi eksplisit dengan hash/alasan dan audit; sumber non-otoritatif tidak dapat
menimpa/menutup periode. Binding authority aktif/approved, versi, fingerprint,
klasifikasi, serta tenant diperiksa ulang. Verifikasi: **36 tes PostgreSQL dan 225
tes non-integrasi lulus**, Ruff dan exporter 152 operasi lulus. [Kontrak frontend dan bukti](MASTER_IMPORT_POLICY_BE07.md).

### BE-08 — Binding kolom dan resolusi referensi master

Prasyarat: BE-03, BE-06, dan BE-07.

- [x] Tambahkan registry relasi kolom → master, required/optional, normalisasi, cardinality, dan versi persetujuan.
- [x] Sediakan rekomendasi binding berdasarkan metadata master dan profiling kolom; pengguna tetap wajib mengonfirmasi mapping.
- [x] Sediakan endpoint resolusi nilai dengan hasil EXACT/CANDIDATE/AMBIGUOUS/NOT_FOUND dan kandidat terotorisasi.
- [x] Resolusi nilai menghasilkan exact/alias/fuzzy candidate dan menandai `requires_question` untuk nilai ambigu/tidak ditemukan.
- [x] Simpan UUID master hasil resolusi ke staging sambil mempertahankan nilai asli; fallback ke nama tampilan ditolak.
- [x] Implementasikan alias berscope tenant/master/kolom, dengan approval dan revision; pencabutan alias masih memerlukan perubahan binding draft.
- [x] Uji referensi tidak ditemukan, ambigu, master/record nonaktif, relasi opsional, serta perubahan alias/master setelah preview dan approval pada PostgreSQL.

Status BE-08: resolver dan hardening dependency selesai pada cakupan kode/test. Alias terikat tenant/tab/kolom/master, edit binding mencabut approval, record nonaktif ditolak, dan UUID staging divalidasi ulang pada preview/approval/apply. Capture/is_current asli mendeteksi perubahan alias/record. Kontrak source_column wajib, revision staging, masking, error, dan batasan ada di [hardening BE-08](MASTER_REFERENCES_BE08.md). Confidence AI tidak otomatis menggabungkan entitas berbeda; FK fisik dan alur lengkap tetap BE-09/BE-11.

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
- [~] Uji penolakan FK orphan/lintas tenant langsung di PostgreSQL, enforcement FK, dan retry constraint sudah tersedia; coverage dependensi bertingkat/siklus serta kegagalan privilege/DDL lintas konfigurasi masih perlu ditambahkan.

Status BE-09: dependency plan, load order, deteksi siklus, pemeriksaan orphan/type, dan deployment FK fisik tersedia. Validasi target kini menggunakan UUID hasil resolusi terhadap `_record_id` master; test PostgreSQL mencakup orphan, isolasi tenant, enforcement FK, dan retry constraint (`reused`). Coverage dependensi bertingkat/siklus dan hardening DDL lintas konfigurasi masih terbuka; query join NL2SQL tetap di luar cakupan BE-09.

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

Status BE-10: worker sudah memanggil review terstruktur ketika OpenAI dikonfigurasi, menyimpan coverage, metadata model/prompt, findings, blocker, masking field sensitif, chunk cache, dan pertanyaan per issue. Penggantian snapshot dengan fingerprint schema sama sudah dicakup; pengujian end-to-end provider/prompt injection nyata masih terbuka. Label “semua diperiksa AI” tidak dipakai untuk hasil sampling atau pengecualian.

### BE-11 — Integrasi alur lengkap dan migrasi data lama

Prasyarat: BE-07–BE-10.

- [x] Sediakan jalur `sync-review` yang membuat batch review per tab dan mengembalikan tab yang belum siap sebagai `BLOCKED`.
- [x] Pertahankan idempotency batch saat sync-review diulang pada snapshot/configuration yang sama.
- [~] Hubungkan sync manual dan terjadwal ke batch review: `/sync-review` manual dan scheduler kini refresh snapshot lalu membuat batch idempotent; approval/apply penuh dan jalur `/sync` legacy masih dipertahankan.
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
- [~] Sediakan registry operasi allowlist beserta parameter schema dan `on_error`; transform `prefix`/`suffix`/`replace` berparameter untuk text/varchar kini didukung dan round-trip XLSX teruji. Expression dinamis, kondisi, dan urutan transform bebas tetap diblokir.
- [~] Lengkapi DQ format/domain, threshold persen, severity/owner, max_age_days, serta default value dengan semantics yang disetujui (runtime format allowlist/domain allowed_values, threshold per rule, default bertipe, umur UTC, dan round-trip XLSX tersedia; severity/owner menjadi metadata, action_on_fail mengendalikan routing; notifikasi owner otomatis belum tersedia).
- [~] Implementasikan versi/master bermasa berlaku: versi eksplisit immutable, key entitas + valid_from, validasi overlap preview/apply dan skip UNCHANGED tersedia. Penutupan periode terbuka tersedia melalui preview opt-in dan approval; rollback, dua apply bersamaan, retry, batas as_of, dan isolasi tenant telah diuji PostgreSQL. Koreksi bebas dan FK as-of masih terbuka. Lihat [panduan](EFFECTIVE_DATING_BE12.md).
- [x] Implementasikan konversi satuan eksplisit untuk massa/volume/panjang, faktor tervalidasi dan pembulatan HALF_UP/HALF_EVEN/DOWN; alias ejaan dan satuan custom tetap unsupported; currency memakai parameter terpisah.
- [x] Rancang split grain/multi-target, schema evolution, default/update condition, serta kebijakan append event identik. [Rancangan dan batas runtime](LOAD_POLICIES_BE12.md); payload multi-target/evolution/kondisi dinamis tetap unsupported.
- [~] Tambahkan dukungan bertahap ke schema, compiler, dry-run, artifact, API, dan XLSX secara bersamaan; numeric/date/locale, DQ, unit/currency/timezone, APPEND tanpa key, dan transform parameter allowlist tersedia. Multi-target, schema evolution, expression/kondisi dinamis, dan parameter lanjutan tetap ditolak.

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

Progres transform parameter BE-12 (26 September 2026): operasi allowlist `prefix`,
`suffix`, dan `replace` mendukung parameter statis pada kolom text/varchar. Kontrak
menolak target non-text, parameter tanpa operation code, operation tanpa parameter,
duplikasi, dan `replace` tanpa replacement. Runtime mengikuti urutan
`transformation_codes`; catalog API dan workbook kolom AC ikut terhubung. Bukti:
**6 tes terarah lulus**, termasuk runtime, kontrak invalid, dan round-trip XLSX.

Selesai per field/fitur jika konfigurasi benar-benar memengaruhi runtime dan export–import tidak kehilangan maknanya. Pecah tahap ini menjadi PR per kemampuan, bukan satu perubahan besar.

### BE-13 — Taxonomy dan mapping kategori

Handoff frontend: [panduan bertahap BE-13](FRONTEND_BE13.md) dan
[payload per aksi](api/BE13_FRONTEND_PAYLOADS.json). Tahap 1-5 sudah terhubung pada frontend;
provider/model nyata dan acceptance pada deployment tujuan belum diverifikasi.

Perbaikan schema registry (9 September 2026): model taxonomy kini memetakan metadata
existing, approval tersimpan, dan migrasi `8a96b7c5d4ef` menyelaraskan index/unique/FK
tenant untuk master binding serta taxonomy. Database test sudah upgrade dan
`alembic check` bersih. Verifikasi: 208 tes non-integrasi dan 17 tes PostgreSQL lulus
(3 migrasi, 1 HTTP taxonomy, 6 APPEND, 7 effective dating), Ruff file perubahan dan
exporter 145 operasi lulus;
[cakupan, bukti, dan downgrade aditif](REGISTRY_SCHEMA_REPAIR.md). Rollout production
serta lifecycle taxonomy lanjutan tetap terpisah dari perbaikan ini.

Prasyarat: BE-08, BE-11, dan kamus parameter BE-12.

Status tinjauan 26 September 2026: **cakupan kode dan frontend BE-13 tersedia; acceptance provider/deployment tujuan belum diverifikasi. BE-14 sudah berjalan sampai tahap 9**.
Guard lifecycle, dependency hash, validasi final-write, revision binding, dan pertanyaan
ambigu telah diperbaiki. [Temuan, kontrak frontend, dan pekerjaan terbuka](REVIEW_BE13.md).

- [~] Buat registry taxonomy/version/hierarchy dan term, terpisah dari identitas record master; create/list term, hierarchy, dan approval immutable tersedia. Draft/revisi/publikasi atomik berikutnya dan snapshot immutable tersedia; sejarah sebelum migrasi tidak direkonstruksi.
- [x] Sediakan binding taxonomy ke kolom sumber dengan optimistic revision dan approval/rejection.
- [x] Sediakan resolver term exact/alias/kandidat/ambigu dengan flag `requires_question`.
- [~] Tambahkan usulan AI, approval mapping, alias terkontrol, serta pertanyaan untuk nilai ambigu (resolver, ranking rekomendasi, dan pertanyaan otomatis worker tersedia; endpoint rekomendasi generatif tersedia dan memerlukan konfirmasi; verifikasi provider nyata masih terbuka, alias dikelola melalui draft/publikasi versi taxonomy).
- [~] Validasi taxonomy berbasis mapping kolom dan invalidasi dependency tersedia pada preview/approval/apply/ETL legacy. Literal rule DQ `in_taxonomy` serta normalisasi/pertanyaan otomatis worker tersedia. Rule memerlukan mapping approved, tidak menerima WARN; nilai asing/ambigu menjadi blocker.
- [~] Field taxonomy tersedia pada mapping kolom ETL (`taxonomy_id`, `taxonomy_version`, `taxonomy_required`) dan dipertahankan di JSON konfigurasi. Editor/render/parse binding taxonomy tab 04 kolom U-W tersedia, dengan identitas signed dan validasi. Editor term registry tetap melalui API.
- [~] Uji hierarki, kode tidak ditemukan, mapping konflik, versioning, dan isolasi tenant: tes HTTP/PostgreSQL untuk parent, immutable approval, stale dependency, pertanyaan, concurrent binding, serta isolasi tenant/batch tersedia. Tes publikasi lintas versi, migration backfill, normalisasi canonical dan workbook taxonomy ditambahkan pada lanjutan ini.

Selesai jika nilai kategori dinormalisasi melalui aturan approved tanpa mengubah identitas master secara keliru.

Progres BE-13 (26 September 2026): suite terarah taxonomy lulus **46 tes** mencakup
publish lintas versi dan invalidasi binding lama, hierarchy/cycle/ancestor aktif,
backfill snapshot migration dan tenant FK, canonical normalization, pertanyaan worker,
AI recommendation contract, serta round-trip workbook taxonomy. Runtime BE-13 tetap
memerlukan acceptance provider OpenAI/deployment tujuan; sejarah taxonomy sebelum
migrasi snapshot tidak direkonstruksi.

### BE-14 — Semantic catalog, metrik, intent, dan join

Prasyarat: BE-09, BE-11; gunakan BE-12/BE-13 jika memakai unit/domain/taxonomy.

- [~] Lengkapi metadata bisnis produk, default periode, unit, sinonim, dan lifecycle approval metrik. Tahap 1: edit name/description; tahap 2: unit/sinonim katalog; tahap 6: definisi bisnis/unit/sinonim dalam konfigurasi reviewed dan workbook C/D/K; tahap 7: periode default UTC dengan override filter, conflict guard, frontend dan workbook I/J. Registry approval metrik terpisah masih terbuka. Kontrak: [frontend BE14](FRONTEND_BE14.md).
- [~] Tambahkan expression/filter/null handling metrik melalui AST/operasi allowlist yang tervalidasi (aggregation/kolom, PRESERVE/ZERO_RESULT, serta filter tetap bertipe melalui aggregate FILTER tersedia dalam konfigurasi reviewed, frontend, dan workbook tab 11 H/M; expression arithmetic AST lanjutan belum).
- [~] Tambahkan query template berparameter dan periode relatif, timezone, output type, priority, serta ambiguity policy. Tahap 5 BE14 meminta pilihan eksplisit untuk template ambigu (backend + Chat frontend), memeriksa ulang akses/versi; parameter, periode, timezone/output dan priority masih terbuka.
- [x] Tambahkan spesifikasi visualisasi allowlist pada QueryPlan dan saved query: table, KPI, bar, line, area, pie/donut, combo, scatter, heatmap; validasi field output, renderer Dashboard/Chat, override manual, dan isolasi SQL/cache tersedia pada tahap 9. Input bahasa alami NL2SQL kini juga menjadi panel utama Dashboard dengan klarifikasi, kandidat template, tabel, chart, detail request, dan feedback.
- [x] Buat registry join allowlist, kardinalitas, arah join, dan kebijakan penanganan agregasi ganda. Registry tenant-scoped dengan lifecycle DRAFT/APPROVED/REJECTED, optimistic revision, validasi product/column, join type, cardinality, duplicate policy, dan aktivasi hanya untuk relationship APPROVED tersedia.
- [x] Perluas structured query compiler multi-product dengan tenant scope, row scope, PII, serta akses tiap sisi join. QueryPlan menerima path relationship terarah; field produk sekunder memakai `PRODUCT.field`, dan SQL guard hanya menerima object/kolom hasil kompilasi katalog.
- [x] Izinkan NL2SQL AI menemukan join hanya dari graph relationship APPROVED yang dapat diakses. Konteks dibatasi 10 produk/50 relationship, mengikuti arah maksimal lima hop, membuang relationship stale/PII, mengunci root product eksplisit, dan menolak kode relationship hasil AI di luar konteks.
- [~] Aktifkan field lanjutan tab 10–13 setelah compiler dan validasinya siap. Tab 10/11 sudah aktif untuk metadata periode dan metrik yang didukung; tab 12/13 serta parameter lanjutan masih terbuka.
- [~] Uji kontrak registry, path compiler, tenant/row scope tiap sisi, field sensitif, agregasi ambigu, cache revision, saved-query validation, dan payload browser sudah tersedia. Eksekusi PostgreSQL nyata untuk LEFT/INNER join, filter waktu lintas product, serta concurrency perubahan relationship masih terbuka.

Selesai jika laporan/join menghasilkan angka yang benar dan tidak memperluas akses data pengguna.

Status tinjauan BE-14 pada 27 September 2026: tahap 1–11 tersedia pada backend, frontend, dan dokumentasi. Structured query multi-product dan discovery NL2SQL memakai relationship APPROVED yang dapat diakses. Bukti saat tahap BE-14 mencakup 337 tes backend non-integration, regresi join/NL2SQL/import terarah, Ruff, 54 unit frontend, 62 skenario browser, dan typecheck. Regresi frontend terbaru setelah BE-16 tercatat pada bagian sinkronisasi frontend di atas. Pekerjaan terbuka BE-14: registry approval metrik, arithmetic AST, template berparameter/priority/output timezone, tab 12/13 lengkap, PostgreSQL join E2E, dan acceptance provider AI/deployment nyata.

Progres registry join BE-14 (27 September 2026): model/migrasi
`platform.join_relationship`, endpoint list/create/edit/approve/reject, validasi
tenant/product/column, cardinality `ONE_TO_ONE`/`MANY_TO_ONE`/`ONE_TO_MANY`,
join type `LEFT`/`INNER`, dan duplicate policy sudah tersedia. Structured compiler
menjalankan path terarah maksimal lima relationship APPROVED, memeriksa akses produk,
tenant/row scope, PII, versi cache, dan agregasi ganda. Dashboard menyediakan pemilih
relationship serta field sekunder qualified. NL2SQL AI menerima graph aman yang sama
dan keluarannya diperiksa ulang sebelum kompilasi. Acceptance provider nyata dan
PostgreSQL/deployment tetap pekerjaan berikutnya.

### BE-15 — Kebijakan AI dan operasional per dataset/task

Prasyarat: BE-10 dan BE-11; kontrak parameter mengikuti BE-12.

- [~] Buat registry task/prompt/version dan assignment model melalui allowlist server; registry tenant-scoped, create/edit DRAFT dengan optimistic revision, approval, prompt mapping internal, runtime override OpenAI, audit edit, frontend, serta assignment per-purpose: DataProduct untuk NL2SQL, source untuk ETL_CONFIG, taxonomy APPROVED untuk TAXONOMY_RECOMMEND, semuanya dengan fallback global. Semua model divalidasi terhadap allowlist server saat simpan dan approval; snapshot immutable serta endpoint riwayat tersedia. API key tetap hanya dari environment.
- [~] Tambahkan trigger, threshold, masking, budget, dan fallback policy per task dengan approval/audit perubahan; batas karakter konteks, budget harian policy yang mengestimasi prompt + konteks + output, fallback model allowlisted satu kali, ledger policy, frontend, dan audit edit tersedia. Trigger sumber dan masking khusus task masih terbuka.
- [x] Tambahkan edit jadwal, timezone, dependency job, concurrency policy, dan incremental watermark yang commit hanya setelah load sukses; cron/timezone/revision/audit, policy `QUEUE_LATEST`/`SKIP_IF_RUNNING`, graph dependency tenant-aware, serta watermark INTEGER/DECIMAL/DATE/DATETIME pada ETL dan import review tersedia pada backend/frontend.
- [~] Implementasikan retention snapshot/artifact/audit sesuai kebutuhan, statistik proses, dan notifikasi NEEDS_INPUT/FAILED; statistik tenant, inbox persisten, event transaksional, acknowledge teraudit, frontend, dan migration tersedia. Policy/worker retention masih terbuka.
- [x] Tambahkan SSE terautentikasi untuk progres job dengan heartbeat, batas koneksi dua menit,
  event terminal, dan fallback polling frontend. Tambahkan cache similarity deterministik yang
  versioned per tenant/taxonomy/algoritma serta perkuat query cache dengan schema key, freshness,
  revisi source/policy, fingerprint keputusan akses, dan `token_version`. Cache embedding tetap
  tidak dibuat karena belum ada provider/model/vector lifecycle yang dapat menjadi kunci invalidasi.
- [~] Aktifkan parameter tab 07/08 bertahap; keduanya tetap read-only pada XLSX. Tab 07 memuat trigger bebas serta alias model/prompt yang harus berasal dari registry server; tab 08 mencampur jadwal/watermark (sudah tersedia lewat API terpisah) dengan batch/retry yang belum memiliki kontrak runtime. Regression workbook memastikan edit kedua tab ditolak. Acceptance rotasi kredensial/provider nyata tetap memerlukan deployment.

Selesai jika operasi berulang dapat dikonfigurasi, diamati, dan dipulihkan tanpa menghilangkan bukti review.

Progres audit BE-15 (30 September 2026): registry `platform.ai_task_policy` dan endpoint
list/create/edit/approve/reject tersedia untuk purpose `ETL_CONFIG`, `TAXONOMY_RECOMMEND`,
dan `NL2SQL`. Prompt version hanya menerima file prompt yang dipetakan server;
model dan seluruh `allowed_models` harus termasuk allowlist server dari settings atau model purpose terkait.
`OpenAIService` memakai policy APPROVED bila tersedia dan tetap mengambil API key dari
environment, bukan workbook/database. Kontrak lengkap: [AI task policy BE-15](AI_TASK_POLICIES_BE15.md).
Migration `c3e6a9b2d4f1` menambahkan assignment DataProduct tenant-aware untuk NL2SQL;
policy scoped diprioritaskan sebelum policy global. Migration `d4f7b0c3e5a2` menambah
batas konteks, budget harian, fallback model, dan `audit.ai_usage_log.policy_id`.
Migration `t0j3f6a9c1e8` menambah `ai_task_policy_version`, baseline snapshot policy
existing, serta GET versi tenant-scoped dengan pagination.
Migration `u1k4g7b0d2f9` menambah scope source/taxonomy dengan foreign key tenant-aware;
runtime memakai source ID untuk ETL/import review dan taxonomy ID untuk rekomendasi.
Runtime mereservasi estimasi biaya worst-case termasuk prompt terdaftar, menolak konteks
atau budget sebelum provider, serta mencoba fallback allowlisted satu kali. Validasi
service kini menolak entri `allowed_models` yang tidak ada di allowlist server dan
approval memeriksa ulang daftar model, model utama/fallback, serta mapping prompt.
Runtime menolak policy APPROVED tersimpan yang assignment modelnya tidak valid.
Verifikasi terarah: 77 tes backend policy/runtime/query-security/scheduler/watermark/
notifikasi/workbook lulus; integrasi PostgreSQL/API history, scope source/taxonomy, dan
scheduler `SYNC_REVIEW` reuse juga lulus. Governance browser test lulus. Frontend regression:
54 unit test, 73 skenario browser, dan build/typecheck lulus. Provider nyata belum dipanggil.

Belum ada definisi retensi per jenis data/masa simpan, trigger task yang disepakati,
atau aturan masking khusus purpose; karena itu policy/worker penghapusan dan aktivasi
import workbook tab 07/08 belum boleh dianggap selesai. Jadwal/watermark
tetap dikelola melalui endpoint khusus; batch/retry XLSX belum memiliki kontrak runtime.
SSE job dan cache similarity/query sudah aktif dengan invalidasi versioned. Cache embedding tetap
ditunda sampai provider, model, dimensi vector, serta lifecycle re-index disepakati; menambah cache
sebelum kontrak itu ada akan menghasilkan hasil stale yang tidak dapat divalidasi.
Rotasi secret terdokumentasi sebagai update environment lalu restart seluruh proses;
acceptance rotasi dan provider nyata tetap bagian deployment BE-17.

Kontrol operasional source kini dapat diedit melalui
`PATCH /sources/{source_id}/schedule`. Migration `e5a8c1d4f6b3` menambah timezone IANA,
optimistic schedule revision, dan concurrency policy. Scheduler tetap memakai durable
job: `QUEUE_LATEST` mempertahankan satu occurrence untuk dijalankan setelah job aktif,
sedangkan `SKIP_IF_RUNNING` memajukan clock dan melewati occurrence tersebut.
Migration `f6b9d2e5a7c4` menambah graph dependency tenant-aware; scheduler menunggu setiap
upstream sukses dan lebih baru daripada keberhasilan downstream terakhir.
Migration `g7c0e3f6b8d5` menambah incremental watermark per tab. Filter mempertahankan
nomor baris sumber dan hanya menerima nilai lebih besar. ETL langsung menahan watermark
bila ada issue; import review mem-pin base/candidate dan baru memajukannya pada apply
sukses dalam transaksi yang sama.
Migration `h8d1f4a7c9e6` menambah inbox notifikasi operasional tenant-scoped. Job gagal,
worker stale, serta batch `NEEDS_INPUT`/`FAILED` menghasilkan event persisten tanpa raw
data. Endpoint summary/list/acknowledge dan halaman Jobs frontend tersedia; acknowledge
idempotent dan teraudit. Retention snapshot/artifact/audit masih terbuka.
Migration `i9e2a5b8d0f7` merekonsiliasi constraint tenant graph dependency dan ledger
AI policy agar metadata model dan jalur upgrade database yang sudah hidup konsisten.

### BE-16 — Kontrol akses berbasis yurisdiksi bisnis

Prasyarat: autentikasi/role fondasi, metadata sumber BE-02, taxonomy BE-13, dan DataProduct
BE-14. Rancangan rinci: [Kontrol akses yurisdiksi BE-16](ACCESS_JURISDICTION_BE16.md).

Tahap 1 selesai pada migration `j0f3b6c9e1a8`: registry atribut tenant-scoped untuk
departemen, domain bisnis, yurisdiksi, dan clearance; assignment bertanggal efektif;
revoke yang merotasi sesi; audit; endpoint effective access role + assignment; serta UI
administrasi frontend. Fondasi ini belum mengubah keputusan akses data lama.
Tahap 2 selesai pada migration `k1a4c7d0f2b9`: kamus delapan aksi baku, permission
bundle tenant-scoped, grant bertanggal efektif, self-grant/revoke guard, rotasi sesi,
audit, effective access gabungan, dan UI administrasi bundle/grant.
Tahap 3 selesai pada migration `l2b5d8e1a3c0`: registry policy/binding, lifecycle
DRAFT/IN_REVIEW/APPROVED/REVOKED, approval admin berbeda, effective dating, preview
evaluator default-deny, explicit deny override, row/column controls, audit, dan UI policy.
Hardening evaluator tahap 3: akun nonaktif tidak lagi memiliki effective actions atau
keputusan ALLOW; aksi EXPORT memerlukan `export_allowed` dari setiap policy ALLOW yang
cocok. UI policy dapat mengatur izin ekspor eksplisit dan preview menampilkan hasil
izinkan/tolak. Tes integrasi PostgreSQL access serta browser BE16 lulus. Ini masih
preview pada tahap 3; enforcement produk SOURCE ditambahkan bertahap pada tahap 4.
Binding policy baru kini mewajibkan kode resource nyata milik tenant aktif; API admin
`/access/resources` menyediakan daftar/pencarian kode berscope tenant dan form Vue
memakai selector. Tes PostgreSQL menolak kode tidak ditemukan/lintas tenant dan akses
viewer ke daftar resource. Binding lama belum dibackfill atau diaudit ulang.
Fondasi tahap 4: migration `m3c6e9f2b4d1` menambah `access_status` terpisah dari status
ETL; sumber baru dan legacy default `ACCESS_POLICY_REQUIRED`. GET sumber dan workspace
Vue menampilkan status tersebut; tes PostgreSQL memverifikasi nilainya bertahan setelah
profiling. Pada saat migrasi ini dibuat, field baru penanda, bukan gate query/export;
gate untuk produk dari sumber dengan metadata ditambahkan setelah aktivasi SOURCE.
Sumber legacy tanpa metadata tetap memakai kontrol lama.
Lanjutan tahap 4: migration `n4d7f0a3c5e2` menambah metadata registrasi wajib untuk
sumber baru dan registry PURPOSE. Backend memeriksa atribut tenant/jenis/aktif, tiga
assignment aktif pendaftar, serta owner/steward aktif sebelum enqueue. Vue memakai
`/access/registration-options` untuk selector dan tes HTTP/browser memeriksa payload,
lintas tenant, serta revoke setelah daftar opsi dimuat. Sumber legacy tetap tanpa
metadata sampai diperbaiki eksplisit. Migration `o5e8a1b4d6f3` menambah optimistic
`access_revision` dan PATCH metadata lengkap untuk legacy/koreksi, dengan audit tanpa
nilai PII serta reset status akses ke pending. Vue menyediakan editor sumber terpilih
dan mempertahankan input saat konflik 409. Migration `p6f9b2c5d7a4` menambah review
metadata PENDING/APPROVED/REJECTED dengan admin reviewer berbeda, reason allowlist,
revision, audit, dan UI ringkasan/reject/approve. `access_status` tetap pending;
aktivasi berikutnya memerlukan SOURCE policy ALLOW approved. Gate bertahap menahan
produk baru pending dari katalog, query, export, report, saved query, join, serta
konteks NL2SQL; setelah aktivasi, evaluator SOURCE menegakkan aksi pengguna saat
lookup dan sebelum cache. Deny/revoke/expiry serta kontrol row/column yang belum
didukung ditolak fail-closed; Vue menyediakan pilihan policy approved. Sumber legacy
tanpa metadata tetap memakai kontrol lama. Policy template, enforcement semua jalur,
row/column policy, access request, dan default-deny penuh masih terbuka.

- [~] Tetapkan kamus aksi (`DISCOVER`, `READ`, `QUERY`, `EXPORT`, `EDIT`, `APPROVE`, `OPERATE`, `ADMIN`) dan keputusan policy dengan **default deny** serta deny eksplisit mengalahkan allow; berlaku pada evaluator dan produk SOURCE BE16, belum seluruh resource/legacy.
- [~] Perluas User Management: lifecycle akun create/activate/suspend/deactivate, role sistem, permission bundle bisnis, assignment yurisdiksi, effective dating, delegasi admin, reset/revoke sesi, dan audit. Create/aktif-nonaktif/role/bundle/assignment tersedia; suspended, delegasi, approval assignment berisiko, dan effective access lengkap belum.
- [x] Sediakan bootstrap admin awal yang idempotent dari secret environment; akun existing dipastikan aktif/`PLATFORM_ADMIN`, password tidak diubah tanpa flag recovery eksplisit, dan reset mencabut token lama. Registrasi user tetap admin-controlled, bukan self-registration publik.
- [x] Buat registry permission bundle/business role untuk paket kewenangan berulang. Bundle memetakan aksi baku, tidak membawa daftar data secara implisit; scope data tetap berasal dari assignment dan policy.
- [~] Terapkan separation-of-duties pada pengelolaan akses: self-grant/self-revoke assignment dan permission grant kini ditolak backend (`SELF_ACCESS_CHANGE`), tetapi pemohon, approver policy, penerima akses, delegasi, dan aturan konflik berisiko lainnya masih perlu diselesaikan.
- [x] Terapkan separation-of-duties minimum pada permission grant: admin tidak dapat memberi atau mencabut bundle miliknya sendiri; approval policy berisiko tetap tahap berikutnya.
- [~] Sediakan endpoint effective-access/capability untuk melihat hasil gabungan role, assignment, policy, deny, masking, dan expiry tanpa mengekspos policy/resource tenant lain. Effective role/assignment/grant dan preview per resource tersedia; endpoint capability gabungan/masking belum.
- [x] Sediakan endpoint tahap 1 effective-access untuk hasil role, aksi dasar, assignment aktif, dan expiry; perluas dengan policy/deny/masking pada tahap evaluator.
- [~] Buat registry hierarkis `organization_unit`, `business_domain`, `jurisdiction`, `data_clearance`, dan `access_purpose`; registry generik `access_attribute` dengan lima jenis, kode tenant-scoped, parent sejenis dan revision tersedia; model/domain lifecycle terpisah belum.
- [x] Buat `user_assignment` many-to-many dengan departemen/domain/wilayah/clearance, `valid_from`/`valid_to`, status, revision, pemberi tugas, dan audit. Perubahan assignment tidak memerlukan role gabungan baru.
- [x] Implementasikan registry `access_attribute` dan `user_assignment` tahap 1 untuk departemen/domain/yurisdiksi/clearance, hierarchy satu jenis, effective dating, optimistic revoke, actor, audit, dan tenant constraint PostgreSQL.
- [~] Tambahkan metadata wajib sumber: unit pemilik, business domain/category, data owner, data steward, yurisdiksi, klasifikasi sensitivitas, tujuan penggunaan, dan policy template. Semua kecuali policy template wajib untuk sumber baru; scope diverifikasi terhadap assignment aktif saat POST, legacy memerlukan koreksi eksplisit.
- [~] Tambahkan status `ACCESS_POLICY_REQUIRED`; sumber lama dibackfill ke status terbatas dan tidak otomatis dianggap publik. Status tersimpan dan produk sumber baru pending ditahan; sumber legacy null-metadata masih dapat dibaca lewat kontrol lama.
- [x] Buat registry `access_policy` dan `access_policy_binding` berversi dengan lifecycle draft/review/approve/revoke, separation of duties, effective dating, alasan, serta optimistic concurrency pada kontrak tahap 3.
- [x] Implementasikan registry dan lifecycle policy/binding tahap 3 dengan optimistic revision, effective dating, alasan keputusan, audit, dan larangan self-approval.
- [~] Implementasikan evaluator terpusat yang menerima subject, action, resource, dan context; preview serta enforcement produk SOURCE tersedia untuk allow/deny, reason, row_scope/column_rules, export flag, dan pasangan policy/revision; row predicate SQL, masking, dan export limit belum tersedia.
- [x] Implementasikan evaluator preview tahap 3 untuk subject/action/resource/waktu, default deny, explicit deny override, row scope, column visibility, export flag, policy IDs, dan reason code; enforcement endpoint data tetap tahap berikutnya.
- [~] Terapkan evaluator di seluruh list/detail source, sheet, configuration, import review, job, artifact, master, taxonomy, DataProduct, query, report, NL2SQL, dan export. DataProduct sumber BE16, query/report berbasis produk, export/join/konteks NL2SQL, list/detail/errors/lineage ETL, list/export/download artefak konfigurasi ber-metadata, serta master records dengan policy MASTER approved memakai evaluator; source admin, sheet, artefak non-konfigurasi, master registry, taxonomy, dan legacy belum.
- [~] Terapkan filter baris dari atribut pengguna secara parameterized melalui compiler, bukan SQL bebas dalam policy. Query produk/join BE16 kini menggabungkan row scope policy dengan scope legacy, memvalidasi field bertipe dan menolak field PII/nonpublik; jalur non-query dan legacy metadata masih terbuka.
- [~] Terapkan kebijakan kolom `VISIBLE`, `MASKED`, dan `HIDDEN` berdasarkan klasifikasi/clearance. Query compiler dan sanitizer katalog kini menghasilkan placeholder untuk dimension `MASKED`, default-hidden PII MEDIUM/HIGH, serta menolak `HIDDEN`/non-visible pada metric, filter, sort, dan join key; lineage, error, preview, export, dan klasifikasi otomatis masih perlu ditutup.
- [~] Untuk query multi-product/join, gunakan irisan izin semua resource dan policy paling ketat; compiler mengecek tiap produk dan relationship pending tidak ditemukan, tetapi row/column policy paling ketat belum diterapkan.
- [~] Batasi katalog, prompt, contoh, schema, relationship, cache, dan hasil AI/NL2SQL pada resource/kolom yang lolos evaluator. Filter produk SOURCE, sanitizer metadata kolom/metric, validasi saved query dan join saat create/update/approve, serta validasi ulang plan tersedia; lineage/error/preview non-query dan invalidasi cache lintas jalur belum lengkap.
- [x] Tambahkan `access_request`/approval untuk permintaan akses sementara, delegasi, alasan bisnis, expiry, revoke, dan notifikasi reviewer tanpa memberikan akses sebelum approval commit. Request atribut/bundle untuk diri sendiri, delegasi admin kepada user aktif, approval admin kedua, effective period maksimum 366 hari, cancel/reject/revoke, optimistic revision, audit, UI, serta inbox reviewer terarah tersedia.
- [~] Pisahkan kepemilikan data dari hak akses: owner/steward dan admin platform tidak otomatis mendapat akses produk SOURCE BE16; seluruh jalur PII legacy dan masking belum terlindungi model ini.
- [~] Masukkan policy/assignment revision ke cache key dan invalidasi session/query cache saat revoke, expiry, perubahan assignment, classification, atau policy. `token_version`, revisi SOURCE/policy, serta fingerprint keputusan efektif kini masuk cache key query produk/join; revoke assignment/grant menaikkan `token_version`, sedangkan grant baru langsung mengubah fingerprint tanpa memutus sesi penerima. Invalidasi classification dan resource non-query masih belum.
- [~] Audit keputusan sensitif dan perubahan policy: subject, action, resource, policy/revision, hasil, alasan kode, request ID, dan waktu; event keputusan/alasan dan actor tersedia tanpa raw PII, tetapi request ID serta revision policy per keputusan belum lengkap.
- [~] Implementasikan frontend registrasi sumber dengan selector registry, capability response, layar User Management/role/permission bundle/assignment, policy/access request, effective-access preview, masking konsisten, serta penjelasan deny yang aman. Registrasi/review/aktivasi, admin policy, access request/delegasi, serta label masking Dashboard tersedia; capability global dan masking konsisten pada seluruh tampilan belum.
- [x] Implementasikan UI tahap 1 pada Administrasi untuk membuat registry, memberi/mencabut assignment bertanggal, melihat histori, dan preview effective access role + assignment.
- [~] Uji matriks role + atribut, hierarchy departemen, multi-assignment, expiry/revoke, deny override, lintas tenant, direct API bypass, row/column leakage, export, cache stale, join, AI context, dan concurrent approval di PostgreSQL. Tes terarah SOURCE tersedia; masking, seluruh jalur dan acceptance concurrency masih perlu.
- [~] Dokumentasikan backfill, rollout bertahap, emergency break-glass dengan expiry/audit, rollback schema, serta acceptance bersama data owner dan security. Strategi rollback/aditif dan batas rollout tercatat; break-glass/acceptance masih terbuka.

Selesai jika setiap resource mempunyai metadata kepemilikan dan policy approved, semua
jalur baca/ubah/query/export memakai evaluator yang sama, serta perubahan yurisdiksi
mencabut akses tanpa menunggu perubahan role atau redeploy aplikasi.

### BE-17 — Kesiapan deployment production

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

Checklist ini adalah gate yang diterapkan pada setiap perubahan sesuai dampaknya, bukan daftar status global yang harus dicentang sekaligus.

- [ ] Model/migrasi dan strategi backfill/rollback ditinjau bila schema berubah.
- [ ] Validasi server, izin role/tenant, revision, idempotency, dan failure handling sesuai dampak perubahan.
- [ ] Pengujian perilaku sukses serta kasus gagal penting lulus di database test terpisah.
- [ ] API Reference menjelaskan payload, respons, error, role, status, dan mekanisme polling/resume yang baru.
- [ ] Contoh payload serta OpenAPI/schema diperbarui; `scripts/export_api_reference.py --check` lulus.
- [ ] Parameter yang belum didukung tetap disebutkan pada capabilities dan tidak dibuang diam-diam saat import Excel.
- [x] Relasi internal dipilih melalui nama/kode bisnis; halaman dan workbook tidak meminta UUID manual. Lihat [aturan identifier](IDENTIFIER_UX.md).
- [ ] Bukti pengujian dan batasan dicatat; status TODO diperbarui setelah kriteria selesai terpenuhi.

## Catatan progres

| Tahap | Status awal | Bukti penyelesaian / pekerjaan berikutnya |
|---|---|---|
| Fondasi review konfigurasi | Selesai di kode/test | [Panduan review ETL](PANDUAN_REVIEW_ETL.md); rollout aplikasi ada pada BE-17 |
| BE-01 | Selesai: kontrak dasar | Keputusan pengguna, schema policy, guard lifecycle/role, dan tes; enforcement runtime diteruskan oleh BE-02 |
| BE-02 | Selesai di kode/test | Migrasi, GET/PUT klasifikasi, gate runtime dan worker; migrasi dilaporkan selesai oleh pengguna |
| BE-03 | Selesai di kode/test | Registry berversi, candidate review, binding/dry-run/approval; pemuatan record diteruskan dan tersedia melalui BE-07 |
| BE-04 | Selesai di kode/test | Target per master, UUID stabil, constraint, storage deployment, pencarian/masking; alur import tersedia melalui BE-05–BE-07 |
| BE-05 | Selesai di kode/test | Snapshot/policy tetap, idempotency, checkpoint, temuan, cancel/revalidate/resume dan recovery; review AI dan apply diteruskan oleh BE-07/BE-10 |
| BE-06 | Selesai di kode/test | Staging, pertanyaan/keputusan berversi, koreksi, kandidat allowlist, proposal registry approved; apply tersedia melalui BE-07 |
| BE-07 | Selesai pada kode/test yang dicakup | Recheck preview setelah lock, revision UPDATE, skip UNCHANGED, rollback/retry; guard insert dan konflik sumber selesai. Provider/end-to-end/production tetap tahap terpisah |
| BE-08 | Selesai pada cakupan kode/test | Resolver berscope, lifecycle alias, validasi UUID, dependency freshness; lihat hardening BE-08 |
| BE-09 | Sebagian besar tersedia | Dependency plan, load order, cycle/orphan/type guard, dan FK fisik tersedia; koreksi otomatis serta hardening DDL lintas kegagalan masih terbuka |
| BE-10 | Tersedia pada cakupan kode/test | Review AI batch, coverage, masking, cache, findings/blocker, dan pertanyaan tersedia; acceptance provider/prompt injection nyata masih terbuka |
| BE-11 | Sebagian selesai | `/sync-review` manual/terjadwal kini membuat batch setelah refresh snapshot dan reuse saat konten sama; orkestrasi approval/apply penuh, apply migrasi, dan E2E domain masih terbuka |
| BE-12 | Sebagian selesai | Backend dan frontend mendukung DQ, precision/varchar, locale angka, unit, timezone, currency, effective dating, APPEND policy, serta editor transform parameter statis; multi-target/schema evolution tetap pending backend |
| BE-13 | Tersedia di kode/frontend | Taxonomy, binding, resolver, rekomendasi dan integrasi UI tersedia; acceptance provider/deployment nyata masih terbuka |
| BE-14 | Tahap 1–11 tersedia; hardening join berlanjut | Frontend mencakup metadata semantic, periode, metrik, ambiguity flow, visualisasi dinamis, lifecycle registry, dan query join approved; backend menyediakan discovery join NL2SQL tervalidasi. Approval metrik, AST lanjutan, template lengkap, provider acceptance, dan PostgreSQL join E2E masih terbuka |
| BE-15 | Sebagian selesai | Backend dan frontend registry AI/version history, scope DataProduct/source/taxonomy, budget/fallback, cron/timezone/concurrency, dependency freshness, incremental watermark transaksional, statistik proses, serta notifikasi persisten/acknowledge tersedia. Trigger/masking lanjutan, retention, workbook tab 07/08, dan provider live masih terbuka |
| BE-16 | Tahap 1–3 dan enforcement produk tahap 4 parsial | Registry atribut/assignment, bundle/grant, policy/binding, metadata sumber, aktivasi SOURCE, evaluasi katalog/query/export/join, serta access request/delegasi/notifikasi reviewer tersedia; legacy masih memakai akses lama, policy template, row/column lintas semua jalur, jalur admin/artefak, default-deny penuh dan rollout masih terbuka |
| BE-17 | Belum selesai | Verifikasi integrasi nyata serta rollout per release |

Referensi: [Spesifikasi master data](MASTER_DATA_DAN_VALIDASI_IMPORT.md), [cakupan template ETL](REVIEW_KONFIGURASI_ETL.md), [API Reference aktif](API_REFERENCE.md), [batasan implementasi](IMPLEMENTASI.md), dan [konfigurasi/rotasi kredensial](KONFIGURASI_DAN_ROTASI_KREDENSIAL.md).
