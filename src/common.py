from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
EVENTS_QUEUE = DATA_DIR / "events_queue.jsonl"
VERIFIED_QUEUE = DATA_DIR / "verified_queue.jsonl"
ALERTS_QUEUE = DATA_DIR / "alerts_queue.jsonl"


def ensure_runtime_paths() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    EVENTS_QUEUE.touch(exist_ok=True)
    VERIFIED_QUEUE.touch(exist_ok=True)
    ALERTS_QUEUE.touch(exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_new_jsonl(path: Path, offset: int) -> tuple[List[Dict[str, Any]], int]:
    records: List[Dict[str, Any]] = []
    new_offset = offset
    with path.open("r", encoding="utf-8") as f:
        f.seek(offset)
        while True:
            line = f.readline()
            if not line:
                break
            new_offset = f.tell()
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"_invalid": line})
    return records, new_offset


def stable_event_id(raw_text: str) -> str:
    digest = hashlib.sha1(raw_text.encode("utf-8")).hexdigest()[:12]
    return f"dq-{digest}"
