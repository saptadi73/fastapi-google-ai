# Aturan action plan dan formula dari Google Sheets

Lima template Excel memuat `Formula_Analitik` dan `Aturan_Action_Plan`. Dua tab ini merupakan kontrol analitik: pilih **Dikecualikan dari ETL** pada discovery. Data/rekap tetap dimuat lewat ETL seperti biasa. `Action_Plan` adalah contoh catatan tindak lanjut manusia, berbeda dari tab aturan pemicu.

Backend menerima tab kontrol melalui API, menyimpan draft immutable, menyediakan preview, menjalankan validasi pengelola pada owner workflow (reviewer berbeda hanya jika mode legacy aktif), kemudian menghitung formula dan usulan tindakan dari metrik produk yang sudah aktif. Saat ini impor, persetujuan dan evaluasi aturan menggunakan API; wizard ETL dan chat AI belum menjalankan alur ini secara otomatis. Helper menyediakan petunjuk dan template.

## Header tab kontrol

| Tab | Kolom berurutan | Cara mengisi |
| --- | --- | --- |
| Formula_Analitik | formula_code, expression, output_unit, description | Kode huruf kecil/angka/underscore, expression tanpa awalan `=`, satuan dan penjelasan bisnis. Maksimal 20 formula. |
| Aturan_Action_Plan | rule_code, formula_code, operator, threshold, threshold_upper, action_description, owner_team_code, priority, due_days | Kode unik, referensi formula, pembanding, ambang angka, usulan tindakan, tim penanggung jawab, LOW/MEDIUM/HIGH dan tenggat 1–365 hari. Maksimal 50 aturan. |

Header tidak boleh diganti, kosong, digabung atau ditambah. Sel teks di-trim saat impor. `threshold_upper` kosong kecuali operator `between`. Owner team adalah label rencana: tidak mengirim notifikasi atau memberi hak akses kepada tim tersebut.

Formula mendukung kode metrik yang dipilih dalam query, angka desimal, `+ - * /` dan tanda kurung. Formula dapat memakai formula sebelumnya dalam urutan tab. Kode tidak dikenal, dependency maju/siklus, fungsi, atribut Python, script dan SQL ditolak. Rumus Excel seperti SUMIFS tidak digunakan di tab kontrol; gunakan agregasi metrik semantic yang sudah direview. Perhitungan memakai Decimal presisi 28 digit; nilai numerik dikirim sebagai string untuk mempertahankan presisi. Unit adalah metadata yang wajib diverifikasi reviewer, bukan pemeriksaan dimensi fisik otomatis.

| Contoh | Expression | Kondisi dan makna |
| --- | --- | --- |
| Keluhan | m_response_breach_count_sum / m_complaint_count_sum | gt 0.10: usulkan review SLA jika pelanggaran >10%. |
| Marketing BTL | m_spend_idr_sum / m_qualified_leads_count_sum | gt 150000: review biaya per qualified lead. Filter BTL dan kelompok atribusi yang sama. |
| Kepuasan | m_satisfied_count_sum / m_valid_response_count_sum | lt 0.50: review bila CSAT <50%; validasi sampel dan metode. |
| Competitiveness | m_weighted_score_avg | lt 3.5: review skor 1–5; pisahkan brand, area dan versi survei. |
| KPI pendapatan | m_revenue_actual_value / m_revenue_target_value | gt 0.50: review pipeline ketika capaian >50%, belum berarti target tercapai. |

Untuk KPI LOWER_IS_BETTER, misalnya waktu respons, arah rumus perlu dibalik sesuai definisi bisnis. `RATIO` memakai 0..1: 50% = **0.50**, bukan 50. `gt` berarti lebih besar, `gte` termasuk sama; `lt`, `lte`, `eq`, `between` juga tersedia. between mencakup kedua batas. Semua aturan yang cocok menghasilkan usulan masing-masing; belum ada penyelesaian otomatis konflik antar-aturan. Tim reviewer harus menghindari kondisi yang bertentangan.

## Alur API

Gunakan Bearer token pengguna. Semua ID dan kode harus berasal dari tenant dan produk yang boleh dibaca akun tersebut. SOURCE_OWNER/DATA_STEWARD/PLATFORM_ADMIN membuat draft; approver konfigurasi sumber yang ditunjuk menyetujui dan harus berbeda dari pembuat. Izin SOURCE, DATA_PRODUCT, kolom dan row scope tetap berlaku pada preview/evaluasi.

