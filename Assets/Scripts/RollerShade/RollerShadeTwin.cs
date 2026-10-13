using UnityEngine;

// Керує моделлю шторки з roller_shade.glb у Unity.
// Повісьте на корінь "Roller_Shade", перетягніть Shade_Fabric і Shade_Tube.
// SetPosition(0..100) викликайте з даних Home Assistant (cover current_position: 100 = відкрито).
public class RollerShadeTwin : MonoBehaviour
{
    [Range(0, 100)] public float targetPercent = 0f;
    public SkinnedMeshRenderer fabric;      // Shade_Fabric (blendshape "Open")
    public Transform tube;                  // Shade_Tube (обертається разом із колесом)
    public Vector3 tubeAxis = Vector3.right; // якщо труба крутиться не в той бік, поставте (-1,0,0)
    public float tubeDegreesFull = 3726f;   // оберт труби на хід 0 -> 100 % (із Blender-скрипта)
    public float speedPercentPerSec = 8f;   // підлаштуйте під реальну швидкість, заміривши час на стенді

    float current;
    int shapeIndex;
    Quaternion tubeBase;

    void Start()
    {
        shapeIndex = fabric.sharedMesh.GetBlendShapeIndex("Open");
        if (shapeIndex < 0) shapeIndex = 0;
        tubeBase = tube.localRotation;
        current = targetPercent;
        Apply();
    }

    public void SetPosition(float percent) => targetPercent = Mathf.Clamp(percent, 0f, 100f);

    void Update()
    {
        current = Mathf.MoveTowards(current, targetPercent, speedPercentPerSec * Time.deltaTime);
        Apply();
    }

    void Apply()
    {
        fabric.SetBlendShapeWeight(shapeIndex, current);
        tube.localRotation = tubeBase * Quaternion.AngleAxis(-current / 100f * tubeDegreesFull, tubeAxis);
    }
}
