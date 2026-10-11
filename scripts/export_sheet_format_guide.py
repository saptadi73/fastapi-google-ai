"""Generate the ideal Google Sheet guide, bounded knowledge articles and static UI content."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "struktur": ("Penamaan, header, grain dan key Google Sheet", ["/workspace", "/sources", "/etl-review/*"]),
    "nilai-waktu": ("Tipe, presisi, tanggal dan periode pengambilan data", ["/workspace", "/etl-review/*", "/quality"]),
    "master-metrik": ("Master istilah, taxonomy, dimensi dan metrik analitik", ["/masters", "/taxonomies", "/workspace", "/data-catalog"]),
    "tindak-lanjut": ("Action plan berbasis bukti dan kualitas data", ["/workspace", "/quality", "/dashboard", "/chat"]),
    "operasi": ("Akses, load dan perubahan sumber analitik", ["/sources", "/workspace", "/jobs", "/admin"]),
    "contoh": ("Contoh Google Sheet KPI dan action plan serta checklist", ["/workspace", "/dashboard", "/chat"]),
}


def section_markdown(section):
    blocks = []
    for block in section["blocks"]:
        if "text" in block:
            blocks.append(block["text"])
        elif "items" in block:
            blocks.append("\n".join(f"- {item}" for item in block["items"]))
        else:
            headers, rows = block["headers"], block["rows"]
            if any(len(row) != len(headers) for row in rows):
                raise ValueError(f"Invalid table shape: {section['id']}")
            lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
            lines.extend("| " + " | ".join(row) + " |" for row in rows)
            blocks.append("\n".join(lines))
    return f"## {section['title']}\n\n" + "\n\n".join(blocks)


def documents(frontend_root=None):
    raw = (ROOT / "docs/google-sheet-format.json").read_text(encoding="utf-8")
    guide = json.loads(raw)
    sections = guide["sections"]
    if len({section["id"] for section in sections}) != len(sections):
        raise ValueError("Duplicate guide section IDs")
    if any(section["group"] not in GROUPS for section in sections):
        raise ValueError("Unknown guide group")
    result = {}
    for index, (group, (title, routes)) in enumerate(GROUPS.items(), 19):
        selected = [section for section in sections if section["group"] == group]
        body = guide["intro"] + "\n\n" + "\n\n".join(section_markdown(section) for section in selected) + "\n"
        if len(body.strip()) > 6000:
            raise ValueError(f"Knowledge article exceeds 6000 characters: {group} ({len(body.strip())})")
        header = (
            f"---\nid: format-google-sheet-{group}\ntitle: Format Google Sheet ideal - {title}\n"
            f"summary: {json.dumps('Rekomendasi data analitik modern, akurat dan presisi: ' + title + '.')}\n"
            f"routes: {json.dumps(routes + ['/guide'])}\naudiences: [\"*\"]\n"
            "source: docs/PANDUAN_FORMAT_GOOGLE_SHEET.md\n---\n"
        )
        result[ROOT / f"docs/knowledge/{index:02}-sheet-format-{group}.md"] = header + body
    full = (
        f"# {guide['title']}\n\n"
        "<!-- Generated from docs/google-sheet-format.json by scripts/export_sheet_format_guide.py. -->\n\n"
        + guide["intro"] + "\n\n" + "\n\n".join(section_markdown(section) for section in sections)
        + "\n\nPanduan aplikasi: **Bantuan > Format Google Sheet ideal** atau **Panduan lengkap > Format Google Sheet ideal**. "
        "Penanganan kode error: [Tabel error response](ERROR_RESPONSES.md).\n"
    )
    result[ROOT / "docs/PANDUAN_FORMAT_GOOGLE_SHEET.md"] = full
    if frontend_root:
        result[frontend_root / "docs/PANDUAN_FORMAT_GOOGLE_SHEET.md"] = full
        result[frontend_root / "src/content/googleSheetFormat.json"] = raw
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--frontend-root", type=Path)
    args = parser.parse_args()
    outputs = documents(args.frontend_root)
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Google Sheet guide is stale: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    print(f"Verified {len(outputs)} Google Sheet guide documents.")


if __name__ == "__main__":
    main()
