# Panduan konfigurasi dan rotasi kredensial

Panduan operasional untuk pengembangan lokal dan persiapan production. Disusun berdasarkan kode proyek pada 8 September 2026. Semua password, key, host, dan ID contoh harus diganti dengan nilai lingkungan tujuan. Dokumen ini tidak menyimpan kredensial asli.

## 1. Lokasi konfigurasi dan proses yang harus diperbarui

Konfigurasi dibaca oleh `app/core/config.py` dari `.env` di root proyek. Environment variable proses dapat mengesampingkan nilai `.env`; jika perubahan file tidak berpengaruh, periksa konfigurasi container atau service manager juga.

`.env` dan direktori `secrets/` sudah diabaikan Git. Sediakan keduanya melalui mekanisme deployment atau secret manager. Setiap instance API dan worker harus memperoleh konfigurasi serta file kredensial yang sama sesuai lingkungannya.

Setelah mengganti konfigurasi, restart atau redeploy **API, worker Celery, dan scheduler Celery beat** yang berjalan. Settings disimpan dalam cache proses; jangan mengandalkan reload development untuk rotasi kredensial. Hanya jalankan satu scheduler beat.

## 2. Daftar konfigurasi

| Variabel | Isi dan kegunaan |
|---|---|
| `DATABASE_URL` | Koneksi operasional aplikasi; juga digunakan Alembic dan bootstrap saat perintah tersebut dijalankan |
| `DATABASE_DDL_URL` | Koneksi untuk deploy tabel `trusted` dan view `semantic`; kosong berarti memakai `DATABASE_URL` |
| `DATABASE_NL2SQL_URL` | Koneksi role khusus SELECT untuk eksekusi query AI |
| `JWT_SECRET` | Secret acak minimal 32 karakter; berbeda per lingkungan |
| `BOOTSTRAP_PASSWORD` | Password admin awal minimal 12 karakter |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path JSON key Google; relatif terhadap root proyek atau path absolut |
| `GOOGLE_CREDENTIAL_REF` | Alias kredensial server; contoh `default` |
| `OPENAI_API_KEY` | API key dari project OpenAI tujuan |
| `OPENAI_MODEL_ETL_CONFIG` | ID model untuk usulan pemetaan dan transformasi ETL |
| `OPENAI_MODEL_NL2SQL` | ID model untuk rencana query terstruktur |
| `OPENAI_INPUT_USD_PER_MILLION` / `OPENAI_OUTPUT_USD_PER_MILLION` | Tarif model untuk estimasi biaya aplikasi |
| `AI_DAILY_TENANT_BUDGET_USD` | Budget harian aplikasi; `0` menonaktifkan batas USD |
| `REDIS_URL` | Redis untuk cache hasil query |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis untuk antrean dan hasil Celery |
| `REDIS_REQUIRED` | Jika `true`, Redis menjadi syarat readiness |
| `TEST_DATABASE_URL` | Database terpisah khusus tes; bukan database production |

Untuk production, isi `APP_ENV=production`, sesuaikan `HOST`, `PORT`, dan `CORS_ORIGINS` dengan deployment. `APP_ENV` tidak otomatis memasang TLS, reverse proxy, atau process manager. Pertahankan `REQUIRE_SEPARATE_APPROVER=true` dan sediakan akun approver terpisah.

## 3. PostgreSQL: satu database, tiga role

Ketiga URL aplikasi menunjuk database yang sama, misalnya `googleai`, dengan pengguna berbeda:

```dotenv
DATABASE_URL=postgresql+asyncpg://openpg:PASSWORD_APP@DB_HOST:5432/googleai
DATABASE_DDL_URL=postgresql+asyncpg://ddlpg:PASSWORD_DDL@DB_HOST:5432/googleai
DATABASE_NL2SQL_URL=postgresql+asyncpg://readpg:PASSWORD_READER@DB_HOST:5432/googleai
```

Encode karakter khusus pada username/password jika digunakan dalam URL, misalnya `@` menjadi `%40`. Sesuaikan TLS dengan server database tujuan. Jangan memakai role superuser sebagai role reader.

### Role reader

Jalankan sebagai administrator PostgreSQL. Jika role sudah ada, jangan ulangi `CREATE ROLE`; gunakan `ALTER ROLE` untuk atribut yang perlu diubah.

```sql
CREATE ROLE readpg
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
    NOREPLICATION NOBYPASSRLS
    PASSWORD 'PASSWORD_READER'
    CONNECTION LIMIT -1;

GRANT CONNECT ON DATABASE googleai TO readpg;
```

