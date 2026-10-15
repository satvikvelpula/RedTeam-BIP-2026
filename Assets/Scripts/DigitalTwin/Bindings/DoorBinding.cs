using UnityEngine;

namespace DigitalTwin
{
    /// <summary>Door/window contact sensor: swings the door leaf open (on) or closed (off).</summary>
    public class DoorBinding : TwinEntityBinding
    {
        [Tooltip("The hinge transform that rotates (Door_leaf).")]
        public Transform hinge;
        [Tooltip("Rotation around world up from the OPEN pose (as modelled) to the closed pose.")]
        public float closedOffsetDegrees = -98f;
        public float swingSpeedDegPerSec = 120f;
        [Tooltip("State shown before any message arrives.")]
        public bool startOpen = false;

        Quaternion _openRot, _closedRot;
        bool _targetOpen;

        void Awake()
        {
            if (hinge == null) hinge = transform;
            _openRot = hinge.rotation;
            _closedRot = Quaternion.AngleAxis(closedOffsetDegrees, Vector3.up) * _openRot;
            _targetOpen = startOpen;
            hinge.rotation = _targetOpen ? _openRot : _closedRot;
        }

        public override void Apply(TwinStateMessage m) => _targetOpen = m.available && m.IsOn;

        void Update()
        {
            var target = _targetOpen ? _openRot : _closedRot;
            hinge.rotation = Quaternion.RotateTowards(hinge.rotation, target, swingSpeedDegPerSec * Time.deltaTime);
        }

        protected override TwinStateMessage BuildSimulatedToggle()
            => TwinStateMessage.Make(entityId, _targetOpen ? "off" : "on", "binary_sensor");
    }
}
