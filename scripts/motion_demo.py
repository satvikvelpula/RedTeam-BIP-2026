#!/usr/bin/env python3
"""
motion_demo.py - demo: motion sensor -> window shade DOWN, RGB strip RED while the shade is down.

Listens to Home Assistant over the WebSocket API (same as ha_twin_logger.py)
and calls HA services over REST. Nothing in the lab's HA config is changed.

  motion "on"                      -> cover.close_cover (shade down)
  motion "off" for --off-delay s   -> cover.open_cover (shade up)
  shade "closed"                   -> strip RED
  shade "open"/"opening"/"closing" -> strip GREEN
  (with --green <entity>: a second strip shows green and the first one turns off)
  shade "closed"                   -> jazz radio on the speaker (--speaker), quiet volume
  shade "open"/"opening"/"closing" -> jazz stops
  press Enter in this window       -> run the "motion" scene by hand (for a busy room)
  Ctrl+C                           -> restore the strip and the shade to how they were at start

If motion is already "on" when the script starts, the scene runs right away.

Usage (PowerShell, same window/token as the logger):
  $env:HA_TOKEN="<token>"
  python motion_demo.py --url http://homeassistant.local:8123
Options: --motion, --rgb, --green, --cover to use other entities; --off-delay seconds.

Which light is which strip? Run
  python motion_demo.py --url http://homeassistant.local:8123 --identify
It turns every available light on (green if it can) for 3 s, one by one,
prints its entity_id, and puts it back as it was.

Test the speaker alone (plays jazz for 20 s, then stops):
  python motion_demo.py --url http://homeassistant.local:8123 --jazz-test
Other speakers in the lab HA: media_player.kitchen, media_player.roam_2_2 (Sonos, need an x-rincon-mp3radio:// URL),
media_player.famnest2, media_player.googlehome6580 (Nest), media_player.home_group.
"""
import argparse
import asyncio
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

import websockets

MOTION = "binary_sensor.motion_sensor"   # Aqara Motion Sensor P1 (re-added 13 Oct; mirror: binary_sensor.aqara_motion_sensor_p1_occupancy)
RGB = "light.rgbw_controller_2"   # Fibaro RGBW Controller 2 (Z-Wave) driving the LED strip
RED = [255, 0, 0]
GREEN = [0, 255, 0]
COVER = "cover.aqara_roller_shade_driver_e1"
SPEAKER = "media_player.famnest2"   # Google Nest "Sonos Stand DarkNest" (tested: plays the stream)
JAZZ_URL = "https://stream.srg-ssr.ch/m/rsj/mp3_128"   # Radio Swiss Jazz, public MP3 stream


def log(msg):
    print(msg, flush=True)


