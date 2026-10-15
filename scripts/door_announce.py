#!/usr/bin/env python3
"""
door_announce.py - says "Door is open" on the stand speaker when the door sensor opens.

Listens to Home Assistant over the WebSocket API (same as ha_twin_logger.py) and calls
tts.speak over REST. Nothing in the lab's HA config is changed.

  door sensor off -> on   ->  speaker says --message (once per opening, --cooldown seconds apart)

Usage (PowerShell, same token as the other scripts):
  $env:HA_TOKEN="<token>"
  python scripts/door_announce.py --url http://homeassistant.local:8123
  python scripts/door_announce.py --url http://homeassistant.local:8123 --test   # speak once and exit
Options: --door, --speaker, --tts, --message, --language, --volume, --cooldown.
"""
import argparse
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request

import websockets

DOOR = "binary_sensor.aqara_door_and_window_sensor_t1_door"   # Aqara Door and Window Sensor T1
SPEAKER = "media_player.famnest2"                             # Google Nest "Sonos Stand DarkNest"
TTS = "tts.google_translate_en_com"


def log(msg):
    print(msg, flush=True)


def call(args, domain, service, data):
    req = urllib.request.Request(
        f"{args.url.rstrip('/')}/api/services/{domain}/{service}",
        data=json.dumps(data).encode(), method="POST",
        headers={"Authorization": f"Bearer {args.token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            log(f"  {domain}.{service} -> HTTP {r.status}")
    except urllib.error.HTTPError as e:
        log(f"  HA error {e.code} on {domain}.{service}: {e.read().decode(errors='replace')[:200]}")
    except (urllib.error.URLError, OSError) as e:
        log(f"  cannot reach HA ({e})")


def announce(args):
    log(f"say '{args.message}' on {args.speaker}")
    if args.volume is not None:
        call(args, "media_player", "volume_set", {"entity_id": args.speaker, "volume_level": args.volume})
    call(args, "tts", "speak", {"entity_id": args.tts, "media_player_entity_id": args.speaker,
                                "message": args.message, "language": args.language})


async def run(args):
    ws_url = args.url.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
    last = 0.0
    while True:
        try:
            async with websockets.connect(ws_url, max_size=None) as ws:
                await ws.recv()
                await ws.send(json.dumps({"type": "auth", "access_token": args.token}))
                if json.loads(await ws.recv()).get("type") != "auth_ok":
                    sys.exit("Authentication failed (check HA_TOKEN).")
                await ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
                log(f"ready. watching {args.door}; Ctrl+C = stop")
                async for raw in ws:
                    m = json.loads(raw)
                    if m.get("type") != "event":
                        continue
                    d = m["event"]["data"]
                    if d.get("entity_id") != args.door:
                        continue
                    old = (d.get("old_state") or {}).get("state")
                    new = (d.get("new_state") or {}).get("state")
                    log(f"door: {old} -> {new}")
                    if old == "off" and new == "on" and time.monotonic() - last >= args.cooldown:
                        last = time.monotonic()
                        await asyncio.to_thread(announce, args)
        except (OSError, websockets.ConnectionClosed) as e:
            log(f"connection lost ({e}); retrying in 3 s")
            await asyncio.sleep(3)


def main():
    p = argparse.ArgumentParser(description="Door opens -> the speaker says 'Door is open'")
    p.add_argument("--url", required=True, help="e.g. http://homeassistant.local:8123")
    p.add_argument("--token", default=os.environ.get("HA_TOKEN"))
    p.add_argument("--door", default=DOOR)
    p.add_argument("--speaker", default=SPEAKER)
    p.add_argument("--tts", default=TTS, help="tts.* entity used to speak")
    p.add_argument("--message", default="Door is open")
    p.add_argument("--language", default="en")
    p.add_argument("--volume", type=float, default=None, help="0.0-1.0; leave out to keep the speaker's volume")
    p.add_argument("--cooldown", type=float, default=10, help="seconds between announcements")
    p.add_argument("--test", action="store_true", help="speak once and exit")
    args = p.parse_args()
    if not args.token:
        sys.exit("No token. Set HA_TOKEN or pass --token.")
    if args.test:
        announce(args)
        return
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