Kemudian, dengan koneksi admin ke **database `googleai`** setelah migrasi menyediakan schema:

```sql
GRANT USAGE ON SCHEMA semantic TO readpg;

-- Untuk setiap view yang sudah ada dan diizinkan:
GRANT SELECT ON semantic.nama_view TO readpg;
```

`nama_view` adalah placeholder. Untuk view yang baru dideploy, aplikasi memberikan `SELECT` kepada username dalam `DATABASE_NL2SQL_URL`. Hindari memberikan role reader akses tulis atau keanggotaan role berprivilege. Aplikasi memeriksa privilege role sebelum eksekusi query AI.

`CONNECTION LIMIT 0` melarang koneksi role biasa; `-1` berarti tanpa batas. Untuk mengganti password:

```sql
ALTER ROLE readpg WITH PASSWORD 'PASSWORD_READER_BARU';
```

Perbarui URL terkait dan restart proses pemakai. Rotasi password pada role yang sama langsung memengaruhi koneksi baru; untuk mengurangi gangguan, gunakan role pengganti dengan izin setara, pindahkan aplikasi, verifikasi, lalu nonaktifkan login role lama.

### Role DDL untuk deployment ETL

Jalankan sebagai admin dengan koneksi ke `googleai`. Schema `trusted` dan `semantic`, serta role aplikasi `openpg`, harus sudah ada. Ganti `openpg` jika username operasional berbeda.

```sql
CREATE ROLE ddlpg
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
    NOREPLICATION NOBYPASSRLS
    PASSWORD 'PASSWORD_DDL'
    CONNECTION LIMIT -1;

GRANT CONNECT ON DATABASE googleai TO ddlpg;
GRANT USAGE, CREATE ON SCHEMA trusted, semantic TO ddlpg;
GRANT SELECT ON ALL TABLES IN SCHEMA trusted TO ddlpg;

GRANT USAGE ON SCHEMA trusted, semantic TO openpg;

ALTER DEFAULT PRIVILEGES FOR ROLE ddlpg IN SCHEMA trusted
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO openpg;

ALTER DEFAULT PRIVILEGES FOR ROLE ddlpg IN SCHEMA semantic
    GRANT SELECT ON TABLES TO openpg;
```

