using System.Text;
using TMPro;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>World-space panel (readable in VR) showing the link status and the latest state of every entity.</summary>
    public class TwinStatusPanel : MonoBehaviour
    {
        public TextMeshPro text;
        public float refreshInterval = 0.25f;
        [Tooltip("Seconds without messages before the link is shown as idle.")]
        public float staleAfter = 30f;
        public int maxRows = 12;

        float _next;
        readonly StringBuilder _sb = new StringBuilder();

        void Update()
        {
            if (Time.unscaledTime < _next || text == null) return;
            _next = Time.unscaledTime + refreshInterval;
            var r = TwinUdpReceiver.Instance;
            _sb.Clear();
            _sb.Append("<b>IVAR LAB · DIGITAL TWIN</b>\n");
            if (r == null) _sb.Append("<color=#ff6b5b>No receiver in scene</color>\n");
            else
            {
                string link;
                if (!r.IsListening) link = $"<color=#ff6b5b>UDP :{r.port} not open</color> {r.LastError}";
                else if (r.LastMessageTime < 0) link = $"<color=#f5c542>Waiting for Home Assistant on UDP :{r.port}</color>";
                else
                {
                    float age = Time.unscaledTime - r.LastMessageTime;
                    link = age < staleAfter
                        ? $"<color=#5be38a>Live</color> · {r.MessagesReceived} msgs · last {age:0}s ago"
                        : $"<color=#f5c542>Idle</color> · {r.MessagesReceived} msgs · last {age:0}s ago";
                }
                var ha = HomeAssistantClient.Instance;
                if (ha != null)
                {
                    string hs = ha.State switch
                    {
                        HomeAssistantClient.Status.Connected => $"<color=#5be38a>Home Assistant: connected</color> · {ha.StatesReceived} updates",
                        HomeAssistantClient.Status.Connecting => "<color=#f5c542>Home Assistant: connecting…</color>",
                        HomeAssistantClient.Status.NoToken => "<color=#ff6b5b>Home Assistant: no token</color> <size=70%>(IVAR > Home Assistant Settings)</size>",
                        HomeAssistantClient.Status.AuthFailed => "<color=#ff6b5b>Home Assistant: token rejected</color>",
                        HomeAssistantClient.Status.Error => $"<color=#ff6b5b>Home Assistant: {ha.LastError}</color>",
                        _ => "<color=#9aa3ad>Home Assistant: off</color>"
                    };
                    _sb.Append(hs).Append("\n");
                }
                var cmd = TwinCommandRouter.Instance;
                if (cmd != null)
                {
                    string On(bool ok) => ok ? "<color=#5be38a>on</color>" : "<color=#9aa3ad>off</color>";
                    _sb.Append(cmd.IsLive ? "<color=#5be38a>Presses → real stand</color>" : "<color=#7fb2ff>Presses → simulated</color>")
                       .Append($" <size=70%>· lamp_api {On(cmd.LampApiOnline)} · motion_demo {On(cmd.MotionDemoOnline)}</size>\n");
                    if (!string.IsNullOrEmpty(cmd.LastResult)) _sb.Append($"<size=70%><color=#9aa3ad>last: {cmd.LastResult}</color></size>\n");
                }
                _sb.Append(link).Append("\n<size=70%><color=#9aa3ad>────────────────────────────</color></size>\n");
                int rows = 0;
                foreach (var kv in r.Latest)
                {
                    if (rows++ >= maxRows) { _sb.Append("…\n"); break; }
                    var m = kv.Value;
                    string val = !m.available ? "<color=#9aa3ad>unavailable</color>"
                               : m.hasNumber ? $"{m.number:0.0} {m.unit}"
                               : (m.IsOn ? $"<color=#5be38a>{m.state}</color>" : m.state);
                    string label = string.IsNullOrEmpty(m.name) ? m.entity_id : m.name;
                    _sb.Append($"{label}  <color=#9aa3ad><size=70%>{m.entity_id}</size></color>\n   {val}{(m.simulated ? "  <size=70%><color=#7fb2ff>(sim)</color></size>" : "")}\n");
                }
                if (rows == 0) _sb.Append("<color=#9aa3ad>No entities yet.\nPoint & pull trigger (VR) or click (desktop) on the door, switch, thermostat or sensor to simulate.</color>");
            }
            text.text = _sb.ToString();
        }
    }
}
