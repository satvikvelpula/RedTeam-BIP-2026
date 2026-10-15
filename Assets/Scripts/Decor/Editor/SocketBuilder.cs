#if UNITY_EDITOR
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DigitalTwin.Decor
{
    /// <summary>
    /// IVAR > Build Wall Sockets: replaces the flat socket plates on the cable trunking with
    /// real Schuko (CEE 7/3, type F) sockets: raised body with bevel, recessed cup, two pin holes
    /// (4.8 mm, 19 mm apart) and the chrome earthing clips top and bottom. Originals are hidden, not deleted.
    /// </summary>
    public static class SocketBuilder
    {
        const string MeshDir = "Assets/Models/Decor/Meshes";
        const string MatDir = "Assets/Models/Decor/Materials";
        const int M = 160;                    // samples around the outline

        // dimensions (metres)
        const float Half = 0.040f;            // 80 mm square
        const float Corner = 0.008f;          // corner radius
        const float Depth = 0.016f;           // body depth from the trunking face
        const float Bevel = 0.0018f;          // front edge chamfer
        const float CupR = 0.0195f;           // 39 mm recess
        const float CupDepth = 0.0140f;
        const float Lip = 0.0012f;            // chamfer around the recess
        const float PinR = 0.0024f;           // 4.8 mm pin holes
        const float PinGap = 0.0095f;         // 19 mm centre-to-centre

        [MenuItem("IVAR/Build Wall Sockets")]
        public static void Build()
        {
            var old = GameObject.Find("WallSockets"); if (old) Object.DestroyImmediate(old);
            var root = new GameObject("WallSockets");
            var body = BodyMesh(); var cup = CupMesh(); var pin = DiskMesh(PinR, 32, "Socket_PinHole"); var pinRim = RingMesh(PinR, PinR + 0.0009f, 32, "Socket_PinRim");

            var lab = GameObject.Find("IVAR Lab");
            Material white = null; int built = 0;
            foreach (var r in lab.GetComponentsInChildren<MeshRenderer>(true))
            {
                if (!r.name.StartsWith("socket_") || r.name.StartsWith("socket_hole")) continue;
                if (white == null) white = r.sharedMaterial;
                var b = r.bounds;
                var holeName = r.name.Replace("socket_", "socket_hole_");
                var hole = FindChild(lab.transform, holeName);

                var s = new GameObject("Socket_" + r.name.Substring(7)).transform; s.SetParent(root.transform, false);
                // local +Z points out of the wall into the room (this trunking faces world -Z)
                s.position = new Vector3(b.center.x, b.center.y, b.max.z);
                s.rotation = Quaternion.LookRotation(Vector3.back, Vector3.up);
                Obj(s, "Body", body, white);
                Obj(s, "Recess", cup, Mat("Socket_RecessPlastic", new Color(0.86f, 0.86f, 0.84f), 0.25f, 0f));
                var black = Mat("Socket_PinHole_Black", new Color(0.015f, 0.015f, 0.018f), 0.0f, 0f);
                var rimMat = Mat("Socket_PinRim", new Color(0.55f, 0.55f, 0.55f), 0.2f, 0f);
                foreach (var x in new[] { -PinGap, PinGap })
                {
                    Obj(s, "PinHole", pin, black).transform.localPosition = new Vector3(x, 0, Depth - CupDepth + 0.0003f);
                    Obj(s, "PinRim", pinRim, rimMat).transform.localPosition = new Vector3(x, 0, Depth - CupDepth + 0.00025f);
                }
                var chrome = Mat("Socket_EarthClip_Chrome", new Color(0.85f, 0.86f, 0.88f), 0.85f, 1f);
                foreach (var sy in new[] { 1f, -1f })
                {
                    // strip along the recess wall + the little bent tongue at the front
                    Box(s, "EarthClip", new Vector3(0, sy * (CupR - 0.0007f), Depth - CupDepth * 0.5f), new Vector3(0.0065f, 0.0012f, CupDepth - 0.002f), chrome);
                    Box(s, "EarthClipTongue", new Vector3(0, sy * (CupR - 0.0016f), Depth - 0.0035f), new Vector3(0.0065f, 0.0026f, 0.0012f), chrome);
                }
                r.enabled = false;
                if (hole) { var hr = hole.GetComponent<Renderer>(); if (hr) hr.enabled = false; }
                built++;
            }
            foreach (var mr in root.GetComponentsInChildren<MeshRenderer>()) mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            AssetDatabase.SaveAssets();
            EditorSceneManager.MarkSceneDirty(root.scene);
            Debug.Log("[Decor] Built " + built + " Schuko sockets.");
        }

        // ------------------------------------------------------------------ meshes
        static Mesh BodyMesh()
        {
            var rings = new List<Vector3[]>();
            var exp = new List<System.Func<Vector3, Vector3>>();
            rings.Add(Contour(Half, Corner, 0f));                                   // back edge (on trunking)
            rings.Add(Contour(Half, Corner, Depth - Bevel));                        // side wall
            exp.Add(p => new Vector3(p.x, p.y, 0));                                 // side faces out
            rings.Add(Contour(Half - Bevel, Corner - Bevel * 0.6f, Depth));         // bevel
            exp.Add(p => new Vector3(p.x, p.y, 0).normalized + Vector3.forward);
            rings.Add(Circle(CupR + Lip, Depth));                                   // front face
            exp.Add(p => Vector3.forward);
            rings.Add(Circle(CupR, Depth - Lip));                                   // lip chamfer into the recess
            exp.Add(p => Vector3.forward - new Vector3(p.x, p.y, 0).normalized);
            return Strips(rings, exp, "Socket_Body");
        }

        static Mesh CupMesh()
        {
            var rings = new List<Vector3[]> { Circle(CupR, Depth - Lip), Circle(CupR, Depth - CupDepth) };
            var exp = new List<System.Func<Vector3, Vector3>> { p => -new Vector3(p.x, p.y, 0) };   // wall faces the axis
            var m = Strips(rings, exp, "Socket_Recess_tmp", false);
            // add the bottom
            var v = new List<Vector3>(m.vertices); var t = new List<int>(m.triangles);
            int c = v.Count; v.Add(new Vector3(0, 0, Depth - CupDepth));
            var bottom = Circle(CupR, Depth - CupDepth); int start = v.Count; v.AddRange(bottom);
            for (int i = 0; i < M; i++) AddTri(v, t, c, start + i, start + (i + 1) % M, Vector3.forward);
            return Finish(v, t, "Socket_Recess");
        }

        static Mesh DiskMesh(float r, int n, string name)
        {
            var v = new List<Vector3> { Vector3.zero }; var t = new List<int>();
            for (int i = 0; i < n; i++) { float a = i * Mathf.PI * 2 / n; v.Add(new Vector3(Mathf.Cos(a) * r, Mathf.Sin(a) * r, 0)); }
            for (int i = 0; i < n; i++) AddTri(v, t, 0, 1 + i, 1 + (i + 1) % n, Vector3.forward);
            return Finish(v, t, name);
        }

        static Mesh RingMesh(float r0, float r1, int n, string name)
        {
            var v = new List<Vector3>(); var t = new List<int>();
            for (int i = 0; i < n; i++) { float a = i * Mathf.PI * 2 / n; var d = new Vector3(Mathf.Cos(a), Mathf.Sin(a), 0); v.Add(d * r0); v.Add(d * r1); }
            for (int i = 0; i < n; i++)
            {
                int a = i * 2, b = ((i + 1) % n) * 2;
                AddTri(v, t, a, a + 1, b + 1, Vector3.forward); AddTri(v, t, a, b + 1, b, Vector3.forward);
            }
            return Finish(v, t, name);
        }

        /// Connect consecutive rings (same sample count) with quads; each strip's faces are oriented to its expected normal.
        static Mesh Strips(List<Vector3[]> rings, List<System.Func<Vector3, Vector3>> expected, string name, bool save = true)
        {
            var v = new List<Vector3>(); var t = new List<int>();
            for (int k = 0; k < rings.Count - 1; k++)
            {
                int baseIdx = v.Count;
                v.AddRange(rings[k]); v.AddRange(rings[k + 1]);       // separate verts per strip -> crisp edges
                for (int i = 0; i < M; i++)
                {
                    int a = baseIdx + i, b = baseIdx + (i + 1) % M, c = baseIdx + M + i, d = baseIdx + M + (i + 1) % M;
                    var mid = (v[a] + v[b] + v[c] + v[d]) * 0.25f;
                    var e = expected[k](mid);
                    AddTri(v, t, a, b, d, e); AddTri(v, t, a, d, c, e);
                }
            }
            return save ? Finish(v, t, name) : Raw(v, t, name);
        }

        static void AddTri(List<Vector3> v, List<int> t, int a, int b, int c, Vector3 expected)
        {
            var n = Vector3.Cross(v[b] - v[a], v[c] - v[a]);
            if (Vector3.Dot(n, expected) >= 0) t.AddRange(new[] { a, b, c }); else t.AddRange(new[] { a, c, b });
        }

        static Vector3[] Circle(float r, float z)
        {
            var p = new Vector3[M];
            for (int i = 0; i < M; i++) { float a = i * Mathf.PI * 2 / M; p[i] = new Vector3(Mathf.Cos(a) * r, Mathf.Sin(a) * r, z); }
            return p;
        }

        /// Rounded square sampled at the same angles as Circle(), by ray-marching from the centre.
        static Vector3[] Contour(float half, float corner, float z)
        {
            var p = new Vector3[M];
            for (int i = 0; i < M; i++)
            {
                float a = i * Mathf.PI * 2 / M; var dir = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
                float lo = 0, hi = half * 1.5f;
                for (int it = 0; it < 40; it++) { float mid = (lo + hi) * 0.5f; if (RoundRectSdf(dir * mid, half, corner) < 0) lo = mid; else hi = mid; }
                var q = dir * lo; p[i] = new Vector3(q.x, q.y, z);
            }
            return p;
        }

        static float RoundRectSdf(Vector2 p, float half, float r)
        {
            var q = new Vector2(Mathf.Abs(p.x) - (half - r), Mathf.Abs(p.y) - (half - r));
            return new Vector2(Mathf.Max(q.x, 0), Mathf.Max(q.y, 0)).magnitude + Mathf.Min(Mathf.Max(q.x, q.y), 0) - r;
        }

        static Mesh Raw(List<Vector3> v, List<int> t, string name)
        { var m = new Mesh { name = name }; m.SetVertices(v); m.SetTriangles(t, 0); return m; }

        static Mesh Finish(List<Vector3> v, List<int> t, string name)
        {
            var m = Raw(v, t, name);
            var uv = new Vector2[v.Count]; for (int i = 0; i < v.Count; i++) uv[i] = new Vector2(v[i].x * 10 + 0.5f, v[i].y * 10 + 0.5f);
            m.uv = uv; m.RecalculateNormals(); m.RecalculateTangents(); m.RecalculateBounds();
            if (!AssetDatabase.IsValidFolder(MeshDir)) { System.IO.Directory.CreateDirectory(MeshDir); AssetDatabase.Refresh(); }
            string p = MeshDir + "/" + name + ".asset";
            if (AssetDatabase.LoadAssetAtPath<Mesh>(p) != null) AssetDatabase.DeleteAsset(p);
            AssetDatabase.CreateAsset(m, p); return m;
        }

        static GameObject Obj(Transform parent, string name, Mesh mesh, Material mat)
        {
            var g = new GameObject(name); g.transform.SetParent(parent, false);
            g.AddComponent<MeshFilter>().sharedMesh = mesh; g.AddComponent<MeshRenderer>().sharedMaterial = mat; return g;
        }

        static void Box(Transform parent, string name, Vector3 c, Vector3 size, Material m)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Cube); g.name = name; Object.DestroyImmediate(g.GetComponent<Collider>());
            g.transform.SetParent(parent, false); g.transform.localPosition = c; g.transform.localScale = size; g.GetComponent<MeshRenderer>().sharedMaterial = m;
        }

        static Material Mat(string name, Color c, float smooth, float metal)
        {
            if (!AssetDatabase.IsValidFolder(MatDir)) { System.IO.Directory.CreateDirectory(MatDir); AssetDatabase.Refresh(); }
            string p = MatDir + "/" + name + ".mat"; var m = AssetDatabase.LoadAssetAtPath<Material>(p);
            if (!m) { m = new Material(Shader.Find("Standard")); AssetDatabase.CreateAsset(m, p); }
            m.color = c; m.SetFloat("_Glossiness", smooth); m.SetFloat("_Metallic", metal); m.enableInstancing = true; EditorUtility.SetDirty(m); return m;
        }

        static Transform FindChild(Transform root, string n)
        { foreach (var t in root.GetComponentsInChildren<Transform>(true)) if (t.name == n) return t; return null; }
    }
}
#endif
