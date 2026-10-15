using System;
using System.Collections.Concurrent;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// VR -> real stand. When Home Assistant is connected, a press on a device in the twin is sent
    /// to the REAL device instead of being simulated; the twin then updates from the real state that
    /// Home Assistant reports back (HomeAssistantClient), so what you see is always the stand.
    ///
    ///   Use case 1  lamp           -> lamp_api.py  (POST http://127.0.0.1:8765/devices/lamp/set),
    ///                                 falls back to HA light.turn_on/off if lamp_api.py isn't running
    ///   Use case 4  motion sensor  -> motion_demo.py --http (POST http://127.0.0.1:8767/scene)
    ///               roller shade   -> HA cover.open_cover / close_cover (motion_demo.py reacts to it)
    ///               LED strip      -> HA light.turn_on / turn_off
    ///   Use case 2  window sensor  -> read-only: mirrored live, a press does nothing on the stand
    ///   Use case 3  thermostat +/- -> temperature.py serve (POST http://127.0.0.1:8766/devices/temperature/set),
    ///                                 falls back to HA climate.set_temperature; siren is driven by temperature.py
    ///
    /// Without Home Assistant (at home, no token) every press is simulated locally, as before.
    /// Uses HttpClient, not UnityWebRequest, so plain-http URLs work without changing Player Settings.
    /// </summary>
    [DefaultExecutionOrder(-80)]
    public class TwinCommandRouter : MonoBehaviour
    {
        public static TwinCommandRouter Instance { get; private set; }

        [Tooltip("Send presses to the real devices when Home Assistant is connected. Off = always simulate.")]
        public bool sendToRealDevices = true;

        [Header("Use case 1 - lamp (lamp_api.py serve)")]
        [Tooltip("Must match ha_entity_id in use_case_1/phrasebook.json")]
        public string lampEntity = "light.aqara_dimmer_switch_h2_2";
        public string lampApiUrl = "http://127.0.0.1:8765";

        [Header("Use case 4 - motion demo (motion_demo.py --http 8767)")]
        public string motionDemoUrl = "http://127.0.0.1:8767";

        [Header("Use case 3 - temperature (use_case_3/temperature.py serve)")]
        public string temperatureApiUrl = "http://127.0.0.1:8766";

        public string LastResult { get; private set; } = "";
        public bool LampApiOnline { get; private set; }
        public bool MotionDemoOnline { get; private set; }
        public bool TemperatureApiOnline { get; private set; }

        static readonly HttpClient Http = new HttpClient { Timeout = TimeSpan.FromSeconds(6) };
        readonly ConcurrentQueue<Action> _main = new ConcurrentQueue<Action>();
        float _nextProbe;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void AutoCreate()
        {
            if (FindObjectOfType<TwinCommandRouter>() != null) return;
            var host = FindObjectOfType<HomeAssistantClient>();
            var go = host != null ? host.gameObject : new GameObject("TwinCommandRouter");
            go.AddComponent<TwinCommandRouter>();
        }

        void Awake()
        {
            if (Instance != null && Instance != this) { Destroy(this); return; }
            Instance = this;
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        /// <summary>True when presses go to the real stand.</summary>
        public bool IsLive
        {
            get
            {
                if (!sendToRealDevices) return false;
                if (Direct) return true;
                var br = TwinBridgeClient.Instance;               // headset: the laptop bridge is connected to HA
                return br != null && br.HaConnected;
            }
        }

        /// <summary>This app has its own Home Assistant connection (Editor / PC with a token).</summary>
        bool Direct { get { var ha = HomeAssistantClient.Instance; return ha != null && ha.State == HomeAssistantClient.Status.Connected; } }
        /// <summary>Headset mode: commands go through twin_bridge.py on the laptop.</summary>
        bool ViaBridge => !Direct && TwinBridgeClient.Instance != null && TwinBridgeClient.Instance.IsConnected;
        static bool IsLocal(string url) => url.StartsWith("http://127.0.0.1") || url.StartsWith("http://localhost");

        void Update()
        {
            while (_main.TryDequeue(out var a)) a();
            if (Time.unscaledTime >= _nextProbe)                       // show helper scripts' status on the panel
            {
                _nextProbe = Time.unscaledTime + 5f;
                Probe(lampApiUrl + "/health", ok => LampApiOnline = ok);
                Probe(motionDemoUrl + "/health", ok => MotionDemoOnline = ok);
                Probe(temperatureApiUrl + "/health", ok => TemperatureApiOnline = ok);
            }
        }

        // ------------------------------------------------------------------ called by TwinEntityBinding.SimulateInteract

        /// <summary>Handle a press. Returns false if it should be simulated locally instead.</summary>
        public bool TryHandlePress(TwinEntityBinding b)
        {
            if (!IsLive || b == null || string.IsNullOrEmpty(b.entityId)) return false;
            string id = b.entityId;
            // no state from HA yet -> toggle what the twin shows instead of always sending "on"
            bool isOn = b.Current != null ? b.Current.IsOn : (b is LightBinding lb ? lb.ShownOn : b is LedStripBinding sb && sb.IsOn);

            if (b is MotionSensorBinding)
            {
                // Task 4: run the motion scene in motion_demo.py (shade down, strip red, jazz).
                Post(motionDemoUrl + "/scene", "{}", "motion_demo /scene",
                     onFail: () => { Debug.LogWarning("[Cmd] motion_demo.py --http is not running — simulating the motion locally."); b.SimulateLocal(); });
                return true;
            }
            if (b is RollerShadeBinding shade)
            {
                bool open = shade.Target <= 0.5f;
                CallService("cover", open ? "open_cover" : "close_cover", id);
                return true;
            }
            if (b is LightBinding && id == lampEntity)
            {
                // Use case 1: through lamp_api.py (it translates and logs the KNX/Matter write).
                string value = isOn ? "off" : "on";
                Post(lampApiUrl + "/devices/lamp/set", "{\"value\":\"" + value + "\"}", "lamp_api " + value,
                     onFail: () => CallService("light", isOn ? "turn_off" : "turn_on", id));
                return true;
            }
            if (id.StartsWith("light.") || id.StartsWith("switch."))
            {
                string domain = id.Substring(0, id.IndexOf('.'));
                CallService(domain, isOn ? "turn_off" : "turn_on", id);
                return true;
            }
            if (id.StartsWith("binary_sensor.") || id.StartsWith("sensor.") || id.StartsWith("siren."))
            {
                Debug.Log($"[Cmd] {id} is a real sensor (read-only) — the twin shows its live state; open/close it on the stand.");
                return true;                                            // don't fake a state the stand doesn't have
            }
            return false;
        }

        // ------------------------------------------------------------------ for sliders / UI

        /// <summary>Lamp brightness 0-255 (0 = off). Use case 1.</summary>
        public void SetLampBrightness(int level)
        {
            level = Mathf.Clamp(level, 0, 255);
            if (!IsLive) { InjectSim(lampEntity, level > 0 ? "on" : "off", "light", m => { m.brightness = level; m.hasBrightness = true; }); return; }
            Post(lampApiUrl + "/devices/lamp/set", "{\"brightness\":" + level + "}", "lamp_api brightness " + level,
                 onFail: () => CallService("light", level > 0 ? "turn_on" : "turn_off", lampEntity, level > 0 ? ",\"brightness\":" + level : ""));
        }

        /// <summary>Thermostat setpoint in °C (use case 3). Returns false when offline, so the caller simulates.</summary>
        public bool SetThermostatTarget(string climateEntity, float celsius)
        {
            if (!IsLive || string.IsNullOrEmpty(climateEntity)) return false;
            string v = celsius.ToString("0.0", System.Globalization.CultureInfo.InvariantCulture);
            Post(temperatureApiUrl + "/devices/temperature/set", "{\"temperature_c\":" + v + "}", "temperature.py set " + v,
                 onFail: () => CallService("climate", "set_temperature", climateEntity, ",\"temperature\":" + v));
            return true;
        }

        /// <summary>Shade position 0 (down) - 100 (up).</summary>
        public void SetShadePosition(string coverEntity, int percent)
        {
            percent = Mathf.Clamp(percent, 0, 100);
            if (!IsLive) { InjectSim(coverEntity, percent > 0 ? "open" : "closed", "cover", m => { m.position = percent; m.hasPosition = true; }); return; }
            CallService("cover", "set_cover_position", coverEntity, ",\"position\":" + percent);
        }

        // ------------------------------------------------------------------ HTTP

        /// <summary>POST /api/services/{domain}/{service} on Home Assistant.</summary>
        public void CallService(string domain, string service, string entityId, string extraJson = "")
        {
            if (ViaBridge)
            {
                string bl = $"HA {domain}.{service} {entityId} (bridge)";
                JObject data;
                try { data = JObject.Parse("{\"entity_id\":\"" + entityId + "\"" + extraJson + "}"); }
                catch { data = new JObject { ["entity_id"] = entityId }; }
                TwinBridgeClient.Instance.CallService(domain, service, data, (ok, code, text) => Report(bl, ok, code, text, null));
                return;
            }
            var ha = HomeAssistantClient.Instance;
            if (ha == null) return;
            string url = ha.url.Trim().TrimEnd('/') + $"/api/services/{domain}/{service}";
            string body = "{\"entity_id\":\"" + entityId + "\"" + extraJson + "}";
            Post(url, body, $"HA {domain}.{service} {entityId}", auth: HomeAssistantClient.LoadToken());
        }

        void Post(string url, string json, string label, Action onFail = null, string auth = null)
        {
            if (auth == null && ViaBridge && IsLocal(url))                 // helper scripts run on the laptop, not the headset
            {
                TwinBridgeClient.Instance.Http("POST", url, json, (ok, code, text) => Report(label + " (bridge)", ok, code, text, onFail));
                return;
            }
            Task.Run(async () =>
            {
                try
                {
                    using (var req = new HttpRequestMessage(HttpMethod.Post, url))
                    {
                        req.Content = new StringContent(json, Encoding.UTF8, "application/json");
                        if (!string.IsNullOrEmpty(auth)) req.Headers.Add("Authorization", "Bearer " + auth);
                        using (var r = await Http.SendAsync(req))
                        {
                            int code = (int)r.StatusCode;
                            string text = await r.Content.ReadAsStringAsync();
                            _main.Enqueue(() =>
                            {
                                LastResult = $"{label} -> HTTP {code}";
                                if (code >= 200 && code < 300) Debug.Log("[Cmd] " + LastResult);
                                else { Debug.LogWarning($"[Cmd] {LastResult}: {Trim(text)}"); onFail?.Invoke(); }
                            });
                        }
                    }
                }
                catch (Exception e)
                {
                    string msg = e.InnerException?.Message ?? e.Message;
                    _main.Enqueue(() =>
                    {
                        LastResult = $"{label} -> {msg}";
                        if (onFail != null) onFail(); else Debug.LogWarning("[Cmd] " + LastResult);
                    });
                }
            });
        }

        void Report(string label, bool ok, int code, string text, Action onFail)
        {
            LastResult = code > 0 ? $"{label} -> HTTP {code}" : $"{label} -> {text}";
            if (ok) { Debug.Log("[Cmd] " + LastResult); return; }
            Debug.LogWarning($"[Cmd] {LastResult}: {Trim(text)}");
            onFail?.Invoke();
        }

        void Probe(string url, Action<bool> set)
        {
            if (ViaBridge && IsLocal(url)) { TwinBridgeClient.Instance.Http("GET", url, null, (ok, c, t) => set(ok)); return; }
            Task.Run(async () =>
            {
                bool ok;
                try { using (var r = await Http.GetAsync(url)) ok = r.IsSuccessStatusCode; } catch { ok = false; }
                _main.Enqueue(() => set(ok));
            });
        }

        static void InjectSim(string entityId, string state, string domain, Action<TwinStateMessage> fill)
        {
            var m = TwinStateMessage.Make(entityId, state, domain);
            fill?.Invoke(m);
            TwinUdpReceiver.Instance?.Inject(m);
        }

        static string Trim(string s) => string.IsNullOrEmpty(s) ? "" : (s.Length > 200 ? s.Substring(0, 200) + "…" : s);
    }
}
