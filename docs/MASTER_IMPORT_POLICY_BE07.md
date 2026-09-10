# Kebijakan insert dan konflik sumber BE-07

Implementasi 10 September 2026 menegakkan policy dari definisi master approved pada
preview, approval, dan apply, termasuk master bermasa berlaku. Tidak ada migrasi database.

## Perilaku preview

| Kasus | Hasil | Tindakan |
|---|---|---|
| Kode baru, PROPOSE_INSERT | INSERT_PROPOSED | Reviewer menyetujui batch beserta usulan insert |
| Kode baru, UPDATE_ONLY | INVALID, reason_code MASTER_INSERT_FORBIDDEN | Perbaiki input atau ubah policy melalui lifecycle master |
| UPDATE biasa dari sumber record yang sama, REQUIRE_REVIEW | UPDATE | Approval batch biasa |
| UPDATE berbeda dari sumber record lain/asal tidak diketahui, REQUIRE_REVIEW | UPDATE dan requires_source_confirmation=true | Konfirmasi eksplisit reviewer, hash preview, dan alasan |
| UPDATE dari sumber non-otoritatif, AUTHORITATIVE_SOURCE | KEY_CONFLICT, reason_code MASTER_SOURCE_FORBIDDEN | Gunakan sumber otoritatif; approval tidak mengabaikan larangan |
| Nilai sama dengan target | UNCHANGED | Tidak memindahkan lineage atau menaikkan revision |

`summary.insert_proposed` menghitung kode master baru yang boleh diusulkan. `summary.insert`
tetap dipakai untuk insert NON_MASTER. Batch yang mengandung INVALID/KEY_CONFLICT tetap
atomik: baris valid lainnya tidak ditulis. `blocking_codes` berisi outcome pemblokir.
`can_approve` menunjukkan tidak adanya blocker data/policy dan kelayakan status pada GET;
frontend tetap harus memenuhi `requires_source_confirmation` sebelum mengirim approval.

AUTHORITATIVE_SOURCE mengatur perubahan record existing; kode baru dari sumber lain
tetap mengikuti PROPOSE_INSERT/UPDATE_ONLY dan approval. Sumber otoritatif wajib berada
dalam tenant yang sama, aktif, tidak dijeda, berklasifikasi MASTER terkonfirmasi, dan
memiliki binding approved ke master/version, revision klasifikasi, serta fingerprint
terbaru. Status binding, sheet, dan sumber diperiksa ulang dengan lock.

## Konfirmasi reviewer

GET/POST preview menambahkan `source_conflicts` dan `requires_source_confirmation`.
Daftar konflik UPDATE berisi `source_row` dan UUID `record_id`; penutupan periode berisi
`record_id` dan `action: CLOSE_PERIOD`. Before/after tetap mengikuti masking per role.
Konfirmasi mencakup seluruh konflik dalam preview tersebut, bukan alias global atau
persetujuan untuk import berikutnya. Untuk memilih sebagian perubahan, perbaiki batch
melalui alur existing lalu buat preview dan approval baru.

```json
{
  "revision_no": 1,
  "preview_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "accept_source_conflicts": true,
  "comment": "Sumber kedua telah dikoreksi dan dipilih menggantikan nilai lama."
}
```

Kirim ke POST `/import-reviews/{id}/approve` memakai role reviewer dan hash nyata dari
preview terbaru. `accept_source_conflicts` default false; tanpa konflik, body lama tetap
berlaku. Konflik memerlukan flag true, hash yang sama, dan alasan non-whitespace.
Tanpa salah satu syarat tersebut: `IMPORT_SOURCE_CONFIRMATION_REQUIRED` (409); hash
berbeda: `IMPORT_PREVIEW_STALE` (409). Larangan policy tetap
`IMPORT_PREVIEW_CONFLICT` (409). Role editor tanpa hak reviewer tetap 403.

Audit `import.source_conflicts_approved` menyimpan reviewer, alasan, daftar konflik,
dan hash preview. Checkpoint menyimpan `source_conflicts_approved_hash`. Apply
memeriksa ulang evidence ini setelah lock; status APPROVED saja tidak cukup.

## Effective dating dan kompatibilitas

Versi baru tanpa penutupan periode juga tunduk pada UPDATE_ONLY. Penutupan periode
existing dari sumber lain memerlukan konfirmasi REQUIRE_REVIEW; sumber non-otoritatif
ditolak `MASTER_SOURCE_FORBIDDEN` (409) ketika mencoba menutup periode.
Guard interval/versi immutable existing tetap berlaku.

Hash preview master kini mencakup policy approved dan daftar konflik sumber. Preview
master yang dibuat sebelum perubahan ini harus dibuat ulang; batch lama yang sudah
APPROVED memerlukan revalidate, preview, dan approval ulang. Perubahan policy atau
target sesudah approval ditolak sebagai stale; authority/binding tidak valid ditolak
`MASTER_AUTHORITY_INVALID` (409). Revalidate mencabut checkpoint approval lama.

## Bukti dan batasan

Hasil verifikasi: **36 tes PostgreSQL lulus** (19 policy, 10 transaksi master,
7 effective dating); **225 tes non-integrasi lulus**, termasuk workbook. Regresi
non-integrasi mengecualikan 104 tes integrasi pada saat koleksi, bukan hasil skip
provider. Tes pencabutan konfirmasi saat revalidate juga lulus setelah penambahan
guard tersebut. Ruff file perubahan, exporter `--check` **152 operasi**, dan
`git diff --check` lulus.

`tests/test_master_import_policy.py` mencakup transaksi PostgreSQL, bypass checkpoint
legacy, policy berubah setelah approval, binding ditolak/stale, sumber nonaktif,
tenant lain, audit konfirmasi, lineage, effective dating, serta kontrak HTTP approval.
Fixture menyiapkan batch siap review dan men-stub `is_current`; tes HTTP mengganti
dependency autentikasi dengan user fixture, tetapi memakai route/schema/service dan
transaksi asli. Ini bukan acceptance provider AI/Google Sheets atau rollout production.
Konsistensi terhadap penulis SQL eksternal yang mengabaikan lock aplikasi belum dibuktikan.

```powershell
venv/Scripts/python.exe -m pytest tests/test_master_import_policy.py tests/test_master_apply_postgres.py tests/test_effective_dating_postgres.py -q
venv/Scripts/python.exe -m pytest -m 'not integration' -q
venv/Scripts/python.exe scripts/export_api_reference.py --check
```
