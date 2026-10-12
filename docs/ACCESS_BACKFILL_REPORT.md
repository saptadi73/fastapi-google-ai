# Laporan dry-run metadata akses sumber lama

Jalankan dari backend pada environment yang memakai konfigurasi database target:

```text
python -m app.cli source-access-backfill-report
```

Perintah ini hanya membaca sumber yang belum di-unlink dan mencetak JSON berisi jumlah per kategori serta identitas tenant, UUID sumber, kode sumber, status akses/review, kategori tindakan, dan nama field metadata yang masih kosong. Nilai metadata, spreadsheet ID, dan data Sheet tidak dicetak. Menjalankan ulang laporan tidak membuat perubahan.

Kategori laporan:

- `OWNER_METADATA_REQUIRED`: owner melengkapi metadata yang kosong melalui form aplikasi.
- `SOURCE_REVIEW_REQUIRED`: approver perlu meninjau registrasi sesuai mode rollout.
- `SOURCE_REVIEW_REJECTED`: owner perlu memperbaiki metadata atau bukti sumber, lalu mengajukan ulang sesuai alur yang aktif.
- `OWNER_ACCESS_ACTIVATION_REQUIRED`: review sumber sudah approved, tetapi akses pemilik belum diaktifkan.
- `READY_NO_BACKFILL`: status akses sudah disetujui; laporan tidak melakukan apa pun.

Laporan ini tidak membuat approval, assignment, policy, ataupun grant. Ia juga tidak mengubah `access_status` atau `access_review_status`. Gunakan hasilnya untuk merencanakan perbaikan manual dan rollout bertahap. Aktivasi akses tetap bergantung pada assignment aktif dan pemeriksaan tenant oleh backend. Jangan mengubah status lama langsung di SQL.

## Batas rollout

Ini adalah inventaris dry-run, bukan migrasi data. Sebelum membuat perintah backfill yang menulis, setiap kategori perlu aturan keputusan, bukti review yang dapat diaudit, idempotency, dukungan dry-run, backup, serta rencana rollback. Sumber tanpa bukti registrasi tidak boleh otomatis dianggap reviewed.
