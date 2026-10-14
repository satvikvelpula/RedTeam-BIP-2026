using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Connects Unity DIRECTLY to Home Assistant (WebSocket API, same as ha_twin_logger.py) — no Python,
    /// no UDP, no IP addresses. Every state the bindings care about is fed into TwinUdpReceiver, so the
    /// door, shade, LED strip, PIR etc. mirror the real devices while Play mode runs.
    /// Token: IVAR > Home Assistant Settings (stored outside the project), or the HA_TOKEN environment variable.
    /// </summary>
    [DefaultExecutionOrder(-90)]
    public class HomeAssistantClient : MonoBehaviour
    {
        public static HomeAssistantClient Instance { get; private set; }

        [Tooltip("Your Home Assistant address")]
        public string url = "http://homeassistant.local:8123";
        public bool connectOnStart = true;
        [Tooltip("Only forward entities used by bindings in the scene (plus the extras below).")]
        public bool onlyBoundEntities = true;
        public string[] extraEntities = { "media_player.famnest2" };

        public enum Status { Off, Connecting, Connected, NoToken, AuthFailed, Error }
        public Status State { get; private set; } = Status.Off;
        public string LastError { get; private set; }
        public int StatesReceived { get; private set; }
        public DateTime LastEventUtc { get; private set; }

        readonly ConcurrentQueue<TwinStateMessage> _queue = new ConcurrentQueue<TwinStateMessage>();
        readonly HashSet<string> _wanted = new HashSet<string>();
        CancellationTokenSource _cts;
        Status _loggedStatus = Status.Off;

        void Awake() { Instance = this; }
        void Start() { if (connectOnStart) Connect(); }
        void OnDisable() { Disconnect(); }
        void OnApplicationQuit() { Disconnect(); }

        // ------------------------------------------------------------------ token storage (outside the project / version control)
        public static string TokenFile => Path.Combine(Application.persistentDataPath, "home_assistant_token.txt");
        public static string LoadToken()
        {
            try { if (File.Exists(TokenFile)) { var t = File.ReadAllText(TokenFile).Trim(); if (t.Length > 0) return t; } } catch { }
            return Environment.GetEnvironmentVariable("HA_TOKEN") ?? "";
        }
        public static void SaveToken(string token)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(TokenFile));
            File.WriteAllText(TokenFile, (token ?? "").Trim());
        }

        // ------------------------------------------------------------------ connection
        public void Connect()
        {
            Disconnect();
            string token = LoadToken();
            if (string.IsNullOrEmpty(token))
            {
                State = Status.NoToken; LastError = "No token. Unity menu: IVAR > Home Assistant Settings";
                Debug.LogWarning("[HA] " + LastError);
                return;
            }
            _wanted.Clear();
            foreach (var b in FindObjectsOfType<TwinEntityBinding>(true))
            {
                if (!string.IsNullOrEmpty(b.entityId)) _wanted.Add(b.entityId);
                foreach (var x in b.ExtraEntityIds) if (!string.IsNullOrEmpty(x)) _wanted.Add(x);
            }
            if (extraEntities != null) foreach (var e in extraEntities) if (!string.IsNullOrEmpty(e)) _wanted.Add(e);
            _cts = new CancellationTokenSource();
            var ct = _cts.Token; var wsUrl = WsUrl(url);
            Task.Run(() => Loop(wsUrl, token, ct));
            Debug.Log($"[HA] Connecting to {wsUrl} for {_wanted.Count} entities: {string.Join(", ", _wanted)}");
        }

        public void Disconnect()
        {
            try { _cts?.Cancel(); } catch { }
            _cts = null;
            if (State == Status.Connected || State == Status.Connecting) State = Status.Off;
        }

        public static string WsUrl(string httpUrl)
        {
            var u = (httpUrl ?? "").Trim().TrimEnd('/');
            if (u.StartsWith("https://")) u = "wss://" + u.Substring(8); else if (u.StartsWith("http://")) u = "ws://" + u.Substring(7);
            return u + "/api/websocket";
        }

        async Task Loop(string wsUrl, string token, CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                using (var ws = new ClientWebSocket())
                {
                    try
                    {
                        State = Status.Connecting;
                        await ws.ConnectAsync(new Uri(wsUrl), ct);
                        await Receive(ws, ct);                                                   // auth_required
                        await Send(ws, new JObject { ["type"] = "auth", ["access_token"] = token }, ct);
                        var auth = JObject.Parse(await Receive(ws, ct) ?? "{}");
                        if ((string)auth["type"] != "auth_ok")
                        {
                            State = Status.AuthFailed; LastError = (string)auth["message"] ?? "authentication failed (check the token)";
                            return;                                                              // retrying won't help
                        }
                        State = Status.Connected; LastError = null;
                        await Send(ws, new JObject { ["id"] = 1, ["type"] = "get_states" }, ct);
                        await Send(ws, new JObject { ["id"] = 2, ["type"] = "subscribe_events", ["event_type"] = "state_changed" }, ct);
                        while (!ct.IsCancellationRequested && ws.State == WebSocketState.Open)
                        {
                            var raw = await Receive(ws, ct);
                            if (raw == null) break;
                            var m = JObject.Parse(raw);
                            if ((int?)m["id"] == 1 && (string)m["type"] == "result" && m["result"] is JArray all)
                            {
                                foreach (var s in all) if (s is JObject so) Enqueue("snapshot", so, null);
                            }
                            else if ((string)m["type"] == "event")
                            {
                                var d = m["event"]?["data"] as JObject;
                                if (d?["new_state"] is JObject nw) Enqueue("change", nw, d["old_state"] as JObject);
                            }
                        }
                    }
                    catch (OperationCanceledException) { break; }
                    catch (Exception e) { State = Status.Error; LastError = e.Message; }
                }
                if (ct.IsCancellationRequested) break;
                try { await Task.Delay(3000, ct); } catch { break; }                             // reconnect
            }
        }

        void Enqueue(string ev, JObject s, JObject old)
        {
            var id = (string)s["entity_id"];
            if (string.IsNullOrEmpty(id) || (onlyBoundEntities && _wanted.Count > 0 && !_wanted.Contains(id))) return;
            if (old != null && (string)old["state"] == (string)s["state"] && TwinAttrs(old) == TwinAttrs(s)) return;   // attribute noise
            _queue.Enqueue(ToMessage(ev, s, old));
        }

        static string TwinAttrs(JObject s)
        {
            var a = s["attributes"] as JObject;
            return a == null ? "" : $"{a["rgb_color"]}|{a["brightness"]}|{a["current_position"]}|{a["temperature"]}";
        }

        /// Same fields as ha_twin_logger.py make_msg().
        public static TwinStateMessage ToMessage(string ev, JObject s, JObject old)
        {
            var id = (string)s["entity_id"]; var a = s["attributes"] as JObject ?? new JObject();
            var state = (string)s["state"] ?? "";
            var m = new TwinStateMessage
            {
                schema = "twin.state.v1", @event = ev,
                ts = (string)s["last_changed"] ?? DateTime.UtcNow.ToString("o"), logged_at = DateTime.UtcNow.ToString("o"),
                entity_id = id, name = (string)a["friendly_name"] ?? id, domain = id.Contains(".") ? id.Substring(0, id.IndexOf('.')) : "",
                device_class = (string)a["device_class"] ?? "", state = state,
                available = state != "unavailable" && state != "unknown" && state != "",
                unit = (string)a["unit_of_measurement"] ?? "", prev_state = (string)old?["state"] ?? ""
            };
            if (m.domain == "binary_sensor") { m.on = state == "on"; m.hasOn = true; }
            if (float.TryParse(state, NumberStyles.Float, CultureInfo.InvariantCulture, out var n)) { m.number = n; m.hasNumber = true; }
            if (a["rgb_color"] is JArray rgb && rgb.Count >= 3) m.rgb_color = new[] { (int)rgb[0], (int)rgb[1], (int)rgb[2] };
            if (a["brightness"] != null && a["brightness"].Type != JTokenType.Null) { m.brightness = (float)a["brightness"]; m.hasBrightness = true; }
            if (a["current_position"] != null && a["current_position"].Type != JTokenType.Null) { m.position = (float)a["current_position"]; m.hasPosition = true; }
            if (m.domain == "climate" && a["temperature"] != null && a["temperature"].Type != JTokenType.Null) { m.target = (float)a["temperature"]; m.hasTarget = true; }
            return m;
        }

        static async Task<string> Receive(ClientWebSocket ws, CancellationToken ct)
        {
            var buf = new ArraySegment<byte>(new byte[32768]);
            using (var ms = new MemoryStream())
            {
                WebSocketReceiveResult r;
                do
                {
                    r = await ws.ReceiveAsync(buf, ct);
                    if (r.MessageType == WebSocketMessageType.Close) return null;
                    ms.Write(buf.Array, 0, r.Count);
                } while (!r.EndOfMessage);
                return Encoding.UTF8.GetString(ms.ToArray());
            }
        }

        static Task Send(ClientWebSocket ws, JObject o, CancellationToken ct)
            => ws.SendAsync(new ArraySegment<byte>(Encoding.UTF8.GetBytes(o.ToString(Newtonsoft.Json.Formatting.None))), WebSocketMessageType.Text, true, ct);

        void Update()
        {
            if (State != _loggedStatus)
            {
                _loggedStatus = State;
                if (State == Status.Connected) Debug.Log("[HA] Connected to Home Assistant — mirroring live states.");
                else if (State == Status.AuthFailed || State == Status.Error) Debug.LogWarning($"[HA] {State}: {LastError}");
            }
            var rx = TwinUdpReceiver.Instance;
            while (_queue.TryDequeue(out var m))
            {
                StatesReceived++; LastEventUtc = DateTime.UtcNow;
                if (rx != null) rx.Inject(m);
            }
        }
    }
}
