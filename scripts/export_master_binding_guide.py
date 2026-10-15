"""Keep the master binding tutorial identical across documentation, knowledge and helper."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def step_text(steps, start=1):
    return "\n\n".join(
        f"### {i}. {step['title']}\n\nHalaman: **{step['where']}**. Pelaksana: {step['actor']}.\n\n"
        + "\n".join(f"- {action}" for action in step["actions"])
        + f"\n\nHasil sebelum lanjut: **{step['result']}**."
        for i, step in enumerate(steps, start)
    )


def documents(frontend_root=None):
    raw = (ROOT / "docs/master-binding-guide.json").read_text(encoding="utf-8")
    guide = json.loads(raw)
    differences = "\n".join(
        f"- **{item['name']}**: {item['purpose']} Contoh: {item['example']}" for item in guide["differences"]
    )
    example = guide["example"]
    example_text = (
        example["description"] + "\n\n| Header sumber | Field master | Tipe | Aturan | Contoh |\n"
        "| --- | --- | --- | --- | --- |\n"
        + "\n".join(
            f"| {r['source']} | {r['target']} | {r['type']} | {r['rule']} | {r['value']} |"
            for r in example["rows"]
        )
        + "\n\n"
        + example["existing_sheet"]
    )
    troubleshooting = "| Pesan / kondisi | Penyebab | Tindakan |\n| --- | --- | --- |\n" + "\n".join(
        f"| {r['symptom']} | {r['cause']} | {r['action']} |" for r in guide["troubleshooting"]
    )
    reference = "\n".join(f"{i}. {step}" for i, step in enumerate(guide["reference_steps"], 1))
    if guide.get("reference_configuration_help"):
        reference += "\n\n" + guide["reference_configuration_help"]
    prerequisites = "\n".join(f"- {item}" for item in guide["prerequisites"])
    completion = "\n".join(f"- {item}" for item in guide["completion"])
    full = (
        f"# {guide['title']}\n\n{guide['intro']}\n\n"
        "Di aplikasi buka **Panduan penggunaan > Binding master** (`/guide#binding-master`) "
        "atau **Bantuan > Panduan khusus binding master**.\n\n"
        f"## Dua jenis binding\n\n{differences}\n\n## Prasyarat\n\n{prerequisites}\n\n"
        f"## Langkah dari Registry sampai pemuatan record\n\n{step_text(guide['steps'])}\n\n"
        f"## {example['title']}\n\n{example_text}\n\n"
        f"## Binding kolom referensi pada NON_MASTER\n\n{reference}\n\n"
        f"## Jika proses belum bisa dilanjutkan\n\n{troubleshooting}\n\n"
        f"## Checklist selesai\n\n{completion}\n\n"
        "Master tersimpan sebagai rujukan di Registry, bukan otomatis data product di Katalog data. "
        "Periksa record melalui Storage & record master. Dataset NON_MASTER yang menggunakannya "
        "memerlukan konfigurasi semantic dan akses tersendiri.\n"
    )
    outputs = {ROOT / "docs/PANDUAN_BINDING_MASTER.md": full}
    articles = [
        (
            35,
            "binding-master-langkah",
            "Binding master: Registry, storage, mapping dan approval",
            "Panduan step by step binding tab MASTER, Simpan binding & dry-run, Setujui binding dan prasyarat.",
            guide["intro"]
            + "\n\n"
            + differences
            + "\n\n"
            + prerequisites
            + "\n\n"
            + step_text(guide["steps"][:6]),
        ),
        (
            36,
            "binding-master-pemuatan",
            "Binding master: pemuatan record dan troubleshooting",
            "Buat batch review/import, Preview, approval, Apply, Record kanonis; MASTER_BINDING_REQUIRED dan tombol tidak aktif.",
            "Binding APPROVED belum memuat record. Tab MASTER tidak diproses lewat approval konfigurasi ETL biasa.\n\n"
            + step_text(guide["steps"][6:], start=7)
            + "\n\n"
            + troubleshooting
            + "\n\n"
            + completion,
        ),
        (
            37,
            "binding-master-referensi",
            "Binding master: contoh mapping bisnis dan rujukan",
            "Contoh BISNIS/is_active, business key stabil dan rujukan NON_MASTER yang berbeda dari binding tab.",
            differences + "\n\n" + example_text + "\n\nBinding kolom referensi:\n\n" + reference,
        ),
    ]
    for number, code, title, summary, body in articles:
        body += "\n\nPanduan utuh: /guide#binding-master atau docs/PANDUAN_BINDING_MASTER.md."
        if len(body) > 6000:
            raise ValueError(f"Knowledge article exceeds helper limit: {code}: {len(body)}")
        metadata = {
            "id": code,
            "title": title,
            "summary": summary,
            "routes": [
                "/masters",
                "/masters/*",
                "/sources/*",
                "/guide",
            ],
            "audiences": ["PLATFORM_ADMIN", "SOURCE_OWNER", "DATA_STEWARD", "TECHNICAL_APPROVER"],
            "source": "docs/PANDUAN_BINDING_MASTER.md",
        }
        header = (
            "---\n"
            + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in metadata.items())
            + "\n---\n"
        )
        outputs[ROOT / f"docs/knowledge/{number:02}-{code}.md"] = header + body + "\n"
    if frontend_root:
        outputs[frontend_root / "src/content/masterBindingGuide.json"] = raw
        outputs[frontend_root / "docs/PANDUAN_BINDING_MASTER.md"] = full
        outputs[frontend_root / "public/guides/PANDUAN_BINDING_MASTER.md"] = full
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-root", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, content in documents(args.frontend_root).items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Master binding guide is stale: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    print("Verified master binding guide in documentation, knowledge and helper.")


if __name__ == "__main__":
    main()
