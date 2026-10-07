# Diagnosis dropdown metadata Google Sheet kosong

Dropdown unit, domain bisnis, dan yurisdiksi pada Workspace diambil dari
`GET /api/v1/access/registration-options`. Endpoint ini hanya mengembalikan assignment
aktif milik akun **yang sedang login**, pada tenant yang sama. Role admin atau atribut
yang tersedia di Registry tidak otomatis menambahkan pilihan.

Sebelum memeriksa database, lihat respons `GET /api/v1/auth/me` dan
`GET /api/v1/access/registration-options` pada tab Network browser. Jangan kirim
header Authorization atau token saat membagikan hasil. `auth/me` harus menyebut
pengguna dan tenant yang dimaksud. Bila `scopes` memuat `MARKETING` berjenis
`DEPARTMENT`, backend sudah mengirim opsi; tekan **Muat ulang pilihan** atau deploy
frontend terbaru bila UI masih kosong. Bila `scopes` tidak memuat Marketing, periksa
assignment di database dengan query baca-saja berikut:

```sql
SELECT t.code AS tenant,
       u.username,
       u.role,
       u.is_active AS user_active,
       a.kind,
       a.code AS attribute_code,
       a.is_active AS attribute_active,
       ua.status AS assignment_status,
       ua.valid_from,
       ua.valid_to,
       CASE
         WHEN ua.id IS NULL THEN 'NO_ASSIGNMENT'
         WHEN NOT u.is_active THEN 'USER_INACTIVE'
         WHEN NOT a.is_active THEN 'ATTRIBUTE_INACTIVE'
         WHEN ua.status <> 'ACTIVE' THEN 'ASSIGNMENT_REVOKED'
         WHEN ua.valid_from > now() THEN 'NOT_YET_VALID'
         WHEN ua.valid_to IS NOT NULL AND ua.valid_to <= now() THEN 'EXPIRED'
         ELSE 'EFFECTIVE'
       END AS result
FROM platform.app_user AS u
JOIN platform.tenant AS t ON t.id = u.tenant_id
LEFT JOIN platform.user_assignment AS ua
       ON ua.user_id = u.id AND ua.tenant_id = u.tenant_id
LEFT JOIN platform.access_attribute AS a
       ON a.id = ua.attribute_id AND a.tenant_id = u.tenant_id
WHERE u.username IN ('saptadi', 'saptadi1')
ORDER BY t.code, u.username, a.kind, a.code, ua.valid_from DESC;
```

Jalankan pada database aplikasi yang dipakai API production, misalnya dari `psql`
setelah `\connect googleai`. Query hanya membaca metadata dan tidak menampilkan
password, token, atau isi Sheet. Hasil `EFFECTIVE` untuk `saptadi1` + `MARKETING`
menandakan pilihan unit harus tersedia ketika **saptadi1** login pada tenant itu.
Assignment `saptadi1` tidak berlaku bagi akun `saptadi`. Domain bisnis dan
yurisdiksi memerlukan baris `EFFECTIVE` masing-masing dengan jenis
`BUSINESS_DOMAIN` dan `JURISDICTION`; keduanya tidak dibuat oleh tombol multi-unit.

Jika tidak ada baris assignment, berikan lewat Administrasi → Pengguna menggunakan
akun admin lain. Jika status bukan `EFFECTIVE`, perbaiki akun, atribut, atau periode
yang disebutkan. Setelah itu tekan **Muat ulang pilihan** di Workspace.
