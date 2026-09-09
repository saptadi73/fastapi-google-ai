# Penyelarasan schema registry setelah BE-12

Migrasi `8a96b7c5d4ef`, setelah `7i85f6b4c3de`, memperbaiki ketidaksesuaian schema
registry yang ditemukan saat pengujian APPEND BE-12. Tidak ada perubahan policy
APPEND, multi-target, atau schema evolution dataset pada tahap ini.

## Masalah dan perbaikan

Endpoint taxonomy sudah mengirim `fingerprint`, `snapshot_hash`, dan `created_by`,
sedangkan model ORM belum mempunyai seluruh field tersebut. Constructor model dapat
gagal sebelum INSERT, dan assignment approval binding hanya menjadi atribut Python
yang tidak tersimpan. Kolom fisik sudah ada sejak migrasi sebelumnya.

Mixin ORM `TaxonomyMetadata` kini memetakan kolom existing untuk taxonomy, term, dan
binding: fingerprint/snapshot_hash string 64, created_by UUID wajib, approved_by UUID
opsional, dan approved_at timestamp dengan zona opsional. Approval taxonomy juga
menyimpan reviewer dan waktu, seperti approval binding. GET berikutnya mengembalikan
metadata yang tersimpan. Body request dan role endpoint tetap mengikuti kontrak
existing; definisi respons lengkap ada di [schema API](api/SCHEMAS.md).

Hash taxonomy merupakan metadata yang dihitung endpoint, bukan bukti review snapshot
Google Sheet. Migrasi sebelumnya mengisi sebagian hash historis dengan nol; repair
ini mempertahankan nilai tersebut dan tidak menganggapnya sebagai snapshot tervalidasi.

## Cakupan migrasi

Empat tabel: `master_column_binding`, `taxonomy`, `taxonomy_term`, dan
`taxonomy_column_binding`. Migrasi memastikan unique `(tenant_id,id)`, index tenant,
serta 14 FK komposit tenant + UUID ke pengguna, source sheet, master, taxonomy, dan
parent term. FK satu kolom yang sudah ada tetap dipertahankan.

Instalasi lama dapat kehilangan constraint master binding karena pernah menjalankan
bentuk lebih awal migrasinya. Instalasi baru sudah mempunyai constraint tersebut.
Repair memeriksa definisi fisik dan menambahkan yang belum ada, sehingga kedua bentuk
bisa di-upgrade dan pemanggilan upgrade ulang tidak menggandakan constraint.
Spesifikasi migration dibekukan dalam file, tanpa mengimpor model aplikasi saat runtime.

Tidak ada kolom, record, metadata audit, atau ID yang dihapus/ditulis ulang. PostgreSQL
memvalidasi data lama ketika memasang FK. Jika terdapat orphan atau relasi lintas
tenant, upgrade gagal dan transaksi DDL dibatalkan; data tidak dipindahkan otomatis
ke tenant lain. Perbaiki penyebabnya melalui proses koreksi data yang direview sebelum
mengulangi upgrade. Pemasangan constraint/index membutuhkan lock dan pemeriksaan data;
jadwalkan rollout sesuai ukuran registry dan aktivitas environment tujuan.

## Rollout dan rollback

Pada sesi ini hanya database test terpisah yang di-upgrade. Jalur verifikasi yang
dipakai memuat guard `tests/conftest.py`, memastikan TEST_DATABASE_URL berbeda dari
database aplikasi dan namanya berakhiran `_test`, sebelum memanggil Alembic.
Environment aplikasi/production belum dimigrasikan.

Sesudah upgrade, jalankan `alembic check` pada koneksi environment yang sama.
Model aplikasi versi ini memerlukan migrasi taxonomy sebelumnya serta repair ini.
Sebelum rollout environment lain, siapkan backup registry dan verifikasi relasi lama;
ikuti prosedur deployment environment tersebut.

**Downgrade repair bersifat aditif:** Alembic boleh memundurkan revision marker, tetapi
constraint/index tetap dipertahankan. Sebagian constraint mungkin sudah ada sebelum
repair; menghapusnya akan melemahkan isolasi tenant dan tidak diperlukan untuk rollback
aplikasi. Tidak ada transformasi data untuk dibalik. Menghapus tenant guard secara
manual bukan bagian rollback ini. Upgrade ulang setelah rollback marker tetap aman.
Migrasi ini membutuhkan koneksi database untuk introspeksi, bukan mode offline `--sql`.

## Bukti pengujian

- `alembic upgrade head` pada database test berhasil dan `alembic check` menghasilkan
  `No new upgrade operations detected`.
- Tiga tes migrasi PostgreSQL memakai schema acak dalam transaksi yang selalu di-rollback:
  baseline lama, baseline dengan constraint master existing, serta data lama lintas tenant.
  Upgrade ulang, downgrade aditif, 14 penolakan FK lintas tenant, metadata historis,
  dan rollback DDL saat data invalid diperiksa.
- Tes HTTP nyata mencakup create taxonomy, parent/child term, approval, create/approve
  binding, baca ulang metadata, dan penolakan akses tenant lain.
- Total tahap ini: **208 tes non-integrasi dan 17 tes PostgreSQL lulus** (3 migrasi,
  1 HTTP taxonomy, 6 APPEND, 7 effective dating). Ruff seluruh file kode perubahan
  dan exporter `--check` yang memverifikasi 145 operasi API lulus.
- Provider Google Sheet dalam fixture HTTP dimock; ini bukan bukti integrasi provider
  atau deployment production. Lifecycle taxonomy lanjutan dan FK as-of tetap pekerjaan
  terpisah.
