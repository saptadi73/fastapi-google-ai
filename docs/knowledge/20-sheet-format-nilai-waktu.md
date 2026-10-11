---
id: format-google-sheet-nilai-waktu
title: Format Google Sheet ideal - Tipe, presisi, tanggal dan periode pengambilan data
summary: "Rekomendasi data analitik modern, akurat dan presisi: Tipe, presisi, tanggal dan periode pengambilan data."
routes: ["/workspace", "/etl-review/*", "/quality", "/guide"]
audiences: ["*"]
source: docs/PANDUAN_FORMAT_GOOGLE_SHEET.md
---
Panduan berdasarkan kemampuan aplikasi Google Sheet AI ini. Tujuannya: data dapat diproses, konsisten lintas sumber dan periode, memiliki ketelitian yang sesuai pengukuran, serta mendukung keputusan yang dapat ditelusuri. Setiap data periodik/berbasis waktu wajib memiliki konteks waktu yang eksplisit.

## 4. Tipe data, nilai kosong, satuan dan presisi

| Jenis nilai | Format ideal di Sheet | Mapping / perhatian |
| --- | --- | --- |
| Kode / ID | Teks, misalnya 0012 atau UNIT-01 | text/varchar; nol depan dan ID panjang harus tetap teks. |
| Jumlah kejadian | Bilangan bulat, misalnya 12 | integer/bigint; jangan campur angka dengan catatan. |
| Nilai ukur / uang | Angka asli, misalnya 1250.75 | numeric; tetapkan precision/scale, unit dan aturan pembulatan sesuai kebutuhan. |
| Persentase | Angka rasio 0.95 dengan tampilan 95% | numeric; dokumentasikan skala 0..1. Jangan campur 95, 0.95 dan teks 95%. |
| Tanggal | Tanggal native Sheets atau teks ISO 2026-01-31 | date dengan parser/format sumber yang dinyatakan. |
| Waktu lengkap | Teks ISO 2026-01-31T16:00:00+07:00 | timestamptz; deklarasikan zona sumber jika input tidak memiliki offset. |
| Boolean | TRUE/FALSE konsisten | boolean; jangan mencampur status bebas dengan flag. |
| Tidak diketahui | Sel kosong sesuai definisi bisnis | NULL bila nullable; 0 berarti hasil ukur nol, bukan tidak tersedia. |

- Pisahkan angka dan unit: value=1250.75, unit_code=KG atau amount_idr=1250.75. Hindari Rp 1.250,75/kg dalam satu field. Jika sumber memang teks angka Indonesia, gunakan parse_decimal_id dan number_locale ID; locale US hanya untuk format yang sesuai.
- Text/varchar mendapat trim otomatis sebelum transformasi, DQ dan AI. Spasi tepi dibuang; spasi tengah dan nol depan tetap. Spasi saja menjadi kosong/NULL; kolom wajib tetap error. Normalize_whitespace, uppercase/lowercase dan replace hanya bila aturan bisnisnya direview.
- Nilai kosong, tidak berlaku, belum diukur dan pengukuran gagal berbeda. Tambahkan measurement_status/missing_reason bila penting; jangan mengisi semuanya dengan 0 atau default sembarang. Hindari tanda - dan N/A pada kolom angka/tanggal.
- Deklarasikan presisi pengukuran, resolusi alat dan aturan pembulatan. Banyak digit tidak otomatis berarti lebih akurat. Uji round-trip nilai penting; numeric database tidak memulihkan ketelitian yang sudah hilang di sumber.
- Konversi unit harus satu dimensi, faktor tetap yang dinyatakan dan rounding/output_scale yang direview. Konversi valuta memerlukan kurs, rate_date dan sumber kurs; bukan kurs real-time otomatis. Jangan menjumlahkan nilai dari unit/mata uang berbeda.

## 5. Waktu dan periode wajib untuk data berbasis waktu

Setiap record periodik atau berbasis waktu wajib memiliki waktu/ periode bisnis yang eksplisit dan tidak NULL sesuai grain. Pisahkan waktu kejadian/pengukuran, cakupan periode dan waktu pengambilan data; waktu sync aplikasi tidak menggantikan ketiganya. Catat collected_at atau metadata pengambilan yang dapat ditelusuri untuk setiap pengambilan dataset; untuk pengukuran lapangan, waktu kejadian/pengukuran tetap disimpan di record. Jangan memakai formula NOW() volatil sebagai bukti waktu pengambilan yang tetap.

| Konteks | Kolom yang dianjurkan | Makna |
| --- | --- | --- |
| Kejadian/transaksi | event_date atau event_at | Kapan kejadian bisnis berlangsung. |
| Pengukuran/survei | measured_at atau sampled_at | Kapan kondisi benar-benar diukur/diamati. |
| Rekap periodik | period_start + period_end | Batas periode yang dicakup; tahun dan tanggal penuh. |
| Snapshot/pengambilan | data_as_of_at + collected_at | Data berlaku sampai kapan dan kapan dikumpulkan/ditarik. |
| Rencana tindak lanjut | due_date + completed_at | Tenggat dan penyelesaian; bukan periode data yang dievaluasi. |

- Untuk KPI bulanan: period_start=2026-01-01 dan period_end=2026-01-31. Waktu pengambilan contoh collected_at=2026-02-02T09:00:00+07:00. Jangan memakai 2 Februari sebagai bulan kinerja Januari.
- Untuk survei titik pantau, measured_at menunjukkan observasi lapangan; collected_at menunjukkan penerimaan data. Jika satu snapshot merepresentasikan kondisi saat tertentu, simpan data_as_of_at. Rekap tidak harus menciptakan event_date palsu.
- Sepakati batas inklusif tanggal untuk contoh periode; timestamp window harus menyatakan konvensi start/end. Uji period_start <= period_end serta tidak ada overlap/gap yang tidak disengaja lewat pemeriksaan sumber/reviewer; jangan menganggap semua aturan lintas kolom tersedia otomatis di editor DQ.
- Jangan hanya menyimpan Januari, W1, Minggu 1 atau 2026 tanpa batas periode yang diperlukan. Minggu perlu tahun, kalender minggu yang disepakati dan batas tanggal. Aplikasi tidak menebak tanggal dari label bulan/minggu dan belum mendukung analisis overlap periode otomatis.
- Tanggal native Google Sheets dibaca sebagai serial: 46023 = 2026-01-01. Gunakan parse_date_id dan Format nilai tanggal = Serial Google Sheets untuk tanggal serial utuh. Bigint/angka masuk akal saja bukan bukti tanggal. Teks tanggal memakai format TEXT dan pola yang sesuai, misalnya %Y-%m-%d.
- Untuk waktu lengkap, gunakan teks ISO dengan offset atau deklarasi source_timezone yang jelas, misalnya Asia/Jakarta. Jangan kirim serial tanggal-waktu pecahan sebagai date serial utuh. Nyatakan timezone organisasi dan aturan batas hari; timestamptz dinormalisasi ke UTC oleh aplikasi.
- Bedakan periode final dan belum lengkap dengan is_period_closed/reporting_status. Bandingkan periode berjalan terhadap periode setara, bukan terhadap sebulan penuh tanpa penjelasan. Cantumkan jadwal, keterlambatan dan cutoff; angka terbaru belum tentu mencakup periode lengkap.
