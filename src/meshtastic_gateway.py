from __future__ import annotations

import argparse
import json
import re
import sys
import time
from typing import Any, Dict, Optional

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover
    serial = None

from common import EVENTS_QUEUE, VERIFIED_QUEUE, append_jsonl, ensure_runtime_paths, read_new_jsonl, stable_event_id, utc_now_iso

DESKQUAKE_PATTERN = re.compile(r"(deskquake|quake|shake|seismic|dq_event)", re.IGNORECASE)


def detect_deskquake(packet_text: str) -> bool:
    return bool(DESKQUAKE_PATTERN.search(packet_text))


def parse_packet(raw_line: str) -> Dict[str, Any]:
    stripped = raw_line.strip()
    if not stripped:
        return {}
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
            return parsed if isinstance(parsed, dict) else {"payload": parsed}
        except json.JSONDecodeError:
            pass
    return {"payload": stripped}


def build_event(packet: Dict[str, Any], raw_line: str) -> Dict[str, Any]:
    event_id = stable_event_id(f"{raw_line}|{utc_now_iso()}")
    return {
        "event_id": event_id,
        "created_at": utc_now_iso(),
        "trigger": "deskquake",
        "node": packet.get("node") or packet.get("from") or "unknown",
        "raw": raw_line.strip(),
        "packet": packet,
    }


def emit_status(serial_conn: Any, message: str) -> None:
    text = message.strip() + "\n"
    if serial_conn is None:
        print(f"[gateway->outgoing] {text}", flush=True)
        return
    serial_conn.write(text.encode("utf-8"))


def run(args: argparse.Namespace) -> int:
    ensure_runtime_paths()

    verified_offset = 0
    serial_conn: Optional[Any] = None

    if args.serial_port == "stdin":
        print("[gateway] Reading from stdin mode", flush=True)
    else:
        if serial is None:
            print("[gateway] pyserial not installed. Use --serial-port stdin for simulation.", file=sys.stderr)
            return 2
        serial_conn = serial.Serial(args.serial_port, args.baud, timeout=1)
        print(f"[gateway] Listening on {args.serial_port} @ {args.baud}", flush=True)

    while True:
        try:
            if args.serial_port == "stdin":
                raw = sys.stdin.readline()
                if not raw:
                    time.sleep(args.poll_interval)
                    continue
            else:
                assert serial_conn is not None
                raw = serial_conn.readline().decode("utf-8", errors="ignore")

            if raw.strip():
                packet = parse_packet(raw)
                if packet and detect_deskquake(raw):
                    event = build_event(packet, raw)
                    append_jsonl(EVENTS_QUEUE, event)
                    print(f"[gateway] event queued: {event['event_id']}", flush=True)

            verified_records, verified_offset = read_new_jsonl(VERIFIED_QUEUE, verified_offset)
            for record in verified_records:
                if "_invalid" in record:
                    continue
                status = "VERIFIED" if record.get("verified") else "NOT_VERIFIED"
                outgoing = f"deskquake {record.get('event_id', 'unknown')} {status}"
                emit_status(serial_conn, outgoing)

            time.sleep(args.poll_interval)
        except KeyboardInterrupt:
            print("\n[gateway] Stopped", flush=True)
            break
        except Exception as exc:  # pragma: no cover
            print(f"[gateway] error: {exc}", file=sys.stderr, flush=True)
            time.sleep(max(args.poll_interval, 1))

    if serial_conn is not None:
        serial_conn.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Meshtastic gateway for DeskQuake event pipeline")
    parser.add_argument("--serial-port", default="/dev/ttyACM0", help="Serial device path or 'stdin' for test mode")
    parser.add_argument("--baud", default=115200, type=int, help="Serial baud rate")
    parser.add_argument("--poll-interval", default=0.4, type=float, help="Loop sleep interval in seconds")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
