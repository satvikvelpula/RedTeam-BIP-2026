"""HTTP calls to Home Assistant.

Every call is POST or GET to HA_URL with one header:

    Authorization: Bearer <long-lived access token>

HA then uses the KNX IP gateway it is already connected to.
We never open a second tunnel to the gateway. Most KNX IP interfaces
allow only one tunneling connection, and Home Assistant is already holding it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


class HaError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"Home Assistant HTTP {status}: {body[:300]}")


class HomeAssistant:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, body: dict | None = None) -> object:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HaError(exc.code, detail) from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            raise HaError(
                0,
                f"Could not connect to {self.base_url}. {reason}. "
                "Connection refused means that host and port are not running Home Assistant. "
                "The address is the one in the browser bar, including :8123, and it is http unless the page itself is https.",
            ) from exc
        if not raw:
            return None
        return json.loads(raw)

    def ping(self) -> dict:
        """GET /api/ returns {"message": "API running."} when the token works."""
        result = self._request("GET", "/api/")
        return result if isinstance(result, dict) else {"message": result}

    def states(self) -> list:
        result = self._request("GET", "/api/states")
        return result if isinstance(result, list) else []

    def entity_state(self, entity_id: str) -> dict:
        result = self._request("GET", "/api/states/" + urllib.request.quote(entity_id))
        return result if isinstance(result, dict) else {}

    def turn_light(self, entity_id: str, on: bool, brightness: int | None = None) -> object:
        if not on or brightness == 0:
            return self._request(
                "POST",
                "/api/services/light/turn_off",
                {"entity_id": entity_id},
            )
        body: dict = {"entity_id": entity_id}
        if brightness is not None:
            body["brightness"] = brightness
        return self._request("POST", "/api/services/light/turn_on", body)

    def set_temperature(self, entity_id: str, temperature_c: float) -> object:
        """Set a climate entity's target temperature. This does not overwrite the measured sensor."""
        return self._request(
            "POST",
            "/api/services/climate/set_temperature",
            {"entity_id": entity_id, "temperature": temperature_c},
        )

    def send_switch(self, group_address: str, bit: int) -> object:
        """Write a DPT 1 value. payload 1 = ON, payload 0 = OFF. No type field."""
        return self._request(
            "POST",
            "/api/services/knx/send",
            {"address": group_address, "payload": bit},
        )

    def list_switchable(self) -> list[dict]:
        """Lights and switches HA already exposes. Copy entity_id into the phrasebook."""
        found = []
        for row in self.states():
            entity_id = row.get("entity_id", "")
            if entity_id.startswith(("light.", "switch.")):
                found.append(
                    {
                        "entity_id": entity_id,
                        "state": row.get("state"),
                        "name": (row.get("attributes") or {}).get("friendly_name"),
                    }
                )
        return found
