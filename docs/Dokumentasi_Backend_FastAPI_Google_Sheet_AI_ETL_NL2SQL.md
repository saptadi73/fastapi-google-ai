# Dokumentasi Teknis Backend FastAPI

## Google Sheets → AI-Assisted ETL Configuration → PostgreSQL → Operational API → NL2SQL

**Versi:** 1.0  
**Tanggal:** 3 September 2026  
**Status:** Baseline implementasi backend  
**Stack utama:** FastAPI, Python, PostgreSQL, SQLAlchemy, Alembic, Google Sheets API, OpenAI Responses API, Redis, Celery/Dramatiq

---

## 1. Tujuan Dokumen

Dokumen ini menjadi acuan teknis untuk membangun backend platform yang:

1. mendaftarkan dan membaca Google Sheet menggunakan Google Sheets API;
2. melakukan profiling struktur dan kualitas data menggunakan Python;
3. meminta OpenAI menyusun draft konfigurasi ETL awal berdasarkan schema konfigurasi baku;
4. menyediakan proses review, koreksi, persetujuan, versioning, dan aktivasi konfigurasi;
5. membuat tabel, constraint, index, dan relasi PostgreSQL secara terkendali;
6. menjalankan ETL rutin secara deterministik tanpa memanggil OpenAI;
7. menyediakan REST API operasional untuk frontend Vue.js;
8. menyediakan Semantic Catalog, saved query, query template, dan NL2SQL yang aman;
9. mencatat lineage, audit, penggunaan token, biaya, error, dan kualitas data.

Prinsip arsitektur:

> OpenAI memahami dan merekomendasikan. Manusia menyetujui. Python memvalidasi dan mengeksekusi. PostgreSQL menyimpan konfigurasi aktif dan data terpercaya.

---

## 2. Keputusan Arsitektur Utama

### 2.1 AI-assisted onboarding, deterministic execution

OpenAI dipanggil ketika:

- Google Sheet pertama kali didaftarkan;
- pengguna meminta rekomendasi ulang;
- schema fingerprint berubah;
- ditemukan kolom, taxonomy, atau pola data baru yang tidak dikenali;
- confidence deterministic mapping berada di bawah threshold.

OpenAI tidak dipanggil pada setiap jadwal ETL. Setelah konfigurasi disetujui dan aktif, Python menjalankan extract, cleansing, validation, transformation, dan load berdasarkan konfigurasi tersebut.

### 2.2 Workbook bukan secret store

Template Excel/Google Sheet hanya memuat identifier dan parameter non-secret. Berikut ini tidak boleh disimpan di workbook:

- private key Service Account;
- OpenAI API key;
- password PostgreSQL;
- JWT secret;
- credential SMTP/notification;
- token pengguna.

Secret disimpan dalam environment variable atau secret manager.

### 2.3 Semantic layer sebagai batas NL2SQL

NL2SQL tidak membaca Google Sheet mentah dan tidak menerima seluruh schema PostgreSQL. Model hanya menerima metadata data product, metric, dimension, relationship, dan semantic view yang:

- berstatus `ACTIVE`;
- diizinkan untuk role pengguna;
- berada dalam tenant pengguna;
- lolos klasifikasi sensitivitas data;
- relevan dengan pertanyaan.

### 2.4 Urutan routing pertanyaan

Urutan pemrosesan permintaan data:

1. dashboard/operational endpoint;
2. saved report;
3. exact intent match;
4. normalized intent match;
5. semantic query builder;
6. validated query cache;
7. OpenAI NL2SQL sebagai fallback.

---

## 3. Arsitektur Logis

```mermaid
flowchart TD
    GS["Google Sheets"] --> ING["Ingestion & Profiler"]
    ING --> RAW["Raw Snapshot"]
    ING --> AI["AI Configuration Generator"]
    AI --> REV["Review & Approval"]
    REV --> REG["Configuration Registry"]
    REG --> ETL["Deterministic ETL Worker"]
    RAW --> ETL
    ETL --> STG["PostgreSQL Staging"]
    STG --> TRU["PostgreSQL Trusted"]
    TRU --> SEM["Semantic Views & Catalog"]
    SEM --> API["Operational API"]
    SEM --> NL["NL2SQL Gateway"]
```

### 3.1 Komponen

| Komponen | Tanggung jawab |
|---|---|
| FastAPI API | Authentication, authorization, CRUD sumber, review, approval, execution status, query API |
| Google Sheets Adapter | Metadata, values, batching, retry, quota handling |
| Dataset Profiler | Header detection, type inference, uniqueness, null ratio, sample, fingerprint |
| AI Configuration Generator | Menghasilkan draft konfigurasi terstruktur |
| Configuration Validator | Memvalidasi identifier, tipe, relasi, rule, konflik, dan referensi |
| Schema Compiler | Menghasilkan DDL terkontrol dari konfigurasi yang disetujui |
| ETL Compiler | Mengompilasi konfigurasi menjadi pipeline deterministic |
| Background Worker | Profiling, AI generation, DDL deployment, ETL, cache refresh |
| PostgreSQL | Registry, raw/staging/trusted, semantic layer, audit |
| Redis | Job queue, distributed lock, rate limiting, result cache |
| NL2SQL Gateway | Intent routing, semantic retrieval, AI fallback, SQL guard |
| Audit Service | Event, lineage, approval, query, token dan biaya |

---

## 4. Struktur Project FastAPI

```text
app/
├── main.py
├── core/
│   ├── config.py
│   ├── database.py
│   ├── security.py
│   ├── logging.py
│   └── exceptions.py
├── api/
│   ├── dependencies.py
│   └── v1/
│       ├── router.py
│       ├── sources.py
│       ├── profiling.py
│       ├── configurations.py
│       ├── approvals.py
│       ├── etl_runs.py
│       ├── data_quality.py
│       ├── semantic_catalog.py
│       ├── operational_queries.py
│       ├── nl2sql.py
│       └── admin_ai_usage.py
├── models/
│   ├── source.py
│   ├── configuration.py
│   ├── etl.py
│   ├── semantic.py
│   ├── nl2sql.py
│   └── audit.py
├── schemas/
│   ├── source.py
│   ├── profiling.py
│   ├── ai_configuration.py
│   ├── configuration.py
│   ├── semantic.py
│   └── nl2sql.py
├── repositories/
│   ├── source_repository.py
│   ├── configuration_repository.py
│   ├── semantic_repository.py
│   └── query_repository.py
├── services/
│   ├── google_sheets_service.py
│   ├── profiling_service.py
│   ├── fingerprint_service.py
│   ├── openai_service.py
│   ├── ai_configuration_service.py
│   ├── configuration_validation_service.py
│   ├── schema_compiler_service.py
│   ├── etl_compiler_service.py
│   ├── etl_execution_service.py
│   ├── data_quality_service.py
│   ├── semantic_catalog_service.py
│   ├── intent_router_service.py
│   ├── nl2sql_service.py
│   ├── sql_guard_service.py
│   └── query_execution_service.py
├── workers/
│   ├── tasks.py
│   ├── profiling_tasks.py
│   ├── etl_tasks.py
│   └── semantic_tasks.py
├── domain/
│   ├── enums.py
│   ├── rules.py
│   └── events.py
├── prompts/
│   ├── etl_configuration_v1.md
│   └── nl2sql_v1.md
├── sql/
│   ├── semantic_views/
│   └── operational_queries/
└── tests/
    ├── unit/
    ├── integration/
    ├── contract/
    └── evaluation/
alembic/
pyproject.toml
.env.example
```

Router hanya menangani HTTP. Business logic ditempatkan pada service. Query persistence ditempatkan pada repository.

---

## 5. Dependency yang Disarankan

