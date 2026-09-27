# Audit kesesuaian backend dan frontend

Audit awal membandingkan `docs/TODO_BACKEND.md` dengan kode pada
`C:\projek\vue-googlesheet-ai` pada 26 September 2026; status BE16 diberi addendum
27 September 2026. Status **tersedia** berarti
kontrak backend memiliki tipe/pemanggilan dan alur UI yang sesuai. Bukti browser
memakai mock API; hasilnya tidak membuktikan deployment Google, OpenAI, PostgreSQL,
worker, atau CORS production.

## Ringkasan

| Tahap | Cakupan backend saat ini | Status frontend | Bukti / gap |
|---|---|---|---|
| Fondasi, BE-01 | Auth, role, source, konfigurasi, review, workbook, job | Tersedia | Shell, workspace, review konfigurasi, job, admin, dan quality sudah terhubung. |
| BE-02 | Klasifikasi tab dan gate revision | Tersedia | `SheetClassification.vue`, helper klasifikasi, unit test dan browser test klasifikasi. |
| BE-03 | Registry/lifecycle master dan source binding | Tersedia | Halaman daftar/detail master serta `MasterBindingView.vue`; create, submit, approve/reject, deactivate dan binding tercakup. |
| BE-04 | Storage master dan pencarian record | Tersedia | `MasterStorageView.vue` menangani storage plan/deploy, masking, pagination/filter, leading zero, serta `as_of`. |
| BE-05 | Daftar/detail/state import review | Tersedia | `ImportReviewsView.vue` dan `ImportReviewDetailView.vue` menangani create/list/detail, cancel, revalidate, resume, findings dan checkpoint. |
| BE-06 | Pertanyaan dan keputusan terstruktur | Tersedia | Detail batch menangani filter pertanyaan, revision, koreksi, pilih kandidat, pertahankan nilai, dan proposal master. |
| BE-07 | Preview, approval, apply dan konflik sumber | Tersedia | Preview token, separation of duties, apply, stale handling, source-conflict confirmation, dan penutupan periode tercakup tes browser. |
| BE-08 | Binding kolom dan resolver referensi | Tersedia | `ColumnBindingsView.vue` serta resolver pada detail batch mendukung EXACT/ALIAS/EMPTY/CANDIDATE/AMBIGUOUS/NOT_FOUND. |
| BE-09 | Dependency plan, orphan check dan deploy FK | Tersedia untuk endpoint aktif | `MastersView.vue` membaca plan/orphan, menampilkan cycle/load order, meminta konfirmasi, lalu deploy FK. Hardening backend yang masih terbuka belum dapat diwakili UI. |
| BE-10 | Evidence review AI per batch | Tersedia untuk kontrak aktif | Detail batch menampilkan coverage, reviewed rows, masked fields, model/prompt metadata, findings dan blocker. Provider nyata tetap pekerjaan deployment. |
| BE-11 | `sync-review` dan preview migrasi | Sebagian, selaras dengan backend | Workspace/review konfigurasi menyediakan manual `sync-review` dan preview migrasi. Orkestrasi approval/apply penuh, apply migrasi, serta E2E domain juga masih terbuka di backend. |
| BE-12 | Parameter runtime, effective dating dan APPEND policy | Tersedia untuk cakupan backend | UI tersedia untuk precision/scale, varchar, date/locale/timezone, unit/currency, DQ, default, effective dating, `as_of`, close periods, APPEND duplicate policy, serta editor `transform_parameters` untuk `prefix`/`suffix`/`replace`. Multi-target/schema evolution memang belum tersedia di backend. |
| BE-13 | Taxonomy registry/version/binding/resolver/AI suggestion | Tersedia untuk cakupan backend | Halaman taxonomy dan binding, version draft/publish, resolver, validasi nilai, saran deterministic/generatif, konfigurasi `in_taxonomy`, workbook, serta pertanyaan batch memiliki implementasi dan tes. Acceptance provider nyata tetap terbuka. |
| BE-14 tahap 1-9 | Metadata semantic, metrik, ambiguity dan visualisasi | Tersedia | `ProductMetadata.vue`, editor semantic di review, Dashboard/Chat, template ambiguity, dan `ResultChart.vue` menangani table/KPI/bar/line/area/pie/donut/combo/scatter/heatmap. |
| BE-14 registry join | CRUD/lifecycle dan structured compiler multi-product | Tersedia | Route `/governance` mengelola lifecycle; Dashboard memilih relationship APPROVED dan field qualified. Backend memeriksa path, akses, scope, PII, dan agregasi. |
| BE-15 tahap runtime | Registry AI, budget/fallback, cron/timezone/concurrency, dependency source, incremental watermark, statistik proses, dan notifikasi persisten | Tersedia untuk endpoint aktif | `/governance` mengelola policy AI, `/jobs` mengelola schedule/dependency serta inbox/acknowledge, dan workspace mengelola watermark per tab. API key tetap tidak masuk frontend. |
| BE-16 (addendum 27 Sep) | Registry atribut/assignment, bundle/grant, policy/binding, metadata/review sumber, aktivasi SOURCE dan gate produk parsial | Sebagian tersedia sesuai cakupan backend | AdminView mengelola registry, assignment, bundle dan policy/preview; Workspace menangani metadata/review/aktivasi; Dashboard/Chat memakai katalog terotorisasi. Sumber legacy tanpa metadata, capability lintas halaman, row/column masking, access request, dan default-deny penuh masih terbuka. |
| BE-17 | Acceptance dan rollout production | Belum selesai | Bukan fitur UI tunggal; bukti deployment lintas layanan tetap diperlukan. |

