---
id: contoh-excel-kepuasan
title: "Contoh Excel - Data kepuasan pelanggan berbasis produk"
summary: "Survei anonim 1-5, respons valid/tidak lengkap, penyebut CSAT dan rekap produk."
routes: ["/guide", "/workspace"]
audiences: ["*"]
source: docs/CONTOH_DATA_ANALITIK.md
---
SELURUH DATA FIKTIF untuk latihan; target/bobot bukan rekomendasi bisnis final.
Survei anonim 1-5, respons valid/tidak lengkap, penyebut CSAT dan rekap produk.

| Tab | Grain | Key | Record contoh |
| --- | --- | --- | --- |
| Survey_Data | satu baris per respons anonim produk metode survei | response_id | 48 |
| CSAT_Rekap | satu baris per produk area versi survei periode | csat_summary_id | 4 |
| Action_Plan | satu baris per tindakan yang merujuk record temuan | action_id | 1 |

Unduh melalui Bantuan > Contoh Excel untuk analitik dan action plan atau /guide#contoh-excel.
File: 03_Kepuasan_Pelanggan_Produk.xlsx. BACA_DULU, Kamus_Data dan Rencana_ETL adalah petunjuk: Dikecualikan dari ETL.
Master bersama dimuat sekali ke Registry master, lalu binding dipakai ulang. Data contoh memiliki kode anonim, tanggal teks ISO dan timestamp ber-offset; review sensitivitas data nyata.
Tanggal: date + parse_date_id + TEXT + %Y-%m-%d. Timestamp: timestamptz. Key contoh unik, saran UPSERT. Metrik/rule/referensi/akses wajib direview; contoh mapping JSON bukan konfigurasi yang otomatis disetujui.
Rasio/rekap utama memakai formula tertaut dan cache. Setelah raw/target diubah atau ditambah, recalculasi di Excel/Sheets dan validasi penyebut, cakupan dan key sebelum memakainya. CSV berisi nilai hasil, bukan formula.
Waktu kejadian/pengukuran dan period_start/end berbeda dari collected_at/data_as_of_at. Jangan mengganti periode bisnis dengan tanggal sync.
Action_Plan merujuk source_sheet/source_record_id, periode, baseline, owner dan tenggat. Cause_status UNVERIFIED: hipotesis perlu bukti. Followup_value kosong/NOT_EVALUATED bukan hasil 0.
Formula_Analitik dan Aturan_Action_Plan Dikecualikan dari ETL. Backend menerima dua tab melalui POST /api/v1/analytics-rules/import-sheet: source_id, name, product_code dan query; contoh JSON tersedia dalam ZIP rules/. Preview, approval reviewer berbeda dengan expected_hash, lalu evaluate menghasilkan usulan PROPOSED dengan bukti angka. Lihat PANDUAN_ATURAN_ANALITIK.md.
50% = 0.50 untuk RATIO. Formula memakai kode metrik dan + - * /, bukan =Excel atau SQL. Periode query wajib eksplisit. Formula NULL/penyebut nol memberikan blocker, bukan tindakan. Perubahan tab kontrol/semantic memerlukan draft dan review ulang. Verifikasi sampel, hipotesis dan target sebelum menjalankan tindakan bisnis.
Batas interpretasi: CSAT memakai skor 4/5 dibagi respons valid, bukan NPS. Sampel kecil opt-in tidak memberi klaim representatif atau confidence statistik otomatis.
Pertanyaan contoh: Berapa respons valid dan respons puas per produk pada Januari 2026? Apakah perubahan CSAT memakai versi pertanyaan dan cakupan yang sebanding?
