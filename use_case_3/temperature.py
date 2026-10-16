"""Use case 3: read room temperature and sound the siren above the high limit.

Unity will GET the JSON. This script does not draw the virtual sensor.
A live reading turns the frient SMSZB-120 siren on while the measured
temperature is above high_c, and turns it off when the reading comes back down.
feed only classifies a number locally and does not touch the siren.

    python3 use_case_3/temperature.py read
    python3 use_case_3/temperature.py feed 26.5
    python3 use_case_3/temperature.py feed 17
    python3 use_case_3/temperature.py serve

serve listens on http://127.0.0.1:8766 and re-reads Home Assistant every 5 s.
Each read logs the measured temperature and the target temperature.
    GET  /devices/temperature          latest reading
    POST /devices/temperature/set      {"temperature_c": 22}   writes the thermostat target
    POST /devices/temperature/feed     {"temperature_c": 26.5}   local band check only

Credentials come from use_case_1/.env (HA_URL, HA_TOKEN).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "use_case_1"))

from ha_client import HaError, HomeAssistant  # noqa: E402

PHRASEBOOK_PATH = ROOT / "phrasebook.json"
HOST = "127.0.0.1"
PORT = 8766
POLL_SECONDS = 5

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("temperature")


def load_env() -> None:
    for env_path in (ROOT / ".env", REPO / "use_case_1" / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    # no .env: HA_TOKEN from the PowerShell window ($env:HA_TOKEN), lab Home Assistant by default
    os.environ.setdefault("HA_URL", "http://homeassistant.local:8123")


def device_row() -> dict:
    book = json.loads(PHRASEBOOK_PATH.read_text(encoding="utf-8"))
    row = book.get("temperature")
    if not row:
        raise SystemExit("phrasebook.json has no temperature row")
    return row


def ha_from_env() -> HomeAssistant | None:
    url = os.environ.get("HA_URL", "").strip()
    token = os.environ.get("HA_TOKEN", "").strip()
    if not url or not token:
        return None
    return HomeAssistant(url, token)


def classify(temperature_c: float, low_c: float, high_c: float) -> str:
    """higher than high_c -> high, lower than low_c -> low, otherwise ok."""
    if temperature_c > high_c:
        return "high"
    if temperature_c < low_c:
        return "low"
    return "ok"


def log_sample(payload: dict) -> None:
    """Print the measured value and the target on every read."""
    measured = float(payload["temperature_c"])
    target = payload.get("target_c")
    target_text = "none" if target is None else f"{float(target):.1f} °C"
    status = payload["status"]
    low_c = float(payload["low_c"])
    high_c = float(payload["high_c"])
    siren = payload.get("siren_state")
    siren_text = f", siren {siren}" if siren else ""
    if status == "high":
        log.warning(
            "measured %.1f °C, target %s, above %.1f °C%s",
            measured, target_text, high_c, siren_text,
        )
    elif status == "low":
        log.warning(
            "measured %.1f °C, target %s, below %.1f °C%s",
            measured, target_text, low_c, siren_text,
        )
    else:
        log.info(
            "measured %.1f °C, target %s, inside %.1f–%.1f °C%s",
            measured, target_text, low_c, high_c, siren_text,
        )


def build_reading(temperature_c: float, source: str) -> dict:
    row = device_row()
    low_c = float(row["low_c"])
    high_c = float(row["high_c"])
    status = classify(temperature_c, low_c, high_c)
    return {
        "device": row["name"],
        "knx_individual_address": row.get("knx_individual_address", ""),
        "ha_entity_id": row.get("ha_entity_id", ""),
        "temperature_c": temperature_c,
        "unit": row.get("unit", "°C"),
        "low_c": low_c,
        "high_c": high_c,
        "status": status,
        "warning": status == "high",
        "siren_entity_id": row.get("siren_entity_id", ""),
        "siren_state": None,
        "source": source,
    }


def reading(temperature_c: float, source: str) -> dict:
    payload = build_reading(temperature_c, source)
    log_sample(payload)
    return payload


class Latest:
    """The most recent live reading. The poll thread writes it; GET reads it."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload: dict | None = None
        self._status: str | None = None

    def get(self) -> dict | None:
        with self._lock:
            return self._payload

    def update(self, payload: dict) -> bool:
        """Store the reading. Return True when the band changed."""
        with self._lock:
            changed = payload["status"] != self._status
            self._payload = payload
            self._status = payload["status"]
            return changed


LATEST = Latest()


