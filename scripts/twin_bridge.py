#!/usr/bin/env python3
"""
twin_bridge.py - laptop bridge between Home Assistant and the RedLab Twin app on a standalone Quest.

The headset has no Home Assistant token and often cannot reach Home Assistant itself, so this
script runs on the lab laptop (which can) and relays both directions over UDP:

  headset  --hello (UDP broadcast, port 5006)-->  bridge      "I am here, I need these entities"
  headset  <--twin.state.v1 (UDP :5005)---------  bridge      snapshot + every change, same JSON as ha_twin_logger.py
  headset  <--twin.bridge.v1 heartbeat----------  bridge      every 2 s, says whether HA is connected
  headset  --call_service / http (UDP :5006)--->  bridge      VR press -> HA service, or -> helper script on this laptop

No IP addresses to type on either side: the headset finds the bridge by broadcast and the bridge
answers to whatever address the hello came from. Laptop and headset must be on the same network
(e.g. the laptop's Windows mobile hotspot, or the same phone hotspot), and Windows Firewall must
allow Python to receive UDP on port 5006 (accept the prompt on first run).

Usage (PowerShell):
  pip install websockets
  $env:HA_TOKEN="<long-lived token>"          # or leave it out: the token saved in Unity is used
  python scripts/twin_bridge.py --url http://homeassistant.local:8123

It also starts the helper scripts (motion_demo.py --http 8767, temperature.py serve, lamp_api.py serve)
with the same token, so ONE window runs the whole stand. --no-helpers if you start them yourself.

Safety: a headset can only call services on the entities it announced in its hello, only in the
domains listed in ALLOWED_DOMAINS (no locks), and "http" requests may only go to 127.0.0.1/localhost.
"""
import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import websockets

BRIDGE_SCHEMA = "twin.bridge.v1"
UNAVAILABLE = {"unavailable", "unknown", None, ""}
ALLOWED_DOMAINS = {"light", "switch", "cover", "climate", "siren", "media_player", "input_boolean", "fan"}
CLIENT_TTL = 15          # seconds without a hello before a headset is forgotten
HEARTBEAT = 2


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def log(text):
    print(f"{datetime.now():%H:%M:%S} {text}", flush=True)


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Helper scripts the twin talks to. Started by the bridge so one command runs the whole stand.
HELPERS = [
    ("motion", ["scripts/motion_demo.py", "--url", "{url}", "--http", "8767"], 8767),   # motion -> shade, red strip, jazz
    ("temp", ["use_case_3/temperature.py", "serve"], 8766),                             # thermostat, siren, alarm lights
    ("lamp", ["use_case_1/lamp_api.py", "serve"], 8765),                                # lamp (KNX/Matter log)
]


