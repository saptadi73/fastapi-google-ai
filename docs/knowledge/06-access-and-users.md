---
id: pengguna-role-dan-akses
title: Pengguna, role, dan kontrol akses
summary: Tanggung jawab role, atribut organisasi, kebijakan akses, dan access request.
routes: ["/admin", "/admin/*", "/users/*", "/access-requests", "/release-approvals", "/account"]
audiences: ["*"]
source: docs/ACCESS_JURISDICTION_BE16.md
---
PLATFORM_ADMIN mengelola pengguna, role, atribut organisasi, permission, dan policy. SOURCE_OWNER mendaftarkan dan menjaga konteks sumber. DATA_STEWARD mengelola klasifikasi, master, taxonomy, konfigurasi, dan kualitas. TECHNICAL_APPROVER mereview perubahan. ANALYST dan VIEWER memakai data yang sudah dipublikasikan dan diizinkan.

Akses tidak hanya ditentukan oleh role. Sistem dapat mempertimbangkan departemen, domain bisnis, yurisdiksi, clearance, purpose, assignment pengguna, scope sumber, row scope, dan sensitivitas kolom. Backend mengambil identitas tenant dan pengguna dari token; pengguna tidak memasukkan UUID tenant atau resource secara manual.

Jika halaman atau data tidak tersedia, ajukan access request dengan alasan bisnis dan scope yang diperlukan. Persetujuan harus diberikan oleh pihak yang berwenang. Jangan membagikan akun, token, password, credential Google, atau informasi sensitif melalui form bantuan AI.

Jika Katalog data kosong walaupun sumber ETL ACTIVE, status ETL bukan status akses. Admin harus memberi pembaca assignment aktif unit, domain bisnis, dan yurisdiksi yang cocok dengan sumber. Pada Access policy, pilih ALLOW, resource SOURCE dari tabel, aksi DISCOVER/READ/QUERY, dan ketiga atribut sumber sebagai wajib. Semua atribut berarti AND, bukan pilihan alternatif. Buat DRAFT, Submit review, lalu admin berbeda memilih Approve policy; pembuat tidak dapat menyetujui sendiri. Jangan memberi ADMIN atau EXPORT untuk kebutuhan katalog/query saja.

Pada Workspace sumber yang sama, reviewer bukan editor metadata memilih Tinjau metadata dan Setujui metadata. Admin bukan editor lalu memilih Muat policy SOURCE, policy approved yang cocok, dan Aktifkan policy sumber sampai status POLICY_APPROVED. Approval metadata saja belum membuka katalog. Policy DATA_PRODUCT saja tidak menggantikan policy SOURCE dan aktivasi sumber induk. Ulangi untuk sumber yang diizinkan; jangan registrasi ulang atau mengulang ETL hanya untuk membuka akses.

Admin memilih pengguna tujuan dan memakai Preview keputusan untuk DISCOVER/QUERY pada sumber; hasil harus POLICY_MATCH. DEFAULT_DENY berarti belum ada ALLOW yang cocok atau assignment kurang; EXPLICIT_DENY tidak bisa ditimpa ALLOW. Sesudahnya uji login pengguna dan katalog. Role harus ada dalam allowed_roles produk; tabel storage MASTER tidak otomatis menjadi Data Product. Policy berlaku bagi semua pengguna yang memenuhi atribut, bukan username khusus. SOURCE_OWNER dan TECHNICAL_APPROVER sudah memiliki aksi baca/query; permission bundle bukan pengganti scope dan policy.

Untuk pengguna yang perlu melihat data beberapa unit, admin membuka Administrasi, memilih pengguna, lalu mencentang seluruh unit yang diizinkan pada Akses multi-unit. Contoh: manajer Penjualan diberi Unit Penjualan Malang dan Unit Penjualan Surabaya. Hubungan induk-anak organisasi tidak otomatis memberikan izin ke unit bawahan. Assignment unit masih perlu didukung policy data, domain bisnis, dan yurisdiksi yang sesuai.

Admin memilih sumber data di bagian Approver per sumber data, lalu memilih reviewer aktif secara terpisah untuk Review metadata sumber, Konfigurasi ETL, dan Batch import. Contoh: manajer A menjadi reviewer metadata dan konfigurasi sumber Penjualan Malang; manajer B mereview batch import-nya. Reviewer harus memiliki role reviewer yang sesuai, tidak boleh menyetujui pekerjaan miliknya sendiri, dan penunjukan itu tidak memberikan akses membaca data. Jika belum ada reviewer untuk salah satu jenis keputusan, hubungi admin sebelum mengajukan keputusan itu.

Jika data harus diperiksa lagi sebelum tayang, admin membuka Persetujuan sebelum data tayang pada sumber yang dipilih. Contoh: sumber laporan gabungan Penjualan dan Keuangan memerlukan satu pemeriksa IT, satu approver bernama dari Penjualan, dan satu approver bernama dari Keuangan. Masing-masing approver unit harus memiliki assignment aktif pada unit tersebut. Setelah konfigurasi ETL disetujui, tiap orang membuka menu Persetujuan tayang, membaca ringkasan data dan hasil pemeriksaan yang relevan, lalu mengisi catatan dan menyetujui atau menolak. Pemeriksa IT menandai checklist skema/mapping, kualitas data, dan keamanan/akses. Deploy tertahan sampai IT dan kedua unit menyetujui revisi yang sama. Jika revisi atau aturan berubah, persetujuan perlu diulang. Penunjukan sebagai approver tidak otomatis memberi izin melihat data di dashboard.
