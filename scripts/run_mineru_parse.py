from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scievo.mineru_client import MineruClient, MineruError  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse paper files via MinerU API.")
    parser.add_argument(
        "--input-csv",
        default=str(ROOT / "configs" / "paper_urls.example.csv"),
        help="CSV with columns: paper_id,title,domain,url,doi",
    )
    parser.add_argument(
        "--mode",
        choices=["precise", "agent", "agent_file"],
        default="precise",
        help="Use precise API (token), agent URL API, or agent local-file upload API.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "data" / "interim" / "markdown"),
        help="Output directory for markdown and metadata files.",
    )
    parser.add_argument("--max-wait-seconds", type=int, default=900)
    parser.add_argument(
        "--page-range",
        default="1-20",
        help="Only for agent_file mode, e.g. 1-20. Keep within lightweight API limits.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(ROOT / ".env")
    args = parse_args()

    token = os.getenv("MU_API_TOKEN", "")
    client = MineruClient(token=token or None)
    input_csv = Path(args.input_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"[WARN] no rows found in {input_csv}")
        return 0

    errors = 0
    for row in rows:
        paper_id = row["paper_id"].strip()
        file_url = row.get("url", "").strip()
        local_path = row.get("local_path", "").strip()
        paper_dir = out_dir / paper_id
        paper_dir.mkdir(parents=True, exist_ok=True)
        display_source = local_path if args.mode == "agent_file" else file_url
        print(f"[INFO] parsing {paper_id}: {display_source}")
        try:
            if args.mode == "precise":
                task_id = client.submit_precise_task(file_url=file_url)
                result = client.wait_precise_task(task_id, max_wait_seconds=args.max_wait_seconds)
                if not result.full_zip_url:
                    raise MineruError("full_zip_url missing when precise task is done")
                zip_path = client.download_file(result.full_zip_url, paper_dir / "full.zip")
                md_path = client.extract_markdown_from_zip(zip_path, paper_dir / "unzipped")
            elif args.mode == "agent_file":
                if not local_path:
                    raise MineruError("agent_file mode requires `local_path` column in CSV")
                abs_local_path = Path(local_path)
                if not abs_local_path.is_absolute():
                    abs_local_path = (ROOT / abs_local_path).resolve()
                if not abs_local_path.is_file():
                    raise MineruError(f"local file not found: {abs_local_path}")
                task_id, signed_upload_url = client.submit_agent_file_task(
                    file_name=abs_local_path.name,
                    page_range=args.page_range,
                )
                client.upload_file_to_signed_url(signed_upload_url, abs_local_path)
                result = client.wait_agent_task(task_id, max_wait_seconds=args.max_wait_seconds)
                if not result.markdown_url:
                    raise MineruError("markdown_url missing when agent file task is done")
                md_path = client.download_file(result.markdown_url, paper_dir / "full.md")
            else:
                task_id = client.submit_agent_url_task(file_url=file_url)
                result = client.wait_agent_task(task_id, max_wait_seconds=args.max_wait_seconds)
                if not result.markdown_url:
                    raise MineruError("markdown_url missing when agent task is done")
                md_path = client.download_file(result.markdown_url, paper_dir / "full.md")

            meta = {
                "paper_id": paper_id,
                "title": row.get("title", ""),
                "domain": row.get("domain", ""),
                "url": file_url,
                "local_path": local_path,
                "doi": row.get("doi", ""),
                "task_id": task_id,
                "mode": args.mode,
                "markdown_path": str(md_path.resolve()),
            }
            (paper_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[OK] {paper_id} done -> {md_path}")
        except Exception as err:  # noqa: BLE001
            errors += 1
            print(f"[ERROR] {paper_id}: {err}")

    if errors:
        print(f"[DONE] finished with {errors} error(s)")
        return 1
    print("[DONE] all tasks completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
