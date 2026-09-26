# Audit kesesuaian backend dan frontend

Audit ini membandingkan `docs/TODO_BACKEND.md` dengan kode pada
`C:\projek\vue-googlesheet-ai` tanggal 26 September 2026. Status **tersedia** berarti
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
| BE-14 registry join | CRUD/lifecycle join relationship; compiler masih single-product | Tersedia untuk endpoint aktif | Route `/governance` menyediakan list/create/edit/approve/reject, revision, produk/kolom, cardinality, join type, dan duplicate policy. UI menjelaskan bahwa JOIN query belum aktif. |
| BE-15 tahap awal | Registry/lifecycle AI task policy dan runtime policy approved | Tersedia untuk endpoint aktif | Route `/governance` menyediakan list/create/approve/reject dengan purpose, prompt version terdaftar, model allowlist, revision, role, error recovery, dan tanpa API key. |
| BE-16 | Acceptance dan rollout production | Belum selesai | Bukan fitur UI tunggal; bukti deployment lintas layanan tetap diperlukan. |

## Hasil implementasi frontend

1. `transform_parameters` tersedia pada tipe kolom ETL, normalisasi/validasi lokal,
   editor operasi `prefix`, `suffix`, dan `replace`, serta tes payload. Expression bebas
   tetap tidak diterima.
2. Halaman Governance menyediakan lifecycle registry join relationship dan menjaga
   revision terbaru. Status APPROVED tetap tidak mengaktifkan query join.
3. Halaman yang sama menyediakan lifecycle AI task policy. Prompt version berasal dari
   mapping server dan API key tidak ditampilkan atau disimpan.
4. `vue-googlesheet-ai/docs/IMPLEMENTASI_FRONTEND.md` dan panduan Governance sudah
   diperbarui mengikuti implementasi aktif.

## Verifikasi audit

- `npm.cmd test`: **54 unit test lulus**.
- `npm.cmd run test:e2e`: **58 browser test lulus**.
- `npm.cmd run build`: typecheck dan build production lulus; Vite hanya memberi warning
  ukuran chunk chart yang sudah ada.
