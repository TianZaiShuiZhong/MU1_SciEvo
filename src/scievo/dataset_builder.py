from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PIPELINE_VERSION = "v0.1.0"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_metric_list(metrics: dict[str, Any]) -> list[dict[str, str]]:
    output = []
    for name, item in metrics.items():
        output.append(
            {
                "name": name,
                "value": str(item.get("value", "")),
                "unit": str(item.get("unit", "")),
                "interpretation": str(item.get("interpretation", "")),
            }
        )
    return output


def normalize_official_case(
    data: dict[str, Any],
    *,
    source_title: str,
    source_url: str,
    source_doi: str = "",
    domain: str = "protein-engineering",
) -> dict[str, Any]:
    steps = []
    for raw_step in data["02_agent_trajectory"]:
        steps.append(
            {
                "step_index": raw_step["step_index"],
                "thought": raw_step["thought"],
                "action": raw_step["action"],
                "tool": raw_step["tool"],
                "parameters": raw_step.get("parameters", {}),
                "observation": raw_step["observation"],
                "outcome": "success" if raw_step.get("valid", False) else "failure",
                "reasoning_tags": [
                    "background_gap_decision",
                    "scientific_reasoning",
                    "tool_decision",
                ],
            }
        )

    verification = data["03_success_verification"]

    return {
        "record_id": "luxsit.full.001",
        "track_type": "Sci-Evo",
        "domain": domain,
        "source": {
            "title": source_title,
            "url": source_url,
            "doi": source_doi,
            "license": "refer to paper/publisher policy",
            "citation": source_title,
        },
        "initial_request": data["01_initial_request"],
        "trajectory": steps,
        "success_verification": {
            "validation_technique": verification["validation_technique"],
            "metrics": _to_metric_list(verification["metrics"]),
            "final_verdict": verification["final_verdict"],
        },
        "provenance": {
            "created_at": utc_now_iso(),
            "pipeline_version": PIPELINE_VERSION,
            "mineru": {
                "used": True,
                "mode": "sample_import",
                "task_id": "official-sample",
                "model_version": "unknown",
            },
            "source_span": ["official_example_json"],
        },
        "quality": {
            "review_status": "draft",
            "traceability_score": 0.95,
            "completeness_score": 1.0,
        },
    }


def _build_step_focus_record(base_record: dict[str, Any], step_index: int, variant_index: int) -> dict[str, Any]:
    focused = deepcopy(base_record)
    focused["record_id"] = f"luxsit.step{step_index:02d}.{variant_index:03d}"
    focused["trajectory"] = [s for s in base_record["trajectory"] if s["step_index"] <= step_index]
    focused["provenance"]["source_span"] = [f"official_example_json:step_{step_index}"]
    focused["quality"]["completeness_score"] = round(step_index / max(len(base_record["trajectory"]), 1), 3)
    return focused


def generate_demo_records(base_record: dict[str, Any], min_count: int = 12) -> list[dict[str, Any]]:
    """Generate a non-fabricated demo set from one real case.

    Notes:
    - This is for pipeline demonstration and schema debugging.
    - For final competition submission, add more independent papers.
    """
    records = [base_record]
    step_count = len(base_record["trajectory"])
    variant = 2
    while len(records) < min_count:
        for step_idx in range(1, step_count + 1):
            if len(records) >= min_count:
                break
            records.append(_build_step_focus_record(base_record, step_idx, variant))
            variant += 1
    return records


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for item in records:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return output_path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