```toml
[project]
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "gunicorn",
  "pydantic",
  "pydantic-settings",
  "sqlalchemy[asyncio]",
  "asyncpg",
  "alembic",
  "google-api-python-client",
  "google-auth",
  "google-auth-httplib2",
  "openai",
  "pandas",
  "pyarrow",
  "sqlglot",
  "redis",
  "celery[redis]",
  "tenacity",
  "httpx",
  "python-jose[cryptography]",
  "passlib[bcrypt]",
  "structlog",
  "prometheus-client",
  "orjson"
]
```

Versi dependency harus dikunci melalui lock file dan diuji sebelum deployment.

---

## 6. Environment Variable

```dotenv
APP_ENV=development
APP_NAME=google-sheet-ai-platform
API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql+asyncpg://app_user:change-me@127.0.0.1:5432/data_platform
DATABASE_DDL_URL=postgresql+asyncpg://ddl_user:change-me@127.0.0.1:5432/data_platform
DATABASE_NL2SQL_URL=postgresql+asyncpg://nl2sql_reader:change-me@127.0.0.1:5432/data_platform

GOOGLE_SERVICE_ACCOUNT_FILE=/run/secrets/google-service-account.json
GOOGLE_SHEETS_READONLY=true

OPENAI_API_KEY=replace-from-secret-manager
OPENAI_MODEL_ETL_CONFIG=replace-with-approved-model
OPENAI_MODEL_NL2SQL=replace-with-approved-model
OPENAI_STORE_RESPONSES=false

REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2

NL2SQL_STATEMENT_TIMEOUT_MS=10000
NL2SQL_MAX_ROWS=1000
NL2SQL_DAILY_USER_LIMIT=25
NL2SQL_RESULT_CACHE_TTL_SECONDS=300
ETL_SAMPLE_ROW_LIMIT=200
```

Gunakan tiga role PostgreSQL terpisah:

- `app_user`: CRUD metadata platform;
- `ddl_user`: membuat/mengubah object pada schema data yang diizinkan;
- `nl2sql_reader`: hanya `SELECT` pada semantic views yang diizinkan.

---

## 7. Pembagian Schema PostgreSQL

| Schema | Isi |
|---|---|
| `platform` | Source registry, configuration, approval, job, audit |
| `raw` | Snapshot sumber tanpa perubahan semantik |
| `staging` | Data yang sudah diparsing tetapi belum dipercaya |
| `trusted` | Tabel bisnis tervalidasi |
| `semantic` | View/materialized view untuk API dan NL2SQL |
| `quarantine` | Baris gagal validasi |
| `audit` | Log immutable dan lineage |

NL2SQL tidak diberi akses ke `platform`, `raw`, `staging`, `trusted`, `quarantine`, atau `audit` secara langsung. Akses hanya ke object terpilih pada `semantic`.

---

## 8. Model Data Metadata Platform

### 8.1 Tabel inti

#### `platform.data_source`

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | UUID PK | Identifier sumber |
| `tenant_id` | UUID | Isolasi tenant |
| `source_code` | varchar unique per tenant | Kode stabil |
| `name` | varchar | Nama bisnis |
| `source_type` | varchar | `GOOGLE_SHEET` |
| `spreadsheet_id` | varchar | ID Google Sheet, bukan URL penuh |
| `description` | text | Konteks bisnis |
| `owner_user_id` | UUID | Pemilik data |
| `credential_ref` | varchar | Referensi secret, bukan isi credential |
| `status` | varchar | Lifecycle source |
| `created_at` | timestamptz | Audit |
| `updated_at` | timestamptz | Audit |

#### `platform.source_sheet`

Satu `data_source` dapat memiliki banyak tab. Setiap tab dapat menghasilkan satu atau beberapa target table jika grain atau domain bisnisnya berbeda.

Kolom penting: `sheet_id`, `sheet_name`, `range_a1`, `header_row`, `data_start_row`, `enabled`, `last_fingerprint`.

#### `platform.profiling_run`

Menyimpan status profiling, sample size, fingerprint, waktu proses, statistik, warning, dan error.

#### `platform.column_profile`

Menyimpan header asli, normalized header, inferred type, null ratio, distinct ratio, min/max, regex pattern, sample masked, dugaan PII, dan confidence.

#### `platform.configuration_version`

| Kolom | Keterangan |
|---|---|
| `version_no` | Nomor meningkat per source |
| `status` | `AI_DRAFT`, `NEEDS_REVIEW`, `APPROVED`, `ACTIVE`, `SUPERSEDED`, `REJECTED` |
| `based_on_fingerprint` | Fingerprint sumber |
| `configuration_json` | Snapshot konfigurasi penuh |
| `ai_response_id` | Referensi respons untuk audit bila disimpan |
| `ai_model` | Model yang dipakai |
| `prompt_version` | Versi prompt |
| `approved_by` | Approver |
| `approved_at` | Waktu approval |

Hanya satu versi dapat berstatus `ACTIVE` untuk satu source/tab pada satu waktu. Terapkan partial unique index.

#### `platform.configuration_artifact`

Setiap versi konfigurasi yang telah divalidasi dapat menghasilkan file konfigurasi machine-readable. Tabel ini menghubungkan versi konfigurasi dengan file fisiknya.

| Kolom | Tipe | Keterangan |
|---|---|---|
| `id` | UUID PK | Identifier artifact |
| `tenant_id` | UUID | Isolasi tenant |
| `configuration_version_id` | UUID FK | Relasi ke `configuration_version` |
| `artifact_type` | varchar | `RUNTIME_CONFIG`, `EXPORT_JSON`, `EXPORT_YAML`, atau `EXPORT_XLSX` |
| `file_name` | varchar | Nama file yang dapat ditampilkan kepada pengguna |
| `storage_uri` | text | Lokasi object/file storage; bukan public URL |
| `mime_type` | varchar | MIME type file |
| `content_hash` | varchar | SHA-256 untuk pemeriksaan integritas |
| `file_size_bytes` | bigint | Ukuran file |
| `generated_by` | UUID nullable | User pembuat atau null jika sistem |
| `generated_at` | timestamptz | Waktu pembuatan |
| `is_current` | boolean | Artifact runtime terkini untuk versinya |
| `metadata_json` | jsonb | Informasi generator/schema tambahan |

Constraint yang wajib:

- `configuration_version_id` harus berasal dari tenant yang sama;
- hanya satu `RUNTIME_CONFIG` dengan `is_current=true` per configuration version;
- `content_hash` diperiksa sebelum worker menggunakan file;
- file tidak boleh berisi credential atau secret;
- perubahan file di luar platform tidak otomatis dipercaya.

#### Relasi Google Sheet dengan konfigurasi

Hubungan canonical adalah:

```text
platform.data_source
  1 ── n platform.source_sheet
  1 ── n platform.configuration_version
  1 ── n platform.configuration_artifact
```

Secara implementasi, `platform.configuration_version` wajib mempunyai `source_sheet_id`. `platform.source_sheet.active_configuration_id` menunjuk versi aktif yang digunakan ETL. Dengan demikian sistem dapat menjawab secara pasti:

- Google Spreadsheet mana yang dimaksud;
- tab mana yang dikonfigurasi;
- konfigurasi aktif yang digunakan;
- file runtime yang terkait;
- konfigurasi versi sebelumnya;
- siapa yang membuat, mengubah, menyetujui, dan mengaktifkan konfigurasi.

Contoh nama dan struktur file:

```text
configs/
└── {tenant_code}/
    └── {source_code}/
        └── {sheet_code}/
            ├── config-v1.json
            ├── config-v2.json
            └── config-v3.json
```

Nama file hanya untuk keterbacaan. Relasi sistem tidak boleh bergantung pada parsing nama file; gunakan UUID dan foreign key pada registry.

#### Source of truth dan fungsi file

