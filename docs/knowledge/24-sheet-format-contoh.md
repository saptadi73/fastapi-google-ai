---
id: format-google-sheet-contoh
title: Format Google Sheet ideal - Contoh Google Sheet KPI dan action plan serta checklist
summary: "Rekomendasi data analitik modern, akurat dan presisi: Contoh Google Sheet KPI dan action plan serta checklist."
routes: ["/workspace", "/dashboard", "/chat", "/guide"]
audiences: ["*"]
source: docs/PANDUAN_FORMAT_GOOGLE_SHEET.md
---
Panduan berdasarkan kemampuan aplikasi Google Sheet AI ini. Tujuannya: data dapat diproses, konsisten lintas sumber dan periode, memiliki ketelitian yang sesuai pengukuran, serta mendukung keputusan yang dapat ditelusuri. Setiap data periodik/berbasis waktu wajib memiliki konteks waktu yang eksplisit.

## 12. Contoh tabel siap analitik dan tindak lanjut

Contoh fiktif berikut menunjukkan grain dan referensi. Angka/periode tidak menjadi default bisnis. Tanggal dicontohkan sebagai teks ISO agar makna jelas; jika Sheet memakai tanggal native, mapping memakai serial Google Sheets yang dinyatakan.

| unit_code | unit_name | is_active |
| --- | --- | --- |
| UNIT-01 | Layanan Anggota | TRUE |
| UNIT-02 | Operasional | TRUE |

Master_Unit: key unit_code unik. Master_Indikator sebaiknya memuat indicator_code, indicator_name, measurement_unit, direction, definition dan method_version. Hindari memakai satu header unit_code untuk sekaligus kode departemen dan satuan pengukuran.

| kpi_record_id | unit_code | indicator_code | period_start | period_end | target_value | actual_value | gap_value | collected_at |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KPI-202601-U01-RSP | UNIT-01 | RESPON_SELESAI | 2026-01-01 | 2026-01-31 | 100 | 90 | 10 | 2026-02-02T09:00:00+07:00 |
| KPI-202602-U01-RSP | UNIT-01 | RESPON_SELESAI | 2026-02-01 | 2026-02-28 | 100 | 96 | 4 | 2026-03-02T09:00:00+07:00 |

KPI_Layanan_Bulanan: satu baris per unit + indikator + periode, direction HIGHER_IS_BETTER, satuan kasus, gap = target - actual. Tambahkan measurement_unit, denominator/sample_count bila diperlukan, data_as_of_at dan reporting_status. Review formula gap, tanggal, key dan UPSERT; jangan memakai contoh ini untuk indikator LOWER_IS_BETTER tanpa mengubah definisi.

| action_id | kpi_record_id | owner_code | action_description | due_date | action_status | expected_outcome |
| --- | --- | --- | --- | --- | --- | --- |
| ACT-001 | KPI-202601-U01-RSP | TEAM-LAYANAN | Tinjau antrean dan jadwal petugas berdasarkan bukti | 2026-02-15 | PLANNED | Minimal 95 kasus selesai pada Februari |

Action_Plan: satu tindakan per action_id; KPI/owner harus memiliki rujukan yang benar. Tambahkan suspected_cause, cause_status, evidence_ref, completed_at dan periode follow-up. Actual 96 pada Februari dapat memenuhi target tindakan 95, tetapi belum membuktikan bahwa tindakan merupakan penyebab perbaikan.

Contoh pertanyaan konsumsi: Tampilkan target dan realisasi RESPON_SELESAI per unit untuk Januari 2026; Bandingkan realisasi Januari dan Februari dengan definisi/periode yang sama; Tampilkan tindakan PLANNED dengan due_date sebelum 2026-02-15. Query memakai metrik/dimensi yang telah direview dan field yang diizinkan, bukan menghitung expression bebas.

## 13. Checklist siap onboarding dan siap keputusan

- Nama file/tab jelas, nama produk unik, deskripsi serta grain tertulis, pemilik dan jadwal diketahui.
- Header satu tingkat, terisi/unik, tidak merged, tidak ada subtotal/baris laporan dan data di luar header.
- Key stabil/unik/tidak NULL; master/taxonomy/referensi sudah disetujui dan record rujukan benar-benar tersedia.
- Data periodik memiliki tanggal/waktu pengukuran atau periode start/end wajib, serta collected_at/data_as_of_at sesuai kebutuhan; timezone, cutoff dan status final jelas.
- Angka, unit, presisi, null vs 0, direction, formula target/realisasi/gap dan denominator disepakati. Metode/sampel/definisi terdokumentasi dan periode sebanding.
- DQ menguji nilai nyata; tidak ada blocker; baris tidak dimuat dan batas cakupan dilaporkan; hasil ETL direkonsiliasi dengan sumber.
- Strategi load mencegah snapshot/revisi dihitung ganda; mapping/schema dan gate rilis mendapat review/approval yang sesuai.
- Metrik dan dimensi tersedia, join disetujui/cardinality benar, produk ACTIVE dan batch SUCCEEDED; akun pembaca lolos allowed_roles dan policy.
- Action plan menunjuk bukti/periodenya, tindakan terukur, owner/tenggat, status, baseline serta periode ukur ulang; hipotesis belum diperlakukan sebagai akar penyebab pasti.
- Pemilik bisnis memverifikasi hasil analisis, keterlambatan data dan kualitas bukti sebelum mengambil keputusan. Data yang rapi meningkatkan ketepatan; tidak menjamin semua kesimpulan otomatis benar.
