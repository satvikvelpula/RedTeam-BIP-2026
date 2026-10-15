using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Listens for UDP datagrams from ha_twin_logger.py (--udp 127.0.0.1:5005) or twin_bridge.py (headset) and
    /// dispatches each parsed message on the main thread.
    /// </summary>
    [DefaultExecutionOrder(-100)]
    public class TwinUdpReceiver : MonoBehaviour
    {
        public static TwinUdpReceiver Instance { get; private set; }

        [Tooltip("Must match the port given to ha_twin_logger.py --udp host:PORT")]
        public int port = 5005;
        public bool listenOnStart = true;
        public bool logToConsole = true;
        [Tooltip("Only real Home Assistant states move the twin. Clicks/keys never fake a state; if Home Assistant is offline nothing changes.")]
        public bool realSensorsOnly = true;

        /// <summary>Fired on the main thread for every message (real or simulated).</summary>
        public event Action<TwinStateMessage> OnMessage;

        public int MessagesReceived { get; private set; }
        public float LastMessageTime { get; private set; } = -1f;
        public string LastError { get; private set; }
        public bool IsListening => _running;
        public IReadOnlyDictionary<string, TwinStateMessage> Latest => _latest;

        readonly ConcurrentQueue<(string json, string from)> _queue = new ConcurrentQueue<(string json, string from)>();
        readonly Dictionary<string, TwinStateMessage> _latest = new Dictionary<string, TwinStateMessage>();
        UdpClient _client;
        Thread _thread;
        volatile bool _running;

        void Awake()
        {
            if (Instance != null && Instance != this) { Destroy(this); return; }
            Instance = this;
        }

        void OnEnable() { if (listenOnStart) StartListening(); }
        void OnDisable() { StopListening(); }
        void OnApplicationQuit() { StopListening(); }

        public void StartListening()
        {
            if (_running) return;
            try
            {
                _client = new UdpClient();
                _client.Client.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
                _client.Client.Bind(new IPEndPoint(IPAddress.Any, port));
                _running = true;
                _thread = new Thread(ReceiveLoop) { IsBackground = true, Name = "TwinUdpReceiver" };
                _thread.Start();
                LastError = null;
                if (logToConsole) Debug.Log($"[Twin] Listening for Home Assistant UDP on port {port}");
            }
            catch (Exception e)
            {
                LastError = e.Message;
                Debug.LogWarning($"[Twin] Could not open UDP port {port}: {e.Message}");
            }
        }

        public void StopListening()
        {
            _running = false;
            try { _client?.Close(); } catch { /* ignore */ }
            _client = null;
            if (_thread != null && _thread.IsAlive) _thread.Join(200);
            _thread = null;
        }

        void ReceiveLoop()
        {
            var any = new IPEndPoint(IPAddress.Any, 0);
            while (_running)
            {
                try
                {
                    byte[] data = _client.Receive(ref any);
                    _queue.Enqueue((Encoding.UTF8.GetString(data), any.Address.ToString()));
                }
                catch (SocketException) { if (!_running) break; }
                catch (ObjectDisposedException) { break; }
                catch (Exception e) { LastError = e.Message; }
            }
        }

        void Update()
        {
            while (_queue.TryDequeue(out var item))
            {
                // Heartbeats and command results from twin_bridge.py (headset mode) go to TwinBridgeClient.
                if (item.json.Contains("\"twin.bridge.v1\"")) { if (TwinBridgeClient.Instance != null) TwinBridgeClient.Instance.HandleBridgeMessage(item.json, item.from); continue; }
                InjectJson(item.json);
            }
        }

        /// <summary>Parse and dispatch one JSON line (same format the logger prints).</summary>
        public void InjectJson(string json)
        {
            if (string.IsNullOrWhiteSpace(json)) return;
            TwinStateMessage m;
            try { m = JsonUtility.FromJson<TwinStateMessage>(json); }
            catch (Exception e) { LastError = "Bad JSON: " + e.Message; return; }
            if (m == null || string.IsNullOrEmpty(m.entity_id)) return;
            m.hasNumber = json.Contains("\"number\"");
            m.hasOn = json.Contains("\"on\":");
            m.hasPosition = json.Contains("\"position\":");
            m.hasBrightness = json.Contains("\"brightness\":");
            if (m.rgb_color != null && m.rgb_color.Length == 0) m.rgb_color = null;
            Inject(m);
        }

        /// <summary>Dispatch an already-built message (used by the simulator and VR interactions).</summary>
        public void Inject(TwinStateMessage m)
        {
            if (m == null) return;
            if (realSensorsOnly && m.simulated)                 // real-only mode: ignore every fake state change
            {
                if (logToConsole) Debug.Log($"[Twin] ignored simulated {m.entity_id} = {m.state} (real sensors only)");
                return;
            }
            _latest[m.entity_id] = m;
            MessagesReceived++;
            LastMessageTime = Time.unscaledTime;
            if (logToConsole)
                Debug.Log($"[Twin] {(m.simulated ? "SIM " : "")}{m.@event} {m.entity_id} = {m.state}{(string.IsNullOrEmpty(m.unit) ? "" : " " + m.unit)}");
            OnMessage?.Invoke(m);
        }

        public bool TryGetLatest(string entityId, out TwinStateMessage m) => _latest.TryGetValue(entityId, out m);
    }
}
