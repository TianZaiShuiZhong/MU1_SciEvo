from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://api.sciverse.space"


class SciverseError(RuntimeError):
    pass


@dataclass
class QueryItem:
    query: str
    domain: str
    top_k: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import independent paper sources from Sciverse API into data/interim/markdown."
    )
    parser.add_argument(
        "--queries-csv",
        default=str(ROOT / "configs" / "sciverse_queries.csv"),
        help="CSV with columns: query,domain,top_k",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=12,
        help="Maximum unique docs to import.",
    )
    parser.add_argument(
        "--max-per-query",
        type=int,
        default=0,
        help="Optional cap for imported docs per query (0 means no cap).",
    )
    parser.add_argument(
        "--content-limit",
        type=int,
        default=3000,
        help="Chunk size per /content request.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=15000,
        help="Maximum characters to fetch per doc.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.2,
        help="Sleep between API calls to reduce rate-limit risk.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries for transient network/server errors.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "data" / "interim" / "markdown"),
        help="Output root with <paper_id>/full.md and meta.json.",
    )
    return parser.parse_args()


def load_token() -> str:
    load_dotenv(ROOT / ".env")
    token = os.getenv("SCIVERSE_API_TOKEN", "").strip()
    if token:
        return token

    api_txt = ROOT / "api.txt"
    if api_txt.exists():
        text = api_txt.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"Sciverse_API=([^\r\n]+)", text)
        if match:
            return match.group(1).strip()

    raise SciverseError("SCIVERSE_API_TOKEN not found. Set .env or api.txt.")


def load_queries(csv_path: Path) -> list[QueryItem]:
    rows: list[QueryItem] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = (row.get("query") or "").strip()
            if not query:
                continue
            domain = (row.get("domain") or "unknown-domain").strip()
            top_k_str = (row.get("top_k") or "8").strip()
            top_k = int(top_k_str) if top_k_str.isdigit() else 8
            rows.append(QueryItem(query=query, domain=domain, top_k=max(1, min(top_k, 100))))
    if not rows:
        raise SciverseError(f"No query rows found in {csv_path}")
    return rows


