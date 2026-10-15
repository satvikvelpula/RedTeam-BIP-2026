using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Drives the warning beacon from an entity (e.g. an alarm, or the door sensor).
    /// Leave entityId empty to keep the beacon flashing all the time.
    /// </summary>
    public class BeaconBinding : TwinEntityBinding
    {
        public BeaconFlasher flasher;
        [Tooltip("Flash when the entity is ON (true) or when it is OFF (false).")]
        public bool flashWhenOn = true;

        void Awake() { if (flasher == null) flasher = GetComponent<BeaconFlasher>(); }

        public override void Apply(TwinStateMessage m)
        {
            if (flasher) flasher.flashing = m.available && (m.IsOn == flashWhenOn);
        }

        protected override TwinStateMessage BuildSimulatedToggle()
        {
            bool currentlyOn = Current != null ? Current.IsOn : (flasher && flasher.flashing) == flashWhenOn;
            return TwinStateMessage.Make(entityId, currentlyOn ? "off" : "on", "binary_sensor");
        }
    }
}