`configuration_json` di PostgreSQL menjadi source of truth. File konfigurasi merupakan artifact berversi yang:

- dapat dilihat dan diunduh pengguna;
- dapat digunakan worker sebagai snapshot immutable;
- dapat diekspor untuk audit atau integrasi;
- dapat dibandingkan antarversi;
- dapat digunakan untuk rollback setelah validasi.

Worker boleh membaca file runtime untuk efisiensi, tetapi harus mencocokkan `configuration_version_id`, `content_hash`, tenant, dan status `ACTIVE` terhadap registry PostgreSQL. File tidak boleh mengaktifkan dirinya sendiri.

#### Contoh file runtime JSON

```json
{
  "schema_version": "1.0",
  "configuration_id": "41d59b20-61ef-4f39-a43d-2a78996efb11",
  "configuration_version": 3,
  "tenant_id": "e104cf73-f0ee-49d2-ab41-d301cf4a7745",
  "source": {
    "source_id": "60c74391-b108-4353-bc81-96ba01154a51",
    "source_sheet_id": "b1c6ad5d-f60c-4b0f-a404-a7e3293a21e5",
    "spreadsheet_id": "google-spreadsheet-id",
    "sheet_name": "Transaksi",
    "range_a1": "A:Z"
  },
  "target": {
    "schema": "trusted",
    "table": "sales_transaction",
    "load_strategy": "UPSERT",
    "business_keys": ["transaction_number"]
  },
  "columns": [],
  "data_quality_rules": [],
  "semantic": {},
  "approved": {
    "status": "ACTIVE",
    "approved_at": "2026-09-03T07:00:00Z"
  }
}
```

Field `approved` pada file bersifat informatif. Status pada database registry tetap menjadi otoritas.

#### `platform.column_mapping`

Memuat `source_column`, `canonical_code`, `target_schema`, `target_table`, `target_column`, `target_type`, `nullable`, `is_primary_key`, `is_business_key`, `transform_rule`, `default_value`, `foreign_key`, `confidence`, `review_status`.

#### `platform.data_quality_rule`

Memuat jenis rule, parameter, severity, `action_on_fail`, dan threshold.

#### `platform.etl_job` dan `platform.etl_run`

`etl_job` menyimpan jadwal dan strategi load. `etl_run` menyimpan satu eksekusi, row count, watermark, error, durasi, dan configuration version.

#### `platform.approval`

Menyimpan reviewer, keputusan, komentar, bagian konfigurasi yang diubah, dan before/after JSON.

### 8.2 Semantic Catalog

Tabel yang diperlukan:

- `platform.data_product`;
- `platform.semantic_object`;
- `platform.metric_definition`;
- `platform.dimension_definition`;
- `platform.join_relationship`;
- `platform.intent_definition`;
- `platform.intent_example`;
- `platform.validated_query_template`;
- `platform.query_parameter_definition`;
- `platform.nl2sql_request_log`;
- `platform.query_result_cache_index`.

### 8.3 Audit dan lineage

Tabel audit minimal:

- `audit.event_log`;
- `audit.data_lineage`;
- `audit.ai_usage_log`;
- `audit.query_execution_log`;
- `audit.schema_change_log`.

Jangan menyimpan prompt mentah jika berisi PII. Simpan versi redacted, hash, token usage, latency, dan identifier konfigurasi.

---

## 9. Lifecycle Sumber dan Konfigurasi

```text
DISCOVERED
→ PROFILING
→ AI_DRAFT
→ NEEDS_REVIEW
→ APPROVED
→ DEPLOYING
→ ACTIVE
```

Status pengecualian:

- `PROFILE_FAILED`;
- `AI_FAILED`;
- `VALIDATION_FAILED`;
- `DEPLOYMENT_FAILED`;
- `CHANGE_DETECTED`;
- `SUSPENDED`;
- `RETIRED`.

Transisi status harus dilakukan melalui service method dan direkam sebagai audit event. Endpoint tidak boleh mengubah status secara bebas.

---

## 10. Implementasi Google Sheets

### 10.1 Persiapan Google Cloud

1. Buat Google Cloud Project.
2. Aktifkan Google Sheets API dan, jika metadata file dibutuhkan, Google Drive API.
3. Buat Service Account khusus platform.
4. Simpan JSON key pada secret store/server, bukan repository.
5. Bagikan Google Sheet kepada email Service Account sebagai Viewer.
6. Gunakan scope read-only:

```python
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
```

Tambahkan Drive read-only hanya bila benar-benar diperlukan untuk pencarian atau metadata Drive.

### 10.2 Service client

```python
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


class GoogleSheetsService:
    def __init__(self, credential_file: str):
        credentials = Credentials.from_service_account_file(
            credential_file,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        self.client = build(
            "sheets",
            "v4",
            credentials=credentials,
            cache_discovery=False,
        )

    def get_metadata(self, spreadsheet_id: str) -> dict:
        return (
            self.client.spreadsheets()
            .get(
                spreadsheetId=spreadsheet_id,
                fields="spreadsheetId,properties.title,sheets.properties",
            )
            .execute()
        )

    def read_values(self, spreadsheet_id: str, range_a1: str) -> list[list]:
        response = (
            self.client.spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=range_a1,
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="SERIAL_NUMBER",
            )
            .execute()
        )
        return response.get("values", [])
```

Gunakan `batchGet` ketika membaca beberapa range. Tambahkan retry exponential backoff untuk error sementara dan quota response.

### 10.3 Registrasi sumber

Request:

```http
POST /api/v1/sources/google-sheets
```

```json
{
  "name": "Penjualan Cabang",
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/xxx/edit",
  "description": "Transaksi penjualan seluruh cabang",
  "credential_ref": "gcp-sa-data-platform",
  "sync_schedule": "0 */6 * * *"
}
```

Backend harus:

1. mengekstrak dan memvalidasi `spreadsheet_id`;
2. memeriksa hak akses;
3. mengambil metadata tab;
4. menyimpan source dan sheet registry;
5. membuat background job profiling;
6. mengembalikan `202 Accepted` dan `job_id`.

### 10.4 Snapshot raw

Untuk audit dan reproducibility, simpan snapshot raw atau minimal payload terkompresi beserta hash. Pilihan implementasi:

- JSONB untuk sumber kecil;
- Parquet/object storage untuk sumber besar;
- raw table per source bila kebutuhan SQL inspection tinggi.

Setiap snapshot memiliki `source_id`, `sheet_id`, `extracted_at`, `source_modified_time` jika tersedia, `content_hash`, `row_count`, dan `configuration_version`.

---

## 11. Dataset Profiling

### 11.1 Tahapan

1. deteksi header row;
2. normalisasi nama header;
3. ambil sample representatif;
4. inferensi tipe data;
5. hitung null/distinct ratio;
6. deteksi kandidat key;
7. deteksi format tanggal, desimal, mata uang, boolean, UUID;
8. deteksi potensi PII;
9. bandingkan dengan canonical dictionary dan source sebelumnya;
10. buat schema fingerprint.

### 11.2 Normalisasi header

Contoh:

```python
import re
import unicodedata


def normalize_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    if not normalized or not normalized[0].isalpha():
        normalized = f"col_{normalized}"
    return normalized[:63]
```

Identifier hasil AI tetap harus melewati fungsi validator yang sama.

### 11.3 Schema fingerprint

Fingerprint minimal dibentuk dari:

```text
sheet_name
+ ordered normalized headers
+ inferred data types
+ header row
+ selected range
```

Jangan memasukkan semua nilai data ke fingerprint schema. Buat fingerprint statistik terpisah untuk mendeteksi perubahan pola data.

