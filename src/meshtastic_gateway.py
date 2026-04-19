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

from common import ALERTS_QUEUE, EVENTS_QUEUE, VERIFIED_QUEUE, append_jsonl, ensure_runtime_paths, read_new_jsonl, stable_event_id, utc_now_iso

DESKQUAKE_PATTERN = re.compile(r"(deskquake|quake|shake|seismic|dq_event)", re.IGNORECASE)


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_magnitude(packet: Dict[str, Any], raw_line: str) -> Optional[float]:
    candidates = [
        packet.get("magnitude"),
        packet.get("mag"),
        (packet.get("packet") or {}).get("magnitude") if isinstance(packet.get("packet"), dict) else None,
    ]
    for candidate in candidates:
        parsed = _to_float(candidate)
        if parsed is not None:
            return parsed

    # Accept plain text patterns like: m=4.3 or magnitude: 4.3
    text_match = re.search(r"(?:m|mag|magnitude)\s*[:=]\s*(\d+(?:\.\d+)?)", raw_line, re.IGNORECASE)
    if text_match:
        return _to_float(text_match.group(1))
    return None


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
    magnitude = _extract_magnitude(packet, raw_line)
    return {
        "event_id": event_id,
        "created_at": utc_now_iso(),
        "trigger": "deskquake",
        "node": packet.get("node") or packet.get("from") or "unknown",
        "magnitude": magnitude,
        "raw": raw_line.strip(),
        "packet": packet,
    }


def emit_status(serial_conn: Any, message: str) -> None:
    text = message.strip() + "\n"
    if serial_conn is None:
        print(f"[gateway->outgoing] {text}", flush=True)
        return
    serial_conn.write(text.encode("utf-8"))


def build_alert_payload(record: Dict[str, Any], confidence_threshold: float) -> Optional[Dict[str, Any]]:
    if not record.get("verified"):
        return None

    confidence = _to_float(record.get("confidence"))
    if confidence is not None and confidence < confidence_threshold:
        return None

    event_id = str(record.get("event_id") or "unknown")
    alert_level = "high" if (confidence is not None and confidence >= 0.9) else "elevated"
    message = f"EMERGENCY ALERT: DeskQuake event {event_id} verified"
    if confidence is not None:
        message += f" (confidence={confidence:.3f})"
    return {
        "alert_id": stable_event_id(f"alert|{event_id}|{utc_now_iso()}"),
        "event_id": event_id,
        "alert_level": alert_level,
        "message": message,
        "confidence": confidence,
        "source": record.get("source"),
        "created_at": utc_now_iso(),
    }


def emit_emergency_alert(serial_conn: Any, alert: Dict[str, Any]) -> None:
    emit_status(serial_conn, alert["message"])


def run(args: argparse.Namespace) -> int:
    ensure_runtime_paths()

    verified_offset = 0
    alerted_event_ids: set[str] = set()
    serial_conn: Optional[Any] = None

    if args.serial_port == "stdin":
        print("[gateway] Reading from stdin mode", flush=True)
    else:
        if serial is None:
            print("[gateway] pyserial not installed. Use --serial-port stdin for simulation.", file=sys.stderr)
            return 2
        serial_conn = serial.Serial(args.serial_port, args.baud, timeout=1)
        print(f"[gateway] Listening on {args.serial_port} @ {args.baud}", flush=True)

    if args.enable_emergency_alerts:
        print(
            f"[gateway] emergency alerts enabled (mesh-only), confidence threshold={args.alert_confidence_threshold}",
            flush=True,
        )
    else:
        print("[gateway] emergency alerts disabled", flush=True)

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

                if not args.enable_emergency_alerts:
                    continue
                event_id = str(record.get("event_id") or "unknown")
                if event_id in alerted_event_ids:
                    continue

                alert = build_alert_payload(record, args.alert_confidence_threshold)
                if alert is None:
                    continue
                emit_emergency_alert(serial_conn, alert)
                append_jsonl(ALERTS_QUEUE, alert)
                alerted_event_ids.add(event_id)
                print(f"[gateway] emergency alert sent: {alert['alert_id']}", flush=True)

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
    parser.add_argument("--enable-emergency-alerts", action="store_true", help="Send emergency alert messages for verified events")
    parser.add_argument(
        "--alert-confidence-threshold",
        default=0.75,
        type=float,
        help="Minimum confidence required before sending emergency alert",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
