from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split dataset jsonl into train/valid/test by record_id hash.")
    parser.add_argument(
        "--input-jsonl",
        default="data/processed/scievo_multi_paper_draft.jsonl",
        help="Input dataset jsonl.",
    )
    parser.add_argument(
        "--out-dir",
        default="data/processed",
        help="Output directory for train/valid/test jsonl.",
    )
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--valid-ratio", type=float, default=0.15)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def bucket(record_id: str) -> float:
    digest = hashlib.md5(record_id.encode("utf-8")).hexdigest()  # noqa: S324
    return int(digest[:8], 16) / 0xFFFFFFFF


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_jsonl)
    out_dir = Path(args.out_dir)
    rows = load_jsonl(input_path)

    rows_sorted = sorted(rows, key=lambda r: bucket(r["record_id"]))
    n = len(rows_sorted)
    n_valid = max(1, round(n * args.valid_ratio)) if n >= 3 else 0
    n_test = max(1, n - round(n * args.train_ratio) - n_valid) if n >= 3 else 0
    n_train = n - n_valid - n_test
    if n_train < 1 and n >= 1:
        n_train = 1
        if n_valid > 0:
            n_valid -= 1
        elif n_test > 0:
            n_test -= 1

    train = rows_sorted[:n_train]
    valid = rows_sorted[n_train : n_train + n_valid]
    test = rows_sorted[n_train + n_valid : n_train + n_valid + n_test]

    write_jsonl(out_dir / "scievo_train.jsonl", train)
    write_jsonl(out_dir / "scievo_valid.jsonl", valid)
    write_jsonl(out_dir / "scievo_test.jsonl", test)

    print(f"[DONE] total={len(rows)} train={len(train)} valid={len(valid)} test={len(test)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
