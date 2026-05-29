from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scievo.validator import validate_records  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Sci-Evo dataset jsonl with schema.")
    parser.add_argument(
        "--schema",
        default=str(ROOT / "schemas" / "scievo.schema.json"),
        help="Schema json path.",
    )
    parser.add_argument(
        "--dataset",
        default=str(ROOT / "data" / "processed" / "scievo_demo.jsonl"),
        help="Dataset jsonl path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate_records(Path(args.schema), Path(args.dataset))
    if errors:
        print("[FAIL] validation errors:")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("[PASS] dataset is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