def parse_temperature(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("temperature_c must be a number")
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError("temperature_c must be a number") from exc


def reading_from_live() -> dict:
    payload = read_live()
    log_sample(payload)
    return payload


def read_live() -> dict:
    row = device_row()
    entity = row.get("ha_entity_id", "").strip()
    ha = ha_from_env()
    if not entity:
        raise RuntimeError(
            "ha_entity_id is empty. 1.1.15 is the KNX individual address of the "
            "Room Control Unit, not a Home Assistant entity. Paste the temperature "
            "sensor id into use_case_3/phrasebook.json. Until then, use feed."
        )
    if ha is None:
        raise RuntimeError("HA_URL or HA_TOKEN is empty")
    state = ha.entity_state(entity)
    raw = state.get("state")
    if raw in (None, "unknown", "unavailable"):
        raise RuntimeError(f"{entity} state is {raw}")
    payload = build_reading(parse_temperature(raw), "home_assistant")
    payload.update(target_fields(ha))
    row = device_row()
    target = payload.get("target_c")
    if row.get("alarm_on_target", False) and target is not None and float(target) > float(row["high_c"]):
        # demo rule: a setpoint above the limit (e.g. raised in VR) is also an over-temperature alarm
        payload["warning"] = True
        payload["alarm_reason"] = "target"
    elif payload["warning"]:
        payload["alarm_reason"] = "measured"
    with ALARM_LOCK:
        apply_alarm_lights(ha, payload)
        apply_siren(ha, payload)
    return payload


ALARM_LOCK = threading.Lock()
ALARM_SAVED: dict | None = None   # light states before the alarm, None while no alarm is active


def apply_alarm_lights(ha: HomeAssistant, payload: dict) -> None:
    """Alarm on: lights in alarm_lights_off go off, alarm_red_lights go solid red. Alarm off: put them back."""
    global ALARM_SAVED
    row = device_row()
    off_list = [e for e in row.get("alarm_lights_off", []) if e]
    red_list = [e for e in row.get("alarm_red_lights", []) if e]
    if not off_list and not red_list:
        return
    if payload.get("warning") and ALARM_SAVED is None:
        saved = {}
        for entity in off_list + red_list:
            try:
                saved[entity] = ha.entity_state(entity)
            except HaError as exc:
                log.warning("alarm: cannot read %s: %s", entity, exc)
        ALARM_SAVED = saved
        log.warning("alarm lights: %s off, %s red", ", ".join(off_list) or "-", ", ".join(red_list) or "-")
        for entity in off_list:
            _try(ha.call_service, "light", "turn_off", {"entity_id": entity})
        for entity in red_list:
            _try(ha.call_service, "light", "turn_on", {"entity_id": entity, "rgb_color": [255, 0, 0], "brightness": 255})
    elif not payload.get("warning") and ALARM_SAVED is not None:
        restore_alarm_lights(ha)


def restore_alarm_lights(ha: HomeAssistant) -> None:
    global ALARM_SAVED
    saved, ALARM_SAVED = ALARM_SAVED or {}, None
    log.info("alarm over: restoring %s", ", ".join(saved) or "nothing")
    for entity, obj in saved.items():
        state = (obj or {}).get("state")
        attrs = (obj or {}).get("attributes") or {}
        if state == "on":
            data = {"entity_id": entity}
            for key in ("rgb_color", "brightness"):
                if attrs.get(key) is not None:
                    data[key] = attrs[key]
            _try(ha.call_service, "light", "turn_on", data)
        elif state == "off":
            _try(ha.call_service, "light", "turn_off", {"entity_id": entity})


def _try(fn, *args) -> None:
    try:
        fn(*args)
    except HaError as exc:
        log.warning("alarm: %s", exc)


def apply_siren(ha: HomeAssistant, payload: dict) -> None:
    """Turn the siren on only while warning is true. Leave it alone when it already matches."""
    entity = str(payload.get("siren_entity_id") or "").strip()
    if not entity:
        return
    want = "on" if payload.get("warning") else "off"
    try:
        current = ha.entity_state(entity).get("state")
    except HaError as exc:
        log.warning("siren read failed: %s", exc)
        return
    if current in (None, "unknown", "unavailable"):
        log.warning("siren %s is %s", entity, current)
        payload["siren_state"] = current
        return
    if current == want:
        payload["siren_state"] = current
        return
    try:
        ha.set_siren(entity, want == "on")
    except HaError as exc:
        log.warning("siren command failed: %s", exc)
        payload["siren_state"] = current
        return
    payload["siren_state"] = want
    if want == "on":
        log.warning("siren on: measured above %.1f °C", float(payload["high_c"]))
    else:
        log.info("siren off: measured back inside the band")


def target_fields(ha: HomeAssistant) -> dict:
    entity = device_row().get("climate_entity_id", "").strip()
    if not entity:
        return {"target_c": None, "hvac_mode": None}
    state = ha.entity_state(entity)
    attrs = state.get("attributes") or {}
    return {"target_c": attrs.get("temperature"), "hvac_mode": state.get("state")}


def set_target(temperature_c: float) -> dict:
    """Write the virtual setpoint to the thermostat. The measured sensor stays a read."""
    row = device_row()
    entity = row.get("climate_entity_id", "").strip()
    if not entity:
        raise RuntimeError("climate_entity_id is empty")
    minimum = float(row.get("min_c", 5))
    maximum = float(row.get("max_c", 35))
    if not minimum <= temperature_c <= maximum:
        raise ValueError(f"target must be between {minimum:g} and {maximum:g} °C")
    ha = ha_from_env()
    if ha is None:
        raise RuntimeError("HA_URL or HA_TOKEN is empty")
    previous = target_fields(ha).get("target_c")
    previous_text = "none" if previous is None else f"{float(previous):.1f} °C"
    ha.set_temperature(entity, temperature_c)
    log.info("target changed from %s to %.1f °C", previous_text, temperature_c)
    time.sleep(0.6)
    payload = read_live()
    payload["requested_c"] = temperature_c
    payload["source"] = "set"
    log_sample(payload)
    LATEST.update(payload)
    return payload


def _temp_text(value: object) -> str:
    if value is None:
        return "none"
    return f"{float(value):.1f} °C"


def _same_temp(left: object, right: object) -> bool:
    if left is None or right is None:
        return left is right
    return round(float(left), 1) == round(float(right), 1)


def watch(interval: float) -> None:
    """Ask Home Assistant on a timer and log measured plus target every time."""
    log.info("watching temperature every %.0f s", interval)
    previous_target = None
    previous_measured = None
    seen = False
    while True:
        try:
            payload = read_live()
        except Exception as exc:   # any error (timeout, dropped connection): log it and keep watching
            log.warning("temperature read failed: %s", exc)
        else:
            target = payload.get("target_c")
            measured = payload.get("temperature_c")
            if seen and not _same_temp(previous_target, target):
                log.info(
                    "target changed from %s to %s",
                    _temp_text(previous_target),
                    _temp_text(target),
                )
            if seen and not _same_temp(previous_measured, measured):
                log.info(
                    "measured changed from %s to %s",
                    _temp_text(previous_measured),
                    _temp_text(measured),
                )
            LATEST.update(payload)
            log_sample(payload)
            previous_target = target
            previous_measured = measured
            seen = True
        time.sleep(interval)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, status: int, payload: object) -> None:
        raw = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        if length > 4096:
            raise ValueError("body too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/health":
            self._json(200, {"ok": True})
            return
        if path != "/devices/temperature":
            self._json(404, {"error": "not found"})
            return
        cached = LATEST.get()
        if cached is not None:
            self._json(200, cached)
            return
        try:
            self._json(200, read_live())
        except (HaError, RuntimeError, ValueError) as exc:
            self._json(409, {"error": str(exc), "phrasebook": device_row()})

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        path_ok = path in ("/devices/temperature/feed", "/devices/temperature/set")
        if not path_ok:
            self._json(404, {"error": "not found"})
            return
        try:
            body = self._read_body()
            value = parse_temperature(body.get("temperature_c"))
            if path.endswith("/set"):
                self._json(200, set_target(value))
            else:
                self._json(200, reading(value, "manual"))
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except (HaError, RuntimeError) as exc:
            self._json(502, {"error": str(exc)})


def main(argv: list[str]) -> None:
    load_env()
    cmd = argv[1] if len(argv) > 1 else "read"
    if cmd == "read":
        try:
            print(json.dumps(reading_from_live(), indent=2))
        except (HaError, RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        return
    if cmd == "set":
        if len(argv) < 3:
            raise SystemExit("usage: python3 use_case_3/temperature.py set 22")
        try:
            print(json.dumps(set_target(parse_temperature(argv[2])), indent=2))
        except (HaError, RuntimeError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        return
    if cmd == "feed":
        if len(argv) < 3:
            raise SystemExit("usage: python3 use_case_3/temperature.py feed 26.5")
        print(json.dumps(reading(parse_temperature(argv[2]), "manual"), indent=2))
        return
    if cmd == "serve":
        threading.Thread(target=watch, args=(POLL_SECONDS,), daemon=True).start()
        server = ThreadingHTTPServer((HOST, PORT), Handler)
        print(f"temperature API on http://{HOST}:{PORT}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            ha = ha_from_env()
            if ha is not None and ALARM_SAVED is not None:   # Ctrl+C during an alarm: siren off, lights back
                siren = device_row().get("siren_entity_id", "")
                if siren:
                    _try(ha.set_siren, siren, False)
                restore_alarm_lights(ha)
        return
    raise SystemExit("commands: read | set <celsius> | feed <celsius> | serve")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        assert classify(25, 18, 25) == "ok"
        assert classify(25.1, 18, 25) == "high"
        assert classify(17.9, 18, 25) == "low"
        sample = build_reading(22.0, "manual")
        assert sample["warning"] is False
        assert sample["siren_state"] is None
        assert sample["siren_entity_id"] == "siren.frient_a_s_smszb_120_siren"
        assert LATEST.update(sample) is True
        assert LATEST.update(build_reading(22.4, "manual")) is False
        hot = build_reading(26.0, "manual")
        assert hot["warning"] is True
        assert LATEST.update(hot) is True
        assert LATEST.get()["status"] == "high"
        print("temperature checks passed")
    else:
        main(sys.argv)
