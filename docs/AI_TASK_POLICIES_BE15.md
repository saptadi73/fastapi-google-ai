# Registry AI task policy BE-15

Status: registry task/prompt/version dan assignment model tersedia pada kode. Trigger,
threshold, fallback per task, jadwal, watermark, retention, notifikasi, dan provider
live masih pekerjaan lanjutan.

## Endpoint

Semua path relatif terhadap `/api/v1` dan tenant-scoped.

| Method | Path | Hak | Body | Hasil |
|---|---|---|---|---|
| GET | `/ai-task-policies` | Auth | - | Policy tenant |
| POST | `/ai-task-policies` | Editor | `AITaskPolicyCreate` | Policy `DRAFT` |
| POST | `/ai-task-policies/{policy_id}/approve` | Reviewer | `AITaskPolicyAction` | Policy `APPROVED` |
| POST | `/ai-task-policies/{policy_id}/reject` | Reviewer | `AITaskPolicyAction` | Policy `REJECTED` |

`revision_no` wajib cocok dengan record terkunci. Approval menaikkan revision dan
membutuhkan role reviewer sesuai kebijakan role aplikasi. API key tidak pernah diterima
oleh payload ini dan tidak disimpan di workbook atau tabel policy.

## Purpose dan prompt

Purpose yang diizinkan:

- `ETL_CONFIG` → `etl_configuration_v1.md`
- `TAXONOMY_RECOMMEND` → `taxonomy_recommend_v1.md`
- `NL2SQL` → `nl2sql_v1.md`

`prompt_version` harus cocok dengan mapping server. Client tidak dapat mengirim path
file prompt bebas. Perubahan prompt memerlukan versi mapping server baru dan review
kode, bukan upload prompt dari workbook.

## Assignment model

`model` harus ada dalam `allowed_models` dan juga allowlist server. Allowlist server
berasal dari `OPENAI_ALLOWED_MODELS` bila diisi, ditambah model purpose yang dikonfigurasi
pada `OPENAI_MODEL_ETL_CONFIG` dan `OPENAI_MODEL_NL2SQL`. Policy `APPROVED` terbaru
untuk tenant dan purpose dipakai oleh `OpenAIService`; bila belum ada, runtime memakai
konfigurasi environment existing.

Budget, quota, timeout, structured output, dan ledger `audit.ai_usage_log` tetap
berlaku. Registry ini belum mengatur trigger, masking per task, fallback, retry policy,
atau assignment dataset individual.

## Rollout

Migration `b2d5f8a1c3e7` membuat `platform.ai_task_policy`. Jalankan upgrade pada
database test/target sesuai prosedur deployment dan verifikasi `alembic check`. Provider
OpenAI nyata belum dipanggil oleh test registry; test menggunakan provider fixture/mock.
