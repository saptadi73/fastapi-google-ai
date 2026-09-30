# Registry AI task policy BE-15

Status 30 September 2026: registry task/prompt/version, assignment model, batas konteks,
budget harian, dan fallback model per task tersedia pada kode. Setiap model yang dicantumkan
di assignment harus termasuk allowlist server; simpan dan approval menolak daftar yang
tidak valid. Estimasi budget mencakup prompt terdaftar, konteks, output maksimum, serta
jumlah percobaan fallback. Runtime menolak policy APPROVED tersimpan yang assignment
modelnya tidak valid. Trigger sumber, masking khusus task, retention, scope dataset
dan provider live masih pekerjaan lanjutan. Jadwal, dependency, watermark,
statistik proses, serta notifikasi operasional persisten sudah tersedia pada BE-15.

## Endpoint

Semua path relatif terhadap `/api/v1` dan tenant-scoped.

| Method | Path | Hak | Body | Hasil |
|---|---|---|---|---|
| GET | `/ai-task-policies` | Auth | - | Policy tenant |
| GET | `/ai-task-policies/{policy_id}/versions` | Auth | `offset`, `limit` | Riwayat immutable; baseline dan revision terbaru lebih dahulu |
| POST | `/ai-task-policies` | Editor | `AITaskPolicyCreate` | Policy `DRAFT` |
| PATCH | `/ai-task-policies/{policy_id}` | Editor | `AITaskPolicyUpdate` | Edit policy `DRAFT` |
| POST | `/ai-task-policies/{policy_id}/approve` | Reviewer | `AITaskPolicyAction` | Policy `APPROVED` |
| POST | `/ai-task-policies/{policy_id}/reject` | Reviewer | `AITaskPolicyAction` | Policy `REJECTED` |

PATCH mengganti assignment draft secara utuh dan wajib membawa `revision_no` terbaru.
Riwayat versi menyimpan snapshot immutable untuk `BASELINE`, `CREATED`, `UPDATED`,
`APPROVED`, dan `REJECTED`, berurutan berdasarkan revision. Snapshot memuat assignment
policy dan status, bukan secret provider. Migration `t0j3f6a9c1e8` membuat baseline dari
kondisi policy saat migration; perubahan sebelum baseline tidak direkonstruksi.

Edit ditolak untuk policy yang bukan DRAFT, menaikkan revision, membersihkan bukti
approval, dan menulis audit `ai_task_policy.updated`. Create/edit memeriksa seluruh
`allowed_models`, model utama, dan fallback terhadap allowlist server. Approval mengulang
validasi allowlist, konsistensi model dengan daftar, fallback, serta mapping prompt purpose
agar assignment tersimpan yang tidak valid tidak dapat disetujui. Approval menaikkan
revision dan membutuhkan role reviewer sesuai kebijakan role aplikasi. API key tidak
pernah diterima oleh payload ini dan tidak disimpan di workbook atau tabel policy.

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
ledger policy sejak 00:00 UTC dan reservasi worst-case untuk prompt developer terdaftar,
konteks, output maksimum, serta model utama plus fallback.
Pricing input/output harus dikonfigurasi jika budget policy aktif. Pelanggaran budget
policy menghasilkan `AI_TASK_BUDGET_EXCEEDED`; budget tenant tetap diperiksa terpisah.

## Scope dataset per purpose

Policy dapat bersifat global atau diikat ke satu dataset dengan tepat satu scope field:

- `ETL_CONFIG`: `data_source_id` menunjuk source tenant yang sama. Scope dipakai saat
  membuat draft AI konfigurasi dan saat review import dari source tersebut.
- `TAXONOMY_RECOMMEND`: `taxonomy_id` menunjuk taxonomy tenant yang aktif dan APPROVED.
- `NL2SQL`: `data_product_code` menunjuk DataProduct aktif yang dapat diakses editor.

Scope yang tidak cocok dengan purpose ditolak oleh schema. Foreign key tenant-aware dan
validasi service mencegah scope lintas tenant. Runtime memilih policy APPROVED yang exact
lebih dahulu, lalu policy global purpose sebagai fallback; tanpa identitas dataset hanya
policy global yang dipertimbangkan.

Saat NL2SQL dipanggil dengan produk eksplisit, atau taxonomy/ETL dipanggil dengan
resource ID yang diketahui, runtime memilih policy scoped APPROVED terlebih dahulu.
NL2SQL juga memakai satu-satunya produk accessible bila tidak ada produk eksplisit.

Quota pengguna, timeout, structured output, dan ledger `audit.ai_usage_log` tetap
berlaku. Registry ini belum mengatur trigger, masking per task, retry lebih dari satu
fallback. Riwayat sebelum baseline tidak direkonstruksi; perubahan lifecycle setelah
baseline memiliki snapshot lengkap.

## Rollout

Migration `b2d5f8a1c3e7` membuat `platform.ai_task_policy`; migration
`c3e6a9b2d4f1` menambahkan scope DataProduct tenant-aware; migration
`d4f7b0c3e5a2` menambah kontrol runtime dan relasi ledger ke policy. Jalankan upgrade pada
database test/target sesuai prosedur deployment dan verifikasi `alembic check`.
Migration `t0j3f6a9c1e8` menambahkan history table/baseline dan `u1k4g7b0d2f9`
menambahkan source/taxonomy scope. Provider
OpenAI nyata belum dipanggil oleh test registry; test menggunakan provider fixture/mock.
DDL migration diverifikasi offline per revision; penerapan pada PostgreSQL target tetap
bagian rollout.
