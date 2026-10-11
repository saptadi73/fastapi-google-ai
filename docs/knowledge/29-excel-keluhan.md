---
id: contoh-excel-keluhan
title: "Contoh Excel - Data keluhan pelanggan"
summary: "Keluhan anonim, SLA respons, status penyelesaian dan rekap produk/periode."
routes: ["/guide", "/workspace"]
audiences: ["*"]
source: docs/CONTOH_DATA_ANALITIK.md
---
SELURUH DATA FIKTIF untuk latihan; target/bobot bukan rekomendasi bisnis final.
Keluhan anonim, SLA respons, status penyelesaian dan rekap produk/periode.

| Tab | Grain | Key | Record contoh |
| --- | --- | --- | --- |
| Keluhan_Data | satu baris per keluhan anonim | complaint_id | 32 |
| Keluhan_Rekap | satu baris per unit produk bulan | complaint_summary_id | 4 |
| Action_Plan | satu baris per tindakan yang merujuk record temuan | action_id | 1 |

Unduh melalui Bantuan > Contoh Excel untuk analitik dan action plan atau /guide#contoh-excel.
File: 01_Keluhan_Pelanggan.xlsx. BACA_DULU, Kamus_Data dan Rencana_ETL adalah petunjuk: Dikecualikan dari ETL.
Master bersama dimuat sekali ke Registry master, lalu binding dipakai ulang. Data contoh memiliki kode anonim, tanggal teks ISO dan timestamp ber-offset; review sensitivitas data nyata.
Tanggal: date + parse_date_id + TEXT + %Y-%m-%d. Timestamp: timestamptz. Key contoh unik, saran UPSERT. Metrik/rule/referensi/akses wajib direview; contoh mapping JSON bukan konfigurasi yang otomatis disetujui.
Rasio/rekap utama memakai formula tertaut dan cache. Setelah raw/target diubah atau ditambah, recalculasi di Excel/Sheets dan validasi penyebut, cakupan dan key sebelum memakainya. CSV berisi nilai hasil, bukan formula.
Waktu kejadian/pengukuran dan period_start/end berbeda dari collected_at/data_as_of_at. Jangan mengganti periode bisnis dengan tanggal sync.
Action_Plan merujuk source_sheet/source_record_id, periode, baseline, owner dan tenggat. Cause_status UNVERIFIED: hipotesis perlu bukti. Followup_value kosong/NOT_EVALUATED bukan hasil 0.
Action plan bukan engine penetapan tindakan otomatis. Verifikasi sampel/metode/causal evidence dan target dengan pemilik bisnis sebelum dijalankan.
Batas interpretasi: Keluhan berulang bukan akar penyebab pasti. Pisahkan keluhan OPEN dari RESOLVED; jangan menghitung detail dan rekap bersama.
Pertanyaan contoh: Berapa keluhan dan pelanggaran SLA per produk bulan Januari 2026? Bagaimana perubahan waktu respons antara Januari dan Februari?