## Hasil implementasi frontend

1. `transform_parameters` tersedia pada tipe kolom ETL, normalisasi/validasi lokal,
   editor operasi `prefix`, `suffix`, dan `replace`, serta tes payload. Expression bebas
   tetap tidak diterima.
2. Halaman Governance menyediakan lifecycle registry join relationship dan menjaga
   revision terbaru. Dashboard hanya mengaktifkan relationship APPROVED yang dapat diakses.
3. Halaman yang sama menyediakan lifecycle AI task policy. Prompt version berasal dari
   mapping server dan API key tidak ditampilkan atau disimpan.
4. `vue-googlesheet-ai/docs/IMPLEMENTASI_FRONTEND.md` dan panduan Governance sudah
   diperbarui mengikuti implementasi aktif.
5. Addendum BE16: form registrasi sumber memakai assignment aktif, admin mereview
   metadata dan memilih policy SOURCE approved, sementara produk sumber pending tidak
   muncul di Dashboard/Chat. Kontrol visual bukan pengganti gate backend; lihat
   [batasan BE16](ACCESS_JURISDICTION_BE16.md).

## Verifikasi audit

- Baseline audit awal: `npm.cmd test` **54 unit test lulus** dan
   `npm.cmd run test:e2e` **62 skenario browser lulus**. Angka ini tidak mencakup
   skenario BE16 yang ditambahkan sesudahnya.
- Baseline audit awal: `npm.cmd run build`: typecheck dan build production lulus; Vite hanya memberi warning
  ukuran chunk chart yang sudah ada.
- Regresi penuh setelah BE16 pada 27 September: `npm test` **54 unit test lulus**,
   `npm run test:e2e -- --reporter=dot` **68 skenario browser lulus**, dan
   `npm run build` (typecheck + build) lulus. Vite masih memberi warning chunk chart
   di atas 500 kB.
- Addendum BE16: tes PostgreSQL backend mencakup penolakan direct API, pemisahan
   reviewer, aktivasi, ketiga scope, deny/revoke, query/export/join dan isolasi tenant.
   Browser frontend memakai mock untuk alur metadata serta produk pending; hasilnya
   tidak membuktikan acceptance deployment. Tes scheduler reuse terpisah masih gagal
   pada assertion `reused` dan tidak boleh digabung ke klaim semua integrasi lulus.
