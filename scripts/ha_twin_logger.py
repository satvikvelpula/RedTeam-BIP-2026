#!/usr/bin/env python3
"""
ha_twin_logger.py - streams Home Assistant sensor states for the digital twin.

Connects to the Home Assistant WebSocket API, takes a snapshot of the selected
entities, then logs every state change as one JSON object per line (JSONL).
Optionally sends each message as a UDP datagram, so a Unity script can listen
with UdpClient and update the prefab.

Usage:
  pip install websockets
  set HA_TOKEN=<long-lived access token>        (Windows)   / export HA_TOKEN=... (Linux/macOS)
  python ha_twin_logger.py --url http://<HA-IP>:8123 --list
  python ha_twin_logger.py --url http://<HA-IP>:8123
  python ha_twin_logger.py --url http://<HA-IP>:8123 --entity binary_sensor.xxx --udp 127.0.0.1:5005

Message format (schema "twin.state.v1"):
  {
    "schema": "twin.state.v1",
    "event": "snapshot" | "change",
    "ts": "2026-10-12T11:20:01.123456+00:00",   # when HA saw the change
    "logged_at": "...",                          # when this script logged it
    "entity_id": "binary_sensor.window_door_is_open",
    "name": "Door/Window Sensor",
    "domain": "binary_sensor",
    "device_class": "door",
    "state": "on",                               # raw HA state string
    "available": true,                           # false if unavailable/unknown
    "on": true,                                  # binary_sensor only: true = open
    "number": 21.5,                              # only if the state is numeric
    "unit": "°C",                                # only if HA gives a unit
    "prev_state": "off"                          # change events only
  }
Fields are typed consistently (no field changes type), so Unity's JsonUtility can parse it.
"""
import argparse
import asyncio
import json
import os
import socket
import sys
from datetime import datetime, timezone

import websockets

OPENING_CLASSES = {"door", "window", "opening", "garage_door"}
UNAVAILABLE = {"unavailable", "unknown", None}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_msg(event, new, old=None):
    entity_id = new["entity_id"]
    domain = entity_id.split(".", 1)[0]
    attrs = new.get("attributes") or {}
    state = new.get("state")
    msg = {
        "schema": "twin.state.v1",
        "event": event,
        "ts": new.get("last_changed") or now_iso(),
        "logged_at": now_iso(),
        "entity_id": entity_id,
        "name": attrs.get("friendly_name", entity_id),
        "domain": domain,
        "device_class": attrs.get("device_class") or "",
        "state": state if state is not None else "",
        "available": state not in UNAVAILABLE,
    }
    if domain == "binary_sensor":
        msg["on"] = state == "on"
    try:
        msg["number"] = float(state)
    except (TypeError, ValueError):
        pass
    if attrs.get("unit_of_measurement"):
        msg["unit"] = attrs["unit_of_measurement"]
    if old is not None:
        msg["prev_state"] = old.get("state") or ""
    return msg


def is_wanted(state_obj, args):
    eid = state_obj["entity_id"]
    if args.all:
        return True
    if args.entity:
        return eid in args.entity
    # Default: door/window/opening sensors only.
    attrs = state_obj.get("attributes") or {}
    return eid.startswith("binary_sensor.") and attrs.get("device_class") in OPENING_CLASSES


class Output:
    def __init__(self, args):
        self.file = open(args.log, "a", encoding="utf-8") if args.log else None
        self.udp = None
        if args.udp:
            host, port = args.udp.rsplit(":", 1)
            self.udp_addr = (host, int(port))
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def emit(self, msg):
        line = json.dumps(msg, ensure_ascii=False)
        print(line, flush=True)
        if self.file:
            self.file.write(line + "\n")
            self.file.flush()
        if self.udp:
            self.udp.sendto(line.encode("utf-8"), self.udp_addr)


def print_entity_list(states):
    rows = sorted(
        (s["entity_id"], (s.get("attributes") or {}).get("device_class") or "-",
         str(s.get("state")), (s.get("attributes") or {}).get("friendly_name") or "")
        for s in states
    )
    for eid, dc, st, name in rows:
        mark = "*" if eid.startswith("binary_sensor.") and dc in OPENING_CLASSES else " "
        print(f"{mark} {eid:60} {dc:14} {st:12} {name}")
    print(f"\n{len(rows)} entities. '*' = door/window sensor (logged by default).")


async def run(args):
    ws_url = args.url.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
    out = Output(args)
    while True:
        try:
            async with websockets.connect(ws_url, max_size=None) as ws:
                await ws.recv()  # auth_required
                await ws.send(json.dumps({"type": "auth", "access_token": args.token}))
                auth = json.loads(await ws.recv())
                if auth.get("type") != "auth_ok":
                    sys.exit(f"Authentication failed: {auth.get('message', auth)}")
                print(f"# connected to {ws_url}", file=sys.stderr)

                await ws.send(json.dumps({"id": 1, "type": "get_states"}))
                if not args.list:
                    await ws.send(json.dumps(
                        {"id": 2, "type": "subscribe_events", "event_type": "state_changed"}))

                async for raw in ws:
                    m = json.loads(raw)
                    if m.get("id") == 1 and m.get("type") == "result":
                        states = m.get("result") or []
                        if args.list:
                            print_entity_list(states)
                            return
                        picked = [s for s in states if is_wanted(s, args)]
                        if not picked:
                            print("# no matching entities; run with --list to see them",
                                  file=sys.stderr)
                        for s in picked:
                            out.emit(make_msg("snapshot", s))
                    elif m.get("type") == "event":
                        data = m["event"]["data"]
                        new, old = data.get("new_state"), data.get("old_state")
                        if not new or not is_wanted(new, args):
                            continue
                        # Skip attribute-only updates (same state), e.g. battery attr refresh.
                        if old and old.get("state") == new.get("state"):
                            continue
                        out.emit(make_msg("change", new, old))
        except (OSError, websockets.ConnectionClosed) as e:
            print(f"# connection lost ({e}); retrying in 3 s", file=sys.stderr)
            await asyncio.sleep(3)


def main():
    p = argparse.ArgumentParser(description="Log Home Assistant states for the digital twin.")
    p.add_argument("--url", required=True, help="Home Assistant URL, e.g. http://192.168.46.20:8123")
    p.add_argument("--token", default=os.environ.get("HA_TOKEN"),
                   help="Long-lived access token (default: HA_TOKEN env var)")
    p.add_argument("--entity", action="append", help="Entity id to log (repeatable)")
    p.add_argument("--all", action="store_true", help="Log every entity")
    p.add_argument("--list", action="store_true", help="List all entities and exit")
    p.add_argument("--log", default="twin_states.jsonl", help="JSONL log file ('' to disable)")
    p.add_argument("--udp", help="Also send each message as UDP to host:port, e.g. 127.0.0.1:5005")
    args = p.parse_args()
    if not args.token:
        sys.exit("No token. Set HA_TOKEN or pass --token.")
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