Default privileges berlaku untuk objek baru yang dibuat **oleh `ddlpg`**, bukan objek lama atau objek yang dibuat role lain. Untuk objek lama yang diperlukan aplikasi, berikan grant secara eksplisit:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON trusted.nama_tabel TO openpg;
GRANT SELECT ON semantic.nama_view TO openpg;
```

Jika view aplikasi sebelumnya dimiliki user lain, `CREATE OR REPLACE VIEW` oleh `ddlpg` memerlukan penyesuaian kepemilikan. Tinjau nama objek dan jalankan sebagai admin:

```sql
ALTER VIEW semantic.nama_view OWNER TO ddlpg;
```

Pemilik view harus tetap bisa membaca tabel sumber. Grant SELECT pada tabel `trusted` lama di atas mendukung hal ini. Transfer ownership tabel hanya jika role baru memang harus mengubah struktur tabel tersebut; jangan memindahkan semua objek database secara massal.

Role DDL ini tidak memerlukan `SUPERUSER`, `CREATEDB`, atau `CREATEROLE`. `CREATE` pada schema adalah izin membuat objek di schema, berbeda dari `CREATEDB`.

### Migrasi bukan deploy ETL

`alembic/env.py` menggunakan **`DATABASE_URL`**, bukan `DATABASE_DDL_URL`. Role DDL di atas tidak otomatis memiliki akses migrasi platform.

Untuk production, jalankan Alembic dalam proses deployment terpisah menggunakan `DATABASE_URL` milik role migrasi yang memiliki izin schema dan ownership yang diperlukan. Setelah migrasi, proses API dan worker tetap memakai koneksi operasionalnya. Pastikan role operasional menerima akses pada tabel platform hasil migrasi. Pembuatan database awal dan pemberian hak akses dilakukan admin sebelum bootstrap.

## 4. OpenAI: setup dan mengganti key

1. Login ke [OpenAI API Keys](https://platform.openai.com/api-keys), pilih project tujuan, lalu buat key.
2. `Owned by You` sesuai untuk pengembangan pribadi. Untuk aplikasi production yang dikelola tim, gunakan Service Account milik project.
3. Simpan key ke secret konfigurasi backend. Pastikan billing dan akses model tersedia pada project tersebut.
4. Model harus mendukung Responses API dan Structured Outputs karena aplikasi memakai `client.responses.parse`.

Contoh model yang dikonfigurasi pada sesi setup ini:

```dotenv
OPENAI_API_KEY=KEY_DARI_PROJECT_TUJUAN
OPENAI_MODEL_ETL_CONFIG=gpt-5-mini
OPENAI_MODEL_NL2SQL=gpt-5-mini
OPENAI_STORE_RESPONSES=false
```

Periksa kembali ketersediaan dan kemampuan model saat deployment; contoh ini bukan jaminan akses untuk semua project. ETL config mengusulkan draft konfigurasi; NL2SQL menghasilkan rencana terstruktur yang disusun menjadi SQL dan divalidasi aplikasi.

### Rotasi key

1. Buat key baru pada project tujuan; biarkan key lama aktif selama perpindahan terencana.
2. Perbarui `OPENAI_API_KEY` di semua konfigurasi API dan worker. Jika berganti project, periksa kembali model, permissions, dan billing.
3. Restart/redeploy semua proses pemakai konfigurasi.
4. Uji satu pembuatan draft ETL AI dan satu pertanyaan NL2SQL dengan data yang diizinkan. Pengujian ini memanggil API dan dapat dikenai biaya; pastikan job ETL diproses worker. Gunakan pertanyaan baru agar hasil cache tidak dianggap sebagai bukti eksekusi baru.
5. Verifikasi hasil dan log penggunaan, lalu cabut key lama di dashboard setelah seluruh instance beralih.

Untuk rollback sebelum key lama dicabut, kembalikan referensi secret sebelumnya dan restart. Jika key lama bocor, cabut segera; jangan menunggu prosedur overlap biasa selesai.

Permissions `Read only` tidak cukup untuk membuat respons AI. Jika memakai `Restricted`, izinkan pembuatan respons pada Responses API. Permissions key OpenAI terpisah dari izin SELECT role PostgreSQL.

### Estimasi biaya

Isi tarif input/output per satu juta token sesuai model dan harga resmi saat deployment. Budget USD positif memerlukan kedua tarif positif; jika tidak, aplikasi mengembalikan `AI_PRICING_REQUIRED`.

Saat ini kode hanya memiliki **satu pasangan tarif untuk kedua model**. Jika model ETL dan NL2SQL berbeda harga, perhitungan tidak dapat mewakili keduanya secara tepat tanpa penyesuaian kode. Estimasi aplikasi juga belum memberi tarif khusus cached tokens; gunakan billing penyedia sebagai acuan tagihan. Nilai tarif dan budget `0` tidak berarti API gratis.

## 5. Google Service Account

### Setup awal

1. Pilih/buat project di [Google Cloud Console](https://console.cloud.google.com/) dan aktifkan Google Sheets API.
2. Buka **IAM & Admin → Service Accounts**, buat identitas khusus aplikasi.
3. Pada akun tersebut, pilih **Keys → Add key → Create new key → JSON**. Simpan file unduhan utuh; jangan menyusun private key sendiri.
4. Letakkan file di lokasi yang tersedia bagi API dan worker, lalu atur path-nya. Nama file boleh berbeda asalkan cocok dengan konfigurasi.

```dotenv
GOOGLE_SERVICE_ACCOUNT_FILE=secrets/google-service-account.json
GOOGLE_CREDENTIAL_REF=default
```

JSON berisi `type`, `project_id`, `client_email`, `private_key_id`, `private_key`, dan informasi endpoint autentikasi. Service Account Google terpisah dari Service Account OpenAI.

Bagikan **setiap spreadsheet yang akan digunakan aplikasi** ke email `client_email` sebagai **Viewer**. Akses pribadi pembuat akun tidak diwariskan ke Service Account. Spreadsheet tidak perlu dibuat publik.

Untuk pendaftaran sumber, isi `credential_ref` dengan alias, bukan email atau isi JSON:

```json
{
  "source_code": "penjualan",
  "name": "Data Penjualan",
  "spreadsheet_url": "https://docs.google.com/spreadsheets/d/ID_SPREADSHEET/edit",
  "description": "Data transaksi penjualan",
  "credential_ref": "default",
  "sync_schedule": "0 */6 * * *"
}
```

Kirim ke `POST /api/v1/sources/google-sheets` dengan autentikasi aplikasi. Jadwal cron menggunakan UTC. Aplikasi saat ini memakai satu file Service Account dan satu alias global; `credential_ref` bukan pemilih banyak file kredensial.

### Mengganti key pada Service Account yang sama

1. Buat JSON key baru pada akun yang sama. `client_email` tetap sama sehingga share spreadsheet tidak perlu diulang.
2. Simpan sebagai file baru, misalnya `secrets/google-service-account-next.json`, lalu ubah `GOOGLE_SERVICE_ACCOUNT_FILE` di semua instance.
3. Restart/redeploy API dan worker; pastikan mount file serta izin baca proses benar.
4. Uji discovery/profiling atau sync pada sumber yang diizinkan hingga job selesai. Membaca JSON secara lokal saja belum membuktikan key diterima Google atau akses Sheet berhasil.
5. Setelah semua proses menggunakan key baru, hapus key lama dari Google Cloud dan hapus salinan lama dari deployment sesuai kebijakan penyimpanan secret.

### Mengganti Service Account atau project Google

1. Buat akun dan JSON key baru; jika project baru, aktifkan Google Sheets API pada project itu.
2. Bagikan semua spreadsheet yang digunakan aplikasi ke **`client_email` baru** sebagai Viewer sebelum perpindahan.
3. Distribusikan JSON baru dan perbarui `GOOGLE_SERVICE_ACCOUNT_FILE`. Alias `GOOGLE_CREDENTIAL_REF=default` dapat dipertahankan.
4. Restart/redeploy, lalu uji sumber yang mewakili seluruh cakupan akses. Gunakan daftar sumber aplikasi untuk memastikan tidak ada spreadsheet terlewat.
5. Setelah verifikasi, cabut key lama dan akses akun lama ke spreadsheet apabila akun tersebut tidak digunakan aplikasi lain.

Untuk rollback terencana, pulihkan path file lama selama key dan share lama masih aktif. Jika kebijakan organisasi melarang pembuatan key, koordinasikan metode autentikasi dengan admin; adapter saat ini memerlukan file JSON Service Account.

## 6. Redis: lokal dan production

Backend bisa berjalan lokal. Redis bukan penanda bahwa aplikasi harus berada di production.

### Lokal tanpa Redis

```dotenv
REDIS_REQUIRED=false
```

Jalankan API dan proses antrean secara manual:

```powershell
.\venv\Scripts\python.exe -m app.server
```

Di terminal lain, ulangi perintah ini saat ada job yang perlu diproses:

```powershell
.\venv\Scripts\python.exe -m app.cli worker-once
```

`REDIS_REQUIRED=false` hanya mengubah syarat readiness; tidak menyediakan broker Celery pengganti. Scheduler otomatis tetap membutuhkan Redis dan proses Celery.

### Lokal dengan Docker

`compose.yaml` menyediakan Redis lokal pada `127.0.0.1:6379`:

```powershell
docker compose up -d redis
docker compose exec redis redis-cli ping
```

Respons pemeriksaan yang diharapkan: `PONG`.

```dotenv
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2
```

Jalankan worker dan beat pada terminal terpisah:

```powershell
.\venv\Scripts\python.exe -m celery -A app.workers.celery_app:celery_app worker --pool=solo --loglevel=info
```

```powershell
New-Item -ItemType Directory -Force storage
.\venv\Scripts\python.exe -m celery -A app.workers.celery_app:celery_app beat --loglevel=info --schedule=storage/celerybeat-schedule
```

### Production

Gunakan Redis yang dapat diakses API/worker, dengan autentikasi dan TLS sesuai layanan tujuan. Atur ketiga URL; jangan menganggap `127.0.0.1` menunjuk host lain dari dalam container. Contoh Compose lokal belum merupakan konfigurasi production lengkap.

Jalankan API, worker, dan satu beat sebagai service terkelola. Contoh Windows `--pool=solo` ditujukan untuk development; worker production sebaiknya pada Linux. Set `REDIS_REQUIRED=true` jika antrean otomatis wajib tersedia. Readiness Redis tidak membuktikan worker atau beat sudah berjalan; verifikasi penyelesaian job juga.

## 7. Validasi setelah konfigurasi atau rotasi

1. Pastikan `.env` dapat dimuat, tidak ada placeholder tersisa, dan ketiga koneksi aplikasi menuju database yang sama.
2. Pastikan file Google tersedia pada semua instance dan JSON/private key dapat dibaca tanpa mencetak isi secret.
3. Periksa database dan readiness melalui endpoint di bawah. Periksa koneksi DDL dan reader secara terpisah karena health database hanya menguji koneksi utama.
4. Verifikasi login, discovery/profiling Google, pembuatan draft AI, approval terpisah, deploy, sync, dan query NL2SQL dengan data uji yang diizinkan. Deploy/sync mengubah data aplikasi; lakukan pada sumber uji atau jadwal verifikasi yang disepakati.
5. Catat waktu rotasi, lingkungan, penanggung jawab, ID key (bukan nilai secret), hasil pengujian, dan waktu pencabutan key lama.

```powershell
.\venv\Scripts\python.exe -m app.cli check-db
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/database
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