```python
import hashlib
import json


def schema_fingerprint(profile: dict) -> str:
    stable = {
        "sheet_name": profile["sheet_name"],
        "header_row": profile["header_row"],
        "columns": [
            {"name": c["normalized_name"], "type": c["inferred_type"]}
            for c in profile["columns"]
        ],
    }
    encoded = json.dumps(stable, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()
```

Jika fingerprint sama dengan konfigurasi aktif, ETL rutin berjalan tanpa OpenAI.

---

## 12. Schema Konfigurasi AI

Output AI harus mengikuti Pydantic model/JSON Schema, bukan teks bebas.

```python
from typing import Literal
from pydantic import BaseModel, Field


class ColumnRecommendation(BaseModel):
    source_column: str
    canonical_code: str | None
    business_name: str
    target_column: str
    target_type: Literal[
        "text", "varchar", "integer", "bigint", "numeric",
        "boolean", "date", "timestamp", "timestamptz", "uuid"
    ]
    nullable: bool
    is_primary_key: bool
    is_business_key: bool
    transformation_codes: list[str]
    taxonomy_code: str | None
    pii_classification: Literal["NONE", "LOW", "MEDIUM", "HIGH"]
    confidence: float = Field(ge=0, le=1)
    reason: str


class RelationshipRecommendation(BaseModel):
    source_column: str
    referenced_data_product_code: str | None
    referenced_column: str | None
    relationship_type: Literal["MANY_TO_ONE", "ONE_TO_ONE", "NONE"]
    confidence: float = Field(ge=0, le=1)
    reason: str


class ETLConfigurationRecommendation(BaseModel):
    source_id: str
    sheet_name: str
    dataset_business_name: str
    dataset_description: str
    grain: str
    target_schema: Literal["trusted"]
    target_table: str
    load_strategy: Literal["APPEND", "UPSERT", "FULL_REFRESH"]
    watermark_column: str | None
    columns: list[ColumnRecommendation]
    relationships: list[RelationshipRecommendation]
    data_quality_rules: list[dict]
    semantic_suggestions: dict
    unresolved_questions: list[str]
    overall_confidence: float = Field(ge=0, le=1)
```

Gunakan schema yang lebih ketat pada implementasi produksi; hindari `dict` bebas dan ganti dengan model bertipe.

---

## 13. Integrasi OpenAI untuk Draft ETL

### 13.1 Pola integrasi

Gunakan OpenAI Responses API dengan Structured Outputs. JSON Schema harus berasal dari Pydantic model agar tipe Python dan schema API tidak berbeda.

```python
from openai import AsyncOpenAI


class OpenAIService:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate_etl_configuration(
        self,
        prompt: str,
    ) -> ETLConfigurationRecommendation:
        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "developer",
                    "content": (
                        "Anda menyusun draft konfigurasi ETL. "
                        "Jangan membuat credential, SQL DDL, atau nama object di luar allowlist. "
                        "Nyatakan ambiguity pada unresolved_questions."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            text_format=ETLConfigurationRecommendation,
        )
        return response.output_parsed
```

Catatan: bentuk parameter SDK dapat berubah sesuai versi SDK. Contract test harus dijalankan ketika dependency OpenAI diperbarui.

### 13.2 Isi prompt ETL

Kirim hanya konteks yang diperlukan:

- tujuan bisnis yang ditulis pengguna;
- nama spreadsheet dan tab;
- column profile;
- sample data yang sudah dimasking;
- canonical dictionary relevan;
- taxonomy relevan;
- daftar data product yang mungkin berhubungan;
- tipe PostgreSQL yang diizinkan;
- aturan penamaan;
- konfigurasi output schema;
- instruksi untuk tidak menebak jika bukti tidak cukup.

Jangan kirim:

- credential;
- seluruh database schema;
- seluruh isi sheet jika sample cukup;
- data PII mentah yang tidak diperlukan;
- tabel tenant lain.

### 13.3 Prompt versioning

Setiap prompt memiliki:

- `prompt_code`;
- `version`;
- checksum;
- tanggal aktif;
- model yang diuji;
- evaluation dataset;
- approval status.

Perubahan prompt tidak boleh mengubah konfigurasi aktif secara otomatis.

### 13.4 Confidence dan review

Kebijakan awal:

| Confidence | Tindakan |
|---|---|
| `>= 0.90` | Dapat dipilih untuk bulk approval, tetap terlihat |
| `0.75–0.89` | Wajib diperiksa |
| `< 0.75` | Wajib dikoreksi atau dikonfirmasi |
| Konflik katalog | Wajib Data Steward |
| DDL/relationship baru | Wajib approver teknis |

Confidence model bukan probabilitas kebenaran yang terkalibrasi. Validasi deterministic dan review manusia tetap menjadi sumber keputusan.

### 13.5 Validasi setelah AI

Setelah output diterima:

1. validasi Pydantic;
2. normalisasi identifier;
3. tolak schema/table di luar allowlist;
4. tolak tipe PostgreSQL di luar daftar;
5. periksa duplikasi target column;
6. periksa PK/business key;
7. periksa FK terhadap object aktif;
8. periksa transform code terhadap registry function;
9. periksa circular relationship;
10. lakukan dry-run pada sample;
11. simpan sebagai `AI_DRAFT`, bukan `ACTIVE`.

Referensi resmi OpenAI menyatakan Structured Outputs memastikan bentuk output mengikuti JSON Schema, tetapi isi tetap perlu divalidasi. Dokumentasi: <https://developers.openai.com/api/docs/guides/structured-outputs>.

---

## 14. Review dan Approval API

### 14.1 Endpoint

```text
GET    /api/v1/sources/{source_id}/profiling-runs/{run_id}
POST   /api/v1/sources/{source_id}/ai-configurations
GET    /api/v1/configurations/{configuration_id}
PATCH  /api/v1/configurations/{configuration_id}
POST   /api/v1/configurations/{configuration_id}/validate
POST   /api/v1/configurations/{configuration_id}/submit-review
POST   /api/v1/configurations/{configuration_id}/approve
POST   /api/v1/configurations/{configuration_id}/reject
POST   /api/v1/configurations/{configuration_id}/deploy
GET    /api/v1/configurations/{configuration_id}/diff
GET    /api/v1/configurations/{configuration_id}/questions
POST   /api/v1/configurations/{configuration_id}/answers
GET    /api/v1/source-sheets/{sheet_id}/configurations
GET    /api/v1/source-sheets/{sheet_id}/configurations/active
GET    /api/v1/configurations/{configuration_id}/artifacts
GET    /api/v1/configurations/{configuration_id}/artifacts/{artifact_id}/download
POST   /api/v1/configurations/{configuration_id}/export
POST   /api/v1/configurations/{configuration_id}/clone
POST   /api/v1/configurations/{configuration_id}/activate
POST   /api/v1/configurations/{configuration_id}/rollback
```

### 14.2 Aturan melihat dan mengedit konfigurasi

Frontend harus dapat menampilkan:

- konfigurasi aktif untuk setiap tab;
- seluruh versi dan statusnya;
- konfigurasi sebelum dan sesudah perubahan;
- file JSON/YAML/XLSX yang tersedia;
- hasil validasi;
- riwayat approval dan activation;
- ETL run yang menggunakan setiap versi.

Konfigurasi berstatus `ACTIVE` dan `SUPERSEDED` bersifat immutable. Jika pengguna memilih **Edit**, backend melakukan clone:

```text
ACTIVE v3
→ clone menjadi NEEDS_REVIEW v4
→ pengguna mengedit v4 melalui form
→ validate
→ approve
→ generate config-v4.json
→ activate v4
→ v3 menjadi SUPERSEDED
```

Dengan pola ini ETL yang sedang berjalan tetap dapat diselesaikan menggunakan v3, sedangkan perubahan pengguna dikerjakan pada v4.

### 14.3 Pembuatan artifact setelah approval

