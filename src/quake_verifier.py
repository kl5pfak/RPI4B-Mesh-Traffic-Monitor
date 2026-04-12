from __future__ import annotations

import argparse
import json
import random
import time
from typing import Any, Dict

import requests

from common import EVENTS_QUEUE, VERIFIED_QUEUE, append_jsonl, ensure_runtime_paths, read_new_jsonl, utc_now_iso


def verify_event_online(event: Dict[str, Any], api_url: str, timeout: float) -> Dict[str, Any]:
    try:
        response = requests.get(
            api_url,
            params={"event_id": event.get("event_id", ""), "trigger": event.get("trigger", "deskquake")},
            timeout=timeout,
        )
        details: Dict[str, Any]
        try:
            details = response.json() if response.text else {}
        except json.JSONDecodeError:
            details = {"raw": response.text[:280]}

        if response.status_code >= 400:
            return {
                "verified": False,
                "source": api_url,
                "reason": f"http_{response.status_code}",
                "details": details,
            }

        verified = bool(details.get("verified", True)) if isinstance(details, dict) else True
        return {
            "verified": verified,
            "source": details.get("source", api_url) if isinstance(details, dict) else api_url,
            "confidence": details.get("confidence", None) if isinstance(details, dict) else None,
            "details": details,
        }
    except requests.RequestException as exc:
        return {"verified": False, "source": api_url, "reason": str(exc), "details": {}}


def verify_event_mock(event: Dict[str, Any]) -> Dict[str, Any]:
    seeded = sum(ord(c) for c in event.get("event_id", ""))
    random.seed(seeded)
    verified = random.random() > 0.35
    confidence = round(random.uniform(0.62, 0.98), 3) if verified else round(random.uniform(0.15, 0.59), 3)
    return {
        "verified": verified,
        "source": "mock-verifier",
        "confidence": confidence,
        "details": {"mode": "mock"},
    }


def run(args: argparse.Namespace) -> int:
    ensure_runtime_paths()
    events_offset = 0

    print("[verifier] started", flush=True)
    while True:
        try:
            events, events_offset = read_new_jsonl(EVENTS_QUEUE, events_offset)
            for event in events:
                if "_invalid" in event:
                    continue

                if args.verify_api_url:
                    result = verify_event_online(event, args.verify_api_url, args.timeout)
                else:
                    result = verify_event_mock(event)

                output = {
                    "event_id": event.get("event_id"),
                    "verified": result.get("verified", False),
                    "verified_at": utc_now_iso(),
                    "source": result.get("source"),
                    "confidence": result.get("confidence"),
                    "reason": result.get("reason"),
                    "details": result.get("details", {}),
                }
                append_jsonl(VERIFIED_QUEUE, output)
                print(
                    f"[verifier] processed {output['event_id']} -> {'VERIFIED' if output['verified'] else 'NOT_VERIFIED'}",
                    flush=True,
                )

            time.sleep(args.poll_interval)
        except KeyboardInterrupt:
            print("\n[verifier] stopped", flush=True)
            break
        except Exception as exc:  # pragma: no cover
            print(f"[verifier] error: {exc}", flush=True)
            time.sleep(max(args.poll_interval, 1))

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeskQuake event verifier")
    parser.add_argument("--verify-api-url", default="", help="HTTP endpoint for event verification")
    parser.add_argument("--poll-interval", default=2.0, type=float, help="Polling interval in seconds")
    parser.add_argument("--timeout", default=5.0, type=float, help="HTTP request timeout")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
