using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// light.* RGB strip (Fibaro RGBW Controller): colours the LED strip on the demo board.
    /// Uses rgb_color/brightness when the logger sends them; otherwise mirrors motion_demo.py
    /// (red while the shade is down, green otherwise).
    /// </summary>
    public class LedStripBinding : TwinEntityBinding
    {
        public Renderer[] leds;
        [Tooltip("Optional point light so the strip actually lights its surroundings")]
        public Light glow;
        public float emissionStrength = 6f;
        [Tooltip("Used to guess the colour when HA doesn't report one")]
        public RollerShadeBinding shade;
        public Color offColor = new Color(0.04f, 0.035f, 0.03f);
        public bool startOn = false;

        public bool IsOn { get; private set; }

        /// <summary>Alarm mode (TwinAlarmScene): show solid red regardless of the real state. null = normal.</summary>
        public Color? Override { get => _override; set { _override = value; Refresh(_lastBrightness); } }
        Color? _override;
        float _lastBrightness = 1f;
        public Color CurrentColor { get; private set; } = Color.green;
        bool _hasExplicitColor;
        MaterialPropertyBlock _mpb;
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        static readonly int ColorId = Shader.PropertyToID("_Color");

        void Awake()
        {
            _mpb = new MaterialPropertyBlock();
            if (leds != null) foreach (var r in leds) if (r) foreach (var m in r.sharedMaterials) if (m) m.EnableKeyword("_EMISSION");
            IsOn = startOn; Refresh();
        }

        public override void Apply(TwinStateMessage m)
        {
            IsOn = m.available && m.IsOn;
            if (m.HasColor) { CurrentColor = m.Color; _hasExplicitColor = true; }
            Refresh(m.hasBrightness ? Mathf.Clamp01(m.brightness / 255f) : 1f);
        }

        void Update()
        {
            // no colour from HA -> follow the demo rule live (red while the shade is down)
            if (IsOn && !_hasExplicitColor && shade)
            {
                var want = shade.IsClosed ? Color.red : Color.green;
                if (want != CurrentColor) { CurrentColor = want; Refresh(); }
            }
        }

        void Refresh(float brightness = 1f)
        {
            _lastBrightness = brightness;
            if (_override.HasValue) { Paint(true, _override.Value, 1f); return; }
            Paint(IsOn, CurrentColor, brightness);
        }

        void Paint(bool on, Color col, float brightness)
        {
            var c = on ? col * Mathf.Max(0.05f, brightness) : offColor;
            if (leds != null)
                foreach (var r in leds)
                {
                    if (!r) continue;
                    r.GetPropertyBlock(_mpb);
                    _mpb.SetColor(EmissionId, on ? c * emissionStrength : Color.black);
                    _mpb.SetColor(ColorId, on ? col : offColor);          // pure colour, no warm tint
                    r.SetPropertyBlock(_mpb);
                }
            if (glow) { glow.enabled = on; glow.color = col; glow.intensity = 0.6f * brightness; }
        }

        /// <summary>Set colour without HA (offline demo).</summary>
        public void SimulateColor(bool on, Color color)
        {
            var m = TwinStateMessage.Make(entityId, on ? "on" : "off", "light");
            m.rgb_color = new[] { Mathf.RoundToInt(color.r * 255), Mathf.RoundToInt(color.g * 255), Mathf.RoundToInt(color.b * 255) };
            m.brightness = 255; m.hasBrightness = true;
            var r = TwinUdpReceiver.Instance; if (r != null) r.Inject(m); else Apply(m);
        }

        protected override TwinStateMessage BuildSimulatedToggle()
            => TwinStateMessage.Make(entityId, IsOn ? "off" : "on", "light");
    }
}
