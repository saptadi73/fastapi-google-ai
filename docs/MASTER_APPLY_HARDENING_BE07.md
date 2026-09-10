# Hardening transaksi master BE-07

Perubahan 10 September 2026 memperbaiki apply master tanpa effective dating. Sebelumnya,
token diperiksa terhadap checkpoint, tetapi perubahan target atau staging setelah approval
tidak dibandingkan kembali dengan rencana approved. Dua batch approved dapat bergiliran
mendapat lock lalu menimpa hasil batch sebelumnya.

Apply kini menghitung ulang preview setelah advisory transaction lock per master diperoleh.
Rencana berbeda ditolak dengan `IMPORT_PREVIEW_STALE` (409) sebelum write. Preview format
lama ditolak `IMPORT_PREVIEW_REQUIRED` (409); buat preview format terbaru. Perubahan
target/staging memerlukan revalidate dan approval ulang sesuai lifecycle batch existing.
Payload endpoint dan schema database tidak berubah.

UPDATE mempertahankan UUID, menaikkan `_revision_no`, memperbarui `_updated_at` dan
lineage sumber. UNCHANGED tidak ditulis ulang dan tidak dihitung pada `rows_applied`.
Record yang tidak muncul dalam batch tetap dipertahankan (`KEEP`). Kegagalan INSERT
membatalkan UPDATE sebelumnya, revision/status batch, dan audit apply dalam transaksi
yang sama. Setelah penyebab kegagalan diperbaiki, retry dengan approval/token yang masih
valid dapat berhasil; retry batch SUCCEEDED ditolak tanpa penulisan ulang.

## Verifikasi

`tests/test_master_apply_postgres.py` menggunakan storage, service preview/approval/apply,
token, lock, constraint, dan transaksi PostgreSQL asli pada `TEST_DATABASE_URL` terpisah.
Sepuluh kasus mencakup UUID/revision/lineage, key null/kosong/duplikat, staging kosong,
rollback dan retry, skip UNCHANGED/KEEP, target/staging stale, serta dua batch bersamaan.
Tes konkurensi memeriksa `pg_blocking_pids` sebelum transaksi pemenang di-commit.

Hasil: **23 tes PostgreSQL** gabungan master (10), effective dating (7), APPEND (6)
lulus; **14 tes** import review/preview HTTP lulus; **225 tes non-integrasi** termasuk
workbook lulus (93 tes integrasi dikecualikan pada perintah regresi non-integrasi).
Ruff file perubahan, exporter `--check` **152 operasi**, dan `git diff --check` lulus.

```powershell
venv/Scripts/python.exe -m pytest tests/test_master_apply_postgres.py tests/test_effective_dating_postgres.py tests/test_append_postgres.py -q
venv/Scripts/python.exe -m pytest -m 'not integration' -q
venv/Scripts/python.exe -m ruff check app/services/import_review_service.py tests/test_master_apply_postgres.py
venv/Scripts/python.exe scripts/export_api_reference.py --check
```

`is_current` di-stub dan batch siap review di-seed untuk memisahkan bukti transaksi dari
onboarding, dependency upstream, dan provider AI. Kebijakan konflik antar sumber
REQUIRE_REVIEW/AUTHORITATIVE_SOURCE serta pembatasan UPDATE_ONLY masih memerlukan
hardening tersendiri; suite ini tidak membuktikan kebijakan tersebut. Tidak ada rollout
production. Penulis SQL eksternal yang mengabaikan lock aplikasi juga di luar bukti ini.
