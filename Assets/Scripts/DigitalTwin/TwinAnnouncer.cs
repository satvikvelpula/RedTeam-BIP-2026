using TMPro;
using UnityEngine;

namespace DigitalTwin
{
    /// <summary>
    /// Announces a state in the twin: while the binding is ON a floating label ("Door is open") hangs above the
    /// device and turns to face the viewer, and on each OFF→ON change the voice clip plays at the device (3D sound,
    /// heard in the headset). The real speaker on the stand is handled by scripts/door_announce.py.
    /// </summary>
    public class TwinAnnouncer : MonoBehaviour
    {
        [Tooltip("Binding to watch (e.g. the DoorBinding on Door_leaf). Found on this object if empty.")]
        public TwinEntityBinding binding;
        public string message = "Door is open";
        [Tooltip("Spoken when the binding turns ON (same Google TTS voice as the Nest speaker).")]
        public AudioClip voice;
        [Range(0, 1)] public float volume = 1f;
        [Tooltip("Label position: above the top of the device by this many metres.")]
        public float labelHeight = 0.25f;
        public float labelSize = 0.9f;
        public Color labelColor = new Color(1f, 0.82f, 0.25f);

        TextMeshPro _label;
        AudioSource _audio;
        bool _wasOn;
        bool _started;

        void Start()
        {
            if (binding == null) binding = GetComponent<TwinEntityBinding>();
            if (binding == null) { enabled = false; return; }

            // anchor = top centre of the device as modelled (before it moves)
            var bounds = new Bounds(binding.transform.position, Vector3.zero);
            foreach (var r in binding.GetComponentsInChildren<Renderer>()) bounds.Encapsulate(r.bounds);
            var anchor = new GameObject("Announcement").transform;
            anchor.position = new Vector3(bounds.center.x, bounds.max.y + labelHeight, bounds.center.z);

            _label = anchor.gameObject.AddComponent<TextMeshPro>();
            _label.text = message;
            _label.fontSize = labelSize;
            _label.color = labelColor;
            _label.alignment = TextAlignmentOptions.Center;
            _label.enableWordWrapping = false;
            _label.fontStyle = FontStyles.Bold;
            _label.outlineWidth = 0.2f;
            _label.outlineColor = new Color32(20, 20, 20, 255);
            anchor.gameObject.SetActive(false);

            _audio = anchor.gameObject.AddComponent<AudioSource>();
            _audio.playOnAwake = false;
            _audio.spatialBlend = 1f;          // 3D: comes from the door
            _audio.minDistance = 2f;
            _audio.maxDistance = 25f;

            _wasOn = binding.Current != null && binding.Current.available && binding.Current.IsOn;
            _started = true;
        }

        void LateUpdate()
        {
            if (!_started) return;
            var cur = binding.Current;
            bool on = cur != null && cur.available && cur.IsOn;

            if (on != _wasOn)
            {
                _label.gameObject.SetActive(on);
                if (on && voice) _audio.PlayOneShot(voice, volume);
                _wasOn = on;
            }

            if (on)
            {
                var cam = Camera.main;
                if (cam) _label.transform.rotation = Quaternion.LookRotation(_label.transform.position - cam.transform.position);
            }
        }

        void OnDestroy()
        {
            if (_label) Destroy(_label.gameObject);
        }
    }
}