1. Konversi Excel menjadi Google Sheets. Muat dan review produk data utama beserta metriknya sampai ACTIVE. Tandai tab kontrol Dikecualikan dari ETL. Periksa kode metrik di katalog: jika diubah, sesuaikan formula.
2. Kirim `POST /api/v1/analytics-rules/import-sheet` dengan `source_id`, `name`, `product_code`, `query`. Backend membaca kedua tab dari sumber terdaftar yang sama dengan produk. Payload query lengkap tiap contoh terdapat pada BACA_DULU dan ZIP `rules/<topik>.json`. File JSON tersebut juga dapat dikirim ke `POST /api/v1/analytics-rules` untuk membuat draft tanpa membaca tab kontrol.
3. Simpan `id` dan `review_hash` dari respons. `GET /api/v1/analytics-rules/{id}` mengembalikan draft beserta definition, status dan hash. `POST .../{id}/preview` menjalankan query dan formula sebagai PREVIEW sebelum approval.
4. Reviewer memeriksa periode, grain/dimension, metrik, unit, arah KPI, sampel, aturan, target, tim, tenggat dan hasil preview. Kirim `POST .../{id}/decision` dengan `expected_hash`, `decision: APPROVE` (atau REJECT) dan `reason`. Approval terikat pada formula, aturan, query dan kontrak semantic yang diperiksa. Reviewer dapat menghentikan aturan APPROVED melalui endpoint yang sama dengan decision REVOKE dan alasan; status REVOKED menolak evaluasi berikutnya.
5. `POST .../{id}/evaluate` mengevaluasi aturan APPROVED menggunakan data product saat ini. Hasil memuat `query`, metadata versi semantic/freshness/cache, dimension, evidence_metrics, hasil formula, blocker serta action_plans PROPOSED. Tenggat dihitung dari tanggal evaluasi UTC ditambah due_days. Audit menyimpan aktor, hash aturan/hasil, metadata query dan jumlah usulan.
6. Jika formula, aturan, periode/query atau semantic berubah, impor/buat draft baru dan minta approval ulang. Draft dan aturan approved tidak diedit langsung. Impor dari Sheet memeriksa hash kedua tab lagi saat approval dan setiap evaluasi. Draft JSON tidak terhubung kembali ke Sheet. Perubahan data bisnis melalui sync dapat memperbarui angka pada aturan approved; perubahan angka bisnis bukan otomatis perubahan definisi aturan. Query mengikuti cache operasional dan metadata cached/freshness_version tersedia.

Contoh payload impor (ganti source_id dan kode produk sesuai katalog):

```json
{
  "source_id": "11111111-2222-4333-8444-555555555555",
  "name": "Review CSAT Januari 2026",
  "product_code": "demo_kepuasan_csat_rekap",
  "query": {
    "metrics": ["m_satisfied_count_sum", "m_valid_response_count_sum"],
    "dimensions": ["product_code", "area_code", "survey_version"],
    "filters": [{"field": "period_start", "operator": "between", "value": ["2026-01-01", "2026-01-31"]}],
    "limit": 1000
  }
}
```

Query wajib memiliki periode waktu eksplisit `between`. Pilih satu produk tanpa join, sort atau offset; kelompokkan pada grain analitik yang benar. Jangan mencampur unit, versi survei, atribusi marketing, detail dengan rekap, atau menggunakan AVG rasio untuk agregasi gabungan. Formula rasio memakai pembilang/penyebut yang sudah diagregasi. Template KPI membatasi satu indikator dan satu plan per kelompok agar MAX tidak menyembunyikan beberapa target.

## Nilai kosong, kegagalan dan batas hasil

| Respons / blocker | Penyebab | Tindakan |
| --- | --- | --- |
| ANALYTICS_RULES_INVALID / VALIDATION_ERROR | Header, formula, kode, metric numerik atau bounds tidak sesuai. | Perbaiki mengikuti template dan kode semantic, kemudian impor ulang. |
| ANALYTICS_PERIOD_REQUIRED | Periode belum eksplisit atau batas terbalik. | Tambahkan between awal/akhir pada dimension waktu yang sah. |
| ANALYTICS_SELF_APPROVAL | Pembuat mencoba menyetujui draft sendiri. | Reviewer konfigurasi sumber yang berbeda memeriksa dan memutuskan. |
| ANALYTICS_APPROVAL_REQUIRED | Aturan masih DRAFT, REJECTED atau REVOKED. | Preview dan minta approval; draft ditolak/dicabut perlu dibuat ulang. |
| ANALYTICS_RULES_STALE | Semantic/tab kontrol berubah, sumber paused/unlinked atau hash/status tidak cocok. | Aktifkan sumber yang sah; impor/buat draft dan review ulang. |
| ANALYTICS_RESULT_TRUNCATED | Jumlah kelompok mencapai batas query/server; hasil mungkin terpotong. | Persempit periode/dimension dan review draft baru; tidak ada tindakan dari hasil parsial. |
| MISSING_VALUE / ZERO_DENOMINATOR | Metrik/dependency NULL atau penyebut nol. | Periksa kelengkapan dan denominator; formula bernilai NULL dan aturan terkait tidak memicu tindakan. |
| NON_NUMERIC_VALUE / NUMERIC_OUT_OF_RANGE | Nilai bukan angka terbatas atau hasil terlalu besar. | Koreksi tipe/metrik atau skala; aturan terkait tidak memicu tindakan. |

Tidak ada record query menghasilkan rows kosong dan tidak ada usulan. Backend tidak menjalankan tindakan bisnis, tidak menulis Google Sheets, tidak membuat klaim sebab-akibat, dan tidak menetapkan signifikansi statistik. Usulan harus diperiksa pemilik bisnis sebelum dijalankan. Pastikan definisi dan bukti data cukup; cocoknya kondisi numerik saja tidak membuktikan tindakan itu akan berhasil.
