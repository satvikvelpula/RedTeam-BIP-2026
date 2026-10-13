using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Base class: links one Home Assistant entity_id to something in the room.
    /// Subclasses implement Apply() for real messages and BuildSimulatedToggle() for testing.
    /// </summary>
    public abstract class TwinEntityBinding : MonoBehaviour
    {
        [Tooltip("Home Assistant entity_id, e.g. binary_sensor.window_door_is_open. Run ha_twin_logger.py --list to see yours.")]
        public string entityId;

        [Tooltip("When pointed at in VR (trigger) or clicked with the mouse, send a simulated state change.")]
        public bool allowSimulatedInteraction = true;

        public TwinStateMessage Current { get; private set; }

        TwinUdpReceiver _receiver;

        protected virtual void Start()
        {
            _receiver = TwinUdpReceiver.Instance != null ? TwinUdpReceiver.Instance : FindObjectOfType<TwinUdpReceiver>();
            if (_receiver == null) { Debug.LogWarning($"[Twin] No TwinUdpReceiver in scene for {name}"); return; }
            _receiver.OnMessage += Handle;
            if (!string.IsNullOrEmpty(entityId) && _receiver.TryGetLatest(entityId, out var m)) Handle(m);
        }

        protected virtual void OnDestroy()
        {
            if (_receiver != null) _receiver.OnMessage -= Handle;
        }

        void Handle(TwinStateMessage m)
        {
            if (string.IsNullOrEmpty(entityId) || m.entity_id != entityId) return;
            Current = m;
            Apply(m);
        }

        /// <summary>Update the visuals for a new state.</summary>
        public abstract void Apply(TwinStateMessage m);

        /// <summary>The message a "press" in VR should produce (e.g. flip on/off).</summary>
        protected abstract TwinStateMessage BuildSimulatedToggle();

        /// <summary>
        /// Called by VR trigger / mouse click / test keys. With Home Assistant connected the press goes to the
        /// REAL device (TwinCommandRouter) and the twin follows the real state; otherwise it is simulated.
        /// </summary>
        public void SimulateInteract()
        {
            if (!allowSimulatedInteraction || string.IsNullOrEmpty(entityId)) return;
            var router = TwinCommandRouter.Instance;
            if (router != null && router.TryHandlePress(this)) return;
            SimulateLocal();
        }

        /// <summary>Toggle only inside the twin (no real device). Routes through the receiver so everything updates consistently.</summary>
        public void SimulateLocal()
        {
            if (string.IsNullOrEmpty(entityId)) return;
            var m = BuildSimulatedToggle();
            if (m == null) return;
            if (_receiver != null) _receiver.Inject(m); else { Current = m; Apply(m); }
        }

        protected bool CurrentIsOn => Current != null && Current.IsOn;
    }
}
