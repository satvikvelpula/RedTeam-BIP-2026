using UnityEngine;
using UnityEngine.XR;

namespace DigitalTwin.VR
{
    /// <summary>
    /// Without a headset: left-click a device in the Game view to simulate a state change
    /// (keys 1-5 also work, see TwinKeyboardSimulator). Does nothing while a headset is active.
    /// </summary>
    public class DesktopClickTester : MonoBehaviour
    {
        public Camera cam;

        void Update()
        {
            if (XRSettings.isDeviceActive || cam == null || !Input.GetMouseButtonDown(0)) return;
            if (Physics.Raycast(cam.ScreenPointToRay(Input.mousePosition), out var hit, 20f, ~0, QueryTriggerInteraction.Collide))
            {
                var press = hit.collider.GetComponentInParent<ITwinPressable>();
                if (press != null) { press.Press(); return; }
                var b = hit.collider.GetComponentInParent<TwinEntityBinding>();
                if (b != null) b.SimulateInteract();
            }
        }
    }
}
