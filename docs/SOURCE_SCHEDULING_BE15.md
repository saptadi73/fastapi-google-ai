# Jadwal source BE-15

Source memiliki jadwal cron lima field, timezone IANA, revision, status pause, dan
kebijakan konkurensi. Pengubahan dilakukan melalui:

```http
PATCH /api/v1/sources/{source_id}/schedule
```

```json
{
  "revision_no": 1,
  "sync_schedule": "0 7 * * 1-5",
  "schedule_timezone": "Asia/Jakarta",
  "concurrency_policy": "SKIP_IF_RUNNING",
  "dependency_source_ids": ["11111111-1111-4111-8111-111111111111"]
}
```

`sync_schedule=null` menonaktifkan pemicu cron tanpa mengubah status pause.
`schedule_timezone` harus nama timezone IANA yang tersedia pada server. Perubahan
mengatur ulang clock jadwal ke waktu simpan agar jadwal lama tidak langsung diputar
ulang. Revision yang sudah berubah menghasilkan `SOURCE_SCHEDULE_CONFLICT`.

Kebijakan konkurensi:

- `QUEUE_LATEST`: selama job ETL/SYNC_REVIEW masih QUEUED atau RUNNING, scheduler tidak
  membuat job kedua dan tidak memajukan clock. Setelah job selesai, satu job terbaru
  akan dibuat pada polling berikutnya.
- `SKIP_IF_RUNNING`: scheduler tidak membuat job kedua dan memajukan clock, sehingga
  occurrence yang bertabrakan dilewati.

Scheduler memakai advisory lock global dan row lock `SKIP LOCKED`, sehingga beberapa
beat/worker tidak menjadwalkan source yang sama secara bersamaan. Setiap edit menulis
audit `source.schedule_updated`; pause/resume tetap memakai endpoint operasional yang
sudah ada. Migration `e5a8c1d4f6b3` harus diterapkan sebelum memakai field baru.

Migration `f6b9d2e5a7c4` menambah graph dependency tenant-aware. Self-reference dan siklus
ditolak; advisory transaction lock per tenant mencegah dua edit paralel membentuk siklus.
Downstream hanya dijadwalkan bila setiap upstream mempunyai job ETL/SYNC_REVIEW
SUCCEEDED dan waktu selesai upstream lebih baru daripada keberhasilan downstream
terakhir. Dependency yang belum pernah sukses atau masih stale menahan downstream tanpa
memajukan clock jadwal. Incremental watermark belum termasuk tahap ini.
