using System.Collections.Generic;
using System.Globalization;
using TMPro;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Use case 3 thermostat. entityId = the measured temperature sensor (read-only), targetEntity = the
    /// climate entity whose setpoint the +/- buttons change. The screen shows the measured value and,
    /// on a second line, the setpoint ("→ 22.0"). Live, the buttons go to temperature.py (or HA directly);
    /// offline they only change the twin.
    /// </summary>
    public class ThermostatBinding : TwinEntityBinding
    {
        public TextMeshPro display;
        public string format = "0.0";
        public string fallbackUnit = "°C";
        [Tooltip("climate.* entity whose target temperature the +/- buttons change (use_case_3/phrasebook.json climate_entity_id)")]
        public string targetEntity = "climate.aqara_floor_heating_thermostat";
        [Tooltip("Each simulated press adds this much (wraps back to simMin above simMax).")]
        public float simStep = 0.5f;
        public float simMin = 18f, simMax = 26f;
        [Tooltip("Setpoint limits, same as min_c / max_c in use_case_3/phrasebook.json")]
        public float targetMin = 5f, targetMax = 35f;

        float _value = 21f;
        float _target = float.NaN;
        string _measuredText = "--.-";

        public float Target => _target;
        /// <summary>Last measured temperature (simulated or from Home Assistant).</summary>
        public float Measured => _value;
        public bool HasMeasured { get; private set; }

        public override IEnumerable<string> ExtraEntityIds { get { if (!string.IsNullOrEmpty(targetEntity)) yield return targetEntity; } }

        void Awake() { if (display) display.text = "--.-"; }

        public override void Apply(TwinStateMessage m)
        {
            if (!m.available) { _measuredText = "n/a"; Refresh(); return; }
            if (m.hasNumber)
            {
                _value = m.number;
                HasMeasured = true;
                string unit = string.IsNullOrEmpty(m.unit) ? fallbackUnit : m.unit;
                _measuredText = m.number.ToString(format, CultureInfo.InvariantCulture) + "<size=60%>" + unit + "</size>";
            }
            else _measuredText = m.state;
            Refresh();
        }

        protected override void ApplyExtra(TwinStateMessage m)
        {
            if (m.hasTarget) { _target = m.target; Refresh(); }
        }

        void Refresh()
        {
            if (!display) return;
            display.text = float.IsNaN(_target)
                ? _measuredText
                : _measuredText + "\n<size=45%>→ " + _target.ToString("0.0", CultureInfo.InvariantCulture) + "</size>";
        }

        /// <summary>+/- buttons. Live: change the real setpoint. Offline: step the simulated temperature.</summary>
        public void SimulateAdjust(float delta)
        {
            if (!allowSimulatedInteraction || string.IsNullOrEmpty(entityId)) return;
            var router = TwinCommandRouter.Instance;
            if (router != null && router.IsLive && !string.IsNullOrEmpty(targetEntity))
            {
                float baseValue = float.IsNaN(_target) ? Mathf.Round(_value) : _target;
                float next = Mathf.Clamp(Mathf.Round((baseValue + delta) * 2f) / 2f, targetMin, targetMax);
                if (router.SetThermostatTarget(targetEntity, next)) { _target = next; Refresh(); return; }   // HA confirms within a moment
            }
            float sim = Mathf.Clamp(Mathf.Round((_value + delta) * 2f) / 2f, simMin, simMax);
            var m = TwinStateMessage.Make(entityId, sim.ToString("0.0", CultureInfo.InvariantCulture), "sensor");
            m.unit = fallbackUnit; m.device_class = "temperature";
            var r = TwinUdpReceiver.Instance;
            if (r != null) r.Inject(m); else Apply(m);
        }

        protected override TwinStateMessage BuildSimulatedToggle()
        {
            float next = _value + simStep;
            if (next > simMax) next = simMin;
            var m = TwinStateMessage.Make(entityId, next.ToString("0.0", CultureInfo.InvariantCulture), "sensor");
            m.unit = fallbackUnit;
            m.device_class = "temperature";
            return m;
        }
    }
}
