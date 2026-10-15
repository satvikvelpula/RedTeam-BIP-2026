using System;

namespace DigitalTwin
{
    /// <summary>
    /// One message from ha_twin_logger.py (schema "twin.state.v1").
    /// Field names match the JSON keys exactly so JsonUtility can parse it.
    /// </summary>
    [Serializable]
    public class TwinStateMessage
    {
        public string schema;
        public string @event;          // "snapshot" | "change"
        public string ts;
        public string logged_at;
        public string entity_id;
        public string name;
        public string domain;
        public string device_class;
        public string state;           // raw HA state string ("on", "off", "21.5", ...)
        public bool available;
        public bool on;                // binary_sensor only
        public float number;           // only meaningful when hasNumber is true
        public string unit;
        public string prev_state;
        public int[] rgb_color;        // lights: [r,g,b] 0-255 (only when HA reports it)
        public float brightness;       // lights: 0-255
        public float position;         // covers: current_position 0 (closed) - 100 (open)
        public float target;           // climate: target temperature (attribute "temperature")

        // Not in the JSON: filled in by the receiver because JsonUtility can't tell
        // "field missing" from "field = default".
        [NonSerialized] public bool hasNumber;
        [NonSerialized] public bool hasOn;
        [NonSerialized] public bool simulated;
        [NonSerialized] public bool hasPosition;
        [NonSerialized] public bool hasBrightness;
        [NonSerialized] public bool hasTarget;

        public bool HasColor => rgb_color != null && rgb_color.Length >= 3;
        public UnityEngine.Color Color => HasColor ? new UnityEngine.Color(rgb_color[0] / 255f, rgb_color[1] / 255f, rgb_color[2] / 255f) : UnityEngine.Color.white;

        /// <summary>True for "on", "open", "home", "detected", "heat" etc. Works for binary_sensor, light, switch.</summary>
        public bool IsOn
        {
            get
            {
                if (hasOn) return on;
                switch ((state ?? "").ToLowerInvariant())
                {
                    case "on": case "open": case "opening": case "true": case "detected":
                    case "home": case "heat": case "cool": case "playing":
                        return true;
                    default:
                        return false;
                }
            }
        }

        public static TwinStateMessage Make(string entityId, string state, string domain = null)
        {
            var m = new TwinStateMessage
            {
                schema = "twin.state.v1",
                @event = "change",
                ts = DateTime.UtcNow.ToString("o"),
                logged_at = DateTime.UtcNow.ToString("o"),
                entity_id = entityId,
                name = entityId,
                domain = domain ?? (entityId != null && entityId.Contains(".") ? entityId.Substring(0, entityId.IndexOf('.')) : ""),
                device_class = "",
                state = state,
                available = true,
                unit = "",
                prev_state = "",
                simulated = true
            };
            if (m.domain == "binary_sensor") { m.on = state == "on"; m.hasOn = true; }
            if (float.TryParse(state, System.Globalization.NumberStyles.Float,
                               System.Globalization.CultureInfo.InvariantCulture, out var n))
            { m.number = n; m.hasNumber = true; }
            return m;
        }
    }
}
