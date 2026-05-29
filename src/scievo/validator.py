from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as err:
                raise ValueError(f"{path}:{line_no} JSON decode error: {err}") from err
    return rows


def validate_records(schema_path: Path, dataset_path: Path) -> list[str]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    rows = load_jsonl(dataset_path)
    errors: list[str] = []
    for idx, item in enumerate(rows, start=1):
        for err in validator.iter_errors(item):
            loc = ".".join(str(part) for part in err.path) or "<root>"
            errors.append(f"row {idx} ({item.get('record_id','unknown')}): {loc}: {err.message}")
    return errors