Setelah approval, backend:

1. membaca `configuration_json` versi yang disetujui;
2. melakukan validasi final dan serialisasi canonical JSON;
3. menghitung SHA-256;
4. menyimpan file pada storage privat;
5. membuat record `configuration_artifact`;
6. menjalankan dry-run schema dan ETL;
7. mengaktifkan konfigurasi hanya jika deployment berhasil.

Jika file YAML atau Excel diperlukan, file tersebut dibuat dari canonical JSON yang sama agar tidak terjadi perbedaan isi.

### 14.4 Rollback

Rollback tidak mengedit versi lama. Backend membuat activation event baru yang menunjuk konfigurasi sebelumnya setelah memeriksa kompatibilitas schema dan data. Rollback harus ditolak jika target versi memerlukan kolom atau object database yang sudah tidak tersedia.

### 14.5 Optimistic locking

Tambahkan `revision_no` atau `updated_at` pada PATCH. Jika dua pengguna mengedit versi yang sama, respons `409 Conflict`.

### 14.6 Separation of duties

Untuk konfigurasi kritis, pembuat/perubah konfigurasi tidak boleh menjadi satu-satunya approver. Role minimal:

- `SOURCE_OWNER`;
- `DATA_STEWARD`;
- `TECHNICAL_APPROVER`;
- `PLATFORM_ADMIN`;
- `ANALYST`;
- `VIEWER`.

---

## 15. Schema Compiler dan Pembuatan Tabel

### 15.1 Prinsip keamanan

Jangan menjalankan DDL yang dihasilkan OpenAI. OpenAI hanya menghasilkan object configuration. Python Schema Compiler menghasilkan DDL dari field yang sudah divalidasi.

Gunakan SQLAlchemy DDL constructs atau identifier quoting resmi. Jangan menggabungkan identifier mentah dari pengguna ke SQL string.

### 15.2 Alur deployment

1. pastikan configuration berstatus `APPROVED`;
2. ambil advisory lock berdasarkan target table;
3. validasi ulang fingerprint dan revision;
4. generate migration plan;
5. tampilkan dry-run/diff;
6. backup metadata object lama;
7. jalankan DDL dalam transaction jika didukung;
8. buat index dan constraint;
9. buat/update semantic view;
10. jalankan smoke test;
11. aktifkan configuration version;
12. tandai versi lama `SUPERSEDED`;
13. tulis schema change log.

### 15.3 Contoh compiler sederhana

```python
from sqlalchemy import (
    MetaData, Table, Column, Text, Integer, BigInteger,
    Numeric, Boolean, Date, DateTime
)


TYPE_MAP = {
    "text": Text,
    "integer": Integer,
    "bigint": BigInteger,
    "numeric": Numeric,
    "boolean": Boolean,
    "date": Date,
    "timestamp": DateTime,
    "timestamptz": DateTime,
}


def compile_table(config: ETLConfigurationRecommendation) -> Table:
    metadata = MetaData(schema="trusted")
    columns = []

    for item in config.columns:
        column_type = TYPE_MAP[item.target_type]
        columns.append(
            Column(
                normalize_identifier(item.target_column),
                column_type(),
                nullable=item.nullable,
                primary_key=item.is_primary_key,
            )
        )

    return Table(
        normalize_identifier(config.target_table),
        metadata,
        *columns,
    )
```

Implementasi produksi harus menangani length/precision, UUID, timezone, unique constraint, FK, index, comment, dan schema evolution.

### 15.4 Perubahan destructive

Schema compiler tidak boleh otomatis:

- menghapus tabel;
- menghapus kolom;
- mempersempit varchar;
- mengubah tipe dengan risiko kehilangan data;
- mengganti primary key;
- menambahkan `NOT NULL` pada tabel berisi data tanpa backfill.

Perubahan tersebut menghasilkan migration proposal dan membutuhkan approval khusus.

### 15.5 Satu Sheet menjadi beberapa tabel

Hal ini diperbolehkan jika satu tab berisi beberapa grain, misalnya header transaksi dan detail barang. Aturannya:

- AI boleh merekomendasikan split;
- pengguna melihat alasan dan relasinya;
- Python memvalidasi business key;
- setiap target mempunyai mapping terpisah;
- lineage tetap menunjuk ke source row/column;
- deployment baru dilakukan setelah approval.

---

## 16. ETL Compiler dan Runtime

### 16.1 Transformation registry

Konfigurasi tidak menyimpan arbitrary Python atau arbitrary SQL. Konfigurasi hanya boleh merujuk kepada transformation code yang terdaftar:

```python
TRANSFORM_REGISTRY = {
    "trim": trim_value,
    "normalize_whitespace": normalize_whitespace,
    "parse_date_id": parse_date_id,
    "parse_decimal_id": parse_decimal_id,
    "uppercase": uppercase,
    "lowercase": lowercase,
    "map_taxonomy": map_taxonomy,
    "null_if_empty": null_if_empty,
}
```

Larangan arbitrary code mencegah konfigurasi menjadi jalur remote code execution.

### 16.2 Tahapan runtime

```text
Acquire source lock
→ Read active configuration
→ Extract increment/full data
→ Persist raw snapshot
→ Normalize row shape
→ Apply deterministic transforms
→ Apply taxonomy/reference mapping
→ Validate DQ rules
→ Send failed rows to quarantine
→ Load staging
→ Merge to trusted
→ Refresh affected semantic objects
→ Update watermark
→ Emit metrics and audit
→ Release lock
```

### 16.3 Idempotency

Gunakan `run_key`:

```text
source_id + sheet_id + source_version/hash + configuration_version
```

Unique constraint mencegah payload yang sama diproses dua kali. Untuk `UPSERT`, business key harus disetujui dan diuji uniqueness-nya.

### 16.4 Load strategy

| Strategi | Penggunaan |
|---|---|
| `APPEND` | Event immutable, tidak ada update baris lama |
| `UPSERT` | Data dapat dikoreksi berdasarkan business key |
| `FULL_REFRESH` | Dataset kecil/reference table |

Full refresh dilakukan melalui temporary table kemudian atomic swap/transaction, bukan truncate sebelum data baru siap.

### 16.5 Data quality action

| Action | Perilaku |
|---|---|
| `REJECT_ROW` | Baris masuk quarantine |
| `WARN` | Baris diproses, warning dicatat |
| `DEFAULT_VALUE` | Nilai diganti sesuai rule |
| `STOP_BATCH` | Seluruh run gagal |
| `REQUIRE_REVIEW` | Run menunggu keputusan |

### 16.6 Background worker

Gunakan Celery/Dramatiq/RQ untuk pekerjaan panjang. Jangan melakukan profiling, OpenAI call, DDL, atau full ETL dalam request HTTP sinkron.

Contoh task:

```python
@celery_app.task(
    bind=True,
    autoretry_for=(TemporaryUpstreamError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def run_etl_task(self, job_id: str):
    return run_async(run_etl_job(job_id))
```

---

## 17. Endpoint ETL dan Monitoring

```text
POST /api/v1/sources/{source_id}/profile
POST /api/v1/sources/{source_id}/sync
POST /api/v1/etl-jobs/{job_id}/run
POST /api/v1/etl-jobs/{job_id}/pause
POST /api/v1/etl-jobs/{job_id}/resume
GET  /api/v1/etl-jobs
GET  /api/v1/etl-runs
GET  /api/v1/etl-runs/{run_id}
GET  /api/v1/etl-runs/{run_id}/errors
GET  /api/v1/etl-runs/{run_id}/lineage
GET  /api/v1/data-quality/issues
POST /api/v1/data-quality/issues/{issue_id}/resolve
GET  /api/v1/quarantine/{source_id}/rows
POST /api/v1/quarantine/{source_id}/reprocess
```

