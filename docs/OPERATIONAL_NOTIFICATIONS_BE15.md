# Statistik proses dan notifikasi operasional BE-15

Implementasi ini memberi operator pandangan tenant-scoped atas status job dan batch
import, serta inbox persisten untuk kondisi yang memerlukan tindakan.

## Endpoint

Role `PLATFORM_ADMIN`, `DATA_STEWARD`, `SOURCE_OWNER`, dan `TECHNICAL_APPROVER` dapat
memakai endpoint berikut:

- `GET /api/v1/operations/summary`
- `GET /api/v1/notifications?unacknowledged_only=true&offset=0&limit=50`
- `POST /api/v1/notifications/{notification_id}/acknowledge`

Summary mengembalikan jumlah per status pada `jobs` dan `import_reviews`, jumlah
notifikasi yang belum diakui, serta `generated_at`. Semua query selalu dibatasi
`tenant_id` pengguna.

Notifikasi dibuat dalam transaksi yang sama saat job berubah ke `FAILED`, worker dianggap
terputus, batch import berubah ke `NEEDS_INPUT`, atau job import gagal dan batch terkait
berubah ke `FAILED`. `event_key` unik per tenant mencegah event kegagalan job yang sama
dicatat dua kali. Payload hanya menyimpan kode error, jenis job, status/revisi, dan ID
resource. Raw row, nilai Sheet, prompt, serta PII tidak disalin ke notifikasi.

Acknowledge mengisi `acknowledged_by` dan `acknowledged_at` dengan lock baris, bersifat
idempotent, dan mencatat `notification.acknowledged` pada audit log. Acknowledge hanya
menandai bahwa operator sudah membaca event; tindakan ini tidak me-retry job, menjawab
pertanyaan import, atau mengubah status resource.

Migration `h8d1f4a7c9e6` membuat `platform.operational_notification`, unique key tenant,
indeks inbox, serta foreign key tenant-aware untuk pengguna yang mengakui. Retention
snapshot/artifact/audit dan kanal push/SSE tetap pekerjaan BE-15 berikutnya.
Migration lanjutan `i9e2a5b8d0f7` merekonsiliasi constraint tenant dari dependency
source dan ledger AI policy yang ditemukan saat validasi schema head.
