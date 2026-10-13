using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;
using UnityEngine.XR.Interaction.Toolkit.Interactors;

namespace DigitalTwin.VR
{
    /// <summary>
    /// Makes a room device usable with the XR Origin controllers (XR Interaction Toolkit 3).
    /// Point the controller ray at it and pull the TRIGGER (or press GRIP) to send a
    /// simulated Home Assistant state change through the device's TwinEntityBinding.
    /// </summary>
    [RequireComponent(typeof(XRSimpleInteractable))]
    public class TwinXRInteractable : MonoBehaviour
    {
        [Tooltip("Binding to trigger. Found automatically on this object or its parents.")]
        public TwinEntityBinding binding;

        XRSimpleInteractable _interactable;
        readonly List<IXRHoverInteractor> _hovering = new List<IXRHoverInteractor>();
        int _lastFrame = -1;

        void Awake()
        {
            _interactable = GetComponent<XRSimpleInteractable>();
            if (binding == null) binding = GetComponentInParent<TwinEntityBinding>();
        }

        void OnEnable()
        {
            _interactable.selectEntered.AddListener(OnSelect);
            _interactable.hoverEntered.AddListener(OnHoverEnter);
            _interactable.hoverExited.AddListener(OnHoverExit);
        }

        void OnDisable()
        {
            _interactable.selectEntered.RemoveListener(OnSelect);
            _interactable.hoverEntered.RemoveListener(OnHoverEnter);
            _interactable.hoverExited.RemoveListener(OnHoverExit);
            _hovering.Clear();
        }

        void OnHoverEnter(HoverEnterEventArgs a) { if (!_hovering.Contains(a.interactorObject)) _hovering.Add(a.interactorObject); }
        void OnHoverExit(HoverExitEventArgs a) { _hovering.Remove(a.interactorObject); }

        // Grip (select) while pointing at the device.
        void OnSelect(SelectEnterEventArgs a) => Press(a.interactorObject);

        // Trigger (activate) while pointing — XRI only sends "activated" to selected objects,
        // so read the trigger directly for hovered devices.
        void Update()
        {
            for (int i = 0; i < _hovering.Count; i++)
                if (_hovering[i] is XRBaseInputInteractor input && input.activateInput.ReadWasPerformedThisFrame())
                    Press(_hovering[i]);
        }

        void Press(IXRInteractor interactor)
        {
            if (Time.frameCount == _lastFrame) return;   // one action per press
            var pressable = GetComponent<ITwinPressable>();
            if (pressable == null && binding == null) return;
            _lastFrame = Time.frameCount;
            if (pressable != null) pressable.Press(); else binding.SimulateInteract();
            if (interactor is Component c)
            {
                var haptics = c.GetComponentInParent<UnityEngine.XR.Interaction.Toolkit.Inputs.Haptics.HapticImpulsePlayer>();
                if (haptics) haptics.SendHapticImpulse(0.4f, 0.08f);
            }
        }
    }
}
