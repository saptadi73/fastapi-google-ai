# API schemas dan parameter

Dihasilkan dari schema/route backend oleh `scripts/export_api_reference.py`. Lihat [API Reference](../API_REFERENCE.md) untuk arti field dan mekanisme bisnis. Snapshot OpenAPI masih memakai Envelope generik untuk banyak respons; jangan menganggap `data: any` sebagai kontrak domain yang lengkap.

## Parameter setiap endpoint

Path lengkap di bawah termasuk prefix. Body `—` berarti tidak ada request body. Query parameter yang tidak tercantum tidak menyediakan fitur filter/pencarian. Batas validasi lintas field dijelaskan di API Reference.

### POST /api/v1/auth/login

Body: [LoginRequest](#loginrequest).

### POST /api/v1/auth/refresh

Body: [RefreshRequest](#refreshrequest).

### GET /api/v1/auth/me

Body: —.

### POST /api/v1/auth/logout

Body: —.

### POST /api/v1/auth/change-password

Body: [PasswordChange](#passwordchange).

### POST /api/v1/users

Body: [UserCreate](#usercreate).

### GET /api/v1/users

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":100} |

### PATCH /api/v1/users/{user_id}

Body: [UserUpdate](#userupdate).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `user_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/source-sheets/{sheet_id}/classification

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `sheet_id` | path | Ya | `string (uuid)` {} |

### PUT /api/v1/source-sheets/{sheet_id}/classification

Body: [SheetClassificationUpdate](#sheetclassificationupdate).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `sheet_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/sources/google-sheets

Body: [SourceCreate](#sourcecreate).

### GET /api/v1/sources

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":100} |

### GET /api/v1/sources/{source_id}

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/sources/{source_id}/sheets

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |

### PATCH /api/v1/source-sheets/{sheet_id}

Body: [SheetUpdate](#sheetupdate).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `sheet_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/sources/{source_id}/discover

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/sources/{source_id}/profile

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/sources/{source_id}/sync

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/sources/{source_id}/ai-configurations

Body: [AIConfigurationRequest](#aiconfigurationrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/source-sheets/{sheet_id}/configurations

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `sheet_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/source-sheets/{sheet_id}/configurations/active

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `sheet_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/master-definitions/{master_id}/storage-plan

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `master_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/master-definitions/{master_id}/deploy-storage

Body: [MasterRevisionRequest](#masterrevisionrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `master_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/master-definitions/{master_id}/records

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `master_id` | path | Ya | `string (uuid)` {} |
| `search` | query | Tidak | `string` {"default":""} |
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":50} |
| `active_only` | query | Tidak | `boolean` {"default":true} |
| `record_id` | query | Tidak | `string (uuid) / null` {} |

### GET /api/v1/master-definitions

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `search` | query | Tidak | `string` {"default":""} |
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":50} |

### POST /api/v1/master-definitions

Body: [MasterDefinitionCreate](#masterdefinitioncreate).

### POST /api/v1/master-definitions/preview

Body: [MasterDefinitionCreate](#masterdefinitioncreate).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `against` | query | Tidak | `string (uuid) / null` {} |

### GET /api/v1/master-definitions/{master_id}

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `master_id` | path | Ya | `string (uuid)` {} |

### PATCH /api/v1/master-definitions/{master_id}

Body: [MasterDefinitionPatch](#masterdefinitionpatch).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `master_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/master-definitions/{master_id}/submit-review

Body: [MasterRevisionRequest](#masterrevisionrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `master_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/master-definitions/{master_id}/approve

Body: [MasterRevisionRequest](#masterrevisionrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `master_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/master-definitions/{master_id}/reject

Body: [MasterRevisionRequest](#masterrevisionrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `master_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/master-definitions/{master_id}/deactivate

Body: [MasterRevisionRequest](#masterrevisionrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `master_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/source-sheets/{sheet_id}/master-binding

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `sheet_id` | path | Ya | `string (uuid)` {} |

### PUT /api/v1/source-sheets/{sheet_id}/master-binding

Body: [MasterBindingUpdate](#masterbindingupdate).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `sheet_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/source-sheets/{sheet_id}/master-binding/approve

Body: [MasterRevisionRequest](#masterrevisionrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `sheet_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/source-sheets/{sheet_id}/master-binding/reject

Body: [MasterRevisionRequest](#masterrevisionrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `sheet_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/sources/{source_id}/profiling-runs

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/sources/{source_id}/profiling-runs/{run_id}

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |
| `run_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/configurations/{config_id}/review

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/workbook-preview

Body: [WorkbookPreviewRequest](#workbookpreviewrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/workbook-apply

Body: [WorkbookApplyRequest](#workbookapplyrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations

Body: [ConfigurationCreate](#configurationcreate).

### GET /api/v1/configurations/{config_id}

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### PATCH /api/v1/configurations/{config_id}

Body: [ConfigurationPatch](#configurationpatch).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/validate

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/submit-review

Body: [ReviewSubmission](#reviewsubmission).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/approve

Body: [Decision](#decision).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/reject

Body: [Decision](#decision).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/clone

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/activate

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/deploy

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/rollback

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/configurations/{config_id}/artifacts

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/configurations/{config_id}/export

Body: [ExportRequest](#exportrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/configurations/{config_id}/artifacts/{artifact_id}/download

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |
| `artifact_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/configurations/{config_id}/questions

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/configurations/{config_id}/diff

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `config_id` | path | Ya | `string (uuid)` {} |
| `against` | query | Ya | `string (uuid)` {} |

### GET /api/v1/jobs

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":100} |

### GET /api/v1/jobs/{job_id}

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `job_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/jobs/{job_id}/retry

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `job_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/etl-jobs

Body: —.

### POST /api/v1/etl-jobs/{job_id}/run

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `job_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/etl-jobs/{job_id}/pause

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `job_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/etl-jobs/{job_id}/resume

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `job_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/etl-runs

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":100} |

### GET /api/v1/etl-runs/{run_id}

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `run_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/etl-runs/{run_id}/errors

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `run_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/etl-runs/{run_id}/lineage

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `run_id` | path | Ya | `string (uuid)` {} |
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":100} |

### GET /api/v1/data-quality/issues

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":100} |

### POST /api/v1/data-quality/issues/{issue_id}/resolve

Body: [ResolutionRequest](#resolutionrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `issue_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/quarantine/{source_id}/rows

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":100} |

### POST /api/v1/quarantine/{source_id}/reprocess

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `source_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/semantic/data-products

Body: —.

### PATCH /api/v1/semantic/data-products/{product_id}

Body: [ProductUpdate](#productupdate).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `product_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/semantic/metrics

Body: —.

### GET /api/v1/semantic/query-templates

Body: —.

### POST /api/v1/semantic/query-templates

Body: [SavedQueryCreate](#savedquerycreate).

### GET /api/v1/semantic/intents

Body: —.

### POST /api/v1/semantic/intents

Body: [SavedQueryCreate](#savedquerycreate).

### POST /api/v1/semantic/query-templates/{template_id}/validate

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `template_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/semantic/query-templates/{template_id}/activate

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `template_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/data-products

Body: —.

### GET /api/v1/data-products/{code}

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `code` | path | Ya | `string` {} |

### GET /api/v1/data-products/{code}/dimensions

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `code` | path | Ya | `string` {} |

### GET /api/v1/data-products/{code}/metrics

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `code` | path | Ya | `string` {} |

### POST /api/v1/data-products/{code}/query

Body: [QueryPlan](#queryplan).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `code` | path | Ya | `string` {} |

### POST /api/v1/data-products/{code}/export

Body: [QueryPlan](#queryplan).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `code` | path | Ya | `string` {} |

### POST /api/v1/saved-queries/{code}/run

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `code` | path | Ya | `string` {} |

### GET /api/v1/reports/sales/summary

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `start_date` | query | Ya | `string (date)` {} |
| `end_date` | query | Ya | `string (date)` {} |

### GET /api/v1/reports/sales/by-branch

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `start_date` | query | Ya | `string (date)` {} |
| `end_date` | query | Ya | `string (date)` {} |

### GET /api/v1/reports/sales/trend

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `start_date` | query | Ya | `string (date)` {} |
| `end_date` | query | Ya | `string (date)` {} |

### GET /api/v1/reports/inventory/stock-position

Body: —.

### GET /api/v1/reports/data-quality/summary

Body: —.

### POST /api/v1/nl2sql/query

Body: [QuestionRequest](#questionrequest).

### GET /api/v1/nl2sql/requests/{request_id}

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `request_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/nl2sql/requests/{request_id}/feedback

Body: [FeedbackRequest](#feedbackrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `request_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/nl2sql/clarifications/{request_id}

Body: [QuestionRequest](#questionrequest).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `request_id` | path | Ya | `string (uuid)` {} |

### POST /api/v1/nl2sql/requests/{request_id}/promote

Body: [SavedQueryCreate](#savedquerycreate).

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `request_id` | path | Ya | `string (uuid)` {} |

### GET /api/v1/admin/ai-usage/by-tenant

Body: —.

### GET /api/v1/admin/ai-usage/summary

Body: —.

### GET /api/v1/admin/ai-usage/by-user

Body: —.

### GET /api/v1/admin/audit-events

Body: —.

| Parameter | Lokasi | Wajib | Tipe / batas |
|---|---|---|---|
| `offset` | query | Tidak | `integer` {"minimum":0,"default":0} |
| `limit` | query | Tidak | `integer` {"maximum":100,"minimum":1,"default":100} |

### GET /health/live

Body: —.

### GET /health

Body: —.

### GET /health/database

Body: —.

### GET /health/ready

Body: —.

## Schema JSON

`Wajib` berarti field harus dikirim. Nullable berbeda dari opsional. Payload StrictModel menolak field tambahan. Default ditampilkan jika tersedia; default factory list/map kosong ditampilkan sebagai `[]`/`{}`.

### AIConfigurationRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `source_sheet_id` | Ya | `string (uuid)` | — | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "source_sheet_id": "22222222-2222-4222-8222-222222222222"
}
```

### ColumnMapping

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `source_column` | Ya | `string` | — | {"maxLength":200,"minLength":1} |
| `target_column` | Ya | `string` | — | {"pattern":"^[a-z][a-z0-9_]{0,62}$"} |
| `target_type` | Ya | `enum ["text","varchar","integer","bigint","numeric","boolean","date","timestamp","timestamptz","uuid"]` | — | — |
| `business_name` | Tidak | `string` | "" | — |
| `nullable` | Tidak | `boolean` | true | — |
| `is_business_key` | Tidak | `boolean` | false | — |
| `is_primary_key` | Tidak | `boolean` | false | — |
| `transformation_codes` | Tidak | `array<enum ["trim","normalize_whitespace","parse_date_id","parse_decimal_id","uppercase","lowercase","null_if_empty"]>` | [] | {"maxItems":10} |
| `pii_classification` | Tidak | `enum ["NONE","LOW","MEDIUM","HIGH"]` | "NONE" | — |
| `confidence` | Tidak | `number` | 1 | {"maximum":1.0,"minimum":0.0} |
| `reason` | Tidak | `string` | "" | — |

### ConfigurationCreate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `source_sheet_id` | Ya | `string (uuid)` | — | — |
| `configuration` | Ya | `ETLConfiguration` | — | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "source_sheet_id": "22222222-2222-4222-8222-222222222222",
  "configuration": {
    "schema_version": "1.0",
    "dataset_business_name": "Penjualan Cabang",
    "dataset_description": "Data transaksi penjualan per cabang",
    "grain": "Satu baris per nomor transaksi",
    "target_schema": "trusted",
    "target_table": "sales_transaction",
    "load_strategy": "UPSERT",
    "columns": [
      {
        "source_column": "ID",
        "target_column": "transaction_id",
        "target_type": "text",
        "nullable": false,
        "is_business_key": true,
        "transformation_codes": [
          "trim"
        ]
      },
      {
        "source_column": "Tanggal",
        "target_column": "transaction_date",
        "target_type": "date",
        "nullable": false,
        "transformation_codes": [
          "parse_date_id"
        ]
      },
      {
        "source_column": "Cabang",
        "target_column": "branch_name",
        "target_type": "text",
        "nullable": false,
        "transformation_codes": [
          "trim"
        ]
      },
      {
        "source_column": "Total",
        "target_column": "net_amount",
        "target_type": "numeric",
        "nullable": false,
        "transformation_codes": [
          "parse_decimal_id"
        ]
      }
    ],
    "data_quality_rules": [
      {
        "column": "net_amount",
        "rule": "min",
        "value": 0,
        "action_on_fail": "REJECT_ROW"
      }
    ],
    "semantic": {
      "code": "SALES",
      "dimensions": [
        "transaction_id",
        "transaction_date",
        "branch_name"
      ],
      "metrics": [
        {
          "code": "net_sales",
          "column": "net_amount",
          "aggregation": "sum",
          "label": "Penjualan bersih"
        },
        {
          "code": "transaction_count",
          "column": "transaction_id",
          "aggregation": "count",
          "label": "Jumlah transaksi"
        }
      ],
      "allowed_roles": [
        "PLATFORM_ADMIN",
        "DATA_STEWARD",
        "ANALYST",
        "VIEWER"
      ]
    },
    "unresolved_questions": [],
    "overall_confidence": 1
  }
}
```

### ConfigurationPatch

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `revision_no` | Ya | `integer` | — | {"minimum":1.0} |
| `configuration` | Ya | `ETLConfiguration` | — | — |
| `question_answers` | Tidak | `map<string, string>` | {} | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "revision_no": 1,
  "configuration": {
    "schema_version": "1.0",
    "dataset_business_name": "Penjualan Cabang",
    "dataset_description": "Data transaksi penjualan per cabang",
    "grain": "Satu baris per nomor transaksi",
    "target_schema": "trusted",
    "target_table": "sales_transaction",
    "load_strategy": "UPSERT",
    "columns": [
      {
        "source_column": "ID",
        "target_column": "transaction_id",
        "target_type": "text",
        "nullable": false,
        "is_business_key": true,
        "transformation_codes": [
          "trim"
        ]
      },
      {
        "source_column": "Tanggal",
        "target_column": "transaction_date",
        "target_type": "date",
        "nullable": false,
        "transformation_codes": [
          "parse_date_id"
        ]
      },
      {
        "source_column": "Cabang",
        "target_column": "branch_name",
        "target_type": "text",
        "nullable": false,
        "transformation_codes": [
          "trim"
        ]
      },
      {
        "source_column": "Total",
        "target_column": "net_amount",
        "target_type": "numeric",
        "nullable": false,
        "transformation_codes": [
          "parse_decimal_id"
        ]
      }
    ],
    "data_quality_rules": [
      {
        "column": "net_amount",
        "rule": "min",
        "value": 0,
        "action_on_fail": "REJECT_ROW"
      }
    ],
    "semantic": {
      "code": "SALES",
      "dimensions": [
        "transaction_id",
        "transaction_date",
        "branch_name"
      ],
      "metrics": [
        {
          "code": "net_sales",
          "column": "net_amount",
          "aggregation": "sum",
          "label": "Penjualan bersih"
        },
        {
          "code": "transaction_count",
          "column": "transaction_id",
          "aggregation": "count",
          "label": "Jumlah transaksi"
        }
      ],
      "allowed_roles": [
        "PLATFORM_ADMIN",
        "DATA_STEWARD",
        "ANALYST",
        "VIEWER"
      ]
    },
    "unresolved_questions": [],
    "overall_confidence": 1
  },
  "question_answers": {}
}
```

### DatabaseHealth

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `database` | Tidak | `"postgresql"` | "postgresql" | — |
| `connected` | Tidak | `true` | true | — |
| `name` | Ya | `string` | — | — |
| `latency_ms` | Ya | `number` | — | {"minimum":0.0} |

### DatabaseHealthResponse

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `status` | Ya | `string` | — | — |
| `data` | Ya | `DatabaseHealth` | — | — |
| `meta` | Tidak | `object` | {} | — |
| `errors` | Tidak | `array<object>` | [] | — |

### DatasetKind

`enum ["MASTER","NON_MASTER"]`

### Decision

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `revision_no` | Ya | `integer` | — | {"minimum":1.0} |
| `comment` | Tidak | `string` | "" | {"maxLength":2000} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "revision_no": 2,
  "comment": "Mapping, business key, dan hasil validasi sudah diperiksa."
}
```

### ETLConfiguration

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `schema_version` | Tidak | `"1.0"` | "1.0" | — |
| `dataset_business_name` | Ya | `string` | — | {"maxLength":200,"minLength":1} |
| `dataset_description` | Tidak | `string` | "" | {"maxLength":2000} |
| `grain` | Ya | `string` | — | {"maxLength":500,"minLength":1} |
| `target_schema` | Tidak | `"trusted"` | "trusted" | — |
| `target_table` | Ya | `string` | — | {"pattern":"^[a-z][a-z0-9_]{0,29}$"} |
| `load_strategy` | Ya | `enum ["APPEND","UPSERT","FULL_REFRESH"]` | — | — |
| `columns` | Ya | `array<ColumnMapping>` | — | {"maxItems":100,"minItems":1} |
| `data_quality_rules` | Tidak | `array<QualityRule>` | [] | {"maxItems":100} |
| `semantic` | Ya | `SemanticDefinition` | — | — |
| `unresolved_questions` | Tidak | `array<string>` | [] | — |
| `overall_confidence` | Tidak | `number` | 1 | {"maximum":1.0,"minimum":0.0} |

### EffectiveDating

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `valid_from_column` | Ya | `string` | — | {"pattern":"^[a-z][a-z0-9_]{0,62}$"} |
| `valid_to_column` | Ya | `string` | — | {"pattern":"^[a-z][a-z0-9_]{0,62}$"} |
| `interval` | Tidak | `"START_INCLUSIVE_END_EXCLUSIVE"` | "START_INCLUSIVE_END_EXCLUSIVE" | — |
| `overlap_policy` | Tidak | `"REJECT"` | "REJECT" | — |

### Envelope

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `status` | Ya | `string` | — | — |
| `data` | Tidak | `any` | — | — |
| `meta` | Tidak | `object` | {} | — |
| `errors` | Tidak | `array<object>` | [] | — |

### ExportRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `format` | Tidak | `enum ["JSON","YAML","XLSX"]` | "JSON" | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "format": "XLSX"
}
```

### FeedbackRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `feedback` | Ya | `string` | — | {"maxLength":1000,"minLength":1} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "feedback": "Hasil sesuai laporan cabang."
}
```

### Liveness

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `alive` | Tidak | `true` | true | — |

### LivenessResponse

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `status` | Ya | `string` | — | — |
| `data` | Ya | `Liveness` | — | — |
| `meta` | Tidak | `object` | {} | — |
| `errors` | Tidak | `array<object>` | [] | — |

### LoginRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `tenant_code` | Ya | `string` | — | {"maxLength":80,"minLength":1} |
| `username` | Ya | `string` | — | {"maxLength":100,"minLength":1} |
| `password` | Ya | `string (password)` | — | {"writeOnly":true} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "tenant_code": "default",
  "username": "admin",
  "password": "PASSWORD_LOGIN_ANDA"
}
```

### MasterBindingUpdate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `revision_no` | Ya | `integer` | — | {"minimum":0.0} |
| `master_definition_id` | Ya | `string (uuid)` | — | — |
| `master_version` | Ya | `integer` | — | {"minimum":1.0} |
| `classification_revision` | Ya | `integer` | — | {"minimum":1.0} |
| `columns` | Ya | `array<ColumnMapping>` | — | {"maxItems":100,"minItems":1} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "revision_no": 0,
  "master_definition_id": "11111111-1111-4111-8111-111111111111",
  "master_version": 1,
  "classification_revision": 2,
  "columns": [
    {
      "source_column": "Kode Produk",
      "target_column": "product_code",
      "target_type": "text",
      "nullable": false,
      "is_business_key": true,
      "transformation_codes": [
        "trim"
      ]
    },
    {
      "source_column": "Nama Produk",
      "target_column": "product_name",
      "target_type": "text",
      "nullable": false,
      "transformation_codes": [
        "trim",
        "normalize_whitespace"
      ]
    }
  ]
}
```

### MasterDefinitionCreate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `code` | Ya | `string` | — | {"pattern":"^[a-z][a-z0-9_]{0,62}$"} |
| `definition` | Ya | `MasterSchema` | — | — |
| `reviewed_candidate_ids` | Tidak | `array<string (uuid)>` | [] | {"maxItems":100} |
| `duplicate_review_reason` | Tidak | `string` | "" | {"maxLength":2000} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "code": "products",
  "definition": {
    "name": "Produk",
    "description": "Identitas produk baku",
    "aliases": [
      "Barang"
    ],
    "fields": [
      {
        "name": "product_code",
        "type": "text",
        "nullable": false,
        "pii_classification": "NONE"
      },
      {
        "name": "product_name",
        "type": "text",
        "nullable": false,
        "pii_classification": "NONE"
      }
    ],
    "business_key": [
      "product_code"
    ],
    "label_field": "product_name",
    "policy": {
      "new_record_policy": "PROPOSE_INSERT",
      "source_conflict_policy": "REQUIRE_REVIEW"
    }
  },
  "reviewed_candidate_ids": [],
  "duplicate_review_reason": ""
}
```

### MasterDefinitionPatch

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `revision_no` | Ya | `integer` | — | {"minimum":1.0} |
| `definition` | Ya | `MasterSchema` | — | — |
| `reviewed_candidate_ids` | Tidak | `array<string (uuid)>` | [] | {"maxItems":100} |
| `duplicate_review_reason` | Tidak | `string` | "" | {"maxLength":2000} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "revision_no": 1,
  "definition": {
    "name": "Produk",
    "description": "Identitas produk baku",
    "aliases": [
      "Barang"
    ],
    "fields": [
      {
        "name": "product_code",
        "type": "text",
        "nullable": false,
        "pii_classification": "NONE"
      },
      {
        "name": "product_name",
        "type": "text",
        "nullable": false,
        "pii_classification": "NONE"
      }
    ],
    "business_key": [
      "product_code"
    ],
    "label_field": "product_name",
    "policy": {
      "new_record_policy": "PROPOSE_INSERT",
      "source_conflict_policy": "REQUIRE_REVIEW"
    }
  },
  "reviewed_candidate_ids": [],
  "duplicate_review_reason": ""
}
```

### MasterField

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `name` | Ya | `string` | — | {"pattern":"^[a-z][a-z0-9_]{0,62}$"} |
| `type` | Ya | `enum ["text","varchar","integer","bigint","numeric","boolean","date","timestamp","timestamptz","uuid"]` | — | — |
| `nullable` | Tidak | `boolean` | true | — |
| `pii_classification` | Tidak | `string` | "NONE" | {"pattern":"^(NONE&#124;LOW&#124;MEDIUM&#124;HIGH)$"} |

### MasterImportPolicy

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `new_record_policy` | Ya | `NewMasterRecordPolicy` | — | — |
| `source_conflict_policy` | Ya | `SourceConflictPolicy` | — | — |
| `authoritative_source_sheet_id` | Tidak | `string (uuid) / null` | — | — |
| `missing_record_policy` | Tidak | `"KEEP"` | "KEEP" | — |
| `deactivation_policy` | Tidak | `"EXPLICIT_REVIEW"` | "EXPLICIT_REVIEW" | — |
| `business_key_change_policy` | Tidak | `"EXPLICIT_MIGRATION"` | "EXPLICIT_MIGRATION" | — |
| `delete_referenced_policy` | Tidak | `"RESTRICT"` | "RESTRICT" | — |
| `effective_dating` | Tidak | `EffectiveDating / null` | — | — |

### MasterRevisionRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `revision_no` | Ya | `integer` | — | {"minimum":1.0} |
| `comment` | Tidak | `string` | "" | {"maxLength":2000} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "revision_no": 2,
  "comment": "Definisi dan mapping sudah diperiksa."
}
```

### MasterSchema

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `name` | Ya | `string` | — | {"maxLength":200,"minLength":1} |
| `description` | Tidak | `string` | "" | {"maxLength":2000} |
| `aliases` | Tidak | `array<string>` | [] | {"maxItems":30} |
| `fields` | Ya | `array<MasterField>` | — | {"maxItems":100,"minItems":1} |
| `business_key` | Ya | `array<string>` | — | {"maxItems":10,"minItems":1} |
| `label_field` | Ya | `string` | — | — |
| `policy` | Ya | `MasterImportPolicy` | — | — |

### MetricDefinition

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `code` | Ya | `string` | — | {"pattern":"^[a-z][a-z0-9_]{0,62}$"} |
| `column` | Ya | `string` | — | — |
| `aggregation` | Ya | `enum ["sum","count","avg","min","max","count_distinct"]` | — | — |
| `label` | Tidak | `string` | "" | — |

### NewMasterRecordPolicy

`enum ["UPDATE_ONLY","PROPOSE_INSERT"]`

### PasswordChange

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `current_password` | Ya | `string (password)` | — | {"writeOnly":true} |
| `new_password` | Ya | `string (password)` | — | {"maxLength":256,"minLength":12,"writeOnly":true} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "current_password": "PASSWORD_LAMA_ANDA",
  "new_password": "PASSWORD_BARU_MINIMAL_12_KARAKTER"
}
```

### ProductUpdate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `allowed_roles` | Tidak | `array<Role> / null` | — | — |
| `status` | Tidak | `enum ["ACTIVE","SUSPENDED"] / null` | — | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "status": "ACTIVE",
  "allowed_roles": [
    "PLATFORM_ADMIN",
    "DATA_STEWARD",
    "ANALYST",
    "VIEWER"
  ]
}
```

### QualityRule

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `column` | Ya | `string` | — | — |
| `rule` | Ya | `enum ["not_null","unique","min","max","allowed_values"]` | — | — |
| `value` | Tidak | `string / integer / number / array<string> / null` | — | — |
| `action_on_fail` | Tidak | `enum ["REJECT_ROW","WARN","STOP_BATCH","REQUIRE_REVIEW"]` | "REJECT_ROW" | — |

### QueryFilter

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `field` | Ya | `string` | — | {"maxLength":63} |
| `operator` | Ya | `enum ["eq","in","between","gte","lte","gt","lt"]` | — | — |
| `value` | Ya | `string / integer / number / boolean / array<string / integer / number> / null` | — | — |

### QueryPlan

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `metrics` | Tidak | `array<string>` | [] | {"maxItems":20} |
| `dimensions` | Tidak | `array<string>` | [] | {"maxItems":20} |
| `filters` | Tidak | `array<QueryFilter>` | [] | {"maxItems":20} |
| `sort` | Tidak | `array<SortField>` | [] | {"maxItems":10} |
| `time_grain` | Tidak | `enum ["none","day","week","month","quarter","year"]` | "none" | — |
| `limit` | Tidak | `integer` | 100 | {"maximum":1000.0,"minimum":1.0} |
| `offset` | Tidak | `integer` | 0 | {"maximum":100000.0,"minimum":0.0} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "metrics": [
    "net_sales",
    "transaction_count"
  ],
  "dimensions": [
    "branch_name"
  ],
  "filters": [
    {
      "field": "transaction_date",
      "operator": "between",
      "value": [
        "2026-09-01",
        "2026-09-30"
      ]
    }
  ],
  "sort": [
    {
      "field": "net_sales",
      "direction": "desc"
    }
  ],
  "time_grain": "none",
  "limit": 100,
  "offset": 0
}
```

### QuestionRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `question` | Ya | `string` | — | {"maxLength":2000,"minLength":3} |
| `data_product_code` | Tidak | `string / null` | — | — |
| `saved_query_code` | Tidak | `string / null` | — | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "question": "Berapa penjualan per cabang pada September 2026?",
  "data_product_code": "SALES",
  "saved_query_code": null
}
```

### Readiness

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `database` | Tidak | `"ready"` | "ready" | — |
| `redis` | Ya | `enum ["ready","unavailable"]` | — | — |
| `background_jobs` | Ya | `enum ["celery","manual_worker_only"]` | — | — |

### ReadinessResponse

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `status` | Ya | `string` | — | — |
| `data` | Ya | `Readiness` | — | — |
| `meta` | Tidak | `object` | {} | — |
| `errors` | Tidak | `array<object>` | [] | — |

### RefreshRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `refresh_token` | Ya | `string` | — | {"maxLength":4096} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "refresh_token": "REFRESH_TOKEN_DARI_LOGIN"
}
```

### ResolutionRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `resolution` | Ya | `string` | — | {"maxLength":2000,"minLength":3} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "resolution": "Nilai tanggal sudah diperbaiki pada Google Sheets; menunggu reprocess."
}
```

### ReviewSubmission

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `revision_no` | Ya | `integer` | — | {"minimum":1.0} |
| `snapshot_hash` | Ya | `string` | — | {"pattern":"^[a-f0-9]{64}$"} |
| `reviewed_columns` | Ya | `array<string>` | — | {"maxItems":100,"minItems":1} |
| `reviewed_sections` | Ya | `array<enum ["identity","columns","cleansing","quality","load","semantic"]>` | — | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "revision_no": 1,
  "snapshot_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "reviewed_columns": [
    "transaction_id",
    "transaction_date",
    "branch_name",
    "net_amount"
  ],
  "reviewed_sections": [
    "identity",
    "columns",
    "cleansing",
    "quality",
    "load",
    "semantic"
  ]
}
```

### Role

`enum ["PLATFORM_ADMIN","SOURCE_OWNER","DATA_STEWARD","TECHNICAL_APPROVER","ANALYST","VIEWER"]`

### SavedQueryCreate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `code` | Ya | `string` | — | {"pattern":"^[A-Za-z][A-Za-z0-9_]{0,62}$"} |
| `data_product_code` | Ya | `string` | — | — |
| `plan` | Ya | `QueryPlan` | — | — |
| `examples` | Tidak | `array<string>` | [] | {"maxItems":50} |
| `allowed_roles` | Tidak | `array<Role>` | ["ANALYST","VIEWER","PLATFORM_ADMIN"] | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "code": "sales_by_branch",
  "data_product_code": "SALES",
  "plan": {
    "metrics": [
      "net_sales",
      "transaction_count"
    ],
    "dimensions": [
      "branch_name"
    ],
    "filters": [
      {
        "field": "transaction_date",
        "operator": "between",
        "value": [
          "2026-09-01",
          "2026-09-30"
        ]
      }
    ],
    "sort": [
      {
        "field": "net_sales",
        "direction": "desc"
      }
    ],
    "time_grain": "none",
    "limit": 100,
    "offset": 0
  },
  "examples": [
    "Penjualan per cabang September 2026"
  ],
  "allowed_roles": [
    "PLATFORM_ADMIN",
    "DATA_STEWARD",
    "ANALYST",
    "VIEWER"
  ]
}
```

### SemanticDefinition

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `code` | Ya | `string` | — | {"pattern":"^[A-Za-z][A-Za-z0-9_]{0,62}$"} |
| `dimensions` | Tidak | `array<string>` | [] | — |
| `metrics` | Tidak | `array<MetricDefinition>` | [] | — |
| `allowed_roles` | Tidak | `array<enum ["PLATFORM_ADMIN","DATA_STEWARD","SOURCE_OWNER","TECHNICAL_APPROVER","ANALYST","VIEWER"]>` | ["PLATFORM_ADMIN","DATA_STEWARD","ANALYST","VIEWER"] | — |

### SheetClassificationUpdate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `revision_no` | Ya | `integer` | — | {"minimum":1.0} |
| `dataset_kind` | Ya | `DatasetKind` | — | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "revision_no": 1,
  "dataset_kind": "NON_MASTER"
}
```

### SheetUpdate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `range_a1` | Tidak | `string / null` | — | — |
| `header_row` | Tidak | `integer / null` | — | — |
| `data_start_row` | Tidak | `integer / null` | — | — |
| `enabled` | Tidak | `boolean / null` | — | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "range_a1": "A:D",
  "header_row": 1,
  "data_start_row": 2,
  "enabled": true
}
```

### SortField

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `field` | Ya | `string` | — | — |
| `direction` | Tidak | `enum ["asc","desc"]` | "asc" | — |

### SourceConflictPolicy

`enum ["REQUIRE_REVIEW","AUTHORITATIVE_SOURCE"]`

### SourceCreate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `source_code` | Ya | `string` | — | {"pattern":"^[a-z][a-z0-9_]{0,62}$"} |
| `name` | Ya | `string` | — | {"maxLength":200,"minLength":1} |
| `spreadsheet_url` | Ya | `string` | — | {"maxLength":500,"minLength":5} |
| `description` | Tidak | `string` | "" | {"maxLength":2000} |
| `credential_ref` | Tidak | `string` | "default" | {"maxLength":100} |
| `sync_schedule` | Tidak | `string / null` | — | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "source_code": "sales_cabang",
  "name": "Penjualan Cabang",
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/ID_SPREADSHEET_ANDA/edit",
  "description": "Satu baris per transaksi penjualan",
  "credential_ref": "default",
  "sync_schedule": "0 */6 * * *"
}
```

### UserCreate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `username` | Ya | `string` | — | {"maxLength":100,"minLength":3,"pattern":"^[a-zA-Z0-9_.@-]+$"} |
| `password` | Ya | `string (password)` | — | {"maxLength":256,"minLength":12,"writeOnly":true} |
| `full_name` | Tidak | `string` | "" | {"maxLength":200} |
| `role` | Tidak | `Role` | "VIEWER" | — |
| `row_scope` | Tidak | `map<string, map<string, array<string>>>` | {} | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "username": "viewer_jakarta",
  "password": "PASSWORD_AWAL_MINIMAL_12_KARAKTER",
  "full_name": "Viewer Cabang Jakarta",
  "role": "VIEWER",
  "row_scope": {
    "SALES": {
      "branch_name": [
        "Jakarta"
      ]
    }
  }
}
```

### UserUpdate

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `role` | Tidak | `Role / null` | — | — |
| `is_active` | Tidak | `boolean / null` | — | — |
| `row_scope` | Tidak | `map<string, map<string, array<string>>> / null` | — | — |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "role": "VIEWER",
  "is_active": true,
  "row_scope": {
    "SALES": {
      "branch_name": [
        "Jakarta",
        "Bandung"
      ]
    }
  }
}
```

### WorkbookApplyRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `revision_no` | Ya | `integer` | — | {"minimum":1.0} |
| `configuration` | Ya | `ETLConfiguration` | — | — |
| `question_answers` | Tidak | `map<string, string>` | {} | — |
| `preview_token` | Ya | `string` | — | {"maxLength":8192,"minLength":1} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "revision_no": 1,
  "configuration": {
    "schema_version": "1.0",
    "dataset_business_name": "Penjualan Cabang",
    "dataset_description": "Data transaksi penjualan per cabang",
    "grain": "Satu baris per nomor transaksi",
    "target_schema": "trusted",
    "target_table": "sales_transaction",
    "load_strategy": "UPSERT",
    "columns": [
      {
        "source_column": "ID",
        "target_column": "transaction_id",
        "target_type": "text",
        "nullable": false,
        "is_business_key": true,
        "transformation_codes": [
          "trim"
        ]
      },
      {
        "source_column": "Tanggal",
        "target_column": "transaction_date",
        "target_type": "date",
        "nullable": false,
        "transformation_codes": [
          "parse_date_id"
        ]
      },
      {
        "source_column": "Cabang",
        "target_column": "branch_name",
        "target_type": "text",
        "nullable": false,
        "transformation_codes": [
          "trim"
        ]
      },
      {
        "source_column": "Total",
        "target_column": "net_amount",
        "target_type": "numeric",
        "nullable": false,
        "transformation_codes": [
          "parse_decimal_id"
        ]
      }
    ],
    "data_quality_rules": [
      {
        "column": "net_amount",
        "rule": "min",
        "value": 0,
        "action_on_fail": "REJECT_ROW"
      }
    ],
    "semantic": {
      "code": "SALES",
      "dimensions": [
        "transaction_id",
        "transaction_date",
        "branch_name"
      ],
      "metrics": [
        {
          "code": "net_sales",
          "column": "net_amount",
          "aggregation": "sum",
          "label": "Penjualan bersih"
        },
        {
          "code": "transaction_count",
          "column": "transaction_id",
          "aggregation": "count",
          "label": "Jumlah transaksi"
        }
      ],
      "allowed_roles": [
        "PLATFORM_ADMIN",
        "DATA_STEWARD",
        "ANALYST",
        "VIEWER"
      ]
    },
    "unresolved_questions": [],
    "overall_confidence": 1
  },
  "question_answers": {},
  "preview_token": "TOKEN_DARI_WORKBOOK_PREVIEW"
}
```

### WorkbookPreviewRequest

| Field | Wajib | Tipe | Default | Batas |
|---|---|---|---|---|
| `content_base64` | Ya | `string` | — | {"maxLength":2800000,"minLength":1} |

Contoh payload valid secara schema (ID harus diganti dengan ID backend):

```json
{
  "content_base64": "BASE64_DARI_FILE_XLSX_EXPORT_APLIKASI"
}
```

## Bentuk record respons

Field hasil serialisasi ORM; semuanya read-only dari sisi response. Ini bukan payload create/PATCH. `id`, `tenant_id`, `created_at` termasuk dalam record. Field JSON memiliki struktur rinci yang dijelaskan di API Reference. Nilai UUID dan timestamp dikirim sebagai string. Field internal yang dikecualikan endpoint tidak ditampilkan pada bentuk public di bawah.

### Record User

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `username` | `VARCHAR(100)` | Tidak |
| `full_name` | `VARCHAR(200)` | Tidak |
| `role` | `VARCHAR(40)` | Tidak |
| `is_active` | `BOOLEAN` | Tidak |
| `row_scope` | `JSONB` | Tidak |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record DataSource

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `source_code` | `VARCHAR(63)` | Tidak |
| `name` | `VARCHAR(200)` | Tidak |
| `spreadsheet_id` | `VARCHAR(200)` | Tidak |
| `description` | `TEXT` | Tidak |
| `owner_user_id` | `CHAR(32)` | Tidak |
| `credential_ref` | `VARCHAR(100)` | Tidak |
| `status` | `VARCHAR(40)` | Tidak |
| `sync_schedule` | `VARCHAR(100)` | Ya |
| `paused` | `BOOLEAN` | Tidak |
| `last_scheduled_at` | `DATETIME` | Ya |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record SourceSheet

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `source_id` | `CHAR(32)` | Tidak |
| `sheet_id` | `INTEGER` | Tidak |
| `sheet_name` | `VARCHAR(200)` | Tidak |
| `range_a1` | `VARCHAR(100)` | Tidak |
| `header_row` | `INTEGER` | Tidak |
| `data_start_row` | `INTEGER` | Tidak |
| `enabled` | `BOOLEAN` | Tidak |
| `last_fingerprint` | `VARCHAR(64)` | Ya |
| `dataset_kind` | `VARCHAR(20)` | Ya |
| `classification_status` | `VARCHAR(32)` | Tidak |
| `classification_revision` | `INTEGER` | Tidak |
| `classification_confirmed_by` | `CHAR(32)` | Ya |
| `classification_confirmed_at` | `DATETIME` | Ya |
| `active_configuration_id` | `CHAR(32)` | Ya |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record ProfilingRun

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `source_id` | `CHAR(32)` | Tidak |
| `source_sheet_id` | `CHAR(32)` | Tidak |
| `fingerprint` | `VARCHAR(64)` | Tidak |
| `profile_json` | `JSONB` | Tidak |
| `status` | `VARCHAR(40)` | Tidak |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record Configuration

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `source_id` | `CHAR(32)` | Tidak |
| `source_sheet_id` | `CHAR(32)` | Tidak |
| `version_no` | `INTEGER` | Tidak |
| `revision_no` | `INTEGER` | Tidak |
| `status` | `VARCHAR(40)` | Tidak |
| `based_on_fingerprint` | `VARCHAR(64)` | Tidak |
| `configuration_json` | `JSONB` | Tidak |
| `review_state` | `JSONB` | Tidak |
| `created_by` | `CHAR(32)` | Tidak |
| `approved_by` | `CHAR(32)` | Ya |
| `approved_at` | `DATETIME` | Ya |
| `ai_response_id` | `VARCHAR(200)` | Ya |
| `ai_model` | `VARCHAR(100)` | Ya |
| `prompt_version` | `VARCHAR(40)` | Ya |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record MasterDefinition

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `code` | `VARCHAR(63)` | Tidak |
| `name` | `VARCHAR(200)` | Tidak |
| `aliases` | `JSONB` | Tidak |
| `definition_json` | `JSONB` | Tidak |
| `approved_definition_json` | `JSONB` | Ya |
| `revision_no` | `INTEGER` | Tidak |
| `approved_version` | `INTEGER` | Tidak |
| `status` | `VARCHAR(32)` | Tidak |
| `is_active` | `BOOLEAN` | Tidak |
| `created_by` | `CHAR(32)` | Tidak |
| `submitted_by` | `CHAR(32)` | Ya |
| `approved_by` | `CHAR(32)` | Ya |
| `approved_at` | `DATETIME` | Ya |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record MasterSourceBinding

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `source_sheet_id` | `CHAR(32)` | Tidak |
| `master_definition_id` | `CHAR(32)` | Tidak |
| `master_version` | `INTEGER` | Tidak |
| `classification_revision` | `INTEGER` | Tidak |
| `revision_no` | `INTEGER` | Tidak |
| `status` | `VARCHAR(32)` | Tidak |
| `columns_json` | `JSONB` | Tidak |
| `fingerprint` | `VARCHAR(64)` | Tidak |
| `snapshot_hash` | `VARCHAR(64)` | Tidak |
| `created_by` | `CHAR(32)` | Tidak |
| `approved_by` | `CHAR(32)` | Ya |
| `approved_at` | `DATETIME` | Ya |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record Artifact

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `configuration_version_id` | `CHAR(32)` | Tidak |
| `artifact_type` | `VARCHAR(30)` | Tidak |
| `file_name` | `VARCHAR(200)` | Tidak |
| `mime_type` | `VARCHAR(120)` | Tidak |
| `content_hash` | `VARCHAR(64)` | Tidak |
| `file_size_bytes` | `INTEGER` | Tidak |
| `is_current` | `BOOLEAN` | Tidak |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record Job

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `kind` | `VARCHAR(30)` | Tidak |
| `source_id` | `CHAR(32)` | Ya |
| `requested_by` | `CHAR(32)` | Tidak |
| `payload` | `JSONB` | Tidak |
| `status` | `VARCHAR(30)` | Tidak |
| `result` | `JSONB` | Tidak |
| `error_code` | `VARCHAR(80)` | Ya |
| `error_message` | `TEXT` | Ya |
| `started_at` | `DATETIME` | Ya |
| `finished_at` | `DATETIME` | Ya |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record ETLRun

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `source_id` | `CHAR(32)` | Tidak |
| `source_sheet_id` | `CHAR(32)` | Tidak |
| `configuration_id` | `CHAR(32)` | Tidak |
| `snapshot_id` | `CHAR(32)` | Tidak |
| `run_key` | `VARCHAR(64)` | Tidak |
| `status` | `VARCHAR(40)` | Tidak |
| `rows_extracted` | `INTEGER` | Tidak |
| `rows_loaded` | `INTEGER` | Tidak |
| `rows_quarantined` | `INTEGER` | Tidak |
| `finished_at` | `DATETIME` | Ya |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record QualityIssue

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `etl_run_id` | `CHAR(32)` | Tidak |
| `source_id` | `CHAR(32)` | Tidak |
| `source_row` | `INTEGER` | Tidak |
| `errors` | `JSONB` | Tidak |
| `status` | `VARCHAR(30)` | Tidak |
| `resolution` | `TEXT` | Ya |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

Endpoint quarantine menambahkan `data: array` berisi nilai mentah baris.

### Record DataProduct

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `source_sheet_id` | `CHAR(32)` | Tidak |
| `code` | `VARCHAR(63)` | Tidak |
| `name` | `VARCHAR(200)` | Tidak |
| `description` | `TEXT` | Tidak |
| `columns` | `JSONB` | Tidak |
| `metrics` | `JSONB` | Tidak |
| `dimensions` | `JSONB` | Tidak |
| `allowed_roles` | `JSONB` | Tidak |
| `status` | `VARCHAR(30)` | Tidak |
| `version` | `INTEGER` | Tidak |
| `freshness_version` | `INTEGER` | Tidak |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record SavedQuery

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `code` | `VARCHAR(63)` | Tidak |
| `data_product_code` | `VARCHAR(63)` | Tidak |
| `plan` | `JSONB` | Tidak |
| `examples` | `JSONB` | Tidak |
| `allowed_roles` | `JSONB` | Tidak |
| `semantic_version` | `INTEGER` | Tidak |
| `status` | `VARCHAR(30)` | Tidak |
| `created_by` | `CHAR(32)` | Tidak |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record QueryRequest

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `user_id` | `CHAR(32)` | Tidak |
| `question_hash` | `VARCHAR(64)` | Tidak |
| `route` | `VARCHAR(40)` | Tidak |
| `plan` | `JSONB` | Tidak |
| `status` | `VARCHAR(40)` | Tidak |
| `clarification_question` | `TEXT` | Ya |
| `feedback` | `TEXT` | Ya |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |

### Record AuditEvent

| Field | Tipe penyimpanan | Nullable |
|---|---|---|
| `user_id` | `CHAR(32)` | Ya |
| `event` | `VARCHAR(100)` | Tidak |
| `resource_id` | `VARCHAR(100)` | Ya |
| `details` | `JSONB` | Tidak |
| `tenant_id` | `CHAR(32)` | Tidak |
| `id` | `CHAR(32)` | Tidak |
| `created_at` | `DATETIME` | Tidak |
