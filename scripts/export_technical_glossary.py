"""Publish plain-language technical terms to docs, knowledge base and static helper."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "dasar": "Dasar pencatatan data",
    "rujukan": "Rujukan dan persiapan data",
    "analitik": "Analitik, ketelitian dan konteks waktu",
    "operasi": "Proses aplikasi dan pemuatan",
}
INTRO = "Bayangkan Google Sheet sebagai buku pencatatan bisnis. Istilah berikut menjelaskan isi buku, aturan pencatatan dan cara aplikasi mengolahnya. Contoh memakai keluhan pelanggan dan rekap KPI."
EXAMPLE = (
    "Contoh terpadu: satu baris adalah rekap penyelesaian keluhan satu unit untuk satu indikator dalam satu bulan. "
    "Itu grain. Unit + indikator + periode dapat menjadi business key. Unit dan periode menjadi dimensi; "
    "target serta realisasi adalah metrik dengan definisi/agregasi yang direview. "
    "Jika angka periode yang sama dikoreksi, UPSERT memperbarui key yang sama. APPEND tanpa key yang tepat "
    "dapat membuat record awal dan koreksi ikut dihitung sehingga hasil berlipat. "
    "Master menyimpan entitas rujukan seperti unit; taxonomy mengatur kategori seperti jenis keluhan."
)


def table(rows):
    lines = ["| Istilah | Arti sederhana | Contoh bisnis |", "| --- | --- | --- |"]
    lines.extend(f"| **{r['term']}** | {r['meaning']} | {r['example']} |" for r in rows)
    return "\n".join(lines)


def documents(frontend_root=None):
    raw = (ROOT / "docs/technical-glossary.json").read_text(encoding="utf-8")
    rows = json.loads(raw)
    if len({row["id"] for row in rows}) != len(rows) or any(row["group"] not in GROUPS for row in rows):
        raise ValueError("Invalid glossary IDs or groups")
    outputs, sections = {}, []
    for index, (group, title) in enumerate(GROUPS.items(), 25):
        selected = [row for row in rows if row["group"] == group]
        body = INTRO + "\n\n" + table(selected) + "\n"
        if len(body.strip()) > 6000:
            raise ValueError(f"Glossary article exceeds provider limit: {group}")
        terms = ", ".join(row["term"] for row in selected)
        header = (
            f"---\nid: istilah-teknis-{group}\ntitle: {json.dumps('Istilah teknis bahasa sederhana - ' + title)}\n"
            f"summary: {json.dumps('Tabel penjelasan untuk non teknis: ' + terms)}\n"
            'routes: ["/guide"]\n'
            'audiences: ["*"]\nsource: docs/ISTILAH_TEKNIS.md\n---\n'
        )
        outputs[ROOT / f"docs/knowledge/{index:02}-glossary-{group}.md"] = header + body
        sections.append(f"## {title}\n\n" + table(selected))
    document = (
        "# Istilah teknis dalam bahasa sederhana\n\n"
        "<!-- Generated from docs/technical-glossary.json by scripts/export_technical_glossary.py. -->\n\n"
        + INTRO + "\n\n" + "\n\n".join(sections) + "\n\n" + EXAMPLE
        + "\n\nDi aplikasi: **Bantuan > Istilah teknis dalam bahasa sederhana** atau **Panduan lengkap > Istilah teknis dalam bahasa sederhana**. "
        "Cari istilah, arti atau contoh. Lihat juga [Format Google Sheet ideal](PANDUAN_FORMAT_GOOGLE_SHEET.md) dan [Tabel error response](ERROR_RESPONSES.md).\n"
    )
    outputs[ROOT / "docs/ISTILAH_TEKNIS.md"] = document
    if frontend_root:
        outputs[frontend_root / "docs/ISTILAH_TEKNIS.md"] = document
        outputs[frontend_root / "src/content/technicalGlossary.json"] = raw
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-root", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, content in documents(args.frontend_root).items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Glossary is stale: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    print("Verified technical glossary documents.")


if __name__ == "__main__":
    main()