`/health/live` hanya membuktikan API merespons. `/health/database` membuktikan koneksi utama. `/health/ready` memeriksa database, tabel migrasi, dan Redis sesuai konfigurasi; endpoint tersebut tidak memverifikasi akses Google, OpenAI, atau keberhasilan ETL.

Untuk instalasi pertama, jalankan migrasi dan bootstrap secara eksplisit sesuai README. Mengubah `BOOTSTRAP_PASSWORD` kemudian menjalankan bootstrap **tidak mengganti password admin yang sudah ada**. Mengganti `JWT_SECRET` akan membuat token lama gagal diverifikasi; rencanakan login ulang pengguna.

## 8. Pemecahan masalah

| Gejala | Pemeriksaan |
|---|---|
| `role ... does not exist` | Jalankan CREATE ROLE pada server yang benar sebelum GRANT/ALTER ROLE |
| Role tidak bisa login | Periksa LOGIN, CONNECTION LIMIT, password, CONNECT, aturan autentikasi server, dan endpoint URL |
| `ConnectionDoesNotExistError` | Koneksi terputus; cek log PostgreSQL/proxy dan koneksi langsung. Jangan menyimpulkan password salah hanya dari error ini |
| `NL2SQL_READER_UNSAFE` | Role reader memiliki privilege yang ditolak guard, misalnya superuser atau hak tulis |
| `permission denied for schema semantic` | Periksa USAGE schema dan SELECT pada view yang diperlukan |
| Deploy view gagal karena owner | Periksa owner view dan akses baca role DDL ke tabel sumber |
| ETL tidak dapat menulis tabel baru | Periksa default grants milik role yang benar-benar membuat tabel |
| `GOOGLE_NOT_CONFIGURED` | Periksa path JSON, mount, izin baca file, dan validitas key |
| `SOURCE_ACCESS_DENIED` | Periksa share ke client_email yang aktif dan aktivasi Google Sheets API |
| `OPENAI_NOT_CONFIGURED` | API key atau model untuk tujuan request belum terisi |
| `AI_UPSTREAM_FAILED` | Periksa key, billing, akses model, permissions, timeout, dan jaringan; kode membungkus beberapa jenis kegagalan dalam error ini |
| Redis timeout / job tertahan | Periksa host/port, layanan Redis, broker/backend, worker, dan beat |

