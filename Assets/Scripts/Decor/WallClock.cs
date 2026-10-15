using System;
using UnityEngine;

namespace DigitalTwin.Decor
{
    /// <summary>Drives clock hands from the PC's local time. Hands rotate around the clock's local Z (face normal).</summary>
    public class WallClock : MonoBehaviour
    {
        public Transform hourHand, minuteHand, secondHand;
        [Tooltip("Sweep the second hand smoothly instead of ticking.")]
        public bool smoothSeconds = false;

        void Update()
        {
            var now = DateTime.Now;
            float sec = now.Second + (smoothSeconds ? now.Millisecond / 1000f : 0f);
            float min = now.Minute + sec / 60f;
            float hr = (now.Hour % 12) + min / 60f;
            if (hourHand) hourHand.localRotation = Quaternion.Euler(0, 0, -hr * 30f);
            if (minuteHand) minuteHand.localRotation = Quaternion.Euler(0, 0, -min * 6f);
            if (secondHand) secondHand.localRotation = Quaternion.Euler(0, 0, -sec * 6f);
        }
    }
}
