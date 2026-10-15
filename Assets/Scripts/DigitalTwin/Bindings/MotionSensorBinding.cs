using UnityEngine;

namespace DigitalTwin
{
    /// <summary>PIR / occupancy sensor: tints the detection cone and lights the status LED when motion is detected.</summary>
    public class MotionSensorBinding : TwinEntityBinding
    {
        public Renderer detectionZone;
        public Renderer statusLed;
        public Color idleZoneColor = new Color(0.49f, 0.80f, 1f, 0.06f);
        public Color activeZoneColor = new Color(1f, 0.35f, 0.25f, 0.22f);
        public Color ledActive = new Color(1f, 0.25f, 0.15f);
        [Tooltip("Seconds to fade between states.")]
        public float fade = 0.3f;

        MaterialPropertyBlock _mpb;
        bool _active;
        float _t;
        static readonly int ColorId = Shader.PropertyToID("_Color");
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

        void Awake()
        {
            _mpb = new MaterialPropertyBlock();
            if (statusLed) foreach (var mat in statusLed.sharedMaterials) if (mat) mat.EnableKeyword("_EMISSION");
            Refresh(0f);
        }

        public override void Apply(TwinStateMessage m) => _active = m.available && m.IsOn;

        void Update()
        {
            float goal = _active ? 1f : 0f;
            if (!Mathf.Approximately(_t, goal)) { _t = Mathf.MoveTowards(_t, goal, Time.deltaTime / Mathf.Max(0.01f, fade)); Refresh(_t); }
        }

        void Refresh(float t)
        {
            if (detectionZone)
            {
                detectionZone.GetPropertyBlock(_mpb);
                _mpb.SetColor(ColorId, Color.Lerp(idleZoneColor, activeZoneColor, t));
                detectionZone.SetPropertyBlock(_mpb);
            }
            if (statusLed)
            {
                statusLed.GetPropertyBlock(_mpb);
                _mpb.SetColor(EmissionId, ledActive * Mathf.Lerp(0.2f, 4f, t));
                statusLed.SetPropertyBlock(_mpb);
            }
        }

        protected override TwinStateMessage BuildSimulatedToggle()
            => TwinStateMessage.Make(entityId, _active ? "off" : "on", "binary_sensor");
    }
}
