using System.Collections;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Wall switch press in VR / with the mouse: the button cap pushes into the frame and springs back,
    /// then the press goes to the binding as usual (real device when Home Assistant is connected).
    /// </summary>
    public class SwitchPress : MonoBehaviour, ITwinPressable
    {
        [Tooltip("Binding to send the press to. Found on this object or its parents.")]
        public TwinEntityBinding binding;
        [Tooltip("Parts that move together (cap + its label insert). Found by name if empty.")]
        public Transform[] parts;
        // New field names on purpose: the scene had travel = 4 mm / 0.06 s, too small to see in the headset.
        [Tooltip("How far the cap travels into the wall (metres, world space)")]
        public float pressDepth = 0.01f;
        public float pressSeconds = 0.1f, holdSeconds = 0.12f, releaseSeconds = 0.22f;

        Vector3[] _rest;
        bool _animating;

        void Awake()
        {
            if (!binding) binding = GetComponentInParent<TwinEntityBinding>();
            if (parts == null || parts.Length == 0)
            {
                var list = new System.Collections.Generic.List<Transform>();
                foreach (var n in new[] { "Button_Cap", "Insert" }) { var t = transform.Find(n); if (t) list.Add(t); }
                parts = list.ToArray();
            }
            _rest = new Vector3[parts.Length];
            for (int i = 0; i < parts.Length; i++) if (parts[i]) _rest[i] = parts[i].localPosition;
        }

        public void Press()
        {
            if (binding) binding.SimulateInteract();
            if (parts.Length > 0 && !_animating && isActiveAndEnabled) StartCoroutine(Click());
        }

        void Pose(float k)
        {
            // the switch faces into the room along +forward, so "into the wall" is -forward
            for (int i = 0; i < parts.Length; i++)
                if (parts[i]) parts[i].localPosition = _rest[i] + parts[i].parent.InverseTransformVector(-transform.forward * pressDepth) * k;
        }

        IEnumerator Click()
        {
            _animating = true;
            for (float t = 0; t < 1; t += Time.deltaTime / pressSeconds) { Pose(t); yield return null; }
            Pose(1);
            yield return new WaitForSeconds(holdSeconds);
            for (float t = 0; t < 1; t += Time.deltaTime / releaseSeconds) { Pose(1 - t); yield return null; }
            Pose(0);
            _animating = false;
        }
    }
}
