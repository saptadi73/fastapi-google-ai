# Lima contoh Excel untuk analitik dan action plan

Semua data, target, harga, bobot dan hasil adalah fiktif. Gunakan sebagai acuan struktur dan evaluasi, bukan keputusan bisnis final.

Unduh paket melalui **Bantuan > Contoh Excel untuk analitik dan action plan** atau **Panduan lengkap > Contoh Excel**.

| Contoh | File Excel | Isi | Batas interpretasi |
| --- | --- | --- | --- |
| Data keluhan pelanggan | [Unduh](https://google.kanjabung.web.id/examples/analytics/01_Keluhan_Pelanggan.xlsx) | Keluhan anonim, SLA respons, status penyelesaian dan rekap produk/periode. | Keluhan berulang bukan akar penyebab pasti. Pisahkan keluhan OPEN dari RESOLVED; jangan menghitung detail dan rekap bersama. |
| Data sebaran marketing ATL/BTL | [Unduh](https://google.kanjabung.web.id/examples/analytics/02_Marketing_ATL_BTL.xlsx) | Campaign, channel, area, budget, spend, leads, biaya dan atribusi. | Reach lintas channel dapat overlap. ATL tidak teratribusi memakai NULL, bukan nol; CPL/ROAS gabungan bukan rata-rata rasio dan bukan bukti efek kausal. |
| Data kepuasan pelanggan berbasis produk | [Unduh](https://google.kanjabung.web.id/examples/analytics/03_Kepuasan_Pelanggan_Produk.xlsx) | Survei anonim 1-5, respons valid/tidak lengkap, penyebut CSAT dan rekap produk. | CSAT memakai skor 4/5 dibagi respons valid, bukan NPS. Sampel kecil opt-in tidak memberi klaim representatif atau confidence statistik otomatis. |
| Data competitiveness harga dan layanan | [Unduh](https://google.kanjabung.web.id/examples/analytics/04_Competitiveness_Harga_Layanan.xlsx) | Harga kemasan dinormalisasi per liter, waktu observasi dan skor produk/layanan/nilai. | Produk, ukuran, promo, outlet, area dan waktu harus sebanding. Harga titik observasi berbeda dari skor survei periode; skor/bobot contoh bukan ranking pasar nyata. |
| Data plan, goal dan pencapaian KPI | [Unduh](https://google.kanjabung.web.id/examples/analytics/05_Plan_Goal_Pencapaian_KPI.xlsx) | Goal, indikator, target, bukti pengukuran, arah KPI, gap dan evaluasi tindakan. | HIGHER dan LOWER memakai rumus berbeda; IDR, kasus, jam dan skor tidak boleh dijumlahkan bersama. Sampel 3 pengukuran hanya demonstrasi. |

## Cara memakai

1. Unduh Excel, baca BACA_DULU, Kamus_Data dan Rencana_ETL. Buat salinan untuk data nyata; jangan menimpa sumber production aktif dengan data contoh.
2. Upload file ke Google Drive, buka/konversi sebagai Google Sheets. Periksa formula, format teks ISO, jumlah record dan nilai sebelum onboarding.
3. Gunakan header baris 1 dan data baris 2. Tab petunjuk Dikecualikan. Master_* masuk alur Registry master; master identik antar-file dimuat sekali saja.
4. Temukan tab, Profiling ulang dan klasifikasi. Mapping JSON di ZIP merupakan saran draft, bukan artifact approved. Terapkan tipe, DQ, master/taxonomy, key, metrik dan akses sesuai proses review aplikasi.
5. Tanggal contoh adalah teks ISO: parse_date_id, TEXT, %Y-%m-%d. Timestamp sudah ber-offset +07:00: timestamptz. Rasio memakai 0..1, skor 1..5 dan uang IDR, bukan teks berisi unit.
6. Rekap/rasio utama memakai formula tertaut ke raw/target dengan cache. Recalculasi setelah impor/edit, lalu periksa periode, key, penyebut dan jumlah record sebelum load. CSV berisi nilai contoh, tanpa formula; jangan memakai CSV lama setelah raw berubah.
7. Review dan approval berbeda pembuat; deploy, sync, validasi record dan izin katalog memakai akun pembaca sebenarnya. Join hanya melalui relasi yang disetujui.
8. Action_Plan membekukan baseline sesuai record/periode bukti. Verifikasi hipotesis, metrik/target, owner, tenggat, sampel dan hasil follow-up; jangan mengklaim tindakan sudah berhasil dari data yang masih kosong.

## Prinsip evaluasi

Formula_Analitik dan Aturan_Action_Plan adalah tab kontrol, Dikecualikan dari ETL. Impor melalui API analytics-rules/import-sheet setelah produk datanya aktif. JSON rules/ di ZIP memuat produk, metrik, dimension dan periode contoh. Lihat [panduan aturan dan formula](PANDUAN_ATURAN_ANALITIK.md) untuk preview, approval dan evaluate. Evaluasi memberi usulan PROPOSED dengan bukti; tindakan bisnis tetap diverifikasi manusia.

Jangan menjumlahkan detail dan rekap bersama, reach antar-channel, persen, nilai KPI berbeda satuan atau beberapa revisi dari record yang sama. Jangan AVG rasio tanpa bobot penyebut yang benar. Skor kepuasan tidak otomatis menjadi NPS; harga kemasan berbeda harus dinormalisasi. Sampel kecil/opt-in tidak membuktikan representasi populasi atau efek kausal tindakan.

Data periodik memuat batas awal/akhir; event/survei memuat waktu bisnis; collected_at/data_as_of_at memberikan konteks pengambilan/kondisi data. Sel kosong berarti belum terukur/tidak berlaku, bukan nol.

## Pemeliharaan

Jalankan `python scripts/build_analytics_examples.py --frontend-root D:/projek/vue-googlesheet-ai`; opsi `--check` memastikan workbook, CSV, mapping, knowledge base dan helper tetap sinkron.
