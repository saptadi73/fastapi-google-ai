# BE-01 — Kebijakan data dan kontrak dasar

Status: kontrak dasar dan pengujian BE-01 tersedia. BE-01 sendiri tidak menambahkan endpoint atau mengubah sync. **Pembaruan BE-02:** klasifikasi tab dan gate eksekusi kini terhubung melalui API; lihat [Klasifikasi tab BE-02](KLASIFIKASI_TAB_BE02.md). Penyimpanan policy master, registry master, dan worker review per import tetap tahap berikutnya.

## Keputusan bisnis yang dikonfirmasi

Pada 8 September 2026 pengguna memilih:

1. **Klasifikasi per tab (`SHEET`).** Satu spreadsheet dapat memiliki tab MASTER dan NON_MASTER. Tidak ada klasifikasi otomatis berdasarkan tipe angka/teks.
2. **Kode master baru diusulkan untuk ditambahkan (`PROPOSE_INSERT`) dan wajib disetujui.** Kode yang sudah ada diperbarui sesuai preview. Menemukan master lama tidak berarti semua kode baru boleh langsung masuk tanpa persetujuan.

`UPDATE_ONLY` tersedia pada kontrak sebagai kebijakan lebih ketat yang harus ditetapkan eksplisit untuk master tertentu, bukan default pengganti keputusan di atas. `classification_scope`, `dataset_kind`, serta `new_record_policy` dan `source_conflict_policy` untuk master wajib dikirim eksplisit. Field aturan tetap memiliki default sesuai schema; simpan hasil normalisasi lengkap agar persetujuan dapat mengacu pada kebijakan yang nyata.

## Aturan teknis awal

Aturan berikut merupakan dasar implementasi konservatif, bukan keputusan pengguna tambahan yang diasumsikan telah diberikan.

| Area | Aturan awal | Dampak |
|---|---|---|
| Sumber ganda | `REQUIRE_REVIEW` | Nilai terakhir tidak otomatis dianggap paling benar; konflik ditahan untuk keputusan |
| Sumber otoritatif | `AUTHORITATIVE_SOURCE` hanya jika ditetapkan eksplisit | Wajib ID tab sumber; service nantinya memeriksa tenant, binding, dan status persetujuan |
| Record tidak muncul lagi | `KEEP` | Tidak dihapus atau dinonaktifkan hanya karena tidak ada dalam Sheet terbaru |
| Penonaktifan | `EXPLICIT_REVIEW` | Tindakan khusus dengan alasan, audit, dan pemeriksaan dampak referensi |
| Perubahan business key | `EXPLICIT_MIGRATION` | Bukan update biasa; perlu mapping key lama-baru dan pemeriksaan konflik |
| Penghapusan record dirujuk | `RESTRICT` | Tidak boleh menghasilkan transaksi yatim |
| Apply | `ATOMIC_BATCH` | Semua perubahan dalam satu batch/tab berhasil bersama atau rollback bersama |
| Pertanyaan wajib | `BLOCK_APPLY` | Tidak bisa dilewati melalui partial load atau request langsung |
| AI review | `REQUIRED_FOR_ALLOWED_FIELDS` | Field yang diizinkan harus mempunyai bukti review lengkap; error/budget habis tidak menjadi hasil bersih |
| Masa berlaku | Awal inklusif, akhir eksklusif; overlap ditolak | Opsional per master; aturan interval harus divalidasi pada record oleh runtime berikutnya |

Sumber otoritatif tidak melewati DQ, konflik revision, mandatory questions, maupun approval. Otoritas untuk satu master tidak menjadi otoritas global. Partial load belum didukung kontrak tahap ini. Policy tidak mengubah nilai Google Sheet secara langsung.

## Contoh penerapan

| Dataset | Jenis dan key | Perilaku |
|---|---|---|
| Produk | MASTER, kode produk bertipe text | Kode sama: usulkan update atribut; kode baru: usulkan insert; nama mirip bukan alasan merge otomatis |
| Karyawan | MASTER, kode karyawan | UUID stabil; perubahan nama tidak mengganti identitas; field personal mengikuti izin pemrosesan AI |
| UOM | MASTER, kode satuan | Alias `KG`/`kg` hanya setelah disetujui; `kg`/`g` memerlukan konversi eksplisit |
| Struktur gaji | MASTER dengan grade dan versi/masa berlaku | Perubahan nominal membuat versi periode yang sesuai; tidak menimpa histori transaksi gaji |
| Penjualan/penilaian | NON_MASTER, key kejadian yang disetujui | Simpan nilai fakta saat kejadian dan referensi UUID master; perubahan master tidak menghitung ulang histori secara implisit |

Key di tabel adalah contoh, bukan aturan global yang otomatis dipasang. Composite key dan schema masa berlaku ditetapkan saat definisi master direview di BE-03/BE-12.

## Kontrak policy v1.0

Schema berada di [data_policy.py](../app/schemas/data_policy.py). Contoh valid untuk master:

```json
{
  "schema_version": "1.0",
  "classification_scope": "SHEET",
  "dataset_kind": "MASTER",
  "master": {
    "new_record_policy": "PROPOSE_INSERT",
    "source_conflict_policy": "REQUIRE_REVIEW",
    "authoritative_source_sheet_id": null,
    "missing_record_policy": "KEEP",
    "deactivation_policy": "EXPLICIT_REVIEW",
    "business_key_change_policy": "EXPLICIT_MIGRATION",
    "delete_referenced_policy": "RESTRICT",
    "effective_dating": null
  },
  "apply_mode": "ATOMIC_BATCH",
  "mandatory_question_policy": "BLOCK_APPLY",
  "ai_review_policy": "REQUIRED_FOR_ALLOWED_FIELDS"
}
```

