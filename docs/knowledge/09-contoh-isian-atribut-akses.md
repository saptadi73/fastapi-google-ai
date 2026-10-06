---
id: contoh-isian-atribut-akses
title: Contoh pengisian departemen, domain, yurisdiksi, clearance, dan purpose
summary: Contoh nilai atribut organisasi untuk admin serta penjelasan perbedaan masing-masing jenis.
routes: ["/admin", "/admin/*", "/workspace", "/access-requests"]
audiences: ["*"]
source: docs/CONTOH_ISIAN_APLIKASI.md
---
Contoh berikut fiktif. Administrator harus menyesuaikan kode dan label dengan struktur organisasi serta kebijakan resmi sebelum membuat atribut pada tenant.

Pada Administrasi → Atribut akses, admin memilih Jenis, lalu mengisi Kode dan Label. Parent opsional untuk hierarki atribut sejenis. UUID atribut dibuat sistem.

| Jenis | Kode contoh | Label contoh | Pertanyaan yang dijawab |
|---|---|---|---|
| DEPARTMENT | `keuangan` | `Departemen Keuangan` | Unit organisasi mana yang memiliki atau menggunakan data? |
| BUSINESS_DOMAIN | `penjualan` | `Penjualan` | Proses atau ranah bisnis apa yang diwakili data? |
| JURISDICTION | `jatim` | `Jawa Timur` | Wilayah atau cakupan bisnis mana yang berlaku? |
| CLEARANCE | `internal` | `Internal` | Tingkat kelayakan akses pengguna menurut kebijakan organisasi? |
| PURPOSE | `analitik_manajemen` | `Analitik Manajemen` | Untuk tujuan penggunaan apa data didaftarkan? |

Kode atribut wajib unik untuk pasangan tenant dan jenis atribut; kodenya hanya boleh berisi huruf, angka, titik, garis bawah, atau tanda minus, maksimal 80 karakter. Label wajib, maksimal 200 karakter. Parent harus dipilih dari jenis atribut yang sama; contohnya `jatim` dapat memiliki parent `indonesia` bila hierarki yurisdiksi memang dikelola seperti itu. Hierarki tidak otomatis memberi izin akses ke seluruh anak atau induk.

Jangan mencampur domain dengan yurisdiksi. `penjualan` menjelaskan jenis kegiatan; `jatim` menjelaskan ruang wilayah. `CLEARANCE` adalah atribut akses pengguna pada Administrasi, sedangkan form pendaftaran sumber meminta Sensitivitas data `LOW`, `MEDIUM`, atau `HIGH`. Keduanya bukan field yang sama. Pilihan atribut di Workspace ETL berasal dari registry dan assignment yang aktif; pengguna memilih label dari dropdown, bukan memasukkan kode atau UUID secara manual.

