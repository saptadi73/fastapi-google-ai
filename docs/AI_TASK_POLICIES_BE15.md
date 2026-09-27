# Registry AI task policy BE-15

Status: registry task/prompt/version, assignment model, batas konteks, budget harian,
dan fallback model per task tersedia pada kode. Trigger sumber, masking khusus task,
retention, dan provider live masih pekerjaan lanjutan. Jadwal, dependency, watermark,
statistik proses, serta notifikasi operasional persisten sudah tersedia pada BE-15.

## Endpoint

Semua path relatif terhadap `/api/v1` dan tenant-scoped.

| Method | Path | Hak | Body | Hasil |
|---|---|---|---|---|
| GET | `/ai-task-policies` | Auth | - | Policy tenant |
| POST | `/ai-task-policies` | Editor | `AITaskPolicyCreate` | Policy `DRAFT` |
| PATCH | `/ai-task-policies/{policy_id}` | Editor | `AITaskPolicyUpdate` | Edit policy `DRAFT` |
| POST | `/ai-task-policies/{policy_id}/approve` | Reviewer | `AITaskPolicyAction` | Policy `APPROVED` |
| POST | `/ai-task-policies/{policy_id}/reject` | Reviewer | `AITaskPolicyAction` | Policy `REJECTED` |

PATCH mengganti assignment draft secara utuh dan wajib membawa `revision_no` terbaru.
Edit ditolak untuk policy yang bukan DRAFT, menaikkan revision, membersihkan bukti
approval, dan menulis audit `ai_task_policy.updated`. Approval menaikkan revision dan
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
pada `OPENAI_MODEL_ETL_CONFIG` dan `OPENAI_MODEL_NL2SQL`. Policy dengan waktu approval
terbaru untuk tenant dan purpose dipakai oleh `OpenAIService`; bila belum ada, runtime memakai
konfigurasi environment existing.

`fallback_model` opsional, wajib berbeda dari `model`, dan wajib berada dalam
`allowed_models` maupun allowlist server. Runtime mencoba fallback satu kali bila model
utama gagal atau tidak menghasilkan structured output. Metadata respons melaporkan
model yang berhasil dan `fallback_used`; ledger menjumlah token dari seluruh respons
yang sempat diterima dan mengaitkannya ke `policy_id`.

`max_context_chars` membatasi konteks antara 1.000 dan 2.000.000 karakter. Runtime
menolak konteks berlebih dengan `AI_CONTEXT_LIMIT_EXCEEDED` sebelum memanggil provider.
`daily_budget_usd` opsional membatasi estimasi biaya harian policy. Pemeriksaan memakai
ledger policy sejak 00:00 UTC dan reservasi worst-case untuk model utama plus fallback.
Pricing input/output harus dikonfigurasi jika budget policy aktif. Pelanggaran budget
policy menghasilkan `AI_TASK_BUDGET_EXCEEDED`; budget tenant tetap diperiksa terpisah.

## Scope data product NL2SQL

`data_product_code` opsional mengikat policy purpose `NL2SQL` ke satu DataProduct aktif
yang dapat diakses editor. Purpose lain wajib memakai null karena runtime ETL/taxonomy
belum mempunyai identitas DataProduct yang konsisten. Foreign key mencakup tenant dan
kode produk sehingga assignment lintas tenant tidak dapat disimpan.

Saat NL2SQL dipanggil dengan produk eksplisit, runtime memilih policy APPROVED untuk
produk tersebut terlebih dahulu lalu policy global purpose NL2SQL sebagai fallback.
Jika pertanyaan hanya memiliki satu produk accessible, kode itu juga dipakai untuk
pemilihan policy. Tanpa produk yang pasti, hanya policy global yang dipertimbangkan.

Quota pengguna, timeout, structured output, dan ledger `audit.ai_usage_log` tetap
berlaku. Registry ini belum mengatur trigger, masking per task, retry lebih dari satu
fallback, atau assignment dataset ETL/taxonomy. Version history rinci belum tersedia;
audit event menyimpan revision dan daftar field pada edit.

## Rollout

Migration `b2d5f8a1c3e7` membuat `platform.ai_task_policy`; migration
`c3e6a9b2d4f1` menambahkan scope DataProduct tenant-aware; migration
`d4f7b0c3e5a2` menambah kontrol runtime dan relasi ledger ke policy. Jalankan upgrade pada
database test/target sesuai prosedur deployment dan verifikasi `alembic check`. Provider
OpenAI nyata belum dipanggil oleh test registry; test menggunakan provider fixture/mock.
DDL migration diverifikasi offline per revision; penerapan pada PostgreSQL target tetap
bagian rollout.
