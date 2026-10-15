using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Desktop test keys (no Home Assistant needed):
    ///   1 = door   2 = motion   3 = temperature +   4 = light   5 = beacon   6 = roller shade   7 = LED strip
    /// </summary>
    public class TwinKeyboardSimulator : MonoBehaviour
    {
        public DoorBinding door;
        public MotionSensorBinding motion;
        public ThermostatBinding thermostat;
        public LightBinding lamp;
        public BeaconBinding beacon;
        public RollerShadeBinding shade;
        public LedStripBinding strip;

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.Alpha1) && door) door.SimulateInteract();
            if (Input.GetKeyDown(KeyCode.Alpha2) && motion) motion.SimulateInteract();
            if (Input.GetKeyDown(KeyCode.Alpha3) && thermostat) thermostat.SimulateInteract();
            if (Input.GetKeyDown(KeyCode.Alpha4) && lamp) lamp.SimulateInteract();
            if (Input.GetKeyDown(KeyCode.Alpha5) && beacon) beacon.SimulateInteract();
            if (Input.GetKeyDown(KeyCode.Alpha6) && shade) shade.SimulateInteract();
            if (Input.GetKeyDown(KeyCode.Alpha7) && strip) strip.SimulateInteract();
        }
    }
}
