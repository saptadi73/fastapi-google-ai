#!/usr/bin/env bash
set -Eeuo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ -x "$project_root/venv/bin/python" ]]; then
    python_bin="$project_root/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    python_bin="$(command -v python3)"
else
    echo "Python tidak ditemukan. Buat atau aktifkan virtual environment terlebih dahulu." >&2
    exit 1
fi

tenant_code="${BOOTSTRAP_TENANT:-default}"
admin_username="admin_etl@kanjabung.com"
admin_full_name="Admin GoogleSheet AI"
admin_password="${BOOTSTRAP_PASSWORD:-}"

if [[ -z "$admin_password" ]]; then
    read -r -s -p "Password untuk $admin_username: " admin_password
    echo
fi

if (( ${#admin_password} < 12 )); then
    echo "Password minimal 12 karakter." >&2
    exit 1
fi

echo "Membuat atau memperbarui admin tenant '$tenant_code'..."
env \
    BOOTSTRAP_TENANT="$tenant_code" \
    BOOTSTRAP_USERNAME="$admin_username" \
    BOOTSTRAP_FULL_NAME="$admin_full_name" \
    BOOTSTRAP_PASSWORD="$admin_password" \
    "$python_bin" -m app.cli bootstrap --reset-existing-password

unset admin_password

echo "Admin production siap:"
echo "  tenant_code: $tenant_code"
echo "  username:    $admin_username"
echo "  role:        PLATFORM_ADMIN"
