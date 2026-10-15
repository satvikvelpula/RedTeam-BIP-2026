using System.Collections;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>Anything that reacts to a VR trigger / mouse click directly (instead of the generic binding toggle).</summary>
    public interface ITwinPressable { void Press(); }

    /// <summary>A physical +/- button on the thermostat: presses in, then steps the temperature.</summary>
    public class ThermostatButton : MonoBehaviour, ITwinPressable
    {
        public ThermostatBinding thermostat;
        [Tooltip("+0.5 for the plus button, -0.5 for the minus button")]
        public float step = 0.5f;
        [Tooltip("How far the button travels into the housing (metres)")]
        public float travel = 0.0007f;

        Vector3 _rest;
        bool _animating;

        void Awake()
        {
            _rest = transform.localPosition;
            if (thermostat == null) thermostat = GetComponentInParent<ThermostatBinding>();
        }

        public void Press()
        {
            if (thermostat) thermostat.SimulateAdjust(step);
            if (!_animating && isActiveAndEnabled) StartCoroutine(Click());
        }

        IEnumerator Click()
        {
            _animating = true;
            var into = transform.parent.InverseTransformDirection(-(thermostat ? thermostat.transform.forward : transform.parent.forward)).normalized;
            var pressed = _rest + into * travel;                          // toward the wall, into the housing
            for (float t = 0; t < 1; t += Time.deltaTime / 0.06f) { transform.localPosition = Vector3.Lerp(_rest, pressed, t); yield return null; }
            for (float t = 0; t < 1; t += Time.deltaTime / 0.10f) { transform.localPosition = Vector3.Lerp(pressed, _rest, t); yield return null; }
            transform.localPosition = _rest;
            _animating = false;
        }
    }
}
