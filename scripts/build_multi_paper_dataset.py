from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scievo.dataset_builder import write_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build multi-paper Sci-Evo draft dataset from MinerU markdown outputs.")
    parser.add_argument(
        "--markdown-root",
        default=str(ROOT / "data" / "interim" / "markdown"),
        help="Root directory containing <paper_id>/meta.json and full.md.",
    )
    parser.add_argument(
        "--output-jsonl",
        default=str(ROOT / "data" / "processed" / "scievo_multi_paper_draft.jsonl"),
        help="Output jsonl path.",
    )
    parser.add_argument(
        "--records-per-paper",
        type=int,
        default=4,
        help="How many draft records to generate per paper from different evidence snippets.",
    )
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_meta(meta_path: Path) -> dict[str, Any]:
    return json.loads(meta_path.read_text(encoding="utf-8"))


def parse_markdown(markdown_text: str) -> tuple[list[str], list[str]]:
    lines = [ln.rstrip() for ln in markdown_text.splitlines()]
    paragraphs = []
    current: list[str] = []
    for line in lines:
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return lines, paragraphs


def extract_title(lines: list[str], fallback: str) -> str:
    for ln in lines:
        if ln.startswith("# "):
            return ln[2:].strip()
    return fallback or "unknown_title"


def extract_abstract(lines: list[str], paragraphs: list[str]) -> str:
    for i, ln in enumerate(lines):
        if ln.strip().lower() == "## abstract":
            block: list[str] = []
            for j in range(i + 1, len(lines)):
                nxt = lines[j].strip()
                if nxt.startswith("## "):
                    break
                if nxt:
                    block.append(nxt)
            if block:
                return " ".join(block)

    for para in paragraphs:
        lower = para.lower()
        if para.startswith("#"):
            continue
        if "doi.org" in lower:
            continue
        if len(para) < 120:
            continue
        if lower.startswith("submitted to"):
            continue
        return para
    return "Abstract extraction pending manual review."


def find_paragraph_by_keywords(paragraphs: list[str], keywords: list[str]) -> str:
    for para in paragraphs:
        lower = para.lower()
        if para.startswith("#"):
            continue
        if len(para) < 80:
            continue
        if any(kw in lower for kw in keywords):
            return para
    return ""


def extract_numeric_phrases(text: str, max_items: int = 3) -> list[str]:
    candidates = re.findall(r"[^.]{0,120}\d[^.]{0,120}\.", text)
    dedup = []
    for c in candidates:
        c = " ".join(c.split())
        if c not in dedup:
            dedup.append(c)
        if len(dedup) >= max_items:
            break
    return dedup