def sciverse_post(path: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(f"{API_BASE}{path}", headers=headers, json=payload, timeout=90)
    if resp.status_code >= 400:
        raise SciverseError(f"POST {path} failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def sciverse_get(path: str, token: str, params: dict[str, Any]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{API_BASE}{path}", headers=headers, params=params, timeout=90)
    if resp.status_code >= 400:
        raise SciverseError(f"GET {path} failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def request_with_retry(
    fn,
    *,
    max_retries: int,
    retry_sleep: float,
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> dict[str, Any]:
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except requests.HTTPError as err:
            last_err = err
            code = getattr(err.response, "status_code", None)
            if code not in retryable_status_codes or attempt >= max_retries:
                raise
        except requests.RequestException as err:
            last_err = err
            if attempt >= max_retries:
                raise
        except SciverseError as err:
            last_err = err
            msg = str(err)
            if attempt >= max_retries:
                raise
            if not any(f"({c})" in msg for c in retryable_status_codes):
                raise
        sleep_s = retry_sleep * (2**attempt)
        time.sleep(sleep_s)
    if last_err:
        raise last_err
    raise SciverseError("unknown retry failure")


def fetch_content(token: str, doc_id: str, limit: int, max_chars: int, sleep_seconds: float) -> str:
    offset = 0
    chunks: list[str] = []
    while True:
        data = sciverse_get(
            "/content",
            token=token,
            params={"doc_id": doc_id, "offset": offset, "limit": limit},
        )
        text = data.get("text", "") or ""
        if text:
            chunks.append(text)
        chars_returned = int(data.get("chars_returned") or len(text))
        more = bool(data.get("more"))
        next_offset = int(data.get("next_offset") or (offset + chars_returned))

        total = sum(len(c) for c in chunks)
        if not more or chars_returned <= 0 or total >= max_chars:
            break
        offset = next_offset
        time.sleep(sleep_seconds)
    joined = "\n\n".join(chunks)
    return joined[:max_chars]


def paper_id_from_doc_id(doc_id: str) -> str:
    digest = hashlib.sha1(doc_id.encode("utf-8")).hexdigest()[:10]
    return f"paper_scv_{digest}"


def existing_doc_ids(out_root: Path) -> set[str]:
    ids: set[str] = set()
    if not out_root.exists():
        return ids
    for meta_path in out_root.glob("*/meta.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        task_id = str(data.get("task_id", "")).strip()
        mode = str(data.get("mode", "")).strip()
        if task_id and mode.startswith("sciverse"):
            ids.add(task_id)
    return ids


def existing_title_keys(out_root: Path) -> set[str]:
    keys: set[str] = set()
    if not out_root.exists():
        return keys
    for meta_path in out_root.glob("*/meta.json"):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        title = str(data.get("title", "")).strip().lower()
        if title:
            keys.add(title)
    return keys


def main() -> int:
    args = parse_args()
    token = load_token()
    queries = load_queries(Path(args.queries_csv))
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    seen_doc_ids = existing_doc_ids(out_root)
    seen_titles = existing_title_keys(out_root)
    selected: list[dict[str, Any]] = []

    for item in queries:
        print(f"[INFO] query: {item.query} (domain={item.domain}, top_k={item.top_k})")
        payload = {"query": item.query, "top_k": item.top_k}
        body = request_with_retry(
            lambda: sciverse_post("/agentic-search", token=token, payload=payload),
            max_retries=args.max_retries,
            retry_sleep=args.sleep_seconds,
        )
        hits = body.get("hits", []) or []
        added_in_query = 0
        for hit in hits:
            doc_id = str(hit.get("doc_id", "")).strip()
            title = str(hit.get("title", "")).strip()
            title_key = title.lower()
            if not doc_id or doc_id in seen_doc_ids:
                continue
            if not title:
                continue
            if title_key in seen_titles:
                continue
            selected.append(
                {
                    "doc_id": doc_id,
                    "title": title,
                    "abstract": str(hit.get("abstract", "") or "").strip(),
                    "domain": item.domain,
                    "query": item.query,
                    "score": hit.get("score"),
                    "chunk": str(hit.get("chunk", "") or "").strip(),
                    "source_type": str(hit.get("source_type", "") or "").strip(),
                    "page_no": hit.get("page_no"),
                }
            )
            seen_doc_ids.add(doc_id)
            seen_titles.add(title_key)
            added_in_query += 1
            if args.max_per_query > 0 and added_in_query >= args.max_per_query:
                break
            if len(selected) >= args.max_docs:
                break
        if len(selected) >= args.max_docs:
            break
        time.sleep(args.sleep_seconds)

    if not selected:
        print("[WARN] no new docs selected from Sciverse")
        return 0

    summary_rows = []
    for idx, item in enumerate(selected, start=1):
        doc_id = item["doc_id"]
        title = item["title"]
        paper_id = paper_id_from_doc_id(doc_id)
        paper_dir = out_root / paper_id
        paper_dir.mkdir(parents=True, exist_ok=True)

        print(f"[INFO] fetching content ({idx}/{len(selected)}): {paper_id} | {title[:80]}")
        try:
            content = request_with_retry(
                lambda: fetch_content(
                    token=token,
                    doc_id=doc_id,
                    limit=args.content_limit,
                    max_chars=args.max_chars,
                    sleep_seconds=args.sleep_seconds,
                ),
                max_retries=args.max_retries,
                retry_sleep=args.sleep_seconds,
            )
        except Exception as err:  # noqa: BLE001
            print(f"[ERROR] content fetch failed for {doc_id}: {err}")
            continue

        if not content.strip():
            print(f"[WARN] empty content for {doc_id}, skip")
            continue

        md_text = f"# {title}\n\n{content}\n"
        md_path = paper_dir / "full.md"
        md_path.write_text(md_text, encoding="utf-8")

        meta = {
            "paper_id": paper_id,
            "title": title,
            "domain": item["domain"],
            "url": f"https://api.sciverse.space/content?doc_id={doc_id}",
            "local_path": "",
            "doi": "",
            "task_id": doc_id,
            "mode": "sciverse_content_v1",
            "markdown_path": str(md_path.resolve()),
            "source_type": item["source_type"],
            "query": item["query"],
            "search_score": item["score"],
            "page_no": item["page_no"],
            "seed_chunk": item["chunk"][:400],
            "abstract": item["abstract"][:1200],
        }
        (paper_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_rows.append(meta)
        time.sleep(args.sleep_seconds)

    summary_path = ROOT / "data" / "interim" / "sciverse_import_summary.jsonl"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        for row in summary_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[DONE] imported {len(summary_rows)} docs -> {out_root}")
    print(f"[DONE] summary -> {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
