# Format Google Sheet ideal untuk analitik dan action plan

<!-- Generated from docs/google-sheet-format.json by scripts/export_sheet_format_guide.py. -->

Panduan berdasarkan kemampuan aplikasi Google Sheet AI ini. Tujuannya: data dapat diproses, konsisten lintas sumber dan periode, memiliki ketelitian yang sesuai pengukuran, serta mendukung keputusan yang dapat ditelusuri. Setiap data periodik/berbasis waktu wajib memiliki konteks waktu yang eksplisit.

## 1. Nama file, tab, bisnis dan produk data

Nama harus menjelaskan subjek bisnis, cakupan dan isi dataset. Gunakan nama stabil; nama file dan tab menjadi acuan identitas, bukan pengganti deskripsi bisnis.

- Contoh file: Kinerja Layanan Pelanggan KAN Jabung 2026. Contoh tab: Keluhan_Harian, KPI_Layanan_Bulanan, Master_Unit, Master_Indikator, Action_Plan. Hindari Sheet1, Copy of, FINAL_FIX atau nama orang tanpa konteks.
- Draft manual menyarankan Nama bisnis = nama file / nama tab dan kode produk dari gabungan nama tersebut. Nama bisnis maksimal 200 karakter; kode produk huruf ASCII/angka/underscore, diawali huruf, maksimal 63 karakter. Saran bisa ditinjau/diedit; nama serupa setelah normalisasi dapat konflik.
- Nama tabel database merupakan konfigurasi terpisah: draft manual menyarankan nama dasar dari tab, lalu aplikasi menambahkan identitas tab pada tabel fisik. Mengganti nama file/tab tidak otomatis mengganti nama produk atau tabel yang sudah aktif.
- Untuk seri lintas tahun, lebih baik file bisnis stabil dan tahun disimpan sebagai nilai kolom. Jika file terpisah per tahun, jaga grain/header/definisi sama dan rancang penggabungan melalui review; aplikasi tidak otomatis menyatukan file.
- Tulis deskripsi dataset: satu baris mewakili apa, sumber pengukuran, pemilik, periode, satuan, jadwal pembaruan dan batas penggunaan. Tab panduan/kamus data terpisah boleh ada, tetapi jangan diikutkan sebagai data ETL.

## 2. Bentuk tabular: satu header, satu baris per record

- Format ideal: header pada baris 1, data mulai baris 2. Satu kolom mewakili satu field dan satu sel satu nilai. Jangan merge cell, menumpuk header dua tingkat, memakai judul laporan di area data, atau membuat tabel berdampingan.
- Header wajib terisi, unik, jelas dan stabil; periksa juga benturan setelah normalisasi. Contoh Nama Unit dan Nama-Unit dapat menjadi nama target yang sama. Gunakan unit_code, event_date, quantity, amount_idr; jangan hanya Nilai atau Total tanpa definisi.
- Jangan letakkan data pada kolom tanpa header. Gunakan range yang mencakup seluruh field yang dibutuhkan dan mulai dari baris 1. Header_row/data_start_row mengatur lokasi header/data bila sumber lama belum rapi.
- Jangan sisipkan subtotal, grand total, catatan, tanda tangan, chart atau baris pemisah ke dalam tabel fakta. Pisahkan tampilan laporan/dashboard dari tab input; subtotal dapat membuat agregat terhitung dua kali.
- Untuk laporan bulan di kolom Jan/Feb/Mar, ubah ke format panjang: period_start, period_end, unit_code, indicator_code, value. Setiap bulan menjadi baris. Untuk target/realisasi pada grain yang sama, kolom target_value dan actual_value tetap boleh berdampingan.
- Warna, format tebal, komentar, filter tampilan dan posisi sel bukan nilai bisnis. Simpan status, kategori, priority dan flag sebagai kolom eksplisit. Jangan mengandalkan baris yang disembunyikan untuk dikecualikan dari ETL.

## 3. Grain, business key dan hubungan data

Tetapkan grain sebelum memilih key/metrik. Contoh transaksi: satu baris per kejadian keluhan. Contoh KPI: satu baris per unit, indikator dan periode. Jangan mencampur transaksi harian, rekap bulanan dan target tahunan dalam satu grain.

