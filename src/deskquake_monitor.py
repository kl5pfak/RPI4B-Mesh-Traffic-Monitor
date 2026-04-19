from __future__ import annotations

import argparse
import time
from typing import Any, Dict

from common import ALERTS_QUEUE, EVENTS_QUEUE, VERIFIED_QUEUE, ensure_runtime_paths, read_new_jsonl


def render_row(record: Dict[str, Any]) -> str:
    event_id = str(record.get("event_id", "-")).ljust(16)
    verified = str(record.get("verified", "-")).ljust(10)
    source = str(record.get("source", "-")).ljust(22)
    confidence = str(record.get("confidence", "-")).ljust(8)
    verified_at = str(record.get("verified_at", "-"))
    return f"{event_id} {verified} {source} {confidence} {verified_at}"


def run(args: argparse.Namespace) -> int:
    ensure_runtime_paths()
    events_offset = 0
    verified_offset = 0
    alerts_offset = 0

    print("[monitor] watching queues", flush=True)
    print("event_id          verified   source                 confidence verified_at", flush=True)
    print("-" * 88, flush=True)

    while True:
        try:
            events, events_offset = read_new_jsonl(EVENTS_QUEUE, events_offset)
            verified, verified_offset = read_new_jsonl(VERIFIED_QUEUE, verified_offset)
            alerts, alerts_offset = read_new_jsonl(ALERTS_QUEUE, alerts_offset)

            for event in events:
                if "_invalid" in event:
                    continue
                print(f"[event] {event.get('event_id')} trigger={event.get('trigger')} node={event.get('node')}", flush=True)

            for result in verified:
                if "_invalid" in result:
                    continue
                print(render_row(result), flush=True)

            for alert in alerts:
                if "_invalid" in alert:
                    continue
                print(
                    f"[alert] {alert.get('alert_id')} level={alert.get('alert_level')} event={alert.get('event_id')} msg={alert.get('message')}",
                    flush=True,
                )

            if not args.watch:
                break
            time.sleep(args.poll_interval)
        except KeyboardInterrupt:
            print("\n[monitor] stopped", flush=True)
            break

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DeskQuake secondary event monitor")
    parser.add_argument("--watch", action="store_true", help="Continuously watch for queue updates")
    parser.add_argument("--poll-interval", default=1.0, type=float, help="Watch poll interval")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
