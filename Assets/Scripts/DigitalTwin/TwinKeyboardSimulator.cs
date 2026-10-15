using UnityEngine;
using UnityEngine.InputSystem;

namespace DigitalTwin
{
    /// <summary>
    /// Desktop test keys (no Home Assistant needed):
    ///   1 = door   2 = motion   3 = temperature +   4 = light   5 = beacon   6 = roller shade   7 = LED strip
    /// Uses the new Input System (the legacy Input Manager is disabled for the Quest build).
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
            var k = Keyboard.current;
            if (k == null) return; // no keyboard on the headset
            if (k.digit1Key.wasPressedThisFrame && door) door.SimulateInteract();
            if (k.digit2Key.wasPressedThisFrame && motion) motion.SimulateInteract();
            if (k.digit3Key.wasPressedThisFrame && thermostat) thermostat.SimulateInteract();
            if (k.digit4Key.wasPressedThisFrame && lamp) lamp.SimulateInteract();
            if (k.digit5Key.wasPressedThisFrame && beacon) beacon.SimulateInteract();
            if (k.digit6Key.wasPressedThisFrame && shade) shade.SimulateInteract();
            if (k.digit7Key.wasPressedThisFrame && strip) strip.SimulateInteract();
        }
    }
}