Respons start job:

```json
{
  "job_id": "uuid",
  "status": "QUEUED",
  "status_url": "/api/v1/etl-runs/uuid"
}
```

Frontend dapat polling endpoint status atau menggunakan SSE/WebSocket untuk progress.

---

## 18. Operational Query API untuk Frontend

Frontend tidak sebaiknya mengirim SQL. Frontend memanggil endpoint bisnis dengan parameter tervalidasi.

### 18.1 Generic catalog-driven endpoint

```text
GET /api/v1/data-products
GET /api/v1/data-products/{code}
GET /api/v1/data-products/{code}/dimensions
GET /api/v1/data-products/{code}/metrics
POST /api/v1/data-products/{code}/query
```

Request:

```json
{
  "metrics": ["net_sales", "transaction_count"],
  "dimensions": ["branch_name"],
  "filters": [
    {"field": "transaction_date", "operator": "between", "value": ["2026-09-01", "2026-09-30"]}
  ],
  "sort": [{"field": "net_sales", "direction": "desc"}],
  "limit": 100
}
```

Backend membangun SQL dari metadata yang diizinkan. Field dan operator harus allowlisted.

### 18.2 Endpoint bisnis spesifik

Untuk dashboard rutin, buat endpoint eksplisit:

```text
GET /api/v1/reports/sales/summary
GET /api/v1/reports/sales/by-branch
GET /api/v1/reports/sales/trend
GET /api/v1/reports/inventory/stock-position
GET /api/v1/reports/data-quality/summary
```

Endpoint spesifik lebih mudah diuji, di-cache, diberi SLA, dan diamankan daripada selalu memakai NL2SQL.

### 18.3 Response envelope

```json
{
  "status": "success",
  "data": [],
  "meta": {
    "data_product": "SALES",
    "query_source": "SAVED_QUERY",
    "as_of": "2026-09-03T07:00:00Z",
    "row_count": 12,
    "cached": false
  },
  "errors": []
}
```

---

## 19. Semantic Catalog

### 19.1 Data product

Setiap data product mendefinisikan:

- code dan business description;
- semantic view;
- grain;
- default date field;
- allowed metrics;
- allowed dimensions;
- allowed filters;
- owner dan steward;
- allowed roles;
- sensitivity;
- status dan version.

### 19.2 Metric

Metric harus disimpan sebagai definisi terkontrol, bukan rumus buatan model.

Contoh:

```yaml
metric_code: net_sales
business_name: Penjualan Bersih
data_product: SALES
expression: sum(net_amount)
aggregation: sum
format: currency_idr
allowed_dimensions:
  - branch_name
  - product_category
  - transaction_date
status: ACTIVE
```

### 19.3 Relationship

Simpan join yang diizinkan:

```yaml
left_object: semantic.vw_sales
right_object: semantic.vw_branch
join_type: many_to_one
condition:
  left_column: branch_id
  right_column: branch_id
cardinality_validated: true
status: ACTIVE
```

Model tidak boleh menciptakan join condition di luar registry.

---

## 20. Desain NL2SQL

### 20.1 Endpoint utama

```http
POST /api/v1/nl2sql/query
```

```json
{
  "question": "Berapa penjualan setiap cabang bulan ini?",
  "conversation_id": null,
  "preferred_format": "table"
}
```

Response:

```json
{
  "status": "success",
  "answer": "Total penjualan per cabang bulan berjalan tersedia pada tabel berikut.",
  "data": [],
  "meta": {
    "route": "INTENT_TEMPLATE",
    "intent_code": "SALES_BY_BRANCH_PERIOD",
    "openai_called": false,
    "cached": false,
    "semantic_version": 12,
    "query_id": "uuid"
  }
}
```

### 20.2 Pipeline routing

```text
Authenticate user
→ Resolve tenant and data permissions
→ Normalize question
→ Extract deterministic parameters
→ Exact/alias intent lookup
→ Semantic similarity lookup
→ If confident: run validated template
→ Else retrieve relevant semantic context
→ Ask OpenAI for structured query plan or candidate SQL
→ SQL guard
→ EXPLAIN and cost check
→ Execute with read-only role
→ Redact/limit result
→ Optionally ask model to summarize small result
→ Audit usage
→ Promote validated recurring query
```

### 20.3 Simpan intent, bukan jawaban permanen

Simpan:

- normalized question;
- example utterance;
- intent code;
- SQL template;
- parameter definition;
- required role;
- semantic version;
- validation status.

Result data hanya di-cache singkat menggunakan:

```text
tenant_id
+ access_scope_hash
+ intent_code/query_hash
+ normalized parameters
+ semantic_version
+ data freshness version
```

### 20.4 Mode yang direkomendasikan: structured query plan

Lebih aman meminta model menghasilkan rencana query daripada SQL bebas:

```python
class QueryFilter(BaseModel):
    dimension: str
    operator: Literal["eq", "in", "between", "gte", "lte"]
    value: str | int | float | list[str]


class SemanticQueryPlan(BaseModel):
    data_product_code: str
    metrics: list[str]
    dimensions: list[str]
    filters: list[QueryFilter]
    time_grain: Literal["day", "week", "month", "quarter", "year", "none"]
    limit: int = Field(ge=1, le=1000)
    clarification_required: bool
    clarification_question: str | None
```

Python memvalidasi semua code terhadap Semantic Catalog kemudian menyusun SQL. Ini mengurangi risiko dibanding membiarkan model membuat join dan expression bebas.

### 20.5 Fallback candidate SQL

Jika query tidak dapat direpresentasikan oleh semantic query plan, OpenAI boleh menghasilkan candidate SQL dengan syarat:

- hanya satu statement `SELECT` atau `WITH ... SELECT`;
- hanya semantic objects yang diberikan;
- tanpa DDL/DML;
- tanpa comment;
- tanpa system catalog;
- tanpa function berbahaya;
- selalu memiliki limit untuk query detail;
- parameter menggunakan placeholder, bukan interpolasi.

### 20.6 OpenAI NL2SQL example

```python
class NL2SQLCandidate(BaseModel):
    intent_code: str | None
    sql: str | None
    parameters: dict[str, str | int | float | None]
    explanation: str
    clarification_required: bool
    clarification_question: str | None


async def generate_candidate(
    client: AsyncOpenAI,
    model: str,
    question: str,
    semantic_context: str,
) -> NL2SQLCandidate:
    response = await client.responses.parse(
        model=model,
        input=[
            {
                "role": "developer",
                "content": (
                    "Buat candidate PostgreSQL read-only hanya dari semantic context. "
                    "Jangan gunakan object yang tidak diberikan. Jika ambigu, minta klarifikasi."
                ),
            },
            {
                "role": "user",
                "content": f"Pertanyaan:\n{question}\n\nSemantic context:\n{semantic_context}",
            },
        ],
        text_format=NL2SQLCandidate,
    )
    return response.output_parsed
```

OpenAI tidak diberi database credential dan tidak mengeksekusi SQL. Eksekusi selalu dilakukan backend.

### 20.7 SQL Guard

Gunakan parser AST seperti SQLGlot. Pemeriksaan string/regex saja tidak cukup.

```python
from sqlglot import exp, parse_one


class UnsafeQuery(ValueError):
    pass


def validate_readonly_sql(sql: str, allowed_objects: set[str]) -> str:
    tree = parse_one(sql, read="postgres")

    forbidden = (
        exp.Insert, exp.Update, exp.Delete, exp.Create,
        exp.Drop, exp.Alter, exp.Command, exp.Merge,
    )
    if any(tree.find(node) for node in forbidden):
        raise UnsafeQuery("Only read-only SELECT queries are allowed")

    referenced = {
        f"{table.db}.{table.name}" if table.db else table.name
        for table in tree.find_all(exp.Table)
    }
    if not referenced.issubset(allowed_objects):
        raise UnsafeQuery("Query references an unauthorized object")

    return tree.sql(dialect="postgres")
```

