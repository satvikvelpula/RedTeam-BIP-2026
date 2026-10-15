using UnityEngine;

/// Flashes a light and an emissive material on/off, like a warning beacon.
public class BeaconFlasher : MonoBehaviour
{
    public Light beaconLight;
    public Renderer domeRenderer;
    [Tooltip("Flashes per second")] public float flashRate = 1.5f;
    [Range(0.05f, 0.95f)] public float dutyCycle = 0.5f;
    public float onIntensity = 3f;
    public Color emissionColor = new Color(1f, 0.08f, 0.04f);
    public float emissionOnStrength = 4f;
    public bool flashing = true;

    MaterialPropertyBlock _mpb;
    static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");

    void Awake()
    {
        _mpb = new MaterialPropertyBlock();
        if (domeRenderer != null)
            foreach (var m in domeRenderer.sharedMaterials) if (m) m.EnableKeyword("_EMISSION");
    }

    void Update()
    {
        bool on = flashing && Mathf.Repeat(Time.time * flashRate, 1f) < dutyCycle;
        if (beaconLight) beaconLight.intensity = on ? onIntensity : 0f;
        if (domeRenderer)
        {
            domeRenderer.GetPropertyBlock(_mpb);
            _mpb.SetColor(EmissionId, on ? emissionColor * emissionOnStrength : Color.black);
            domeRenderer.SetPropertyBlock(_mpb);
        }
    }
}
