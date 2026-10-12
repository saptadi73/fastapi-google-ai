---
id: contoh-excel-kpi
title: "Contoh Excel - Data plan, goal dan pencapaian KPI"
summary: "Goal, indikator, target, bukti pengukuran, arah KPI, gap dan evaluasi tindakan."
routes: ["/guide", "/workspace"]
audiences: ["*"]
source: docs/CONTOH_DATA_ANALITIK.md
---
SELURUH DATA FIKTIF untuk latihan; target/bobot bukan rekomendasi bisnis final.
Goal, indikator, target, bukti pengukuran, arah KPI, gap dan evaluasi tindakan.

| Tab | Grain | Key | Record contoh |
| --- | --- | --- | --- |
| KPI_Plan | satu baris per unit indikator periode versi target aktif | plan_id | 8 |
| KPI_Measurement | satu baris per bukti pengukuran indikator | measurement_id | 24 |
| KPI_Result | satu baris per plan indikator periode | kpi_result_id | 8 |
| Action_Plan | satu baris per tindakan yang merujuk record temuan | action_id | 1 |

Unduh melalui Bantuan > Contoh Excel untuk analitik dan action plan atau /guide#contoh-excel.
File: 05_Plan_Goal_Pencapaian_KPI.xlsx. BACA_DULU, Kamus_Data dan Rencana_ETL adalah petunjuk: Dikecualikan dari ETL.
Master bersama dimuat sekali ke Registry master, lalu binding dipakai ulang. Data contoh memiliki kode anonim, tanggal teks ISO dan timestamp ber-offset; review sensitivitas data nyata.
Tanggal: date + parse_date_id + TEXT + %Y-%m-%d. Timestamp: timestamptz. Key contoh unik, saran UPSERT. Metrik/rule/referensi/akses wajib direview; contoh mapping JSON bukan konfigurasi yang otomatis disetujui.
Rasio/rekap utama memakai formula tertaut dan cache. Setelah raw/target diubah atau ditambah, recalculasi di Excel/Sheets dan validasi penyebut, cakupan dan key sebelum memakainya. CSV berisi nilai hasil, bukan formula.
Waktu kejadian/pengukuran dan period_start/end berbeda dari collected_at/data_as_of_at. Jangan mengganti periode bisnis dengan tanggal sync.
Action_Plan merujuk source_sheet/source_record_id, periode, baseline, owner dan tenggat. Cause_status UNVERIFIED: hipotesis perlu bukti. Followup_value kosong/NOT_EVALUATED bukan hasil 0.
Formula_Analitik dan Aturan_Action_Plan Dikecualikan dari ETL. Backend menerima dua tab melalui POST /api/v1/analytics-rules/import-sheet: source_id, name, product_code dan query; contoh JSON tersedia dalam ZIP rules/. Preview, approval reviewer berbeda dengan expected_hash, lalu evaluate menghasilkan usulan PROPOSED dengan bukti angka. Lihat PANDUAN_ATURAN_ANALITIK.md.
50% = 0.50 untuk RATIO. Formula memakai kode metrik dan + - * /, bukan =Excel atau SQL. Periode query wajib eksplisit. Formula NULL/penyebut nol memberikan blocker, bukan tindakan. Perubahan tab kontrol/semantic memerlukan draft dan review ulang. Verifikasi sampel, hipotesis dan target sebelum menjalankan tindakan bisnis.
Batas interpretasi: HIGHER dan LOWER memakai rumus berbeda; IDR, kasus, jam dan skor tidak boleh dijumlahkan bersama. Sampel 3 pengukuran hanya demonstrasi.
Pertanyaan contoh: Indikator mana yang belum mencapai target Januari 2026? Apa bukti pengukuran dan rencana tindak lanjut setiap plan?