def unity_token():
    """Token saved in Unity (IVAR > Home Assistant Settings): %USERPROFILE%/AppData/LocalLow/TRedLab/RedLab Twin."""
    path = os.path.join(os.path.expanduser("~"), "AppData", "LocalLow", "TRedLab", "RedLab Twin", "home_assistant_token.txt")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def port_busy(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_helpers(args):
    """Start motion_demo.py, temperature.py and lamp_api.py with the same token; their output goes here with a prefix."""
    env = dict(os.environ, HA_TOKEN=args.token, HA_URL=args.url, PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    procs = []
    for name, argv, port in HELPERS:
        if port_busy(port):
            log(f"[{name}] already running on :{port} (started by hand) - not starting another")
            continue
        cmd = [sys.executable, "-u"] + [a.format(url=args.url) for a in argv]
        try:
            p = subprocess.Popen(cmd, cwd=REPO, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        except OSError as e:
            log(f"[{name}] could not start: {e}")
            continue
        procs.append((name, p))

        def pump(name=name, p=p):
            for line in p.stdout:
                log(f"[{name}] {line.rstrip()}")
            log(f"[{name}] STOPPED (exit code {p.wait()}) - the stand part '{name}' no longer works, see the lines above")

        threading.Thread(target=pump, daemon=True).start()
        log(f"[{name}] started: {' '.join(argv[:1])}")
    return procs


def stop_helpers(procs):
    for name, p in procs:
        if p.poll() is None:
            p.terminate()


def make_msg(event, new, old=None):
    """Same fields as HomeAssistantClient.ToMessage() in Unity (twin.state.v1)."""
    entity_id = new["entity_id"]
    domain = entity_id.split(".", 1)[0]
    a = new.get("attributes") or {}
    state = new.get("state")
    msg = {
        "schema": "twin.state.v1",
        "event": event,
        "ts": new.get("last_changed") or now_iso(),
        "logged_at": now_iso(),
        "entity_id": entity_id,
        "name": a.get("friendly_name", entity_id),
        "domain": domain,
        "device_class": a.get("device_class") or "",
        "state": state if state is not None else "",
        "available": state not in UNAVAILABLE,
    }
    if domain == "binary_sensor":
        msg["on"] = state == "on"
    try:
        msg["number"] = float(state)
    except (TypeError, ValueError):
        pass
    if a.get("unit_of_measurement"):
        msg["unit"] = a["unit_of_measurement"]
    rgb = a.get("rgb_color")
    if isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
        msg["rgb_color"] = [int(rgb[0]), int(rgb[1]), int(rgb[2])]
    if a.get("brightness") is not None:
        msg["brightness"] = float(a["brightness"])
    if a.get("current_position") is not None:
        msg["position"] = float(a["current_position"])
    if domain == "climate" and a.get("temperature") is not None:
        msg["target"] = float(a["temperature"])
    if old is not None:
        msg["prev_state"] = old.get("state") or ""
    return msg


def twin_attrs(s):
    a = (s or {}).get("attributes") or {}
    return (str(a.get("rgb_color")), a.get("brightness"), a.get("current_position"), a.get("temperature"))


def do_http(method, url, body):
    host = urllib.parse.urlparse(url).hostname
    if host not in ("127.0.0.1", "localhost"):
        return False, 0, f"only 127.0.0.1/localhost allowed, not {host}"
    data = body.encode("utf-8") if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return 200 <= r.status < 300, r.status, r.read(500).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return False, e.code, e.read(300).decode("utf-8", "replace")
    except Exception as e:  # connection refused = helper script not running
        return False, 0, str(getattr(e, "reason", e))


class UdpProtocol(asyncio.DatagramProtocol):
    def __init__(self, bridge):
        self.bridge = bridge

    def datagram_received(self, data, addr):
        try:
            msg = json.loads(data.decode("utf-8"))
        except Exception:
            return
        if isinstance(msg, dict):
            asyncio.ensure_future(self.bridge.handle(msg, addr))

    def error_received(self, exc):
        pass  # e.g. ICMP port unreachable after a headset left; ignore


class Bridge:
    def __init__(self, args):
        self.args = args
        self.states = {}        # entity_id -> HA state object
        self.clients = {}       # (ip, reply_port) -> {"entities": set, "seen": t, "device": str}
        self.ws = None
        self.ha_ok = False
        self.pending = {}
        self.next_id = 100
        self.transport = None

    # ------------------------------------------------------------------ UDP side
    def send(self, obj, addr):
        if self.transport:
            self.transport.sendto(json.dumps(obj, ensure_ascii=False).encode("utf-8"), addr)

    def heartbeat(self):
        return {"schema": BRIDGE_SCHEMA, "event": "heartbeat", "ha": self.ha_ok}

    def client_for(self, ip):
        for key, c in self.clients.items():
            if key[0] == ip:
                return key, c
        return (ip, 5005), None

    def send_snapshot(self, key, entities):
        n = 0
        for eid in entities:
            s = self.states.get(eid)
            if s:
                self.send(make_msg("snapshot", s), key)
                n += 1
        return n

    async def handle(self, msg, addr):
        kind = msg.get("type")
        ip = addr[0]
        if kind == "hello":
            key = (ip, int(msg.get("reply_port") or 5005))
            new = key not in self.clients
            ents = set(msg.get("entities") or [])
            self.clients[key] = {"entities": ents, "seen": time.time(), "device": msg.get("device", "")}
            self.send(self.heartbeat(), key)
            if new or msg.get("want_snapshot"):
                n = self.send_snapshot(key, ents)
                if new:
                    log(f"headset connected: {ip} ({msg.get('device', '?')}), {len(ents)} entities, sent {n} states")
                    self.report_missing(ents)
            return

        key, client = self.client_for(ip)
        if kind == "call_service":
            ok, text = await self.call_service(msg, client)
            log(f"{'OK ' if ok else 'ERR'} {ip}: {msg.get('domain')}.{msg.get('service')} "
                f"{(msg.get('data') or {}).get('entity_id', '')} - {text}")
            self.send({"schema": BRIDGE_SCHEMA, "event": "result", "id": msg.get("id"),
                       "ok": ok, "status": 200 if ok else 0, "text": text, "ha": self.ha_ok}, key)
        elif kind == "http":
            method = (msg.get("method") or "POST").upper()
            url = msg.get("url") or ""
            if client is None:
                ok, status, text = False, 0, "send hello first"
            else:
                ok, status, text = await asyncio.get_running_loop().run_in_executor(
                    None, do_http, method, url, msg.get("body") or "")
            if method != "GET":  # GETs are the 5 s health probes; keep the console readable
                log(f"{'OK ' if ok else 'ERR'} {ip}: {method} {url} -> {status or text}")
            self.send({"schema": BRIDGE_SCHEMA, "event": "result", "id": msg.get("id"),
                       "ok": ok, "status": status, "text": text[:300], "ha": self.ha_ok}, key)

    def report_missing(self, ents):
        if not self.states:
            return
        missing = sorted(e for e in ents if e not in self.states)
        bad = sorted(e for e in ents if e in self.states and self.states[e].get("state") in UNAVAILABLE)
        if missing:
            log("WARNING: not in Home Assistant (the twin cannot control/show them): " + ", ".join(missing))
        if bad:
            log("WARNING: unavailable in Home Assistant (device offline?): " + ", ".join(bad))

    async def heartbeat_loop(self):
        while True:
            await asyncio.sleep(HEARTBEAT)
            now = time.time()
            for key in [k for k, c in self.clients.items() if now - c["seen"] > CLIENT_TTL]:
                log(f"headset {key[0]} gone (no hello for {CLIENT_TTL} s)")
                del self.clients[key]
            for key in self.clients:
                self.send(self.heartbeat(), key)

    # ------------------------------------------------------------------ Home Assistant side
    async def call_service(self, msg, client):
        domain, service = msg.get("domain") or "", msg.get("service") or ""
        data = msg.get("data") or {}
        eid = data.get("entity_id") or ""
        if domain not in ALLOWED_DOMAINS:
            return False, f"domain '{domain}' not allowed"
        if client is None:
            return False, "send hello first"
        if eid not in client["entities"]:
            return False, f"{eid} is not used by this headset"
        if self.ws is None:
            return False, "Home Assistant not connected"
        if self.states and eid not in self.states:
            # HA answers "success" for unknown entities and does nothing - say it clearly instead
            return False, f"{eid} does not exist in Home Assistant (renamed? check Settings > Entities)"
        self.next_id += 1
        mid = self.next_id
        fut = asyncio.get_running_loop().create_future()
        self.pending[mid] = fut
        try:
            await self.ws.send(json.dumps({"id": mid, "type": "call_service", "domain": domain,
                                           "service": service, "service_data": data}))
            r = await asyncio.wait_for(fut, 6)
        except Exception as e:
            self.pending.pop(mid, None)
            return False, f"{type(e).__name__}: {e}"
        if r.get("success"):
            st = self.states.get(eid) or {}
            return True, f"ok (HA state before: {st.get('state', '?')})"
        return False, (r.get("error") or {}).get("message", "failed")

    async def ha_loop(self):
        ws_url = self.args.url.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
        while True:
            try:
                async with websockets.connect(ws_url, max_size=None) as ws:
                    await ws.recv()  # auth_required
                    await ws.send(json.dumps({"type": "auth", "access_token": self.args.token}))
                    auth = json.loads(await ws.recv())
                    if auth.get("type") != "auth_ok":
                        log(f"Home Assistant rejected the token: {auth.get('message', auth)}")
                        os._exit(1)
                    self.ws, self.ha_ok = ws, True
                    log(f"connected to Home Assistant ({ws_url})")
                    await ws.send(json.dumps({"id": 1, "type": "get_states"}))
                    await ws.send(json.dumps({"id": 2, "type": "subscribe_events", "event_type": "state_changed"}))
                    async for raw in ws:
                        m = json.loads(raw)
                        if m.get("type") == "result":
                            mid = m.get("id")
                            if mid == 1:
                                for s in m.get("result") or []:
                                    self.states[s["entity_id"]] = s
                                for key, c in self.clients.items():
                                    self.send_snapshot(key, c["entities"])
                                    self.report_missing(c["entities"])
                            elif mid in self.pending:
                                fut = self.pending.pop(mid)
                                if not fut.done():
                                    fut.set_result(m)
                        elif m.get("type") == "event":
                            data = m["event"]["data"]
                            new, old = data.get("new_state"), data.get("old_state")
                            if not new:
                                continue
                            eid = new["entity_id"]
                            self.states[eid] = new
                            if old and old.get("state") == new.get("state") and twin_attrs(old) == twin_attrs(new):
                                continue  # attribute noise
                            msg = None
                            for key, c in self.clients.items():
                                if eid in c["entities"]:
                                    msg = msg or make_msg("change", new, old)
                                    self.send(msg, key)
                            if msg:
                                log(f"-> {eid} = {new.get('state')}")
            except (OSError, websockets.ConnectionClosed, asyncio.TimeoutError) as e:
                log(f"Home Assistant connection lost ({e}); retrying in 3 s")
            finally:
                self.ws, self.ha_ok = None, False
                for fut in self.pending.values():
                    if not fut.done():
                        fut.set_exception(ConnectionError("Home Assistant disconnected"))
                self.pending.clear()
            await asyncio.sleep(3)

    async def run(self):
        loop = asyncio.get_running_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: UdpProtocol(self), local_addr=("0.0.0.0", self.args.port))
        try:
            ips = sorted({i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
        except OSError:
            ips = []
        log(f"bridge listening on UDP :{self.args.port}  (this laptop: {', '.join(ips) or '?'})")
        log("start RedLab Twin on the headset; it finds this bridge by itself")
        await asyncio.gather(self.ha_loop(), self.heartbeat_loop())


def main():
    p = argparse.ArgumentParser(description="Relay Home Assistant <-> RedLab Twin on a standalone headset.")
    p.add_argument("--url", default="http://homeassistant.local:8123", help="Home Assistant URL")
    p.add_argument("--token", default=os.environ.get("HA_TOKEN"), help="Long-lived token (default: HA_TOKEN env var)")
    p.add_argument("--port", type=int, default=5006, help="UDP port the headset sends to (default 5006)")
    p.add_argument("--no-helpers", action="store_true",
                   help="do not start motion_demo.py / temperature.py / lamp_api.py (you run them yourself)")
    args = p.parse_args()
    if not args.token:
        args.token = unity_token()
        if args.token:
            log("token: from Unity (IVAR > Home Assistant Settings)")
    if not args.token:
        sys.exit("No token. Set HA_TOKEN, pass --token, or save it in Unity: IVAR > Home Assistant Settings.")
    procs = [] if args.no_helpers else start_helpers(args)
    try:
        asyncio.run(Bridge(args).run())
    except KeyboardInterrupt:
        pass
    finally:
        stop_helpers(procs)


if __name__ == "__main__":
    main()