- Sediakan ID stabil dan unik, misalnya complaint_id, kpi_record_id atau action_id. Kode tidak berubah ketika baris disortir/disisipkan; nomor urut tampilan dan nomor baris bukan identitas yang stabil.
- Business key tidak boleh NULL dan harus unik sesuai grain. Untuk KPI, key dapat gabungan unit_code + indicator_code + period_start + period_end. Kolom yang mirip ID hanya kandidat dari profiling; reviewer harus membuktikan keunikannya.
- Master unit/indikator menyediakan rujukan satu record unik. Fakta dapat memiliki banyak baris per satu unit: relasi MANY_TO_ONE. Jika master memakai key gabungan, sediakan satu kode rujukan unik karena resolver mencari satu field master.
- Join antar-produk harus didefinisikan dan disetujui di Governance. Nama kolom sama tidak membuktikan relasi. Uji cardinality dan jumlah baris sebelum/sesudah join agar nilai tidak berlipat.
- Untuk perubahan historis, pilih kebijakan eksplisit: UPSERT memperbarui record dengan key sama; sejarah revisi memerlukan revision_no/as_of_at serta grain/key yang mencakup versi dan filter versi yang dipakai. Jangan menjumlahkan semua versi sebagai kejadian baru.

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

## 6. Master data, taxonomy dan konsistensi istilah

- Gunakan master untuk entitas/rujukan: unit, produk, pelanggan, indikator. Sediakan kode unik stabil, label bisnis, definisi dan is_active bila diperlukan. Nama manusia bukan pilihan key yang aman bila dapat berubah/berulang.
- Gunakan taxonomy untuk kategori terkendali: jenis keluhan, status, tingkat prioritas dan kelas aktivitas. Term/code baku, alias yang direview dan versi mencegah KAN Jabung/KAN JABUNG/Jabung diperlakukan sebagai kategori berbeda tanpa bukti.
- Di Google Sheet, gunakan dropdown validasi dari daftar kode baku untuk membantu input; proteksi kolom key/formula sesuai kebutuhan pemilik. Dropdown saja tidak menggantikan validasi master/taxonomy di aplikasi.
- Klasifikasikan tab MASTER/NON_MASTER dengan benar. Master memerlukan definisi approved, storage, record yang sudah di-Apply dan source binding approved. Binding approved saja belum memuat record.
- Untuk transaksi, binding referensi master dan binding taxonomy harus sesuai versi approved/profil terbaru. Nilai tidak ditemukan atau ambigu perlu pertanyaan/koreksi; AI/skor tinggi tidak membuktikan relasi dan tidak boleh memilih diam-diam.
- Kamus data menjelaskan tiap header, definisi, tipe, nullability, unit, contoh, daftar nilai, pemilik dan asal field. Perubahan arti indikator/kategori perlu versi, bukan mengganti label lama tanpa jejak.

## 7. Dimensi, metrik dan pengukuran yang tidak menyesatkan

- Dimensi menjawab menurut apa: unit, indikator, kategori dan tanggal/periode. Metrik menjawab berapa: jumlah kejadian, volume, nilai target dan realisasi. Pada konfigurasi NON_MASTER, kolom numerik publik seperti int/integer, bigint, numeric/decimal, real, dan double precision otomatis masuk katalog metrik. Key numerik memakai count_distinct, nama yang mengindikasikan persen/rasio/rate memakai avg, dan kolom numerik lain memakai sum sebagai agregasi awal.
- Tinjau arti bisnis, unit, dan agregasi metrik otomatis sebelum deploy. Kolom sensitif dikecualikan. Tab MASTER tidak mendapat metrik otomatis karena angka sering berfungsi sebagai kode atau atribut identitas.
- Untuk produk NON_MASTER aktif yang dibuat sebelum aturan ini tersedia, operator dapat menjalankan python -m app.cli semantic-numeric-metric-backfill untuk melihat dry-run, lalu python -m app.cli semantic-numeric-metric-backfill --apply setelah memeriksa daftar perubahan. Ini hanya memperbarui semantic catalog dan audit; ETL, tabel fisik, dan baris data tidak dimuat ulang. Perintah idempotent dan mempertahankan definisi metrik yang sudah ada.
- Agregasi yang tersedia: sum, count, avg, min, max, count_distinct. SUM hanya untuk ukuran aditif pada grain yang sama. Saldo/stok/snapshot kondisi tidak otomatis boleh dijumlahkan lintas waktu; pilih definisi/filter periode yang tepat.
- Jangan SUM persen atau AVG persen yang memiliki penyebut berbeda. Rasio total secara bisnis = total pembilang / total penyebut; simpan numerator/denominator atau siapkan rekap rasio pada grain yang benar. Expression rasio bebas belum didukung editor metrik, jadi jangan menjanjikan kalkulasi tersebut otomatis.
- Untuk KPI, simpan target_value, actual_value, unit_code dan indicator_code dengan definisi sama. Jika gap_value/achievement_ratio disiapkan di Sheet, rumus harus direview dan denominasi jelas. Target 0 memerlukan aturan NULL/status, bukan pembagian tak hingga.
- Tetapkan direction HIGHER_IS_BETTER atau LOWER_IS_BETTER dan threshold yang disetujui. Gap target 100, realisasi 90 = kekurangan 10 pada indikator makin tinggi makin baik; keluhan target maksimal 10, realisasi 15 = kelebihan 5 pada indikator makin rendah makin baik.
- Untuk rata-rata/persentase, sertakan sample_count, eligible_count/denominator, cakupan populasi dan metode. Perubahan metode, sampel, definisi atau cutoff dapat menjelaskan tren; korelasi atau perbedaan agregat bukan bukti sebab-akibat.
- Join dan roll-up perlu uji duplikat, cardinality, periode dan filter versi. Jangan mencampur realisasi akumulatif YTD dengan target bulanan atau unit KG dengan liter. Field MEDIUM/HIGH tidak boleh dipakai sebagai dimensi/metrik produk analitik.
- Sertakan ketidakpastian jika memang diukur: ukuran sampel, cakupan, metode, resolusi dan interval/error pengukuran yang sah. Tandai perubahan metode, bias sampel, musim dan kejadian luar biasa. Jangan mengarang tingkat keyakinan statistik atau menyimpulkan sebab-akibat hanya dari chart.

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