Tambahkan kontrol:

- PostgreSQL transaction read-only;
- statement timeout;
- row limit;
- connection pool terpisah;
- denylist function;
- allowlist schema/table/column;
- `EXPLAIN (FORMAT JSON)` sebelum eksekusi;
- batas estimated cost/rows;
- concurrency limit;
- per-user quota;
- cancellation;
- redaction hasil.

### 20.8 Eksekusi read-only

```python
from sqlalchemy import text


async def execute_nl2sql(session, sql: str, params: dict) -> list[dict]:
    await session.execute(text("SET TRANSACTION READ ONLY"))
    await session.execute(text("SET LOCAL statement_timeout = '10s'"))
    result = await session.execute(text(sql), params)
    return [dict(row._mapping) for row in result.fetchmany(1000)]
```

Selain pemeriksaan aplikasi, role `nl2sql_reader` harus tidak memiliki privilege tulis. Defense in depth wajib diterapkan.

### 20.9 Klarifikasi

Jika pertanyaan seperti “tampilkan penjualan terbaik” tidak menjelaskan periode atau definisi terbaik, sistem tidak boleh menebak. Response:

```json
{
  "status": "clarification_required",
  "question": "Periode penjualan mana yang ingin digunakan?",
  "options": ["Bulan ini", "Kuartal ini", "Tahun ini"]
}
```

---

## 21. Pengendalian Token dan Biaya NL2SQL

Setiap permintaan melalui decision router. Catat:

- `route`: operational, saved query, intent, semantic builder, OpenAI;
- input/output/cached token;
- model;
- latency;
- estimated cost;
- user dan tenant;
- success/failure;
- query fingerprint;
- cache hit;
- reason OpenAI dipanggil.

Kebijakan:

1. OpenAI tidak dipanggil bila exact/semantic intent sudah cukup yakin.
2. Hanya metadata relevan yang dikirim.
3. Prefix prompt yang stabil diletakkan di awal untuk memanfaatkan prompt caching.
4. Pertanyaan tervalidasi dipromosikan menjadi intent/query template.
5. Terapkan quota harian berdasarkan role.
6. Terapkan budget limit tenant dan circuit breaker.
7. Hentikan NL2SQL AI bila budget tercapai; saved queries tetap berjalan.

Prompt caching OpenAI dapat menurunkan biaya prefix yang sama, tetapi bukan pengganti application cache dan tetap memiliki penggunaan token. Dokumentasi: <https://developers.openai.com/api/docs/guides/prompt-caching>.

---

## 22. Endpoint NL2SQL dan Semantic Administration

```text
POST /api/v1/nl2sql/query
POST /api/v1/nl2sql/clarifications/{request_id}
GET  /api/v1/nl2sql/requests/{request_id}
POST /api/v1/nl2sql/requests/{request_id}/feedback
POST /api/v1/nl2sql/requests/{request_id}/promote

GET    /api/v1/semantic/data-products
POST   /api/v1/semantic/data-products
PATCH  /api/v1/semantic/data-products/{id}
GET    /api/v1/semantic/metrics
POST   /api/v1/semantic/metrics
GET    /api/v1/semantic/intents
POST   /api/v1/semantic/intents
POST   /api/v1/semantic/intents/{id}/examples
POST   /api/v1/semantic/query-templates/{id}/validate
POST   /api/v1/semantic/query-templates/{id}/activate

GET /api/v1/admin/ai-usage/summary
GET /api/v1/admin/ai-usage/by-user
GET /api/v1/admin/ai-usage/by-tenant
GET /api/v1/admin/nl2sql/cache-performance
```

---

## 23. Authentication, Authorization, dan Multi-Tenancy

### 23.1 Authentication

Gunakan JWT/OIDC. Token minimal memuat:

- `sub`;
- `tenant_id`;
- roles/scopes;
- expiry;
- issuer/audience.

### 23.2 Authorization

Setiap akses data harus memeriksa:

- tenant;
- data product permission;
- row scope, misalnya cabang;
- column sensitivity;
- action permission.

Jangan hanya mengandalkan filter yang dibuat model. Scope keamanan ditambahkan backend setelah query plan dibuat.

### 23.3 Tenant isolation

Pilihan yang disarankan:

- semua metadata memiliki `tenant_id`;
- Row Level Security PostgreSQL untuk tabel metadata/trusted yang sesuai;
- view semantic memasukkan scope tenant;
- cache key selalu memasukkan tenant dan access-scope hash.

---

## 24. Error Handling

Gunakan error code stabil:

| Code | HTTP | Makna |
|---|---:|---|
| `SOURCE_ACCESS_DENIED` | 403 | Service Account tidak dapat membaca Sheet |
| `SOURCE_NOT_FOUND` | 404 | Sheet/tab tidak ditemukan |
| `PROFILE_FAILED` | 422 | Profiling gagal |
| `AI_CONFIGURATION_INVALID` | 422 | Output AI gagal validasi |
| `CONFIGURATION_CONFLICT` | 409 | Revision/fingerprint berubah |
| `APPROVAL_REQUIRED` | 409 | Belum boleh deploy |
| `SCHEMA_CHANGE_UNSAFE` | 422 | Perubahan destructive |
| `ETL_RUN_LOCKED` | 409 | Run lain masih aktif |
| `NL2SQL_CLARIFICATION_REQUIRED` | 422 | Pertanyaan ambigu |
| `NL2SQL_UNSAFE_QUERY` | 422 | SQL tidak lolos guard |
| `NL2SQL_QUOTA_EXCEEDED` | 429 | Kuota pengguna/tenant habis |
| `UPSTREAM_RATE_LIMITED` | 503 | API upstream membatasi request |

Jangan mengembalikan stack trace, credential, prompt internal, atau SQL sensitif ke frontend.

---

## 25. Observability

### 25.1 Metrics

- `source_profile_duration_seconds`;
- `etl_run_duration_seconds`;
- `etl_rows_extracted_total`;
- `etl_rows_loaded_total`;
- `etl_rows_quarantined_total`;
- `schema_drift_total`;
- `openai_requests_total`;
- `openai_tokens_input_total`;
- `openai_tokens_output_total`;
- `nl2sql_route_total{route=...}`;
- `nl2sql_guard_rejection_total`;
- `nl2sql_cache_hit_ratio`;
- `query_template_promotion_total`.

### 25.2 Structured logging

Setiap log menggunakan correlation fields:

```json
{
  "request_id": "uuid",
  "tenant_id": "uuid",
  "user_id": "uuid",
  "source_id": "uuid",
  "etl_run_id": "uuid",
  "configuration_version": 4,
  "event": "etl.load.completed"
}
```

Jangan log nilai sel mentah secara default.

---

## 26. Pengujian

### 26.1 Unit test

- header normalization;
- type inference;
- fingerprint stability;
- transformation registry;
- DQ rules;
- schema compiler;
- intent normalization;
- SQL AST guard;
- permission injection;
- cache key generation.

### 26.2 Integration test

- Google Sheets mock/test spreadsheet;
- PostgreSQL temporary database;
- Alembic migration;
- worker job lifecycle;
- OpenAI adapter mocked dengan fixture terstruktur;
- DDL dry-run;
- staging-to-trusted merge;
- transaction rollback.

### 26.3 Contract test OpenAI

Gunakan dataset prompt tetap untuk memastikan:

- output selalu parse ke Pydantic;
- canonical mapping konsisten;
- ambiguity menghasilkan pertanyaan;
- model tidak membuat schema terlarang;
- NL2SQL hanya memakai semantic context;
- token dan latency berada di batas yang disetujui.

