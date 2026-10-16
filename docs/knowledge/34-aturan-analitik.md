---
id: aturan-analitik-action-plan
title: "Formula analitik dan aturan action plan dari Google Sheets"
summary: "Impor tab Formula_Analitik dan Aturan_Action_Plan, preview, approval dan evaluasi berbasis bukti angka."
routes: ["/guide", "/workspace"]
audiences: ["*"]
source: docs/PANDUAN_ATURAN_ANALITIK.md
---
Lima contoh Excel di Bantuan > Contoh Excel memuat Formula_Analitik dan Aturan_Action_Plan. Tandai kedua tab Dikecualikan dari ETL; data/rekap tetap NON_MASTER. Action_Plan adalah contoh catatan tindakan manusia, berbeda dari aturan pemicu. Impor, approval dan evaluasi aturan saat ini melalui API; wizard ETL/chat AI belum menjalankannya otomatis.

| Tab | Header berurutan | Isi |
| --- | --- | --- |
| Formula_Analitik | formula_code, expression, output_unit, description | Kode unik, rumus tanpa =Excel, satuan dan penjelasan. Maksimal 20. |
| Aturan_Action_Plan | rule_code, formula_code, operator, threshold, threshold_upper, action_description, owner_team_code, priority, due_days | Referensi formula, pembanding, angka ambang, tindakan, tim, LOW/MEDIUM/HIGH, tenggat 1–365 hari. Maksimal 50. |

Formula mendukung kode metrik dan formula sebelumnya, angka desimal, + - * / dan kurung. Fungsi, SQL, script, dependency maju/siklus dan kode tidak dikenal ditolak. Gunakan kode metric yang tersedia pada produk aktif. Decimal 28 digit digunakan; hasil angka dikirim sebagai string. Unit dan arah indikator perlu diverifikasi reviewer.

50% = 0.50 pada RATIO. Operator gt lebih besar; gte termasuk sama; lt, lte, eq dan between tersedia. threshold_upper hanya untuk between; kedua batas termasuk. Semua aturan yang cocok memberi usulan masing-masing, sehingga hindari aturan bertentangan.

| Contoh | Rumus | Pemicu contoh |
| --- | --- | --- |
| Keluhan | m_response_breach_count_sum / m_complaint_count_sum | gt 0.10, review SLA. |
| Marketing BTL | m_spend_idr_sum / m_qualified_leads_count_sum | gt 150000 IDR/lead; filter BTL, pisahkan atribusi. |
| Kepuasan | m_satisfied_count_sum / m_valid_response_count_sum | lt 0.50; validasi sampel. |
| Competitiveness | m_weighted_score_avg | lt 3.5 pada skala 1–5; pisahkan brand/area/versi. |
| KPI pendapatan | m_revenue_actual_value / m_revenue_target_value | gt 0.50, usulan review pipeline; bukan berarti target tercapai. |

1. Muat/review produk utama dan metrik hingga ACTIVE. Konversi Excel ke Google Sheets; dua tab kontrol Dikecualikan dari ETL. Samakan kode formula dengan metrik katalog.
2. POST /api/v1/analytics-rules/import-sheet: source_id, name, product_code, query. Produk dan tab kontrol harus dari sumber terdaftar yang sama. Contoh query ada di BACA_DULU dan ZIP rules/<topik>.json. Alternatif POST /api/v1/analytics-rules menerima JSON definition tersebut, tanpa menghubungkan Sheet.
3. Simpan id/review_hash respons. GET /api/v1/analytics-rules/{id} membaca draft. POST .../{id}/preview menghitung PREVIEW.
4. Reviewer konfigurasi sumber yang ditunjuk, berbeda pembuat: POST .../{id}/decision dengan expected_hash, decision APPROVE/REJECT, reason. Tinjau grain, periode, unit, target, sample, bukti, tim dan tenggat. Reviewer dapat menghentikan aturan APPROVED dengan decision REVOKE dan alasan ke endpoint yang sama.
5. POST .../{id}/evaluate menghasilkan formula, evidence_metrics, dimension, query, metadata semantic/freshness/cache, blocker dan action_plans PROPOSED/UNVERIFIED. Tenggat memakai tanggal evaluasi UTC + due_days. Tidak mengirim notifikasi atau menjalankan tindakan.
6. Tab kontrol/semantic/query berubah: impor/buat draft baru dan review ulang. Versi immutable. Impor Sheet memeriksa kedua tab saat approval/evaluate. Data bisnis dapat berubah setelah sync tanpa mengubah definisi aturan; metadata cached/freshness memberi konteks angka terbaru.

Query wajib filter periode between pada dimension waktu. Satu produk tanpa join, sort atau offset. Pilih grain benar: jangan campur satuan, versi survei, model atribusi atau detail+rekap. Rasio gabungan dihitung dari jumlah pembilang/penyebut, bukan AVG persen. KPI LOWER membutuhkan arah formula sesuai bisnis.

NULL/penyebut nol memberi blocker MISSING_VALUE/ZERO_DENOMINATOR; formula dan dependencynya tidak memicu tindakan. Rows kosong tidak menghasilkan usulan. Hasil mencapai batas query/server ditolak dengan ANALYTICS_RESULT_TRUNCATED. ANALYTICS_APPROVAL_REQUIRED perlu approval; ANALYTICS_SELF_APPROVAL hanya pada mode legacy; owner workflow mengizinkan validasi aturan sendiri setelah preview sukses; ANALYTICS_RULES_STALE perlu draft/review baru; ANALYTICS_PERIOD_REQUIRED perlu periode; ANALYTICS_RULES_INVALID perlu perbaikan header/kode/formula.

Akses tenant, SOURCE/DATA_PRODUCT, kolom dan row scope tetap berlaku. Usulan numerik bukan bukti akar penyebab atau keberhasilan tindakan. Owner team adalah label rencana. Panduan API lengkap: docs/PANDUAN_ATURAN_ANALITIK.md.