def build_record(meta: dict[str, Any], md_path: Path, variant_index: int, records_per_paper: int) -> dict[str, Any]:
    markdown_text = md_path.read_text(encoding="utf-8", errors="ignore")
    lines, paragraphs = parse_markdown(markdown_text)

    title = extract_title(lines, meta.get("title", ""))
    abstract_text = extract_abstract(lines, paragraphs)
    method_para = find_paragraph_by_keywords(
        paragraphs,
        ["we use", "we introduce", "we investigate", "we present", "we propose", "we develop", "method"],
    )
    result_para = find_paragraph_by_keywords(
        paragraphs,
        ["we show", "results", "outperform", "achieve", "demonstrate", "indicate", "found"],
    )
    if not method_para:
        method_para = abstract_text
    if not result_para:
        result_para = abstract_text

    evidence_pool = [abstract_text, method_para, result_para]
    selected = evidence_pool[(variant_index - 1) % len(evidence_pool)]

    metrics_text = extract_numeric_phrases(abstract_text + " " + result_para)
    if not metrics_text:
        metrics = [
            {
                "name": "reported_quantitative_signal",
                "value": "not_explicit",
                "unit": "textual",
                "interpretation": "No explicit numeric metric parsed automatically; manual curation required.",
            }
        ]
    else:
        metrics = []
        for idx, mt in enumerate(metrics_text, start=1):
            metrics.append(
                {
                    "name": f"reported_metric_{idx}",
                    "value": mt,
                    "unit": "text_span",
                    "interpretation": "Directly extracted numeric evidence from source markdown.",
                }
            )

    trajectory = [
        {
            "step_index": 1,
            "thought": abstract_text[:1200],
            "action": "problem_formulation",
            "tool": {"name": "MinerU markdown evidence extraction", "version": "agent_file_api_v1"},
            "parameters": {"paper_id": meta.get("paper_id", "")},
            "observation": "Research objective and context extracted from abstract/introduction text.",
            "outcome": "partial",
            "reasoning_tags": ["problem_definition", "evidence_based"],
        },
        {
            "step_index": 2,
            "thought": method_para[:1200],
            "action": "method_design",
            "tool": {"name": "Manual structuring assistant", "version": "v0.1"},
            "parameters": {"source": "markdown_paragraph_search"},
            "observation": selected[:1200],
            "outcome": "partial",
            "reasoning_tags": ["method_selection", "draft_from_text"],
        },
        {
            "step_index": 3,
            "thought": result_para[:1200],
            "action": "result_validation",
            "tool": {"name": "Text evidence checker", "version": "v0.1"},
            "parameters": {"numeric_span_count": len(metrics)},
            "observation": result_para[:1200],
            "outcome": "partial",
            "reasoning_tags": ["result_interpretation", "needs_manual_review"],
        },
    ]

    if records_per_paper > 1:
        keep_steps = ((variant_index - 1) % 3) + 1
        trajectory = trajectory[:keep_steps]

    paper_id = meta.get("paper_id", "paper")
    src_url = meta.get("url", "").strip()
    if not src_url:
        local_path = meta.get("local_path", "").strip()
        if local_path:
            lp = Path(local_path)
            if not lp.is_absolute():
                lp = (ROOT / lp).resolve()
            src_url = lp.as_uri()
        else:
            src_url = "https://example.org/unknown-source"

    return {
        "record_id": f"{paper_id}.draft.{variant_index:03d}",
        "track_type": "Sci-Evo",
        "domain": meta.get("domain", "unknown-domain"),
        "source": {
            "title": title,
            "url": src_url,
            "doi": meta.get("doi", ""),
            "license": "follow original paper license",
            "citation": title,
        },
        "initial_request": {
            "target_name": title,
            "input_data": abstract_text[:1200],
            "user_intent": "Extract reproducible scientific reasoning trajectory from paper text.",
            "quantifiable_goal": metrics[0]["value"] if metrics else "pending_manual_annotation",
        },
        "trajectory": trajectory,
        "success_verification": {
            "validation_technique": "Draft evidence extracted from paper markdown; manual curation still required.",
            "metrics": metrics,
            "final_verdict": "Draft record generated from authentic paper text with traceable source snippets.",
        },
        "provenance": {
            "created_at": utc_now_iso(),
            "pipeline_version": "v0.2.0",
            "mineru": {
                "used": True,
                "mode": meta.get("mode", ""),
                "task_id": meta.get("task_id", ""),
                "model_version": "agent-lightweight",
            },
            "source_span": [selected[:240]],
        },
        "quality": {
            "review_status": "draft",
            "traceability_score": 0.8,
            "completeness_score": round(len(trajectory) / 3, 3),
        },
    }


def main() -> int:
    args = parse_args()
    root = Path(args.markdown_root)
    records: list[dict[str, Any]] = []
    seen_source_keys: set[str] = set()

    for paper_dir in sorted(root.iterdir()):
        if not paper_dir.is_dir():
            continue
        meta_path = paper_dir / "meta.json"
        md_path = paper_dir / "full.md"
        if not (meta_path.exists() and md_path.exists()):
            continue
        meta = load_meta(meta_path)
        md_text = md_path.read_text(encoding="utf-8", errors="ignore")
        lines, _ = parse_markdown(md_text)
        source_title = extract_title(lines, meta.get("title", ""))
        source_key = f"{source_title.strip().lower()}|{meta.get('doi','').strip().lower()}"
        if source_key in seen_source_keys:
            continue
        seen_source_keys.add(source_key)
        for i in range(1, args.records_per_paper + 1):
            records.append(build_record(meta, md_path, i, args.records_per_paper))

    if not records:
        print(f"[WARN] no records generated from {root}")
        return 1

    out_path = write_jsonl(records, Path(args.output_jsonl))
    print(f"[DONE] wrote {len(records)} records -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