## 10. Kepemilikan, keamanan dan hak konsumsi

- Tetapkan Data Owner, Data Steward, unit pemilik, domain bisnis, yurisdiksi, purpose dan sensitivitas yang sesuai isi sumber. Bagikan Sheet ke Service Account backend sebagai Viewer; aplikasi tidak menulis ulang sel sumber.
- Klasifikasikan PII per kolom berdasarkan isi, bukan nama header saja. Hindari NIK, kontak, alamat atau nama pribadi jika analisis cukup memakai kode anonim/agregat. Kontrol akses berlaku juga pada narasi action plan dan evidence_ref.
- Konfigurasi ACTIVE dan sync SUCCEEDED tidak otomatis membuat produk terlihat bagi semua pengguna. Allowed_roles produk serta policy SOURCE/DATA_PRODUCT dan assignment aktif pembaca harus cocok; semua required attributes pada policy berlaku AND.
- Pada owner workflow, SOURCE_OWNER/DATA_STEWARD satu unit menjalankan discovery, profiling, validasi, deploy dan sync tanpa approver terpisah, termasuk item lama. Unit aktif menentukan akses default; policy khusus dan sensitivitas tetap berlaku. Role reviewer lama tidak otomatis mendapat hak pengelola.
- Validasi konsumsi memakai akun pembaca yang sebenarnya: katalog terlihat, field yang diizinkan tersedia dan hasil query masuk akal. Jangan menghapus sensitivitas atau memperluas policy hanya agar katalog terisi.

## 11. Strategi load, pembaruan dan perubahan Sheet

- UPSERT cocok untuk KPI periodik/current-state yang dapat dikoreksi: record dengan key sama diperbarui. APPEND cocok untuk kejadian baru yang stabil; keyless APPEND dapat memakai SKIP_IDENTICAL sesuai review, tetapi baris yang berubah bisa menjadi record baru dan menyebabkan hitungan ganda.
- FULL_REFRESH mengganti isi target dengan snapshot lengkap dan memerlukan alur review yang sesuai; snapshot parsial tidak boleh dipakai seolah mencakup semua data. Master memakai definisi/storage/source binding dan batch master, bukan ETL biasa.
- Sepakati jadwal, cutoff, target freshness dan petugas. Setelah deploy ACTIVE dengan approval terpisah, akses/rilis siap, Sync manual memuat NON_MASTER yang valid; master/FULL_REFRESH/batch biasa tetap memakai preview, approval dan Apply sesuai alurnya.
- Jika file/tab di-rename, ditambah atau dihapus, pilih sumber yang sama di Workspace dan tekan Temukan tab, tunggu SUCCEEDED, lalu Profiling ulang. Muat ulang data tersimpan tidak membaca ulang daftar tab di Google.
- Perubahan header, mapping, tipe, key atau makna memerlukan profil/draft/review terbaru. Preview perubahan schema di langkah 7, konfirmasi dan approval sebelum worker deploy. Rename/drop fisik atau dependency tidak aman dapat diblokir; jangan hapus tabel untuk mengakalinya.
- REVIEW_STALE berarti sumber berubah dibanding snapshot review. Contoh starat_date diganti start_date: profil dan review ulang; tidak cukup retry deploy lama. Hindari perubahan selama review/deploy, termasuk formula volatil yang mengubah nilai tiap pembacaan.
- Setelah load, periksa SUCCEEDED per tab/batch, jumlah record, waktu terakhir dimuat, coverage dan akses katalog. Job induk sukses tidak membuktikan semua tab dimuat; NEEDS_INPUT berarti menunggu tindakan. Gunakan tabel error response pada helper untuk penanganan kode.

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

Panduan aplikasi: **Bantuan > Format Google Sheet ideal** atau **Panduan lengkap > Format Google Sheet ideal**. Penanganan kode error: [Tabel error response](ERROR_RESPONSES.md). Arti istilah: [Istilah teknis dalam bahasa sederhana](ISTILAH_TEKNIS.md).
