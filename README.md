# RPI4B Mesh Traffic Monitor

This workspace provides a lightweight gateway + verifier pipeline for Meshtastic packet intake, DeskQuake trigger detection, online verification, and screen-friendly monitoring.

## Version History

- See CHANGELOG.md for release and beta update notes.

## Project Layout

- `src/meshtastic_gateway.py`
  - Owns `/dev/ttyACM0`
  - Receives packets
  - Detects DeskQuake triggers
  - Writes event queue
  - Sends outgoing verification status messages
  - Sends emergency alerts for verified high-confidence events
- `src/quake_verifier.py`
  - Polls event queue
  - Checks online source
  - Writes result queue
- `src/deskquake_monitor.py`
  - Secondary screen monitor for live event/result output
- `data/events_queue.jsonl`
  - Event queue from gateway to verifier
- `data/verified_queue.jsonl`
  - Verification queue from verifier back to gateway/monitor
- `data/alerts_queue.jsonl`
  - Emergency alerts emitted by gateway

## Quick Start

1. Create virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run verifier:

```bash
python src/quake_verifier.py --poll-interval 2
```

3. Run gateway (new terminal):

```bash
python src/meshtastic_gateway.py --serial-port /dev/ttyACM0
```

Enable emergency alert output over mesh:

```bash
python src/meshtastic_gateway.py \
  --serial-port /dev/ttyACM0 \
  --enable-emergency-alerts \
  --alert-confidence-threshold 0.75
```

4. Run secondary monitor (third terminal):

```bash
python src/deskquake_monitor.py --watch
```

## API Verification

By default, verifier uses a resilient mock mode when no API is provided.

Use real online verification endpoint:

```bash
export VERIFY_API_URL="https://your.api/verify"
python src/quake_verifier.py --verify-api-url "$VERIFY_API_URL"
```

Expected API response (example):

```json
{
  "verified": true,
  "confidence": 0.91,
  "source": "national-seismic-db"
}
```

## Packet Input Format

The gateway accepts plain text or JSON lines from serial input.

Examples that trigger DeskQuake event detection:

- `deskquake trigger m=4.1` 
- `{"type":"deskquake","node":"alpha","magnitude":4.1}`

## Notes

- Queues are JSONL files so each service can run independently.
- For production, consider replacing file queues with Redis, MQTT, or SQLite.
- Run on Raspberry Pi with proper serial permissions (e.g. user in `dialout` group).

## Emergency Alert Behavior (Beta)

- Gateway always emits verification status lines for each verification record.
- With `--enable-emergency-alerts`, gateway also emits:
  - `EMERGENCY ALERT: DeskQuake event <event_id> verified (...)`
- Alerts are emitted only for verified events that pass the confidence threshold.
- Each event is alert-sent once per gateway process runtime.
- Alert payloads are persisted to `data/alerts_queue.jsonl` for local monitoring/auditing.

## Dashboard Integration Notes

This project now includes a live mesh dashboard with dual-source packet visibility and earthquake context overlays.

### Implemented Features

- Merged decoded messages from serial and MQTT feeds into one view.
- Cross-source deduplication for matching messages.
- Short message/noise filtering to reduce keepalive clutter.
- Node long-name enrichment from NODEINFO data.
- Enhanced map popups (source, SNR, RSSI, hops, altitude, position).
- Dark-theme UI refresh with improved panel behavior and scrolling.
- USGS earthquake integration using:
  - https://earthquake.usgs.gov/fdsnws/event/1/
- USGS map markers and 100-mile radius overlay.
- Local sensor events retained with separate color coding.
- Local panel name updated to: Local Earthquake Sensor Omron D7S.

### Data Feeds (Web)

- `decoded_messages_recent.json`: merged + deduplicated decoded messages.
- `mqtt_nodes_recent.json`: node IDs seen via MQTT.
- `usgs_quakes.json`: verified USGS earthquakes in radius window.

### Scheduled Jobs (Pi)

- `build_mqtt_nodes_json.py`: every minute.
- `build_decoded_messages.py`: every minute.
- `fetch_usgs_quakes.py`: every 5 minutes.

### Runtime Files (Pi)

- `/home/oden/bin/build_mqtt_nodes_json.py`
- `/home/oden/bin/build_decoded_messages.py`
- `/home/oden/bin/fetch_usgs_quakes.py`
- `/var/www/html/mesh/index.html`