Untuk NON_MASTER, kirim `dataset_kind: "NON_MASTER"` dan `master: null`. Binding ke master yang dirujuk merupakan kontrak relasi terpisah pada BE-08. Schema menolak policy master pada NON_MASTER, master tanpa policy, sumber otoritatif yang tidak cocok dengan mode konflik, field ekstra, partial apply, skip AI saat error, serta kolom awal/akhir masa berlaku yang sama.

Kontrak ini belum menjadi body endpoint aktif. Jangan menambahkan field tersebut ke `ETLConfiguration` atau `SourceCreate` yang sekarang; keduanya tetap memakai kontrak pada API Reference. Tidak ada migrasi database pada BE-01.

## Lifecycle import dan role

Kontrak transisi berada di [import_workflow.py](../app/domain/import_workflow.py). Tabel berikut adalah lifecycle batch baru, bukan perubahan status `Job` atau `Configuration` yang sudah berjalan.

| Status awal | Aksi | Status hasil | Pelaksana |
|---|---|---|---|
| CLASSIFICATION_REQUIRED | CLASSIFY | MAPPING_REQUIRED | Editor |
| MAPPING_REQUIRED | SUBMIT_MAPPING | VALIDATING | Editor |
| VALIDATING | START_AI | AI_REVIEWING | Worker |
| VALIDATING / AI_REVIEWING | REQUEST_INPUT | NEEDS_INPUT | Worker |
| NEEDS_INPUT | RESUME | VALIDATING | Editor |
| AI_REVIEWING | FINISH_REVIEW | READY_FOR_APPROVAL | Worker |
| READY_FOR_APPROVAL | APPROVE | APPROVED | Approver |
| READY_FOR_APPROVAL | REJECT | NEEDS_INPUT | Approver |
| APPROVED | APPLY | APPLYING | Editor |
| APPLYING | COMPLETE | SUCCEEDED | Worker |
| VALIDATING / AI_REVIEWING / APPLYING | FAIL | FAILED | Worker |
| VALIDATING / AI_REVIEWING / NEEDS_INPUT / READY_FOR_APPROVAL / APPROVED | INVALIDATE | STALE_REVIEW | Worker |
| FAILED / STALE_REVIEW | REVALIDATE | VALIDATING | Editor |
| Selain APPLYING / SUCCEEDED / CANCELLED | CANCEL | CANCELLED | Editor |

Editor: PLATFORM_ADMIN, SOURCE_OWNER, DATA_STEWARD. Approver: PLATFORM_ADMIN, TECHNICAL_APPROVER. ANALYST/VIEWER tidak dapat mengubah lifecycle. Worker bukan role API dan konteks internalnya tidak boleh diterima dari request pengguna. Hak baca objek/field akan ditegakkan oleh endpoint tenant-scoped pada tahap berikutnya.

Fungsi transisi hanya memeriksa role dan jalur status. Service BE-05 dan seterusnya **tetap wajib** memeriksa tenant, ownership, revision, klasifikasi/binding, snapshot/master/policy evidence, coverage AI, pertanyaan wajib, approver terpisah, dan lock transaksi. Fungsi ini sendiri tidak membuktikan batch aman di-apply. Retry dari FAILED/STALE_REVIEW wajib mengulang validasi prasyarat; bila klasifikasi atau mapping belum sesuai, service harus menahannya. Tidak ada transisi langsung NEEDS_INPUT → APPROVED/APPLYING.

SUCCEEDED dan CANCELLED bersifat terminal. Input baru setelah terminal membuat batch baru. Ketika APPLYING sudah memegang lock, perubahan evidence ditangani pemeriksaan transaksi dan rollback/failure; cancel tidak memotong commit separuh jalan.

## Handoff implementasi berikutnya

- BE-02: simpan klasifikasi tab, revision, actor/time, API baca/simpan, dan gate klasifikasi; binding master menyusul BE-03.
- BE-03: simpan policy pada definisi master approved; validasi sumber otoritatif terhadap tenant dan binding nyata.
- BE-05–BE-11: hubungkan lifecycle ke model, job, snapshot, pertanyaan, evidence, approval, dan apply atomik.
- BE-12: implementasikan pemeriksaan periode pada data record serta konversi satuan; deklarasi schema saja belum menjalankan aturan tersebut.

Tes kontrak: [test_data_policy.py](../tests/test_data_policy.py). Pengujian tahap BE-01 bersama kontrak API menghasilkan **11 tes lulus**; ini pengujian terarah, bukan klaim menjalankan ulang seluruh suite. Ruff dan pemeriksaan API Reference juga lulus. Pada penyelesaian BE-01 terdapat 89 operasi aktif; BE-02 menambahkan dua operasi klasifikasi menjadi 91. Endpoint policy master/import penuh belum tersedia.

Untuk mengulangi pemeriksaan dari root backend:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_data_policy.py tests/test_api_contract.py -q
.\venv\Scripts\python.exe -m ruff check app/schemas/data_policy.py app/domain/import_workflow.py tests/test_data_policy.py
.\venv\Scripts\python.exe scripts/export_api_reference.py --check
```
