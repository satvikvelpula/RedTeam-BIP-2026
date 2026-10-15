using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Use case 4 music in the twin: the same rule as motion_demo.py —
    /// while the roller shade is DOWN (closed) jazz plays; when it goes up the music fades out.
    /// Also plays while the real speaker (media_player.famnest2) reports "playing".
    /// The jazz loop is synthesised at start (no audio file, no internet needed on the headset).
    /// </summary>
    public class TwinMusicPlayer : MonoBehaviour
    {
        public RollerShadeBinding shade;
        [Tooltip("Real speaker in Home Assistant; its 'playing' state also starts the music.")]
        public string speakerEntity = "media_player.famnest2";
        [Range(0, 1)] public float volume = 0.45f;
        public float fadeSeconds = 1.5f;
        [Tooltip("0 = everywhere in the room (2D), 1 = comes from this object's position (3D).")]
        [Range(0, 1)] public float spatialBlend = 0f;

        public bool Playing => _want;

        AudioSource _audio;
        bool _want;
        string _speakerState = "";
        TwinUdpReceiver _rx;

        void Start()
        {
            if (!shade) shade = FindObjectOfType<RollerShadeBinding>(true);
            _audio = gameObject.AddComponent<AudioSource>();
            _audio.loop = true; _audio.playOnAwake = false; _audio.volume = 0f; _audio.spatialBlend = spatialBlend;
            _audio.clip = JazzLoop.Make();
            _rx = TwinUdpReceiver.Instance;
            if (_rx != null)
            {
                _rx.OnMessage += OnMessage;
                if (_rx.TryGetLatest(speakerEntity, out var m)) OnMessage(m);
            }
        }

        void OnDestroy() { if (_rx != null) _rx.OnMessage -= OnMessage; }

        void OnMessage(TwinStateMessage m)
        {
            if (m.entity_id == speakerEntity) _speakerState = m.state ?? "";
        }

        void Update()
        {
            bool want = (shade && (shade.State == "closed" || shade.State == "closing")) || _speakerState == "playing";
            if (want != _want)
            {
                _want = want;
                Debug.Log(want ? "[Music] shade down -> jazz on" : "[Music] shade up -> jazz off");
                if (want && !_audio.isPlaying) _audio.Play();
            }
            float target = _want ? volume : 0f;
            _audio.volume = Mathf.MoveTowards(_audio.volume, target, Time.deltaTime * volume / Mathf.Max(0.05f, fadeSeconds));
            if (!_want && _audio.isPlaying && _audio.volume <= 0.001f) _audio.Pause();
        }
    }

    /// Small swing jazz loop: ii-V-I-VI in F (Gm9 C13 Fmaj9 D13b9) x2, electric-piano comping,
    /// walking bass and a ride/hi-hat pattern. 16 s at 120 bpm, mono 22 kHz.
    static class JazzLoop
    {
        const int Rate = 22050;
        const float Beat = 0.5f;                      // 120 bpm

        public static AudioClip Make()
        {
            int bars = 8;
            int n = Mathf.CeilToInt(bars * 4 * Beat * Rate);
            var d = new float[n];
            int[][] chords =
            {
                new[] { 65, 69, 70, 74 },   // Gm9   F A Bb D
                new[] { 64, 69, 70, 74 },   // C13   E A Bb D
                new[] { 64, 67, 69, 72 },   // Fmaj9 E G A C
                new[] { 66, 71, 72, 76 },   // D13b9 F# B C E
            };
            int[][] bass =
            {
                new[] { 43, 46, 50, 49 },   // G Bb D C#
                new[] { 48, 52, 55, 52 },   // C E G E
                new[] { 41, 45, 48, 50 },   // F A C D
                new[] { 50, 54, 57, 44 },   // D F# A Ab -> leads back to G
            };
            float[] ride = { 0f, 1f, 1.66f, 2f, 3f, 3.66f };
            for (int bar = 0; bar < bars; bar++)
            {
                int c = bar % 4;
                float t0 = bar * 4 * Beat;
                for (int b = 0; b < 4; b++) AddBass(d, t0 + b * Beat, Beat * 0.95f, bass[c][b]);
                AddChord(d, t0, Beat * 0.9f, chords[c], 0.55f);
                AddChord(d, t0 + 1 * Beat + Beat * 0.66f, Beat * 1.2f, chords[c], 0.45f);
                foreach (var r in ride) AddRide(d, t0 + r * Beat, r % 1f > 0.1f ? 0.5f : 0.8f);
                AddHat(d, t0 + 1 * Beat); AddHat(d, t0 + 3 * Beat);
            }
            float max = 0f; foreach (var v in d) max = Mathf.Max(max, Mathf.Abs(v));
            if (max > 0f) for (int i = 0; i < n; i++) d[i] = d[i] / max * 0.85f;
            var clip = AudioClip.Create("TwinJazz", n, 1, Rate, false);
            clip.SetData(d, 0);
            return clip;
        }

        static float Hz(int midi) => 440f * Mathf.Pow(2f, (midi - 69) / 12f);

        static void AddBass(float[] d, float t, float len, int note)
        {
            float f = Hz(note);
            int s0 = (int)(t * Rate), cnt = (int)(len * Rate);
            for (int i = 0; i < cnt && s0 + i < d.Length; i++)
            {
                float x = i / (float)Rate;
                float env = Mathf.Exp(-x * 3.5f) * Mathf.Clamp01(x * 200f) * Mathf.Clamp01((cnt - i) / 300f);
                float w = 2f * Mathf.PI * f * x;
                d[s0 + i] += env * (0.9f * Mathf.Sin(w) + 0.25f * Mathf.Sin(2 * w)) * 0.5f;
            }
        }

        static void AddChord(float[] d, float t, float len, int[] notes, float vel)
        {
            int s0 = (int)(t * Rate), cnt = (int)(len * Rate);
            foreach (var note in notes)
            {
                float f = Hz(note);
                for (int i = 0; i < cnt && s0 + i < d.Length; i++)
                {
                    float x = i / (float)Rate;
                    float env = Mathf.Exp(-x * 2.2f) * Mathf.Clamp01(x * 300f) * Mathf.Clamp01((cnt - i) / 400f);
                    float w = 2f * Mathf.PI * f * x;
                    float s = Mathf.Sin(w + 0.6f * Mathf.Sin(w) * Mathf.Exp(-x * 6f));   // electric-piano-ish
                    d[s0 + i] += env * s * vel * 0.12f;
                }
            }
        }

        static uint _seed = 12345;
        static float Noise() { _seed = _seed * 1664525u + 1013904223u; return (_seed >> 9) / 4194304f - 1f; }

        static void AddRide(float[] d, float t, float vel)
        {
            int s0 = (int)(t * Rate), cnt = (int)(0.35f * Rate);
            float prev = 0f;
            for (int i = 0; i < cnt && s0 + i < d.Length; i++)
            {
                float x = i / (float)Rate;
                float n = Noise(); float hp = n - prev; prev = n;
                float ping = Mathf.Sin(2f * Mathf.PI * 5200f * x) * 0.3f;
                d[s0 + i] += (hp * 0.5f + ping) * Mathf.Exp(-x * 12f) * vel * 0.10f;
            }
        }

        static void AddHat(float[] d, float t)
        {
            int s0 = (int)(t * Rate), cnt = (int)(0.06f * Rate);
            float prev = 0f;
            for (int i = 0; i < cnt && s0 + i < d.Length; i++)
            {
                float x = i / (float)Rate;
                float n = Noise(); float hp = n - prev; prev = n;
                d[s0 + i] += hp * Mathf.Exp(-x * 60f) * 0.10f;
            }
        }
    }
}
