from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scievo.dataset_builder import (  # noqa: E402
    generate_demo_records,
    normalize_official_case,
    read_json,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Sci-Evo demo dataset from official sample.")
    parser.add_argument(
        "--input-json",
        default=str(ROOT / "Sci-Evo_tool_case.json"),
        help="Path to official sample JSON.",
    )
    parser.add_argument(
        "--output-jsonl",
        default=str(ROOT / "data" / "processed" / "scievo_demo.jsonl"),
        help="Output jsonl path.",
    )
    parser.add_argument("--min-count", type=int, default=12, help="Minimum record count.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_json = read_json(Path(args.input_json))
    base_record = normalize_official_case(
        source_json,
        source_title="De novo design of artificial luciferases from scratch",
        source_url="https://cdn.kesci.com/admin/tcsy5zdaw/Sci-Evo-Sample.pdf",
        source_doi="10.1038/s41586-023-06268-6",
    )
    records = generate_demo_records(base_record, min_count=args.min_count)
    out = write_jsonl(records, Path(args.output_jsonl))
    print(f"[DONE] wrote {len(records)} records -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

