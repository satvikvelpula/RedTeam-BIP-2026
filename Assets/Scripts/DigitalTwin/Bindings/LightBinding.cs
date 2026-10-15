using UnityEngine;

namespace DigitalTwin
{
    /// <summary>light.* / switch.* entity: turns the pendant lamp (and its glowing bulb) on/off and dims it with HA brightness (use case 1). Also mirrors state on the KNX switch LED.</summary>
    public class LightBinding : TwinEntityBinding
    {
        public Light[] lights;
        public Renderer[] emissiveBulbs;
        public Color bulbEmission = new Color(1f, 0.75f, 0.45f) * 2.5f;
        [Tooltip("Optional: LED on the wall switch that shows the state.")]
        public Renderer switchLed;
        public Color switchLedOn = new Color(0.45f, 1.35f, 3f);
        public Color switchLedOff = new Color(0.05f, 0.08f, 0.12f);
        public bool startOn = true;

        bool _on;
        /// <summary>What the twin shows right now (used when no state has come from Home Assistant yet).</summary>
        public bool ShownOn => _on;
        float _level = 1f;                 // 0-1, from HA "brightness" (the lab lamp is a dimmer)
        float[] _baseIntensity;
        MaterialPropertyBlock _mpb;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        void Awake()
        {
            _mpb = new MaterialPropertyBlock();
            if (lights != null) { _baseIntensity = new float[lights.Length]; for (int i = 0; i < lights.Length; i++) _baseIntensity[i] = lights[i] ? lights[i].intensity : 1f; }
            Set(startOn);
        }

        public override void Apply(TwinStateMessage m)
        {
            if (m.hasBrightness) _level = Mathf.Clamp01(m.brightness / 255f);
            else if (m.IsOn && !m.simulated) _level = 1f;
            Set(m.available && m.IsOn);
        }

        void Set(bool on)
        {
            _on = on;
            float k = Mathf.Lerp(0.15f, 1f, _level);
            if (lights != null)
                for (int i = 0; i < lights.Length; i++)
                {
                    if (!lights[i]) continue;
                    lights[i].enabled = on;
                    if (_baseIntensity != null) lights[i].intensity = _baseIntensity[i] * k;
                }
            if (emissiveBulbs != null)
                foreach (var r in emissiveBulbs)
                {
                    if (!r) continue;
                    r.GetPropertyBlock(_mpb);
                    _mpb.SetColor(EmissionId, on ? bulbEmission * k : Color.black);
                    r.SetPropertyBlock(_mpb);
                }
            if (switchLed)
            {
                switchLed.GetPropertyBlock(_mpb);
                _mpb.SetColor(EmissionId, on ? switchLedOn : switchLedOff);
                switchLed.SetPropertyBlock(_mpb);
            }
        }

        protected override TwinStateMessage BuildSimulatedToggle()
        {
            string domain = entityId.StartsWith("switch.") ? "switch" : "light";
            return TwinStateMessage.Make(entityId, _on ? "off" : "on", domain);
        }
    }
}
