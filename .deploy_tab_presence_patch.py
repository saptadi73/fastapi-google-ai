from pathlib import Path

replacements = {
    "app/services/import_review_service.py": [
        (
            "        await self.session.refresh(source)\n        if not sheet.enabled or source.paused:\n",
            "        await self.session.refresh(source)\n        if not sheet.is_present:\n            raise AppError(\"IMPORT_SOURCE_TAB_MISSING\", \"Tab sudah tidak ditemukan pada Google Sheet; jalankan discovery ulang setelah tab dipulihkan.\", 409)\n        if not sheet.enabled or source.paused:\n",
        ),
        (
            "        if (not binding or not sheet or not source or not sheet.enabled or source.paused\n",
            "        if (not binding or not sheet or not source or not sheet.is_present or not sheet.enabled or source.paused\n",
        ),
    ],
    "app/services/master_service.py": [
        (
            "            metadata_ready = (\n                binding.status == \"APPROVED\"\n                and validation[\"valid\"]\n                and validation[\"snapshot_hash\"] == binding.snapshot_hash\n            )\n            storage_ready = False\n            reason = \"MASTER_BINDING_REVIEW_REQUIRED\"\n",
            "            metadata_ready = (\n                binding.status == \"APPROVED\"\n                and sheet.is_present\n                and sheet.enabled\n                and validation[\"valid\"]\n                and validation[\"snapshot_hash\"] == binding.snapshot_hash\n            )\n            storage_ready = False\n            reason = (\n                \"SOURCE_TAB_MISSING\"\n                if not sheet.is_present\n                else \"SOURCE_TAB_DISABLED\"\n                if not sheet.enabled\n                else \"MASTER_BINDING_REVIEW_REQUIRED\"\n            )\n",
        ),
    ],
}

for filename, pairs in replacements.items():
    path = Path(filename)
    content = path.read_text(encoding="utf-8")
    for old, new in pairs:
        if content.count(old) != 1:
            raise SystemExit(f"Expected exactly one target block in {filename}; no changes applied to that block")
        content = content.replace(old, new, 1)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Patched {filename}")