def call(args, domain, service, entity_id, **extra):
    """Call an HA service over REST (blocking)."""
    url = f"{args.url.rstrip('/')}/api/services/{domain}/{service}"
    req = urllib.request.Request(
        url, data=json.dumps({"entity_id": entity_id, **extra}).encode(), method="POST",
        headers={"Authorization": f"Bearer {args.token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            log(f"  {domain}.{service} {entity_id} {extra or ''}-> HTTP {r.status}")
    except urllib.error.HTTPError as e:
        log(f"  HA error {e.code} on {domain}.{service} {entity_id}: {e.read().decode(errors='replace')[:200]}")
    except (urllib.error.URLError, OSError) as e:
        log(f"  cannot reach HA ({e})")


class Demo:
    def __init__(self, args):
        self.args = args
        self.initial = {}       # entity_id -> full state object at start, for restore
        self.strip_on = {}      # strip entity -> last on/off we sent
        self.jazz_on = None     # last jazz on/off we sent
        self.active = False     # scene currently applied
        self.off_task = None

    async def scene_on(self, why):
        if self.off_task:
            self.off_task.cancel()
            self.off_task = None
        if self.active:
            return
        self.active = True
        log(f"MOTION ({why}) -> shade DOWN")
        await asyncio.to_thread(call, self.args, "cover", "close_cover", self.args.cover)

    def motion_cleared(self):
        if self.active and not self.off_task:
            log(f"no motion -> shade UP in {self.args.off_delay:g} s")
            self.off_task = asyncio.ensure_future(self._scene_off_later())

    async def _scene_off_later(self):
        try:
            await asyncio.sleep(self.args.off_delay)
        except asyncio.CancelledError:
            return
        self.off_task = None
        self.active = False
        log("CLEAR -> shade UP")
        await asyncio.to_thread(call, self.args, "cover", "open_cover", self.args.cover)

    async def set_strip(self, entity, on, color):
        if not entity or self.strip_on.get(entity) == on:
            return
        self.strip_on[entity] = on
        if on:
            await asyncio.to_thread(call, self.args, "light", "turn_on", entity,
                                    rgb_color=color, brightness=255)
        else:
            await asyncio.to_thread(call, self.args, "light", "turn_off", entity)

    async def set_jazz(self, on):
        if not self.args.speaker or self.jazz_on == on:
            return
        started_by_us = self.jazz_on is True
        self.jazz_on = on
        if not on and not started_by_us:
            return  # never stop music we did not start
        if on:
            log(f"shade DOWN -> jazz on {self.args.speaker}")
            await asyncio.to_thread(jazz_start, self.args)
        else:
            log("shade not down -> jazz stop")
            await asyncio.to_thread(call, self.args, "media_player", "media_stop", self.args.speaker)

    async def on_cover_state(self, state):
        """Red strip while the shade is down; green strip while it is up or moving."""
        if state not in ("closed", "open", "opening", "closing"):
            return
        down = state == "closed"
        await self.set_jazz(down)
        if not self.args.green:  # one strip: red when down, green otherwise
            color = RED if down else GREEN
            if self.strip_on.get(self.args.rgb) == color:
                return
            self.strip_on[self.args.rgb] = color
            log(f"shade {state} -> strip {'RED' if down else 'GREEN'}")
            await asyncio.to_thread(call, self.args, "light", "turn_on", self.args.rgb,
                                    rgb_color=color, brightness=255)
            return
        log(f"shade {state} -> " + ("RED strip on, green off" if down else "GREEN strip on, red off"))
        await self.set_strip(self.args.rgb, down, RED)
        await self.set_strip(self.args.green, not down, GREEN)

    async def manual_pulse(self):
        await self.scene_on("Enter key")
        self.motion_cleared()

    def restore(self):
        if self.jazz_on:
            call(self.args, "media_player", "media_stop", self.args.speaker)
        vol0 = ((self.initial.get(self.args.speaker) or {}).get("attributes") or {}).get("volume_level")
        if self.jazz_on is not None and vol0 is not None:
            call(self.args, "media_player", "volume_set", self.args.speaker, volume_level=vol0)
        cover0 = (self.initial.get(self.args.cover) or {}).get("state")
        log(f"restoring strips and shade (shade -> {cover0})")
        for e in (self.args.rgb, self.args.green):
            if e:
                restore_light(self.args, e, self.initial.get(e))
        if cover0 in ("open", "opening"):
            call(self.args, "cover", "open_cover", self.args.cover)
        elif cover0 in ("closed", "closing"):
            call(self.args, "cover", "close_cover", self.args.cover)


def jazz_start(args):
    call(args, "media_player", "volume_set", args.speaker, volume_level=args.volume)
    call(args, "media_player", "play_media", args.speaker,
         media_content_id=args.jazz_url, media_content_type=args.content_type)


def jazz_test(args):
    log(f"jazz on {args.speaker} for 20 s ({args.jazz_url}, type {args.content_type})")
    log("a Google speaker needs ~5-8 s to start the stream; it usually chimes first")
    jazz_start(args)
    try:
        time.sleep(20)
    finally:
        call(args, "media_player", "media_stop", args.speaker)
    log("stopped. If you heard nothing, try another --speaker.")


def restore_light(args, entity, obj):
    obj = obj or {}
    if obj.get("state") == "on":
        a = obj.get("attributes") or {}
        extra = {k: a[k] for k in ("rgb_color", "brightness") if a.get(k) is not None}
        call(args, "light", "turn_on", entity, **extra)
    elif obj.get("state") == "off":
        call(args, "light", "turn_off", entity)


async def get_states(args):
    ws_url = args.url.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
    async with websockets.connect(ws_url, max_size=None) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": args.token}))
        if json.loads(await ws.recv()).get("type") != "auth_ok":
            sys.exit("Authentication failed (check HA_TOKEN).")
        await ws.send(json.dumps({"id": 1, "type": "get_states"}))
        while True:
            m = json.loads(await ws.recv())
            if m.get("id") == 1:
                return m.get("result") or []


def identify(args):
    """Turn each available light on for 3 s (green if it supports color), then put it back."""
    lights = [s for s in asyncio.run(get_states(args))
              if s["entity_id"].startswith("light.") and s["state"] in ("on", "off")]
    log(f"{len(lights)} lights. Watch the stand; each one lights up for 3 s.")
    for i, s in enumerate(lights, 1):
        eid = s["entity_id"]
        a = s.get("attributes") or {}
        modes = set(a.get("supported_color_modes") or [])
        color = bool(modes & {"rgb", "rgbw", "rgbww", "hs", "xy"})
        log(f"\n[{i}/{len(lights)}] {eid}  ({a.get('friendly_name', '')})  was {s['state']}, "
            f"{'GREEN' if color else 'on (no color)'}")
        if color:
            call(args, "light", "turn_on", eid, rgb_color=GREEN, brightness=255)
        else:
            call(args, "light", "turn_on", eid)
        time.sleep(3)
        restore_light(args, eid, s)
        time.sleep(1)
    log("\ndone. Use the entity_id you saw: --rgb <red strip> --green <green strip>")


def start_keyboard(loop, queue):
    def reader():
        for _ in sys.stdin:
            loop.call_soon_threadsafe(queue.put_nowait, "enter")
    threading.Thread(target=reader, daemon=True).start()


async def run(args, demo):
    ws_url = args.url.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
    keys = asyncio.Queue()
    start_keyboard(asyncio.get_running_loop(), keys)

    async def key_loop():
        while True:
            await keys.get()
            await demo.manual_pulse()

    key_task = asyncio.ensure_future(key_loop())
    try:
        while True:
            try:
                async with websockets.connect(ws_url, max_size=None) as ws:
                    await ws.recv()
                    await ws.send(json.dumps({"type": "auth", "access_token": args.token}))
                    if json.loads(await ws.recv()).get("type") != "auth_ok":
                        sys.exit("Authentication failed (check HA_TOKEN).")
                    await ws.send(json.dumps({"id": 1, "type": "get_states"}))
                    await ws.send(json.dumps({"id": 2, "type": "subscribe_events",
                                              "event_type": "state_changed"}))
                    async for raw in ws:
                        m = json.loads(raw)
                        if m.get("id") == 1 and m.get("type") == "result":
                            objs = {s["entity_id"]: s for s in m.get("result") or []}
                            states = {e: o["state"] for e, o in objs.items()}
                            missing = [e for e in (args.motion, args.rgb, args.green, args.cover, args.speaker)
                                       if e and e not in states]
                            if missing:
                                sys.exit(f"Not found in HA: {', '.join(missing)}")
                            if not demo.initial:
                                demo.initial = {e: objs[e] for e in
                                                (args.rgb, args.green, args.cover, args.speaker) if e}
                            log(f"ready. motion={states[args.motion]}  red strip={states[args.rgb]}  "
                                f"shade={states[args.cover]}  speaker={states.get(args.speaker, 'not set')}")
                            await demo.on_cover_state(states[args.cover])
                            log("Enter = run the scene by hand, Ctrl+C = stop and restore")
                            if states[args.motion] == "on":
                                await demo.scene_on("already on at start")
                        elif m.get("type") == "event":
                            d = m["event"]["data"]
                            new, old = d.get("new_state") or {}, d.get("old_state") or {}
                            if new.get("state") == old.get("state"):
                                continue
                            if d.get("entity_id") == args.cover:
                                log(f"shade: {old.get('state')} -> {new.get('state')}")
                                await demo.on_cover_state(new.get("state"))
                                continue
                            if d.get("entity_id") != args.motion:
                                continue
                            log(f"sensor: {old.get('state')} -> {new.get('state')}")
                            if new.get("state") == "on":
                                await demo.scene_on("sensor")
                            elif new.get("state") == "off":
                                demo.motion_cleared()
            except (OSError, websockets.ConnectionClosed) as e:
                log(f"connection lost ({e}); retrying in 3 s")
                await asyncio.sleep(3)
    finally:
        key_task.cancel()


def main():
    p = argparse.ArgumentParser(description="Motion -> shade down; red strip while down, green while up/moving")
    p.add_argument("--url", required=True, help="e.g. http://homeassistant.local:8123")
    p.add_argument("--token", default=os.environ.get("HA_TOKEN"))
    p.add_argument("--motion", default=MOTION)
    p.add_argument("--rgb", default=RGB, help="the strip: RED while the shade is down, GREEN otherwise")
    p.add_argument("--green", default=None, help="optional second strip for GREEN (then --rgb shows only RED)")
    p.add_argument("--identify", action="store_true", help="flash every light one by one and exit")
    p.add_argument("--speaker", default=SPEAKER, help="media_player for jazz ('' = no music)")
    p.add_argument("--jazz-url", default=JAZZ_URL, help="stream URL to play")
    p.add_argument("--volume", type=float, default=0.6, help="0.0-1.0")
    p.add_argument("--content-type", default="music", help="e.g. music or audio/mpeg")
    p.add_argument("--jazz-test", action="store_true", help="play jazz 20 s on --speaker and exit")
    p.add_argument("--cover", default=COVER)
    p.add_argument("--off-delay", type=float, default=10, help="seconds without motion before undo")
    args = p.parse_args()
    if not args.token:
        sys.exit("No token. Set HA_TOKEN or pass --token.")
    if args.jazz_test:
        try:
            jazz_test(args)
        except KeyboardInterrupt:
            pass
        return
    if args.identify:
        try:
            identify(args)
        except KeyboardInterrupt:
            pass
        return
    demo = Demo(args)
    try:
        asyncio.run(run(args, demo))
    except KeyboardInterrupt:
        pass
    finally:
        if demo.initial:
            demo.restore()


if __name__ == "__main__":
    main()
