using UnityEngine;

namespace DigitalTwin
{
    /// <summary>light.* / switch.* entity: turns the pendant lamp (and its glowing bulb) on/off. Also mirrors state on the KNX switch LED.</summary>
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
        MaterialPropertyBlock _mpb;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        void Awake()
        {
            _mpb = new MaterialPropertyBlock();
            Set(startOn);
        }

        public override void Apply(TwinStateMessage m) => Set(m.available && m.IsOn);

        void Set(bool on)
        {
            _on = on;
            if (lights != null) foreach (var l in lights) if (l) l.enabled = on;
            if (emissiveBulbs != null)
                foreach (var r in emissiveBulbs)
                {
                    if (!r) continue;
                    r.GetPropertyBlock(_mpb);
                    _mpb.SetColor(EmissionId, on ? bulbEmission : Color.black);
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
