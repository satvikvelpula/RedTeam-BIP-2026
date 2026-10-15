using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.XR;

namespace DigitalTwin.VR
{
    /// <summary>
    /// Without a headset: left-click a device in the Game view to simulate a state change
    /// (keys 1-7 also work, see TwinKeyboardSimulator). Does nothing while a headset is active.
    /// Uses the new Input System (the legacy Input Manager is disabled for the Quest build).
    /// </summary>
    public class DesktopClickTester : MonoBehaviour
    {
        public Camera cam;

        void Update()
        {
            var mouse = Mouse.current;
            if (XRSettings.isDeviceActive || cam == null || mouse == null || !mouse.leftButton.wasPressedThisFrame) return;
            if (Physics.Raycast(cam.ScreenPointToRay(mouse.position.ReadValue()), out var hit, 20f, ~0, QueryTriggerInteraction.Collide))
            {
                var press = hit.collider.GetComponentInParent<ITwinPressable>();
                if (press != null) { press.Press(); return; }
                var b = hit.collider.GetComponentInParent<TwinEntityBinding>();
                if (b != null) b.SimulateInteract();
            }
        }
    }
}
