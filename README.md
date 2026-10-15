# RedTeam · BIP 2026 — KNX digital twin in XR

Team repository for the Erasmus+ BIP project at TalTech (Tallinn, October 2026): a digital twin of a KNX "smart home" training stand, shown in VR/AR.

## Project goal

- 3D model of the KNX stand and its devices
- VR/AR application (Unity)
- Show sensor and device states, ideally live from the real stand
- Interaction: press something in VR and something happens on the stand
- Documentation and a final presentation on 16 October 2026

## What is in the repository

```
Models/                    3D models (.blend for Blender, .fbx for Unity) + preview renders
  KNX_Switch/              KNX wall switch
  Pendant_Lamp/            pendant lamp (actuator)
  Window_Sensor/           window contact sensor
  Thermostat/              room thermostat
  Warning_Beacon/          warning beacon / signal light
  PIR_Sensor/              PIR motion sensor
  IVAR_Lab/                approximate model of the TalTech IVAR lab room (context scene)
blender_scripts/           Python scripts that generate the models in Blender
  01_knx_switch.py … 06_pir_sensor.py
  07_ivar_lab.py           builds Models/IVAR_Lab from ivar_lab_data.json
  ivar_lab_data.json
web/
  ivar-lab.html            interactive 3D viewer of the IVAR lab (three.js, runs in a browser)
```

## Working with the models

**Blender (5.x):** open any `.blend` in `Models/`. All models use metres, Z up.

**Unity:** import the `.fbx` files from `Models/<Device>/`. For the lab room, export `ivar-lab-taltech.blend` to FBX/glTF from Blender, or use the `.glb` export in the web viewer.

**Rebuilding a model from its script:** open Blender, switch an area to the Python Console (Shift+F4) and run:

```python
p = r"<path to repo>\blender_scripts\07_ivar_lab.py"
exec(compile(open(p, encoding="utf-8").read(), p, "exec"), {"__file__": p, "__name__": "__main__"})
```

`07_ivar_lab.py` writes `Models/IVAR_Lab/ivar-lab-taltech.blend` and four preview renders into `Models/IVAR_Lab/renders/`.

## IVAR lab model

The IVAR room (Industrial Virtual & Augmented Reality Lab, TalTech Department of Mechanical and Industrial Engineering) is reconstructed from public sources:

- the official 360° panorama: https://ivar.taltech.ee/360
- the equipment list: https://ivar.taltech.ee/equipment
- the TalTech lab page: https://taltech.ee/en/department-mechanical-and-industrial-engineering/laboratories/IVAR-laboratory

No official floor plan is public, so dimensions are approximate (±0.5–1 m). Equipment from the official list that is not visible in the panorama (Fanuc CRX, Omron TM5, Unitree robots, headsets, drones) is placed in a separate `ConditionalPlacement` / «З переліку (умовно)» collection. In the `.blend` file, the ceiling collection is hidden by default so the room can be seen from above.

Open `web/ivar-lab.html` in a browser for an interactive view with an equipment list, plan view and first-person walk.

## Team

RedTeam, BIP 2026 (TalTech, Tallinn).

## Unity digital twin — live with the real stand

Branch `integrate/scene` is the Unity project (Unity **2022.3.62f3**, scene `Assets/Scenes/IvarLab.unity`).
It contains use case 1 (lamp), use case 2 (window sensor logger), use case 3 (temperature + siren) and use case 4 (motion demo).

**Real stand → VR.** `HomeAssistantClient` (on the `DigitalTwin` object) subscribes to Home Assistant over
WebSocket and every binding mirrors its entity: lamp on/off + brightness, window open/closed, motion,
roller shade position, LED strip colour, room temperature + thermostat setpoint, siren (warning beacon). `scripts/ha_twin_logger.py --udp 127.0.0.1:5005` can still feed the
same scene over UDP (port 5005), e.g. for logging.

**VR → real stand.** `TwinCommandRouter` (created automatically at Play) sends every press (VR trigger/grip,
mouse click, test keys 1-7) to the real device while Home Assistant is connected, and the twin then shows the
state Home Assistant reports back. Without a connection, presses are simulated as before.

| Press in VR on | Goes to | Real result |
|---|---|---|
| Pendant lamp / KNX switch (use case 1) | `use_case_1/lamp_api.py serve` → HA `light.aqara_dimmer_switch_h2_2` (falls back to HA directly) | lamp on/off |
| PIR sensor (use case 4) | `scripts/motion_demo.py --http 8767` → `POST /scene` | shade down, strip red, jazz; shade up after the delay |
| Roller shade | HA `cover.open_cover` / `close_cover` | shade moves; `motion_demo.py` switches the strip red/green |
| LED strip | HA `light.turn_on` / `turn_off` | strip on/off |
| Window sensor (use case 2) | nothing — it is a real sensor | open/close the real window, the twin follows |
| Thermostat +/− buttons (use case 3) | `use_case_3/temperature.py serve` → `POST /devices/temperature/set` (falls back to HA `climate.set_temperature`) | setpoint of `climate.aqara_floor_heating_thermostat` changes; the screen shows measured and `→ setpoint` |
| Warning beacon (use case 3) | nothing — `temperature.py` drives `siren.frient_a_s_smszb_120_siren` | beacon flashes while the siren is on (measured above 25 °C) |

`TwinCommandRouter.SetLampBrightness(0-255)` and `SetShadePosition(entity, 0-100)` are there for sliders.

### Running it in the lab

1. Token: Unity menu **IVAR > Home Assistant Settings** → paste the long-lived token → *Save + Test*
   (or set `HA_TOKEN` as an environment variable before starting Unity Hub). URL `http://homeassistant.local:8123`.
2. Helper scripts (PowerShell, from the repo root, `pip install websockets` once):
   ```powershell
   $env:HA_URL="http://homeassistant.local:8123"; $env:HA_TOKEN="<token>"
   python use_case_1/lamp_api.py serve                                  # use case 1, port 8765
   python use_case_3/temperature.py serve                               # use case 3, port 8766
   python scripts/motion_demo.py --url $env:HA_URL --http 8767          # use case 4
   python scripts/ha_twin_logger.py --url $env:HA_URL --udp 127.0.0.1:5005   # use case 2 (optional log)
   ```
3. Press Play. The status panel shows *Presses → real stand* and whether lamp_api / motion_demo / temperature are running.
