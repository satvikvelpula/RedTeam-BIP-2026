"""Turn our JSON command into the two things Home Assistant needs.

Our API speaks this:

    {"device": "lamp", "value": "on"}

Home Assistant already knows the KNX IP gateway. It does not want a raw
KNXnet/IP frame from us. It wants one of these JSON bodies:

    entity path, preferred when the lamp is already a HA light:
        POST /api/services/light/turn_on
        {"entity_id": "light.stand_lamp"}

    explicit telegram path, used when we only know the group address:
        POST /api/services/knx/send
        {"address": "1/1/1", "payload": 1}

payload 1 with no "type" field means DPT 1 (a 1-bit switch). 1 is ON, 0 is OFF.
DPT 1.001 is the named switch variant of that same 1-bit value.
Inside HA, the KNX integration encodes that bit into the bus telegram.
"""

from __future__ import annotations

# GroupValueWrite, data packed into the low bits of the APCI.
# ON  -> 0x00 0x81
# OFF -> 0x00 0x80
# Those two bytes are the application data (APDU), not the whole IP packet.
APDU_ON = bytes((0x00, 0x81))
APDU_OFF = bytes((0x00, 0x80))


def switch_bit(value: str) -> int:
    """Accept the words our API allows and return the DPT 1 bit."""
    word = value.strip().lower()
    if word in ("on", "1", "true"):
        return 1
    if word in ("off", "0", "false"):
        return 0
    raise ValueError('value must be "on" or "off"')


def brightness_byte(level: object) -> int:
    """Home Assistant brightness is an integer 0–255. 0 means off."""
    if isinstance(level, bool) or not isinstance(level, int):
        raise ValueError("brightness must be an integer from 0 to 255")
    if not 0 <= level <= 255:
        raise ValueError("brightness must be an integer from 0 to 255")
    return level


def percent_to_brightness(percent: object) -> int:
    """0–100 percent, same scale a slider usually has. 100 becomes 255."""
    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        raise ValueError("brightness_pct must be a number from 0 to 100")
    if not 0 <= percent <= 100:
        raise ValueError("brightness_pct must be a number from 0 to 100")
    return round(percent * 255 / 100)


def encode_group_address(group_address: str) -> bytes:
    """Pack main/middle/sub into the 2-byte destination KNX puts on the bus.

    Layout: 5 bits main (0-31), 3 bits middle (0-7), 8 bits sub (0-255).
    1/1/1 becomes 0x0901.
    """
    parts = group_address.split("/")
    if len(parts) != 3:
        raise ValueError(f"group address must look like 1/2/3, got {group_address!r}")
    main, middle, sub = (int(p) for p in parts)
    if not (0 <= main <= 31 and 0 <= middle <= 7 and 0 <= sub <= 255):
        raise ValueError(f"group address out of range: {group_address}")
    packed = (main << 11) | (middle << 8) | sub
    return packed.to_bytes(2, "big")


def explain(value: str, group_address: str, ha_entity_id: str, ha_url: str) -> dict:
    """Describe one lamp command without sending it."""
    bit = switch_bit(value)
    apdu = APDU_ON if bit else APDU_OFF
    address = group_address.strip()
    entity = ha_entity_id.strip()
    base = ha_url.rstrip("/") if ha_url else "<HA_URL>"

    telegram = None
    if address:
        telegram = {
            "apci": "GroupValueWrite",
            "dpt": "1.001",
            "destination": address,
            "destination_hex": encode_group_address(address).hex(" "),
            "payload_bit": bit,
            "apdu_hex": apdu.hex(" "),
            "what_ha_sends_for_us": {
                "method": "POST",
                "url": f"{base}/api/services/knx/send",
                "body": {"address": address, "payload": bit},
            },
        }

    entity_call = None
    if entity:
        action = "turn_on" if bit else "turn_off"
        entity_call = {
            "method": "POST",
            "url": f"{base}/api/services/light/{action}",
            "body": {"entity_id": entity},
            "why": (
                "This call asks Home Assistant to switch this entity. "
                "Home Assistant uses the integration that owns it. "
                "A KNX telegram is built only when the phrasebook has a group address."
            ),
        }

    return {
        "your_json": {"device": "lamp", "value": "on" if bit else "off"},
        "home_assistant_entity_call": entity_call,
        "telegram": telegram,
    }


def explain_brightness(level: int, ha_entity_id: str, ha_url: str) -> dict:
    """Describe a dimmer level without sending it.

    1–255 is light.turn_on with that brightness. 0 is light.turn_off.
    The number is the level itself. There is no lookup table.
    """
    brightness = brightness_byte(level)
    entity = ha_entity_id.strip()
    base = ha_url.rstrip("/") if ha_url else "<HA_URL>"
    entity_call = None
    if entity and brightness == 0:
        entity_call = {
            "method": "POST",
            "url": f"{base}/api/services/light/turn_off",
            "body": {"entity_id": entity},
        }
    elif entity:
        entity_call = {
            "method": "POST",
            "url": f"{base}/api/services/light/turn_on",
            "body": {"entity_id": entity, "brightness": brightness},
        }
    return {
        "your_json": {"device": "lamp", "brightness": brightness},
        "home_assistant_entity_call": entity_call,
        "telegram": None,
    }


if __name__ == "__main__":
    # Worked example only. 1/1/1 is not the stand's address.
    sample = explain("on", "1/1/1", "light.example_lamp", "http://homeassistant.local:8123")
    assert encode_group_address("1/1/1") == bytes((0x09, 0x01))
    assert sample["telegram"]["apdu_hex"] == "00 81"
    assert sample["telegram"]["what_ha_sends_for_us"]["body"] == {"address": "1/1/1", "payload": 1}
    off = explain("off", "1/1/1", "", "http://homeassistant.local:8123")
    assert off["telegram"]["apdu_hex"] == "00 80"
    assert off["telegram"]["what_ha_sends_for_us"]["body"]["payload"] == 0
    half = explain_brightness(128, "light.example_lamp", "http://homeassistant.local:8123")
    assert half["home_assistant_entity_call"]["body"] == {
        "entity_id": "light.example_lamp",
        "brightness": 128,
    }
    assert percent_to_brightness(100) == 255
    assert percent_to_brightness(50) == 128
    assert explain_brightness(0, "light.example_lamp", "http://ha")["home_assistant_entity_call"]["url"].endswith(
        "/light/turn_off"
    )
    print("translate.py checks passed")
    print("ON  to 1/1/1 -> destination", sample["telegram"]["destination_hex"], "APDU", sample["telegram"]["apdu_hex"])
    print("OFF to 1/1/1 -> APDU", off["telegram"]["apdu_hex"])
