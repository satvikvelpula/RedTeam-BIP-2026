using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Headset (standalone Quest) -> laptop link. The headset has no Home Assistant token and may not
    /// reach Home Assistant at all, so it talks to Scripts/twin_bridge.py on the lab laptop instead:
    ///   * every 2 s it sends "hello" (UDP broadcast + bridgeHost, port 5006) with the entities it needs;
    ///   * the bridge answers from its own IP: state messages (twin.state.v1) to our UDP port 5005,
    ///     heartbeats and command results (twin.bridge.v1), which TwinUdpReceiver hands to us;
    ///   * presses go back to the bridge as "call_service" (HA) or "http" (helper scripts on the laptop).
    /// No IP addresses to type: the bridge is found by broadcast and remembered from its replies.
    /// In the Editor it is off by default, because the Editor connects to Home Assistant directly.
    /// </summary>
    [DefaultExecutionOrder(-85)]
    public class TwinBridgeClient : MonoBehaviour
    {
        public static TwinBridgeClient Instance { get; private set; }

        [Tooltip("UDP port twin_bridge.py listens on (--port)")]
        public int bridgePort = 5006;
        [Tooltip("Tried besides broadcast. 192.168.137.1 = laptop running a Windows mobile hotspot.")]
        public string bridgeHost = "192.168.137.1";
        public bool useInEditor = false;
        public float helloInterval = 2f;
        public float timeoutSeconds = 8f;

        /// <summary>Bridge answered recently.</summary>
        public bool IsConnected => _bridgeIp != null && Time.unscaledTime - _lastSeen < timeoutSeconds;
        /// <summary>The bridge itself is connected to Home Assistant.</summary>
        public bool HaConnected => IsConnected && _haConnected;
        public string BridgeIp => _bridgeIp;
        public bool IsActive => _udp != null;

        UdpClient _udp;
        string _bridgeIp;
        float _lastSeen = -1000f, _nextHello;
        bool _haConnected;
        int _nextId = 1;
        string[] _entities;
        readonly Dictionary<int, Action<bool, int, string>> _pending = new Dictionary<int, Action<bool, int, string>>();
        readonly Dictionary<int, float> _sentAt = new Dictionary<int, float>();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void AutoCreate()
        {
            if (FindObjectOfType<TwinBridgeClient>() != null) return;
            var rx = FindObjectOfType<TwinUdpReceiver>();
            var go = rx != null ? rx.gameObject : new GameObject("TwinBridgeClient");
            go.AddComponent<TwinBridgeClient>();
        }

        void Awake()
        {
            if (Instance != null && Instance != this) { Destroy(this); return; }
            Instance = this;
        }

        void OnEnable()
        {
            if (Application.isEditor && !useInEditor) return;
            try
            {
                _udp = new UdpClient(0) { EnableBroadcast = true };
                Debug.Log($"[Bridge] Looking for twin_bridge.py on UDP :{bridgePort} (broadcast, {bridgeHost})");
            }
            catch (Exception e) { Debug.LogWarning("[Bridge] Could not open UDP socket: " + e.Message); _udp = null; }
        }

        void OnDisable()
        {
            try { _udp?.Close(); } catch { }
            _udp = null;
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        void Update()
        {
            if (_udp == null) return;
            if (Time.unscaledTime >= _nextHello)
            {
                _nextHello = Time.unscaledTime + helloInterval;
                SendHello();
            }
            if (_sentAt.Count > 0)                                          // expire unanswered commands
            {
                List<int> dead = null;
                foreach (var kv in _sentAt) if (Time.unscaledTime - kv.Value > timeoutSeconds) (dead ??= new List<int>()).Add(kv.Key);
                if (dead != null) foreach (var id in dead) Finish(id, false, 0, "bridge did not answer");
            }
        }

        string[] Entities()
        {
            if (_entities != null) return _entities;
            var set = new HashSet<string>();
            foreach (var b in FindObjectsOfType<TwinEntityBinding>(true))
            {
                if (!string.IsNullOrEmpty(b.entityId)) set.Add(b.entityId);
                foreach (var x in b.ExtraEntityIds) if (!string.IsNullOrEmpty(x)) set.Add(x);
            }
            var ha = FindObjectOfType<HomeAssistantClient>(true);
            if (ha != null && ha.extraEntities != null) foreach (var e in ha.extraEntities) if (!string.IsNullOrEmpty(e)) set.Add(e);
            _entities = new string[set.Count];
            set.CopyTo(_entities);
            return _entities;
        }

        void SendHello()
        {
            var rx = TwinUdpReceiver.Instance;
            var o = new JObject
            {
                ["type"] = "hello",
                ["reply_port"] = rx != null ? rx.port : 5005,
                ["want_snapshot"] = !IsConnected,
                ["device"] = SystemInfo.deviceModel,
                ["entities"] = new JArray(Entities())
            };
            byte[] data = Encoding.UTF8.GetBytes(o.ToString(Newtonsoft.Json.Formatting.None));
            if (IsConnected) SendTo(_bridgeIp, data);
            else
            {
                SendTo("255.255.255.255", data);
                if (!string.IsNullOrEmpty(bridgeHost)) SendTo(bridgeHost, data);
                if (_bridgeIp != null && _bridgeIp != bridgeHost) SendTo(_bridgeIp, data);
            }
        }

        void SendTo(string host, byte[] data)
        {
            try { _udp.Send(data, data.Length, new IPEndPoint(IPAddress.Parse(host), bridgePort)); }
            catch { /* network not up yet; the next hello retries */ }
        }

        /// <summary>Called by TwinUdpReceiver (main thread) for every twin.bridge.v1 datagram.</summary>
        public void HandleBridgeMessage(string json, string senderIp)
        {
            JObject o;
            try { o = JObject.Parse(json); } catch { return; }
            bool wasConnected = IsConnected;
            _bridgeIp = senderIp;
            _lastSeen = Time.unscaledTime;
            if (!wasConnected) Debug.Log($"[Bridge] Connected to twin_bridge.py at {senderIp}");
            if (o["ha"] != null) _haConnected = (bool)o["ha"];
            if ((string)o["event"] == "result" && o["id"] != null)
                Finish((int)o["id"], (bool?)o["ok"] ?? false, (int?)o["status"] ?? 0, (string)o["text"] ?? "");
        }

        void Finish(int id, bool ok, int status, string text)
        {
            _sentAt.Remove(id);
            if (_pending.TryGetValue(id, out var cb)) { _pending.Remove(id); cb?.Invoke(ok, status, text); }
        }

        void Send(JObject o, Action<bool, int, string> cb)
        {
            if (!IsConnected) { cb?.Invoke(false, 0, "bridge not connected"); return; }
            int id = _nextId++;
            o["id"] = id;
            _pending[id] = cb;
            _sentAt[id] = Time.unscaledTime;
            SendTo(_bridgeIp, Encoding.UTF8.GetBytes(o.ToString(Newtonsoft.Json.Formatting.None)));
        }

        /// <summary>Home Assistant service call through the bridge. data includes entity_id.</summary>
        public void CallService(string domain, string service, JObject data, Action<bool, int, string> cb)
            => Send(new JObject { ["type"] = "call_service", ["domain"] = domain, ["service"] = service, ["data"] = data }, cb);

        /// <summary>HTTP request the bridge makes on the laptop (only to 127.0.0.1 / localhost helper scripts).</summary>
        public void Http(string method, string url, string body, Action<bool, int, string> cb)
            => Send(new JObject { ["type"] = "http", ["method"] = method, ["url"] = url, ["body"] = body ?? "" }, cb);
    }
}