## 9. Catatan review lokal pada 8 September 2026

Ini adalah snapshot pemeriksaan, bukan jaminan kesiapan production:

- Format `.env` valid dan tidak ada variabel kosong atau placeholder yang terdeteksi.
- Database utama dan role DDL berhasil terhubung. Izin schema dan default grants DDL sudah tersedia.
- File Google valid secara lokal; akses langsung ke Google Sheets belum diuji.
- Key OpenAI terisi dan kedua model menggunakan `gpt-5-mini`; request langsung OpenAI belum diuji.
- Koneksi reader masih menghasilkan `ConnectionDoesNotExistError`, meskipun LOGIN, CONNECT, USAGE semantic, dan connection limit role sudah sesuai.
- Redis, broker Celery, dan backend Celery timeout.
- Tarif estimasi dan budget AI masih `0`.

Selesaikan dan uji ulang kondisi yang belum berhasil sebelum menggunakan hasil review sebagai bukti kesiapan deployment.

## Referensi

- [README dan alur menjalankan aplikasi](../README.md)
- [Konfigurasi aplikasi](../app/core/config.py)
- [Deploy schema ETL](../app/services/schema_compiler_service.py)
- [Adapter Google Sheets](../app/services/google_sheets_service.py)
- [Adapter OpenAI dan estimasi biaya](../app/services/openai_service.py)
- [OpenAI: membuat API key](https://developers.openai.com/api/docs/quickstart)
- [OpenAI: Service Account dan permissions](https://developers.openai.com/api/docs/guides/terraform/service-accounts)
- [OpenAI: GPT-5 Mini](https://developers.openai.com/api/docs/models/gpt-5-mini)
- [Google: membuat dan menghapus Service Account key](https://docs.cloud.google.com/iam/docs/keys-create-delete)
- [PostgreSQL: privilege dan ownership](https://www.postgresql.org/docs/current/ddl-priv.html)
- [PostgreSQL: default privileges](https://www.postgresql.org/docs/16/sql-alterdefaultprivileges.html)
