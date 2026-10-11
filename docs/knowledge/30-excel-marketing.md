---
id: contoh-excel-marketing
title: "Contoh Excel - Data sebaran marketing ATL/BTL"
summary: "Campaign, channel, area, budget, spend, leads, biaya dan atribusi."
routes: ["/guide", "/workspace"]
audiences: ["*"]
source: docs/CONTOH_DATA_ANALITIK.md
---
SELURUH DATA FIKTIF untuk latihan; target/bobot bukan rekomendasi bisnis final.
Campaign, channel, area, budget, spend, leads, biaya dan atribusi.

| Tab | Grain | Key | Record contoh |
| --- | --- | --- | --- |
| Marketing_Data | satu baris per campaign channel area produk periode | marketing_record_id | 16 |
| Action_Plan | satu baris per tindakan yang merujuk record temuan | action_id | 1 |

Unduh melalui Bantuan > Contoh Excel untuk analitik dan action plan atau /guide#contoh-excel.
File: 02_Marketing_ATL_BTL.xlsx. BACA_DULU, Kamus_Data dan Rencana_ETL adalah petunjuk: Dikecualikan dari ETL.
Master bersama dimuat sekali ke Registry master, lalu binding dipakai ulang. Data contoh memiliki kode anonim, tanggal teks ISO dan timestamp ber-offset; review sensitivitas data nyata.
Tanggal: date + parse_date_id + TEXT + %Y-%m-%d. Timestamp: timestamptz. Key contoh unik, saran UPSERT. Metrik/rule/referensi/akses wajib direview; contoh mapping JSON bukan konfigurasi yang otomatis disetujui.
Rasio/rekap utama memakai formula tertaut dan cache. Setelah raw/target diubah atau ditambah, recalculasi di Excel/Sheets dan validasi penyebut, cakupan dan key sebelum memakainya. CSV berisi nilai hasil, bukan formula.
Waktu kejadian/pengukuran dan period_start/end berbeda dari collected_at/data_as_of_at. Jangan mengganti periode bisnis dengan tanggal sync.
Action_Plan merujuk source_sheet/source_record_id, periode, baseline, owner dan tenggat. Cause_status UNVERIFIED: hipotesis perlu bukti. Followup_value kosong/NOT_EVALUATED bukan hasil 0.
Action plan bukan engine penetapan tindakan otomatis. Verifikasi sampel/metode/causal evidence dan target dengan pemilik bisnis sebelum dijalankan.
Batas interpretasi: Reach lintas channel dapat overlap. ATL tidak teratribusi memakai NULL, bukan nol; CPL/ROAS gabungan bukan rata-rata rasio dan bukan bukti efek kausal.
Pertanyaan contoh: Berapa biaya marketing menurut channel dan area periode Januari 2026? Bandingkan qualified leads BTL pada attribution model yang sama.
