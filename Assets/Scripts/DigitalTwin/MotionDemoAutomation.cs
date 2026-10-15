using System.Collections;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Unity mirror of motion_demo.py, for testing WITHOUT Home Assistant:
    ///   motion ON                     -> shade DOWN
    ///   motion OFF for offDelay sec   -> shade UP
    ///   shade closed                  -> strip RED, otherwise GREEN
    /// It only reacts to simulated events (VR press, keys, test sender). Real Home Assistant events
    /// are left alone — with motion_demo.py running, HA itself does this and the twin just mirrors it.
    /// </summary>
    public class MotionDemoAutomation : MonoBehaviour
    {
        public MotionSensorBinding motion;
        public RollerShadeBinding shade;
        public LedStripBinding strip;
        public float offDelay = 10f;
        [Tooltip("Also run the demo for REAL motion events (only if motion_demo.py is NOT running).")]
        public bool reactToRealEvents = false;

        Coroutine _off;
        bool _active;
        TwinUdpReceiver _rx;

        void Start()
        {
            _rx = TwinUdpReceiver.Instance;
            if (_rx != null) _rx.OnMessage += OnMessage;
            if (shade != null) shade.StateChanged += OnShadeState;
        }

        void OnDestroy()
        {
            if (_rx != null) _rx.OnMessage -= OnMessage;
            if (shade != null) shade.StateChanged -= OnShadeState;
        }

        void OnMessage(TwinStateMessage m)
        {
            if (motion == null || m.entity_id != motion.entityId) return;
            if (!m.simulated && !reactToRealEvents) return;
            if (m.IsOn)
            {
                if (_off != null) { StopCoroutine(_off); _off = null; }
                if (_active) return;
                _active = true;
                Debug.Log("[Demo] MOTION -> shade DOWN");
                if (shade) shade.SimulateSet(false);
            }
            else if (_active && _off == null)
            {
                Debug.Log($"[Demo] no motion -> shade UP in {offDelay:0} s");
                _off = StartCoroutine(OffLater());
            }
        }

        IEnumerator OffLater()
        {
            yield return new WaitForSeconds(offDelay);
            _off = null; _active = false;
            Debug.Log("[Demo] CLEAR -> shade UP");
            if (shade) shade.SimulateSet(true);
        }

        // shade closed -> RED, open/opening/closing -> GREEN (only while the demo drives things)
        void OnShadeState(string state)
        {
            if (strip == null || (!_active && _off == null && state != "open")) return;
            bool down = state == "closed";
            strip.SimulateColor(true, down ? Color.red : Color.green);
        }
    }
}
