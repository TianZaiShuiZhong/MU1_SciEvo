from __future__ import annotations

import json
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


class MineruError(RuntimeError):
    pass


@dataclass
class ParseResult:
    task_id: str
    state: str
    markdown_url: str | None = None
    full_zip_url: str | None = None
    err_msg: str | None = None


class MineruClient:
    """Thin client for MinerU precise API and agent API."""

    def __init__(self, token: str | None = None, timeout: int = 60):
        self.token = token
        self.timeout = timeout
        self.precise_base = "https://mineru.net/api/v4"
        self.agent_base = "https://mineru.net/api/v1/agent"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def submit_precise_task(
        self,
        file_url: str,
        model_version: str = "vlm",
        language: str = "en",
        enable_table: bool = True,
        enable_formula: bool = True,
    ) -> str:
        if not self.token:
            raise MineruError("Precise API requires MU_API_TOKEN.")
        payload = {
            "url": file_url,
            "model_version": model_version,
            "language": language,
            "enable_table": enable_table,
            "enable_formula": enable_formula,
        }
        resp = requests.post(
            f"{self.precise_base}/extract/task",
            headers=self._headers(),
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise MineruError(f"submit_precise_task failed: {body}")
        return body["data"]["task_id"]

    def query_precise_task(self, task_id: str) -> ParseResult:
        resp = requests.get(
            f"{self.precise_base}/extract/task/{task_id}",
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise MineruError(f"query_precise_task failed: {body}")
        data = body["data"]
        return ParseResult(
            task_id=data["task_id"],
            state=data["state"],
            full_zip_url=data.get("full_zip_url"),
            err_msg=data.get("err_msg"),
        )

    def wait_precise_task(self, task_id: str, max_wait_seconds: int = 900, poll_seconds: int = 5) -> ParseResult:
        start = time.time()
        while True:
            result = self.query_precise_task(task_id)
            if result.state == "done":
                return result
            if result.state == "failed":
                raise MineruError(f"task {task_id} failed: {result.err_msg}")
            elapsed = time.time() - start
            if elapsed > max_wait_seconds:
                raise MineruError(f"task {task_id} timeout after {max_wait_seconds}s")
            time.sleep(poll_seconds)

    def submit_agent_url_task(self, file_url: str) -> str:
        payload = {"url": file_url}
        resp = requests.post(
            f"{self.agent_base}/parse/url",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise MineruError(f"submit_agent_url_task failed: {body}")
        return body["data"]["task_id"]

    def submit_agent_file_task(
        self,
        file_name: str,
        language: str = "en",
        enable_table: bool = True,
        is_ocr: bool = False,
        enable_formula: bool = True,
        page_range: str | None = None,
    ) -> tuple[str, str]:
        payload: dict[str, Any] = {
            "file_name": file_name,
            "language": language,
            "enable_table": enable_table,
            "is_ocr": is_ocr,
            "enable_formula": enable_formula,
        }
        if page_range:
            payload["page_range"] = page_range
        resp = requests.post(
            f"{self.agent_base}/parse/file",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise MineruError(f"submit_agent_file_task failed: {body}")
        data = body["data"]
        return data["task_id"], data["file_url"]

    def upload_file_to_signed_url(self, signed_url: str, local_file_path: Path) -> int:
        with local_file_path.open("rb") as f:
            resp = requests.put(signed_url, data=f, timeout=self.timeout * 4)
        if not (200 <= resp.status_code < 300):
            raise MineruError(f"upload failed with status {resp.status_code}: {resp.text[:200]}")
        return resp.status_code

    def query_agent_task(self, task_id: str) -> ParseResult:
        resp = requests.get(
            f"{self.agent_base}/parse/{task_id}",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise MineruError(f"query_agent_task failed: {body}")
        data = body["data"]
        return ParseResult(
            task_id=data["task_id"],
            state=data["state"],
            markdown_url=data.get("markdown_url"),
            err_msg=data.get("err_msg"),
        )

    def wait_agent_task(self, task_id: str, max_wait_seconds: int = 300, poll_seconds: int = 3) -> ParseResult:
        start = time.time()
        while True:
            result = self.query_agent_task(task_id)
            if result.state == "done":
                return result
            if result.state == "failed":
                raise MineruError(f"agent task {task_id} failed: {result.err_msg}")
            elapsed = time.time() - start
            if elapsed > max_wait_seconds:
                raise MineruError(f"agent task {task_id} timeout after {max_wait_seconds}s")
            time.sleep(poll_seconds)

    @staticmethod
    def download_file(url: str, output_path: Path, timeout: int = 120) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            with output_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        return output_path

    @staticmethod
    def extract_markdown_from_zip(zip_path: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(output_dir)
        md_candidates = sorted(output_dir.rglob("full.md"))
        if not md_candidates:
            raise MineruError(f"No full.md found in {zip_path}")
        return md_candidates[0]

    @staticmethod
    def load_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))
