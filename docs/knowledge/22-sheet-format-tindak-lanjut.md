---
id: format-google-sheet-tindak-lanjut
title: Format Google Sheet ideal - Action plan berbasis bukti dan kualitas data
summary: "Rekomendasi data analitik modern, akurat dan presisi: Action plan berbasis bukti dan kualitas data."
routes: ["/workspace", "/quality", "/dashboard", "/chat", "/guide"]
audiences: ["*"]
source: docs/PANDUAN_FORMAT_GOOGLE_SHEET.md
---
Panduan berdasarkan kemampuan aplikasi Google Sheet AI ini. Tujuannya: data dapat diproses, konsisten lintas sumber dan periode, memiliki ketelitian yang sesuai pengukuran, serta mendukung keputusan yang dapat ditelusuri. Setiap data periodik/berbasis waktu wajib memiliki konteks waktu yang eksplisit.

## 8. Data yang mendukung action plan akurat

Aplikasi menyediakan ETL, katalog, query dan visualisasi dari metrik/dimensi/relasi yang disetujui. Tidak ada jaminan otomatis bahwa data menghasilkan diagnosis kausal atau tindakan yang benar. Action plan perlu bukti, definisi indikator, konteks, pemilik dan verifikasi hasil oleh manusia.

| Bagian | Kolom / isi yang dianjurkan | Tujuan |
| --- | --- | --- |
| Bukti masalah | kpi_record_id, unit_code, indicator_code, period_start, period_end | Menautkan masalah ke unit, ukuran dan periode tertentu. |
| Besaran dan konteks | target_value, actual_value, gap_value, denominator, sample_count, data_as_of_at | Menunjukkan selisih, basis perhitungan dan freshness. |
| Penyebab | suspected_cause, cause_status, evidence_ref | Bedakan hipotesis dari penyebab yang sudah diverifikasi. |
| Keputusan | action_id, action_description, priority, owner_code, due_date, expected_outcome | Tindakan terukur, penanggung jawab dan tenggat. |
| Pelaksanaan | action_status, completed_at, followup_period_start, followup_period_end | Memantau pelaksanaan dan periode ukur ulang. |
| Evaluasi | baseline_value, followup_value, verification_status, evidence_ref | Memeriksa hasil pada definisi/metode dan periode yang sebanding. |

- Satu baris Action_Plan = satu tindakan. Jika satu masalah memiliki tiga tindakan, buat tiga action_id dan referensikan kpi_record_id yang sama. Jangan menggandakan baris KPI atau mengulang realisasi lalu menjumlahkannya untuk tiap tindakan.
- Tulis hasil yang dapat diukur: Turunkan waktu respons dari 48 ke 24 jam pada periode Februari, bukan Tingkatkan layanan. Untuk efek tindakan, catat baseline, waktu pelaksanaan, ukuran sampel, intervensi lain dan hasil periode berikutnya.
- Tab Action_Plan dapat diproses sebagai NON_MASTER dengan mapping/DQ/key yang direview; ini bukan fitur task management, pengingat otomatis atau approval tindakan bisnis khusus. Join ke KPI hanya melalui relationship yang disetujui.
- Gunakan owner_code/unit_code baku; pisahkan identitas/kontak pribadi ke sumber yang aksesnya sesuai. Kolom narasi bisa mengandung PII atau instruksi tidak tepercaya; jangan menganggap semua teks aman untuk analitik.
- Jangan mengarang akar penyebab, target, status penyelesaian atau hasil ukur yang belum ada. Kesimpulan disertai periode, sumber, batas cakupan dan status final data; action plan direview pemilik bisnis sebelum dilaksanakan.

## 9. Validasi, audit dan kualitas analitik

- Pemeriksaan wajib: header terisi/unik, key unik/tidak kosong, tipe cocok, referensi/term approved, angka/satuan konsisten, dan waktu/periode tersedia untuk record periodik. Periksa record nyata, bukan hanya sampel profiling.
- Gunakan DQ not_null, unique, min/max, allowed_values, format, in_taxonomy atau max_age_days bila sesuai kemampuan editor dan tipe field. Min 0 tidak berlaku pada semua angka: koreksi/refund/gap dapat negatif jika definisinya sah.
- Aturan lintas kolom, rekonsiliasi total, overlap periode, formula KPI dan kesetaraan populasi perlu pemeriksaan tambahan di Sheet/proses review bila tidak tersedia sebagai rule terdaftar. Jangan menyisipkan SQL/expression bebas.
- Tentukan WARN, REJECT_ROW, STOP_BATCH atau REQUIRE_REVIEW sesuai risiko. Periksa temuan dan karantina; laporkan rows_extracted, rows_loaded, rows_invalid serta excluded/rejected agar angka terlihat tidak menutupi kehilangan cakupan.
- Simpan provenance seperti source_record_id, measured_at, collected_at, data_as_of_at, source_system, method_version dan revision_no sesuai kebutuhan. Jejak ETL/job aplikasi melengkapi provenance bisnis, bukan menggantikan bukti pengukuran sumber.
- Untuk angka penting, rekonsiliasi jumlah record dan agregat sebelum/sesudah ETL terhadap snapshot sumber yang sama. Uji batas desimal, tanggal, missing, duplikat dan referensi ambigu. AI mendampingi review; tidak menggantikan uji data deterministik.
- Nilai sensitif dikaburkan saat review AI. [REDACTED] bukan nilai rusak/duplikat; server membuktikan duplicate whole-row dari data asli. KEEP_ORIGINAL hanya setelah nilai sah diverifikasi, dengan alasan yang diaudit.
