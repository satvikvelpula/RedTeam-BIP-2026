# IVAR Lab Digital Twin

XR application for the smart-home stand in room VK1 406, TalTech Virumaa College. One Unity scene reads the devices from Home Assistant and sends commands back to the same stand. The five demonstrations — lamp, door, temperature and siren, motion scene, and door announcement — run in that scene together.

Unity **2022.3.62f3**. Scene `Assets/Scenes/IvarLab.unity`. On the lab router `RUT361_F473`, Home Assistant is `http://homeassistant.local:8123`.

## Run

1. Open the scene. **IVAR > Home Assistant Settings** → paste the token → **Save + Test**.
2. Copy `use_case_1/.env.example` to `use_case_1/.env` and set `HA_URL` and `HA_TOKEN`.
3. From the repository root:

```text
python use_case_1/lamp_api.py serve
python use_case_3/temperature.py serve
python scripts/motion_demo.py --url http://homeassistant.local:8123 --http 8767
```

4. Press Play. The panel must show **Home Assistant: connected** and **Presses → real stand**.

A headset package is **RedLab > Build Quest APK**. On a standalone Quest, run `python scripts/twin_bridge.py --url http://homeassistant.local:8123` instead of the three programs above.

## Documentation

The report is in [`docs/IVAR_Lab_Digital_Twin_Technical_Report.pdf`](docs/IVAR_Lab_Digital_Twin_Technical_Report.pdf). The same account in Markdown is [`docs/RedLab-Twin-Technical-Report.md`](docs/RedLab-Twin-Technical-Report.md). Test recordings go in `footage/`.
