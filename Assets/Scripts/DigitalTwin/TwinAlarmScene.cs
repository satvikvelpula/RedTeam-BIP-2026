using System.Collections.Generic;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Use case 3 alarm in the twin. While the alarm is on:
    ///   * every light in the room goes dark (lamp, ceiling LEDs, window light, sun),
    ///   * the warning beacon flashes red, the LED strip shows solid red,
    ///   * the ambient light turns a dim red and a two-tone siren sounds.
    /// When it ends, everything goes back to what the bindings say.
    ///
    /// Alarm = the real siren is on (Home Assistant, driven by use_case_3/temperature.py)
    ///      OR the measured temperature is above highC
    ///      OR the thermostat setpoint is above highC (same rule as temperature.py "alarm_on_target"),
    /// so the twin shows the alarm at once, also offline and before temperature.py reacts.
    /// </summary>
    [DefaultExecutionOrder(100)]
    public class TwinAlarmScene : MonoBehaviour
    {
        public ThermostatBinding thermostat;
        public BeaconBinding beacon;
        public LedStripBinding strip;
        [Tooltip("Same as high_c in use_case_3/phrasebook.json")]
        public float highC = 25f;
        [Tooltip("Also alarm when the setpoint is above highC (same as alarm_on_target in phrasebook.json)")]
        public bool alarmOnTarget = true;
        [Tooltip("Lights that stay on during the alarm (beacon and strip glow are always kept).")]
        public Light[] keepLights;
        public Color alarmAmbient = new Color(0.22f, 0.02f, 0.02f);
        public bool sirenSound = true;
        [Range(0, 1)] public float sirenVolume = 0.35f;

        public bool Active { get; private set; }

        readonly Dictionary<Light, bool> _saved = new Dictionary<Light, bool>();
        readonly HashSet<Light> _keep = new HashSet<Light>();
        Color _sky, _equator, _ground, _flat;
        float _ambientIntensity;
        AudioSource _audio;

        void Awake()
        {
            if (!thermostat) thermostat = FindObjectOfType<ThermostatBinding>(true);
            if (!beacon) beacon = FindObjectOfType<BeaconBinding>(true);
            if (!strip) strip = FindObjectOfType<LedStripBinding>(true);
        }

        bool SirenOn
        {
            get
            {
                var m = beacon ? beacon.Current : null;
                return m != null && m.available && m.IsOn;
            }
        }

        bool TooHot
        {
            get
            {
                if (!thermostat) return false;
                if (thermostat.HasMeasured && thermostat.Measured > highC) return true;
                return alarmOnTarget && !float.IsNaN(thermostat.Target) && thermostat.Target > highC;
            }
        }

        void LateUpdate()
        {
            bool want = SirenOn || TooHot;
            if (want != Active) { if (want) Enter(); else Exit(); }
            if (!Active) return;
            foreach (var l in _saved.Keys) if (l) l.enabled = false;                // bindings may switch lamps back on
            if (beacon && beacon.flasher) beacon.flasher.flashing = true;
        }

        void Enter()
        {
            Active = true;
            Debug.Log("[Alarm] temperature alarm ON -> lights off, red only");
            _keep.Clear();
            if (keepLights != null) foreach (var l in keepLights) if (l) _keep.Add(l);
            if (beacon && beacon.flasher && beacon.flasher.beaconLight) _keep.Add(beacon.flasher.beaconLight);
            if (strip && strip.glow) _keep.Add(strip.glow);
            _saved.Clear();
            foreach (var l in FindObjectsOfType<Light>(true))
                if (!_keep.Contains(l)) { _saved[l] = l.enabled; l.enabled = false; }

            _sky = RenderSettings.ambientSkyColor; _equator = RenderSettings.ambientEquatorColor;
            _ground = RenderSettings.ambientGroundColor; _flat = RenderSettings.ambientLight;
            _ambientIntensity = RenderSettings.ambientIntensity;
            RenderSettings.ambientSkyColor = RenderSettings.ambientEquatorColor = RenderSettings.ambientLight = alarmAmbient;
            RenderSettings.ambientGroundColor = alarmAmbient * 0.5f;

            if (strip) strip.Override = Color.red;
            if (beacon && beacon.flasher) beacon.flasher.flashing = true;
            if (sirenSound) PlaySiren();
        }

        void Exit()
        {
            Active = false;
            Debug.Log("[Alarm] temperature alarm OFF -> lights restored");
            foreach (var kv in _saved) if (kv.Key) kv.Key.enabled = kv.Value;
            _saved.Clear();
            // lamps that changed during the alarm: let their bindings re-apply the current state
            foreach (var b in FindObjectsOfType<LightBinding>(true)) if (b.Current != null) b.Apply(b.Current);

            RenderSettings.ambientSkyColor = _sky; RenderSettings.ambientEquatorColor = _equator;
            RenderSettings.ambientGroundColor = _ground; RenderSettings.ambientLight = _flat;
            RenderSettings.ambientIntensity = _ambientIntensity;

            if (strip) strip.Override = null;
            if (beacon && beacon.flasher)
                beacon.flasher.flashing = beacon.Current != null && beacon.Current.available && beacon.Current.IsOn == beacon.flashWhenOn;
            if (_audio) _audio.Stop();
        }

        void PlaySiren()
        {
            if (!_audio)
            {
                _audio = gameObject.AddComponent<AudioSource>();
                _audio.loop = true; _audio.playOnAwake = false; _audio.spatialBlend = 0f;
                _audio.clip = MakeSiren();
            }
            _audio.volume = sirenVolume;
            _audio.Play();
        }

        /// Two-tone siren (960 / 770 Hz, 0.5 s each), generated so no audio file is needed.
        static AudioClip MakeSiren()
        {
            const int rate = 22050;
            int n = rate;                                   // 1 s loop
            var data = new float[n];
            double phase = 0;
            for (int i = 0; i < n; i++)
            {
                double f = i < n / 2 ? 960 : 770;
                phase += 2 * System.Math.PI * f / rate;
                float sq = System.Math.Sin(phase) >= 0 ? 1f : -1f;
                float s = 0.55f * (float)System.Math.Sin(phase) + 0.25f * sq;
                int k = i % (n / 2);
                float edge = Mathf.Clamp01(k / 200f) * Mathf.Clamp01((n / 2 - k) / 200f);   // no clicks
                data[i] = s * edge * 0.8f;
            }
            var clip = AudioClip.Create("TwinSiren", n, 1, rate, false);
            clip.SetData(data, 0);
            return clip;
        }

        void OnDisable() { if (Active) Exit(); }
    }
}
