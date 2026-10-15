#if UNITY_EDITOR
using System;
using System.Linq;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

namespace DigitalTwin.EditorTools
{
    /// <summary>IVAR > Home Assistant Settings: paste the token, test the connection, check every entity the twin uses.</summary>
    public class HomeAssistantSettingsWindow : EditorWindow
    {
        string _url = "http://homeassistant.local:8123";
        string _token = "";
        string _report = "";
        Vector2 _scroll;

        [MenuItem("IVAR/Home Assistant Settings")]
        public static void Open() { var w = GetWindow<HomeAssistantSettingsWindow>("Home Assistant"); w.minSize = new Vector2(520, 420); }

        void OnEnable()
        {
            var c = FindObjectOfType<HomeAssistantClient>(true);
            if (c) _url = c.url;
            _token = HomeAssistantClient.LoadToken();
        }

        void OnGUI()
        {
            EditorGUILayout.LabelField("Connection", EditorStyles.boldLabel);
            _url = EditorGUILayout.TextField("Home Assistant URL", _url);
            _token = EditorGUILayout.PasswordField("Long-lived token", _token);
            EditorGUILayout.HelpBox("Home Assistant > your profile > Security > Long-lived access tokens > Create token.\n" +
                                    "Saved on this PC only (" + HomeAssistantClient.TokenFile + "), never in the project.", MessageType.Info);
            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("Save", GUILayout.Height(26))) Save();
                if (GUILayout.Button("Save + Test connection & entities", GUILayout.Height(26))) { Save(); Test(); }
                if (GUILayout.Button("List covers / lights / sensors", GUILayout.Height(26))) { Save(); ListEntities(); }
            }
            EditorGUILayout.Space();
            _scroll = EditorGUILayout.BeginScrollView(_scroll);
            EditorGUILayout.TextArea(_report, GUILayout.ExpandHeight(true));
            EditorGUILayout.EndScrollView();
        }

        void Save()
        {
            HomeAssistantClient.SaveToken(_token);
            foreach (var c in FindObjectsOfType<HomeAssistantClient>(true)) { Undo.RecordObject(c, "HA url"); c.url = _url.Trim().TrimEnd('/'); EditorUtility.SetDirty(c); }
            if (Application.isPlaying) foreach (var c in FindObjectsOfType<HomeAssistantClient>()) c.Connect();
        }

        HttpClient Client()
        {
            var h = new HttpClient { Timeout = TimeSpan.FromSeconds(6) };
            h.DefaultRequestHeaders.Add("Authorization", "Bearer " + _token.Trim());
            return h;
        }

        void Test()
        {
            var sb = new StringBuilder();
            string baseUrl = _url.Trim().TrimEnd('/');
            try
            {
                using (var h = Client())
                {
                    var r = h.GetAsync(baseUrl + "/api/").Result;
                    if ((int)r.StatusCode == 401) { _report = "✗ Reached Home Assistant, but the TOKEN was rejected (401). Create a new long-lived token."; return; }
                    if (!r.IsSuccessStatusCode) { _report = $"✗ Home Assistant answered HTTP {(int)r.StatusCode}"; return; }
                    sb.AppendLine("✓ Connected to Home Assistant at " + baseUrl + " — token OK\n");
                    sb.AppendLine("Entities used in the scene:");
                    foreach (var b in FindObjectsOfType<TwinEntityBinding>(true).OrderBy(b => b.entityId))
                    {
                        if (string.IsNullOrEmpty(b.entityId)) continue;
                        var s = h.GetAsync(baseUrl + "/api/states/" + b.entityId).Result;
                        if (s.IsSuccessStatusCode)
                        {
                            var o = JObject.Parse(s.Content.ReadAsStringAsync().Result); var a = o["attributes"] as JObject;
                            string extra = a?["current_position"] != null ? $"  position {a["current_position"]}%" : a?["rgb_color"] != null ? $"  rgb {a["rgb_color"].ToString(Newtonsoft.Json.Formatting.None)}" : "";
                            sb.AppendLine($"  ✓ {b.entityId,-42} = {o["state"]}{extra}   ({b.GetType().Name} on '{b.name}')");
                        }
                        else sb.AppendLine($"  ✗ {b.entityId,-42} NOT FOUND in Home Assistant   ({b.GetType().Name} on '{b.name}') — fix its entityId");
                    }
                    sb.AppendLine("\nPress Play: the twin connects by itself (HomeAssistantClient on the 'DigitalTwin' object).");
                }
            }
            catch (Exception e) { sb.AppendLine("✗ Could not reach " + baseUrl + ": " + (e.InnerException?.Message ?? e.Message)); sb.AppendLine("Check the URL and that this PC is on the lab network."); }
            _report = sb.ToString();
        }

        void ListEntities()
        {
            try
            {
                using (var h = Client())
                {
                    var r = h.GetAsync(_url.Trim().TrimEnd('/') + "/api/states").Result;
                    if (!r.IsSuccessStatusCode) { _report = $"HTTP {(int)r.StatusCode} — save a valid token first"; return; }
                    var arr = JArray.Parse(r.Content.ReadAsStringAsync().Result);
                    var sb = new StringBuilder();
                    foreach (var dom in new[] { "cover", "light", "switch", "binary_sensor", "sensor", "media_player" })
                    {
                        sb.AppendLine($"── {dom} ──");
                        foreach (var o in arr.OfType<JObject>().Where(o => ((string)o["entity_id"]).StartsWith(dom + ".")).OrderBy(o => (string)o["entity_id"]))
                            sb.AppendLine($"  {o["entity_id"],-50} {o["state"],-12} {o["attributes"]?["friendly_name"]}");
                    }
                    _report = sb.ToString();
                }
            }
            catch (Exception e) { _report = "Could not reach Home Assistant: " + (e.InnerException?.Message ?? e.Message); }
        }
    }
}
#endif
