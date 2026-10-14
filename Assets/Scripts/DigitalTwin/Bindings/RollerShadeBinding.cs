using System;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// cover.* entity (Aqara Roller Shade Driver E1): rolls the shade fabric with its "Open" blend shape
    /// (0 = down/closed, 100 = up/open) and spins the roller tube while it moves.
    /// Understands states open / closed / opening / closing and the current_position attribute.
    /// </summary>
    public class RollerShadeBinding : TwinEntityBinding
    {
        public SkinnedMeshRenderer fabric;
        public string openBlendShape = "Open";
        [Tooltip("Roller tube (spins while moving). Its chain wheel spins with it.")]
        public Transform tube;
        [Tooltip("Seconds for a full travel. Measured on the lab Aqara E1 (14 Oct): ~30 s. HA only reports start/end, so the twin animates at this speed.")]
        public float travelSeconds = 30f;
        [Tooltip("Tube revolutions for a full travel (visual only)")]
        public float tubeTurns = 9f;
        [Range(0, 1)] public float startOpen = 1f;

        /// <summary>0 = fully down (closed), 1 = fully up (open).</summary>
        public float Position { get; private set; }
        public float Target { get; private set; }
        public bool IsClosed => Target <= 0.001f && Position <= 0.02f;
        public bool IsMoving => Mathf.Abs(Target - Position) > 0.001f;
        /// <summary>"open", "closed", "opening" or "closing" — what HA would report right now.</summary>
        public string State => IsMoving ? (Target > Position ? "opening" : "closing") : (Position <= 0.02f ? "closed" : "open");
        public event Action<string> StateChanged;

        int _shape = -1;
        Vector3 _tubeAxis = Vector3.right;
        string _lastState;

        void Awake()
        {
            if (fabric && fabric.sharedMesh) _shape = fabric.sharedMesh.GetBlendShapeIndex(openBlendShape);
            if (tube)
            {
                var mf = tube.GetComponent<MeshFilter>();
                if (mf && mf.sharedMesh)
                {
                    var s = mf.sharedMesh.bounds.size;     // spin around the tube's long axis
                    _tubeAxis = s.x >= s.y && s.x >= s.z ? Vector3.right : (s.y >= s.z ? Vector3.up : Vector3.forward);
                }
            }
            Position = Target = Mathf.Clamp01(startOpen);
            ApplyVisual(0f);
            _lastState = State;
        }

        bool _lastWasSimulated;

        public override void Apply(TwinStateMessage m)
        {
            if (!m.available) return;
            _lastWasSimulated = m.simulated;
            if (m.hasPosition) { Target = Mathf.Clamp01(m.position / 100f); if (m.state != "opening" && m.state != "closing") Position = Mathf.MoveTowards(Position, Target, 0.25f); }
            switch ((m.state ?? "").ToLowerInvariant())
            {
                case "open": if (!m.hasPosition) Target = 1f; break;
                case "closed": Target = 0f; break;
                case "opening": if (!m.hasPosition || Target <= Position) Target = 1f; break;
                case "closing": if (!m.hasPosition || Target >= Position) Target = 0f; break;
            }
        }

        void Update()
        {
            float before = Position;
            Position = Mathf.MoveTowards(Position, Target, Time.deltaTime / Mathf.Max(0.1f, travelSeconds));
            ApplyVisual(Position - before);
            var st = State;
            if (st != _lastState)
            {
                _lastState = st; StateChanged?.Invoke(st);
                // simulated travel finished -> report the final state like the real driver would
                if (_lastWasSimulated && !IsMoving && !string.IsNullOrEmpty(entityId) && TwinUdpReceiver.Instance != null)
                    TwinUdpReceiver.Instance.Inject(TwinStateMessage.Make(entityId, st, "cover"));
            }
        }

        void ApplyVisual(float delta)
        {
            if (fabric && _shape >= 0) fabric.SetBlendShapeWeight(_shape, Position * 100f);
            if (tube && Mathf.Abs(delta) > 0f) tube.Rotate(_tubeAxis, delta * tubeTurns * 360f, Space.Self);
        }

        /// <summary>Drive the shade without Home Assistant (VR press, offline demo).</summary>
        public void SimulateSet(bool open)
        {
            if (string.IsNullOrEmpty(entityId)) { Target = open ? 1f : 0f; return; }
            var m = TwinStateMessage.Make(entityId, open ? "opening" : "closing", "cover");
            var r = TwinUdpReceiver.Instance; if (r != null) r.Inject(m); else Apply(m);
        }

        protected override TwinStateMessage BuildSimulatedToggle()
            => TwinStateMessage.Make(entityId, Target > 0.5f ? "closing" : "opening", "cover");
    }
}
