"""Use case 1: ask the real stand lamp to turn on or off.

Unity will later call this API. The prefab does not speak KNX.
It sends JSON here, and this process asks Home Assistant, which
already holds the gateway connection and the group-address table.

Run from the repository root:

    python3 use_case_1/lamp_api.py explain on
    python3 use_case_1/lamp_api.py discover
    python3 use_case_1/lamp_api.py on
    python3 use_case_1/lamp_api.py off
    python3 use_case_1/lamp_api.py brightness 128
    python3 use_case_1/lamp_api.py serve

serve listens on http://127.0.0.1:8765
    POST /devices/lamp/set    {"value": "on"}
    POST /devices/lamp/set    {"brightness": 128}
    POST /devices/lamp/set    {"brightness_pct": 50}
    GET  /devices/lamp
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ha_client import HaError, HomeAssistant
from translate import brightness_byte, explain, explain_brightness, percent_to_brightness, switch_bit

ROOT = Path(__file__).resolve().parent
PHRASEBOOK_PATH = ROOT / "phrasebook.json"
HOST = "127.0.0.1"
PORT = 8765


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def phrasebook() -> dict:
    return json.loads(PHRASEBOOK_PATH.read_text(encoding="utf-8"))


def lamp_row() -> dict:
    row = phrasebook().get("lamp")
    if not row:
        raise SystemExit("phrasebook.json has no lamp row")
    return row


def ha_from_env() -> HomeAssistant | None:
    url = os.environ.get("HA_URL", "").strip()
    token = os.environ.get("HA_TOKEN", "").strip()
    if not url or not token:
        return None
    return HomeAssistant(url, token)


def light_snapshot(state: dict) -> dict:
    attrs = state.get("attributes") or {}
    return {
        "entity_id": state.get("entity_id"),
        "state": state.get("state"),
        "brightness": attrs.get("brightness"),
    }


def build_plan(value: str) -> dict:
    row = lamp_row()
    plan = explain(
        value,
        row.get("group_address", ""),
        row.get("ha_entity_id", ""),
        os.environ.get("HA_URL", ""),
    )
    plan["phrasebook"] = {
        "group_address": row.get("group_address", ""),
        "dpt": row.get("dpt", "1.001"),
        "ha_entity_id": row.get("ha_entity_id", ""),
        "writable": row.get("writable", False),
    }
    return plan


def build_level_plan(level: int) -> dict:
    row = lamp_row()
    plan = explain_brightness(
        level,
        row.get("ha_entity_id", ""),
        os.environ.get("HA_URL", ""),
    )
    plan["phrasebook"] = {
        "group_address": row.get("group_address", ""),
        "dpt": row.get("dpt", ""),
        "ha_entity_id": row.get("ha_entity_id", ""),
        "writable": row.get("writable", False),
    }
    return plan


def send(value: str) -> dict:
    """Translate, then perform one write. Never both entity and knx.send."""
    row = lamp_row()
    if not row.get("writable", False):
        raise SystemExit("phrasebook marks the lamp as not writable")

    bit = switch_bit(value)
    plan = build_plan(value)
    ha = ha_from_env()
    entity = row.get("ha_entity_id", "").strip()
    address = row.get("group_address", "").strip()

    if ha is None:
        plan["sent"] = False
        plan["reason"] = "HA_URL or HA_TOKEN is empty. Translation only, nothing was written."
        return plan
    if not entity and not address:
        plan["sent"] = False
        plan["reason"] = "Fill ha_entity_id or group_address in phrasebook.json. Nothing was written."
        return plan

    if entity:
        plan["sent_via"] = "light." + ("turn_on" if bit else "turn_off")
        plan["home_assistant_result"] = ha.turn_light(entity, bit == 1)
    else:
        plan["sent_via"] = "knx.send"
        plan["home_assistant_result"] = ha.send_switch(address, bit)

    plan["sent"] = True
    if entity:
        time.sleep(0.4)
        plan["state_after"] = light_snapshot(ha.entity_state(entity))
    return plan


def send_brightness(level: int) -> dict:
    """One light.turn_on with a 0–255 brightness. 0 turns the dimmer off."""
    row = lamp_row()
    if not row.get("writable", False):
        raise SystemExit("phrasebook marks the lamp as not writable")

    brightness = brightness_byte(level)
    plan = build_level_plan(brightness)
    ha = ha_from_env()
    entity = row.get("ha_entity_id", "").strip()

    if ha is None:
        plan["sent"] = False
        plan["reason"] = "HA_URL or HA_TOKEN is empty. Translation only, nothing was written."
        return plan
    if not entity:
        plan["sent"] = False
        plan["reason"] = "brightness needs ha_entity_id. A group-address bit cannot carry a level."
        return plan

    plan["sent_via"] = "light.turn_off" if brightness == 0 else "light.turn_on"
    plan["home_assistant_result"] = ha.turn_light(entity, brightness != 0, brightness)
    plan["sent"] = True
    time.sleep(0.4)
    plan["state_after"] = light_snapshot(ha.entity_state(entity))
    return plan


def discover() -> list[dict]:
    ha = ha_from_env()
    if ha is None:
        raise SystemExit("Set HA_URL and HA_TOKEN in use_case_1/.env first.")
    print(ha.ping())
    return ha.list_switchable()


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
        try:
            if path == "/devices/lamp":
                plan = build_plan("on")
                ha = ha_from_env()
                entity = lamp_row().get("ha_entity_id", "").strip()
                body = {"phrasebook": plan["phrasebook"]}
                if ha and entity:
                    snap = light_snapshot(ha.entity_state(entity))
                    body["state"] = snap["state"]
                    body["brightness"] = snap["brightness"]
                elif not ha:
                    body["state"] = None
                    body["reason"] = "HA_URL or HA_TOKEN is empty"
                else:
                    body["state"] = None
                    body["reason"] = "ha_entity_id is empty, so there is no HA state to read"
                self._json(200, body)
                return
            if path == "/health":
                self._json(200, {"ok": True})
                return
            self._json(404, {"error": "not found"})
        except (HaError, ValueError) as exc:
            self._json(502, {"error": str(exc)})

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path != "/devices/lamp/set":
            self._json(404, {"error": "not found"})
            return
        try:
            body = self._read_body()
            if "brightness" in body:
                plan = send_brightness(brightness_byte(body["brightness"]))
            elif "brightness_pct" in body:
                plan = send_brightness(percent_to_brightness(body["brightness_pct"]))
            else:
                plan = send(str(body.get("value", "")))
            status = 200 if plan.get("sent") else 409
            self._json(status, plan)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except HaError as exc:
            self._json(502, {"error": str(exc)})


def main(argv: list[str]) -> None:
    load_env()
    cmd = argv[1] if len(argv) > 1 else "explain"
    if cmd == "explain" and len(argv) > 3 and argv[2] == "brightness":
        print(json.dumps(build_level_plan(brightness_byte(int(argv[3]))), indent=2))
        return
    if cmd == "explain":
        value = argv[2] if len(argv) > 2 else "on"
        plan = build_plan(value)
        if plan["telegram"] is None and not plan["phrasebook"]["ha_entity_id"]:
            plan["example_not_your_stand"] = explain(
                value,
                "1/1/1",
                "light.example_lamp",
                "http://homeassistant.local:8123",
            )
            plan["example_not_your_stand"]["warning"] = (
                "1/1/1 and light.example_lamp are textbook values so you can see the shape. "
                "They are not the stand. Nothing is sent."
            )
        print(json.dumps(plan, indent=2))
        return
    if cmd == "brightness":
        if len(argv) < 3:
            raise SystemExit("usage: python3 use_case_1/lamp_api.py brightness 0-255")
        try:
            plan = send_brightness(brightness_byte(int(argv[2])))
        except HaError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(plan, indent=2))
        if not plan.get("sent"):
            raise SystemExit(2)
        return
    if cmd in ("on", "off"):
        try:
            plan = send(cmd)
        except HaError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(plan, indent=2))
        if not plan.get("sent"):
            raise SystemExit(2)
        return
    if cmd == "discover":
        print(json.dumps(discover(), indent=2))
        return
    if cmd == "serve":
        server = ThreadingHTTPServer((HOST, PORT), Handler)
        print(f"lamp API on http://{HOST}:{PORT}")
        server.serve_forever()
        return
    raise SystemExit("commands: explain [on|off] | explain brightness 0-255 | on | off | brightness 0-255 | discover | serve")


if __name__ == "__main__":
    main(sys.argv)
