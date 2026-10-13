using TMPro;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>Temperature sensor: shows the value on the thermostat's screen.</summary>
    public class ThermostatBinding : TwinEntityBinding
    {
        public TextMeshPro display;
        public string format = "0.0";
        public string fallbackUnit = "°C";
        [Tooltip("Each simulated press adds this much (wraps back to simMin above simMax).")]
        public float simStep = 0.5f;
        public float simMin = 18f, simMax = 26f;

        float _value = 21f;

        void Awake() { if (display) display.text = "--.-"; }

        public override void Apply(TwinStateMessage m)
        {
            if (!display) return;
            if (!m.available) { display.text = "n/a"; return; }
            if (m.hasNumber)
            {
                _value = m.number;
                string unit = string.IsNullOrEmpty(m.unit) ? fallbackUnit : m.unit;
                display.text = m.number.ToString(format, System.Globalization.CultureInfo.InvariantCulture) + "<size=60%>" + unit + "</size>";
            }
            else display.text = m.state;
        }

        /// <summary>Step the (simulated) temperature up or down — used by the +/- buttons.</summary>
        public void SimulateAdjust(float delta)
        {
            if (!allowSimulatedInteraction || string.IsNullOrEmpty(entityId)) return;
            float next = Mathf.Clamp(Mathf.Round((_value + delta) * 2f) / 2f, simMin, simMax);
            var m = TwinStateMessage.Make(entityId, next.ToString("0.0", System.Globalization.CultureInfo.InvariantCulture), "sensor");
            m.unit = fallbackUnit; m.device_class = "temperature";
            var r = TwinUdpReceiver.Instance;
            if (r != null) r.Inject(m); else Apply(m);
        }

        protected override TwinStateMessage BuildSimulatedToggle()
        {
            float next = _value + simStep;
            if (next > simMax) next = simMin;
            var m = TwinStateMessage.Make(entityId, next.ToString("0.0", System.Globalization.CultureInfo.InvariantCulture), "sensor");
            m.unit = fallbackUnit;
            m.device_class = "temperature";
            return m;
        }
    }
}
