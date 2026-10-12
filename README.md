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
