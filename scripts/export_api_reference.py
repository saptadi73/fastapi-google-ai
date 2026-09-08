"""Export offline API docs and validate their coverage; never connects to services."""

import argparse
import importlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build_documents():
    from pydantic import BaseModel

    from app.core import config

    # Documentation must not include local configuration or need real credentials.
    settings = config.Settings(
        _env_file=None,
        app_name="google-sheet-ai-platform",
        api_v1_prefix="/api/v1",
        database_url="postgresql+asyncpg://docs:docs@127.0.0.1/docs_unused",
        jwt_secret="documentation-only-placeholder-32-characters",
    )
    config.get_settings = lambda: settings
    from app.main import app
    from app.models.audit import AuditEvent
    from app.models.auth import User
    from app.models.configuration import Artifact, Configuration
    from app.models.etl import ETLRun, Job, QualityIssue
    from app.models.import_review import ImportDecision, ImportQuestion, ImportReview, ImportReviewRow
    from app.models.master import MasterDefinition, MasterSourceBinding
    from app.models.semantic import DataProduct, QueryRequest, SavedQuery
    from app.models.source import DataSource, ProfilingRun, SourceSheet

    spec = app.openapi()
    models = {}
    for name in (
        "auth",
        "source",
        "configuration",
        "master",
        "import_review",
        "semantic",
        "nl2sql",
        "monitoring",
        "health",
        "common",
    ):
        module = importlib.import_module("app.schemas." + name)
        for cls in vars(module).values():
            if isinstance(cls, type) and issubclass(cls, BaseModel):
                models[cls.__name__] = cls

    examples = json.loads((ROOT / "docs/api/PAYLOADS.json").read_text(encoding="utf-8"))
    bodies = set()
    for methods in spec["paths"].values():
        for operation in methods.values():
            body = operation.get("requestBody", {}).get("content", {}).get("application/json")
            if body:
                bodies.add(body["schema"]["$ref"].rsplit("/", 1)[-1])
    if bodies != set(examples):
        raise ValueError(f"Payload examples mismatch: {bodies ^ set(examples)}")
    for name, payload in examples.items():
        models[name].model_validate(payload)

    def compact(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("|", "&#124;")

    def kind(schema):
        if "$ref" in schema:
            return schema["$ref"].rsplit("/", 1)[-1]
        if "anyOf" in schema:
            return " / ".join(kind(x) for x in schema["anyOf"])
        if "enum" in schema:
            return "enum " + compact(schema["enum"])
        if "const" in schema:
            return compact(schema["const"])
        if schema.get("type") == "array":
            return "array<" + kind(schema.get("items", {})) + ">"
        if schema.get("type") == "object" and isinstance(schema.get("additionalProperties"), dict):
            return "map<string, " + kind(schema["additionalProperties"]) + ">"
        return schema.get("type", "any") + (" (" + schema["format"] + ")" if "format" in schema else "")

    lines = [
        "# API schemas dan parameter",
        "",
        "Dihasilkan dari schema/route backend oleh `scripts/export_api_reference.py`. "
        "Lihat [API Reference](../API_REFERENCE.md) untuk arti field dan mekanisme bisnis. "
        "Snapshot OpenAPI masih memakai Envelope generik untuk banyak respons; "
        "jangan menganggap `data: any` sebagai kontrak domain yang lengkap.",
        "",
        "## Parameter setiap endpoint",
        "",
        "Path lengkap di bawah termasuk prefix. Body `—` berarti tidak ada request body. "
        "Query parameter yang tidak tercantum tidak menyediakan fitur filter/pencarian. "
        "Batas validasi lintas field dijelaskan di API Reference.",
        "",
    ]
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            lines += [f"### {method.upper()} {path}", ""]
            body = operation.get("requestBody", {}).get("content", {}).get("application/json")
            body_name = body["schema"]["$ref"].rsplit("/", 1)[-1] if body else None
            lines += ["Body: " + (f"[{body_name}](#{body_name.lower()})" if body_name else "—") + ".", ""]
            params = operation.get("parameters", [])
            if params:
                lines += ["| Parameter | Lokasi | Wajib | Tipe / batas |", "|---|---|---|---|"]
                for param in params:
                    schema = param["schema"]
                    bounds = {k: v for k, v in schema.items() if k in ("minimum", "maximum", "default")}
                    lines.append(
                        f"| `{param['name']}` | {param['in']} | "
                        f"{'Ya' if param.get('required') else 'Tidak'} | `{kind(schema)}` {compact(bounds)} |"
                    )
                lines.append("")

    lines += [
        "## Schema JSON",
        "",
        "`Wajib` berarti field harus dikirim. Nullable berbeda dari opsional. "
        "Payload StrictModel menolak field tambahan. Default ditampilkan jika tersedia; "
        "default factory list/map kosong ditampilkan sebagai `[]`/`{}`.",
        "",
    ]
    for name, schema in sorted(spec["components"]["schemas"].items()):
        lines += [f"### {name}", ""]
        if "properties" not in schema:
            lines += [f"`{kind(schema)}`", ""]
            continue
        lines += ["| Field | Wajib | Tipe | Default | Batas |", "|---|---|---|---|---|"]
        for field, prop in schema["properties"].items():
            default = compact(prop["default"]) if "default" in prop else "—"
            model_field = getattr(models.get(name), "model_fields", {}).get(field)
            if default == "—" and model_field and model_field.default_factory in (list, dict):
                default = compact(model_field.default_factory())
            constraints = {
                k: v
                for k, v in prop.items()
                if k
                in (
                    "minLength",
                    "maxLength",
                    "minimum",
                    "maximum",
                    "pattern",
                    "minItems",
                    "maxItems",
                    "writeOnly",
                )
            }
            lines.append(
                f"| `{field}` | {'Ya' if field in schema.get('required', []) else 'Tidak'} | "
                f"`{kind(prop)}` | {default} | {compact(constraints) if constraints else '—'} |"
            )
        if name in examples:
            lines += [
                "",
                "Contoh payload valid secara schema (ID harus diganti dengan ID backend):",
                "",
                "```json",
                json.dumps(examples[name], ensure_ascii=False, indent=2),
                "```",
            ]
        lines.append("")

    lines += [
        "## Bentuk record respons",
        "",
        "Field hasil serialisasi ORM; semuanya read-only dari sisi "
        "response. Ini bukan payload create/PATCH. `id`, `tenant_id`, `created_at` termasuk dalam "
        "record. Field JSON memiliki struktur rinci yang dijelaskan di API Reference. Nilai UUID "
        "dan timestamp dikirim sebagai string. Field internal yang dikecualikan endpoint tidak "
        "ditampilkan pada bentuk public di bawah.",
        "",
    ]
    for cls, exclude in [
        (User, {"password_hash", "token_version"}),
        (DataSource, set()),
        (SourceSheet, set()),
        (ProfilingRun, set()),
        (Configuration, set()),
        (MasterDefinition, set()),
        (MasterSourceBinding, set()),
        (ImportReview, {"configuration_json", "dependencies", "findings"}),
        (ImportReviewRow, {"raw_data", "transformed_data", "corrected_data"}),
        (ImportQuestion, {"evidence"}),
        (ImportDecision, {"before_data", "after_data", "evidence"}),
        (Artifact, {"storage_uri"}),
        (Job, set()),
        (ETLRun, set()),
        (QualityIssue, {"data"}),
        (DataProduct, {"view_name"}),
        (SavedQuery, set()),
        (QueryRequest, set()),
        (AuditEvent, set()),
    ]:
        lines += [
            f"### Record {cls.__name__}",
            "",
            "| Field | Tipe penyimpanan | Nullable |",
            "|---|---|---|",
        ]
        for col in cls.__table__.columns:
            if col.key not in exclude:
                lines.append(f"| `{col.key}` | `{col.type}` | {'Ya' if col.nullable else 'Tidak'} |")
        if cls is QualityIssue:
            lines += ["", "Endpoint quarantine menambahkan `data: array` berisi nilai mentah baris."]
        lines.append("")
    return spec, {
        ROOT / "docs/api/openapi.json": json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        ROOT / "docs/api/SCHEMAS.md": "\n".join(lines),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify docs without writing")
    args = parser.parse_args()
    spec, documents = build_documents()
    reference = (ROOT / "docs/API_REFERENCE.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"\| (GET|POST|PATCH|PUT|DELETE) \| `([^`]+)` \|", reference))
    operations = {
        (m.upper(), p.removeprefix("/api/v1")) for p, methods in spec["paths"].items() for m in methods
    }
    if documented != operations:
        raise SystemExit(
            f"Endpoint coverage mismatch. Missing={operations - documented}; extra={documented - operations}"
        )
    for path, content in documents.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Stale generated documentation: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    print(
        f"Verified {len(operations)} operations, every request payload example, and documentation snapshots."
    )


if __name__ == "__main__":
    main()