### 26.4 NL2SQL evaluation set

Siapkan kumpulan:

- pertanyaan mudah;
- sinonim Bahasa Indonesia/Inggris;
- pertanyaan multi-metric;
- pertanyaan ambigu;
- pertanyaan tanpa data;
- prompt injection;
- permintaan data tanpa izin;
- query mahal;
- pertanyaan yang harus diarahkan ke saved report.

Ukuran keberhasilan:

- intent accuracy;
- execution accuracy;
- result correctness;
- unsafe query rejection rate;
- clarification precision;
- persentase pertanyaan tanpa OpenAI;
- biaya rata-rata per pertanyaan.

---

## 27. Deployment

### 27.1 Process terpisah

Jalankan minimal:

- FastAPI web process;
- worker process;
- scheduler/beat process;
- PostgreSQL;
- Redis;
- Nginx reverse proxy.

### 27.2 Startup order

1. PostgreSQL dan Redis siap;
2. jalankan `alembic upgrade head`;
3. start worker;
4. start scheduler;
5. start FastAPI/Gunicorn;
6. health check;
7. aktifkan traffic Nginx.

### 27.3 Health endpoint

```text
GET /health/live
GET /health/ready
```

Readiness memeriksa database dan Redis. Pemeriksaan OpenAI/Google API tidak dilakukan pada setiap health check agar tidak menambah biaya atau quota; gunakan scheduled dependency check terpisah.

---

## 28. Urutan Implementasi Teknis

### Fase 1 — Foundation

1. scaffold FastAPI;
2. konfigurasi async SQLAlchemy;
3. authentication dan tenant context;
4. schema `platform` dan `audit` melalui Alembic;
5. Redis dan worker;
6. structured logging dan error envelope.

**Definition of done:** user dapat login, source metadata dapat dibuat, job dapat diantrikan, audit event tercatat.

### Fase 2 — Google Sheets ingestion

1. setup Service Account;
2. source registration;
3. metadata/tab discovery;
4. batch value reader;
5. raw snapshot;
6. retry, quota, dan permission error;
7. profiling dan fingerprint.

**Definition of done:** sistem dapat membaca Sheet test, menampilkan profile, dan mendeteksi perubahan schema.

### Fase 3 — AI configuration onboarding

1. finalisasi Pydantic configuration schema;
2. prompt v1;
3. OpenAI Responses adapter;
4. masking PII;
5. Structured Outputs parsing;
6. deterministic validator;
7. draft configuration persistence;
8. token/cost audit.

**Definition of done:** source baru menghasilkan draft konfigurasi valid tanpa langsung memodifikasi database.

### Fase 4 — Review dan approval

1. configuration form API;
2. unresolved questions;
3. PATCH dengan optimistic locking;
4. validation endpoint;
5. approval workflow;
6. configuration diff dan versioning.
7. pembuatan artifact JSON/YAML/XLSX dari canonical configuration;
8. daftar, preview, download, clone, activate, dan rollback API;
9. relasi `source_sheet.active_configuration_id` dan `configuration_artifact`.

**Definition of done:** setiap tab memiliki konfigurasi berversi yang dapat dilihat dan diedit melalui clone draft; setelah approval tersedia file artifact tervalidasi dan relasinya tercatat di registry.

### Fase 5 — Schema dan ETL compiler

1. identifier/type allowlist;
2. DDL planner;
3. safe migration classifier;
4. transformation registry;
5. DQ engine;
6. staging loader;
7. trusted upsert/append/full refresh;
8. quarantine dan lineage;
9. scheduler dan idempotency.

**Definition of done:** konfigurasi aktif dapat membuat target aman dan menjalankan ETL berulang tanpa OpenAI.

### Fase 6 — Operational API dan semantic layer

1. data product registry;
2. metric/dimension registry;
3. relationship registry;
4. semantic views;
5. generic query builder;
6. endpoint laporan spesifik;
7. cache dan permission.

**Definition of done:** dashboard utama tidak memerlukan NL2SQL.

### Fase 7 — NL2SQL controlled fallback

1. intent registry dan examples;
2. deterministic parameter extractor;
3. exact/normalized/semantic matching;
4. validated template executor;
5. relevant schema retrieval;
6. structured semantic query plan;
7. OpenAI SQL fallback;
8. SQL AST guard;
9. `EXPLAIN`, timeout, limit, read-only role;
10. feedback, evaluation, dan promotion workflow.

**Definition of done:** pertanyaan lama menggunakan template; pertanyaan baru hanya menggunakan object semantic yang diizinkan dan tidak dapat menulis database.

### Fase 8 — Hardening

1. load test;
2. penetration/prompt-injection test;
3. backup/restore drill;
4. schema drift drill;
5. AI budget circuit breaker;
6. observability dashboard;
7. runbook insiden;
8. disaster recovery.

---

## 29. Acceptance Criteria Utama

Platform dianggap siap produksi jika:

- pengguna non-IT dapat mendaftarkan Google Sheet dan menerima rekomendasi konfigurasi;
- tidak ada credential di workbook atau log;
- output AI tidak pernah dieksekusi sebagai code/DDL mentah;
- konfigurasi harus disetujui sebelum aktif;
- konfigurasi memiliki version dan audit trail;
- setiap tab Google Sheet dapat ditelusuri ke konfigurasi aktif dan file artifact tertentu;
- konfigurasi aktif dapat dilihat dan diunduh, tetapi perubahan harus melalui versi draft baru;
- artifact mempunyai content hash dan tidak dapat mengaktifkan dirinya tanpa status registry;
- ETL berulang tidak memanggil OpenAI ketika fingerprint tidak berubah;
- baris gagal dapat ditelusuri dan diproses ulang;
- dashboard rutin menggunakan operational endpoint;
- pertanyaan berulang menggunakan intent/query template;
- NL2SQL hanya menggunakan semantic allowlist dan PostgreSQL role read-only;
- seluruh SQL AI lolos AST validation dan resource guard;
- tenant dan row-level access tidak ditentukan oleh model;
- penggunaan token, biaya, latency, dan route tercatat;
- schema drift menghasilkan draft baru, bukan perubahan otomatis.

---

## 30. Referensi Implementasi OpenAI

- Responses API migration and current request patterns: <https://developers.openai.com/api/docs/guides/migrate-to-responses>
- Structured Outputs: <https://developers.openai.com/api/docs/guides/structured-outputs>
- Function calling: <https://developers.openai.com/api/docs/guides/function-calling>
- Prompt caching: <https://developers.openai.com/api/docs/guides/prompt-caching>
- Cost optimization: <https://developers.openai.com/api/docs/guides/cost-optimization>

Gunakan dokumentasi resmi dan versi SDK yang dikunci saat implementasi. Jangan menyalin contoh SDK tanpa contract test karena signature dapat berubah antarversi.

---

## 31. Ringkasan Keputusan Final

1. Google Sheet adalah source, bukan langsung database query target.
2. Python melakukan profiling sebelum AI.
3. OpenAI membuat draft konfigurasi terstruktur pada onboarding atau exception.
4. Manusia menyetujui konfigurasi.
5. Python Schema Compiler membuat object database dari allowlist.
6. Python menjalankan ETL rutin tanpa OpenAI.
7. Data dipercaya berada pada PostgreSQL `trusted` dan disajikan melalui `semantic`.
8. Frontend memakai operational API untuk kebutuhan rutin.
9. NL2SQL adalah fallback setelah saved query dan semantic query builder.
10. Pertanyaan tervalidasi dipromosikan menjadi intent/query template agar tidak terus menggunakan token.
11. OpenAI tidak memegang credential dan tidak mengeksekusi SQL.
12. PostgreSQL permission, AST guard, timeout, limit, audit, dan approval menjadi kontrol utama.
