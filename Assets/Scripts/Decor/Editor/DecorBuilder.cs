#if UNITY_EDITOR
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace DigitalTwin.Decor
{
    /// <summary>
    /// IVAR > Build Decorations: generates framed posters, a live wall clock, a snake plant,
    /// books, a mug and a succulent, with procedurally built smooth meshes. Safe to re-run.
    /// </summary>
    public static class DecorBuilder
    {
        const string MeshDir = "Assets/Models/Decor/Meshes";
        const string MatDir = "Assets/Models/Decor/Materials";
        const string TexDir = "Assets/Textures/Decor";

        [MenuItem("IVAR/Build Decorations")]
        public static void Build()
        {
            EnsureDir("Assets/Models/Decor"); EnsureDir(MeshDir); EnsureDir(MatDir);
            var old = GameObject.Find("Decorations");
            if (old) Object.DestroyImmediate(old);
            var root = new GameObject("Decorations");

            // wall planes (room-facing surfaces)
            float sideboardWallZ = Bounds("Wall_Sideboard").min.z;          // faces -Z
            float partitionC = Bounds("Wall_Partition_c").max.z;            // faces +Z
            float partitionB = Bounds("Wall_Partition_b").max.z;
            float lintel = Bounds("Wall_Partition_lintel").max.z;
            var intoSideboardWall = Quaternion.identity;                    // root +Z points into the wall
            var intoPartition = Quaternion.Euler(0, 180, 0);

            // ---------------- posters
            Poster(root.transform, "Poster_DigitalTwin", new Vector3(-4.60f, 1.62f, sideboardWallZ), intoSideboardWall, 0.50f);
            Poster(root.transform, "Poster_Landscape", new Vector3(-5.35f, 1.68f, partitionC), intoPartition, 0.50f);
            Poster(root.transform, "Poster_Automation", new Vector3(-2.60f, 1.60f, partitionB), intoPartition, 0.46f);

            // ---------------- clock above the inner doorway
            Clock(root.transform, new Vector3(-1.50f, 2.60f, lintel), intoPartition, 0.32f);

            // ---------------- floor plant in the window corner
            SnakePlant(root.transform, new Vector3(-5.45f, 0f, -0.33f));

            // ---------------- sideboard styling
            var top = Bounds("top");
            float y = top.max.y;
            Books(root.transform, new Vector3(-2.86f, y, -0.12f));
            Mug(root.transform, new Vector3(-2.25f, y, -0.36f));
            Succulent(root.transform, new Vector3(-1.75f, y, -0.26f));

            foreach (var r in root.GetComponentsInChildren<MeshRenderer>())
            { r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On; r.receiveShadows = true; }
            AssetDatabase.SaveAssets();
            EditorSceneManager.MarkSceneDirty(root.scene);
            Debug.Log("[Decor] Decorations built.");
        }

        // ======================================================================= pieces
        static void Poster(Transform parent, string tex, Vector3 wallPoint, Quaternion intoWall, float width)
        {
            float h = width * 1.4142f, frame = 0.022f, depth = 0.025f, mat = 0.035f;
            var go = new GameObject(tex); go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(wallPoint, intoWall);
            go.transform.position -= go.transform.forward * 0.002f;
            var frameMat = Mat("Frame_BlackAluminium", new Color(0.06f, 0.06f, 0.065f), 0.55f, 0.6f);
            var matBoard = Mat("Passepartout", new Color(0.96f, 0.955f, 0.94f), 0.05f, 0f);
            float W = width + 2 * (mat + frame), H = h + 2 * (mat + frame);
            // frame: 4 bars, front face slightly proud
            Box(go.transform, "Frame_T", new Vector3(0, H / 2 - frame / 2, -depth / 2), new Vector3(W, frame, depth), frameMat);
            Box(go.transform, "Frame_B", new Vector3(0, -H / 2 + frame / 2, -depth / 2), new Vector3(W, frame, depth), frameMat);
            Box(go.transform, "Frame_L", new Vector3(-W / 2 + frame / 2, 0, -depth / 2), new Vector3(frame, H - 2 * frame, depth), frameMat);
            Box(go.transform, "Frame_R", new Vector3(W / 2 - frame / 2, 0, -depth / 2), new Vector3(frame, H - 2 * frame, depth), frameMat);
            Box(go.transform, "Backing", new Vector3(0, 0, -0.004f), new Vector3(W - 2 * frame, H - 2 * frame, 0.006f), matBoard);
            var art = Quad(go.transform, "Art", new Vector3(0, 0, -0.0085f), width, h);
            var artMat = Mat("Art_" + tex, Color.white, 0.12f, 0f, Tex(tex));
            art.GetComponent<MeshRenderer>().sharedMaterial = artMat;
            // subtle glass with reflections
            var glass = Quad(go.transform, "Glass", new Vector3(0, 0, -depth + 0.004f), W - 2 * frame, H - 2 * frame);
            glass.GetComponent<MeshRenderer>().sharedMaterial = GlassMat();
            glass.GetComponent<MeshRenderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        static void Clock(Transform parent, Vector3 wallPoint, Quaternion intoWall, float diameter)
        {
            float r = diameter / 2;
            var go = new GameObject("WallClock"); go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(wallPoint, intoWall);
            // rim: lathe around local Z (profile in r, z)
            var rimProfile = new List<Vector2> {
                new Vector2(r - 0.012f, -0.004f), new Vector2(r - 0.006f, -0.040f), new Vector2(r + 0.004f, -0.046f),
                new Vector2(r + 0.012f, -0.038f), new Vector2(r + 0.014f, -0.010f), new Vector2(r + 0.010f, 0f) };
            var rim = MeshObj(go.transform, "Rim", LatheZ(rimProfile, 96, "ClockRim"), Mat("Clock_Rim", new Color(0.10f, 0.10f, 0.11f), 0.6f, 0.2f));
            var face = MeshObj(go.transform, "Face", Disk(r - 0.006f, 96, -0.012f, "ClockFace"), Mat("Clock_Face", Color.white, 0.25f, 0f, Tex("Clock_Face")));
            var glass = MeshObj(go.transform, "Glass", Disk(r - 0.004f, 96, -0.040f, "ClockGlass"), GlassMat());
            glass.GetComponent<MeshRenderer>().shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var handMat = Mat("Clock_Hands", new Color(0.07f, 0.07f, 0.08f), 0.5f, 0.3f);
            var hour = Hand(go.transform, "HourHand", r * 0.50f, 0.010f, -0.020f, handMat);
            var minute = Hand(go.transform, "MinuteHand", r * 0.78f, 0.007f, -0.024f, handMat);
            var second = Hand(go.transform, "SecondHand", r * 0.86f, 0.0025f, -0.028f, Mat("Clock_Second", new Color(0.85f, 0.15f, 0.12f), 0.5f, 0f));
            MeshObj(go.transform, "Cap", LatheZ(new List<Vector2> { new Vector2(0, -0.032f), new Vector2(0.007f, -0.031f), new Vector2(0.008f, -0.018f), new Vector2(0.006f, -0.016f) }, 32, "ClockCap"), handMat);
            var wc = go.AddComponent<WallClock>(); wc.hourHand = hour; wc.minuteHand = minute; wc.secondHand = second;
        }

        static Transform Hand(Transform parent, string name, float length, float width, float z, Material m)
        {
            var pivot = new GameObject(name).transform; pivot.SetParent(parent, false); pivot.localPosition = new Vector3(0, 0, z);
            // tapered blade pointing +Y, with a short tail
            var mesh = new Mesh { name = "Clock_" + name };
            float tail = length * 0.18f;
            var v = new[] { new Vector3(-width, -tail, 0), new Vector3(width, -tail, 0), new Vector3(width * 0.55f, length, 0), new Vector3(-width * 0.55f, length, 0) };
            mesh.vertices = new[] { v[0], v[1], v[2], v[3], v[0], v[1], v[2], v[3] };
            mesh.triangles = new[] { 0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7 };
            mesh.RecalculateNormals(); mesh.RecalculateBounds();
            SaveMesh(mesh, "Clock_" + name);
            MeshObj(pivot, "Blade", mesh, m);
            return pivot;
        }

        static void SnakePlant(Transform parent, Vector3 floor)
        {
            var go = new GameObject("SnakePlant"); go.transform.SetParent(parent, false); go.transform.position = floor;
            // pot: matte white ceramic, slightly tapered with rolled rim
            var pot = new List<Vector2> {
                new Vector2(0.000f, 0.010f), new Vector2(0.125f, 0.010f), new Vector2(0.132f, 0.000f), new Vector2(0.140f, 0.004f),
                new Vector2(0.168f, 0.360f), new Vector2(0.176f, 0.372f), new Vector2(0.176f, 0.392f), new Vector2(0.168f, 0.398f),
                new Vector2(0.158f, 0.392f), new Vector2(0.150f, 0.370f), new Vector2(0.148f, 0.360f) };
            MeshObj(go.transform, "Pot", LatheY(pot, 72, "SnakePlant_Pot"), Mat("Ceramic_MatteWhite", new Color(0.92f, 0.91f, 0.89f), 0.32f, 0f));
            MeshObj(go.transform, "Soil", DiskY(0.150f, 48, 0.352f, "SnakePlant_Soil"), Mat("Soil", Color.white, 0.05f, 0f, Tex("Soil_Albedo"), null, 6f));
            var leafMat = Mat("Leaf_SnakePlant", new Color(0.78f, 0.95f, 0.72f), 0.42f, 0f, Tex("Leaf_Albedo"), Tex("Leaf_Normal"));
            var rng = new System.Random(11);
            for (int i = 0; i < 14; i++)
            {
                float a = (float)(i * 137.5 * Mathf.Deg2Rad);
                float rad = 0.02f + 0.085f * Mathf.Sqrt(i / 14f);
                float len = 0.55f + (float)rng.NextDouble() * 0.45f - rad * 1.2f;
                float wid = 0.045f + (float)rng.NextDouble() * 0.02f;
                var leaf = BladeMesh(len, wid, 0.10f + (float)rng.NextDouble() * 0.12f, (float)(rng.NextDouble() - 0.5) * 0.8f, 18, "SnakeLeaf_" + i);
                var lg = MeshObj(go.transform, "Leaf_" + i, leaf, leafMat);
                lg.transform.localPosition = new Vector3(Mathf.Cos(a) * rad, 0.345f, Mathf.Sin(a) * rad);
                lg.transform.localRotation = Quaternion.Euler(0, -a * Mathf.Rad2Deg + 90f, 0) * Quaternion.Euler(4f + rad * 90f, 0, 0);
            }
            var col = go.AddComponent<CapsuleCollider>(); col.center = new Vector3(0, 0.45f, 0); col.radius = 0.18f; col.height = 0.9f;
        }

        static void Succulent(Transform parent, Vector3 onTop)
        {
            var go = new GameObject("Succulent"); go.transform.SetParent(parent, false); go.transform.position = onTop;
            var pot = new List<Vector2> {
                new Vector2(0f, 0.004f), new Vector2(0.040f, 0.004f), new Vector2(0.044f, 0f), new Vector2(0.050f, 0.002f),
                new Vector2(0.056f, 0.080f), new Vector2(0.058f, 0.088f), new Vector2(0.052f, 0.090f), new Vector2(0.050f, 0.082f) };
            MeshObj(go.transform, "Pot", LatheY(pot, 48, "Succulent_Pot"), Mat("Ceramic_Terracotta", new Color(0.70f, 0.40f, 0.28f), 0.2f, 0f));
            MeshObj(go.transform, "Soil", DiskY(0.050f, 32, 0.078f, "Succulent_Soil"), Mat("Soil", Color.white, 0.05f, 0f, Tex("Soil_Albedo"), null, 6f));
            var m = Mat("Leaf_Succulent", new Color(0.70f, 0.86f, 0.78f), 0.35f, 0f, Tex("Leaf_Albedo"), Tex("Leaf_Normal"));
            int idx = 0;
            for (int ring = 0; ring < 3; ring++)
            {
                int count = 9 - ring * 2; float tilt = 62f - ring * 18f; float len = 0.055f - ring * 0.012f;
                for (int k = 0; k < count; k++)
                {
                    float a = k * 360f / count + ring * 20f;
                    var leaf = BladeMesh(len, len * 0.42f, 0.02f, 0f, 8, "SucculentLeaf_" + ring + "_" + k, true);
                    var lg = MeshObj(go.transform, "Leaf_" + idx++, leaf, m);
                    lg.transform.localPosition = new Vector3(0, 0.082f + ring * 0.006f, 0);
                    lg.transform.localRotation = Quaternion.Euler(0, a, 0) * Quaternion.Euler(tilt, 0, 0);
                }
            }
        }

        static void Books(Transform parent, Vector3 start)
        {
            var go = new GameObject("Books"); go.transform.SetParent(parent, false); go.transform.position = start;
            var m = Mat("Books", Color.white, 0.18f, 0f, Tex("Book_Spines"));
            var pages = Mat("Book_Pages", new Color(0.93f, 0.91f, 0.85f), 0.05f, 0f);
            float x = 0; var rng = new System.Random(4);
            int[] order = { 0, 3, 6, 1, 4, 2, 7 };
            for (int i = 0; i < order.Length; i++)
            {
                float t = 0.022f + (float)rng.NextDouble() * 0.022f, h = 0.20f + (float)rng.NextDouble() * 0.06f, d = 0.15f + (float)rng.NextDouble() * 0.04f;
                var b = new GameObject("Book_" + i).transform; b.SetParent(go.transform, false);
                b.localPosition = new Vector3(x + t / 2, 0, 0);
                bool lean = i == order.Length - 1;
                if (lean) { b.localRotation = Quaternion.Euler(0, 0, 14f); b.localPosition += new Vector3(0.018f, 0, 0); }
                var mesh = BookMesh(t, h, d, order[i], "Book_" + i);
                MeshObj(b, "Cover", mesh, m);
                Box(b, "Pages", new Vector3(0, h / 2, 0.004f), new Vector3(t * 0.86f, h - 0.008f, d - 0.012f), pages, false);   // recessed behind the spine
                x += t + 0.0015f;
            }
        }

        static void Mug(Transform parent, Vector3 onTop)
        {
            var go = new GameObject("Mug"); go.transform.SetParent(parent, false); go.transform.position = onTop;
            go.transform.rotation = Quaternion.Euler(0, 35, 0);
            var prof = new List<Vector2> {
                new Vector2(0f, 0.002f), new Vector2(0.034f, 0.002f), new Vector2(0.038f, 0f), new Vector2(0.041f, 0.006f),
                new Vector2(0.042f, 0.094f), new Vector2(0.040f, 0.098f), new Vector2(0.037f, 0.094f), new Vector2(0.036f, 0.012f), new Vector2(0f, 0.010f) };
            var ceramic = Mat("Ceramic_GlossNavy", new Color(0.12f, 0.20f, 0.34f), 0.82f, 0f);
            MeshObj(go.transform, "Body", LatheY(prof, 64, "Mug_Body"), ceramic);
            MeshObj(go.transform, "Coffee", DiskY(0.0362f, 40, 0.070f, "Mug_Coffee"), Mat("Coffee", new Color(0.16f, 0.09f, 0.05f), 0.9f, 0f));
            MeshObj(go.transform, "Handle", Torus(0.026f, 0.0055f, 32, 12, 200f, "Mug_Handle"), ceramic).transform.localPosition = new Vector3(0.046f, 0.050f, 0);
        }

        // ======================================================================= mesh helpers
        static Mesh LatheY(List<Vector2> prof, int seg, string name)      // profile (radius, height) around Y
        {
            var verts = new List<Vector3>(); var uvs = new List<Vector2>(); var tris = new List<int>();
            float total = 0; var acc = new float[prof.Count];
            for (int i = 1; i < prof.Count; i++) { total += Vector2.Distance(prof[i], prof[i - 1]); acc[i] = total; }
            for (int s = 0; s <= seg; s++)
            {
                float a = s * Mathf.PI * 2 / seg; float c = Mathf.Cos(a), sn = Mathf.Sin(a);
                for (int i = 0; i < prof.Count; i++) { verts.Add(new Vector3(prof[i].x * c, prof[i].y, prof[i].x * sn)); uvs.Add(new Vector2((float)s / seg, acc[i] / Mathf.Max(total, 1e-4f))); }
            }
            int n = prof.Count;
            for (int s = 0; s < seg; s++) for (int i = 0; i < n - 1; i++)
            { int a = s * n + i, b = (s + 1) * n + i; tris.AddRange(new[] { a, a + 1, b, b, a + 1, b + 1 }); }
            return Finish(verts, uvs, tris, name);
        }

        static Mesh LatheZ(List<Vector2> prof, int seg, string name)      // profile (radius, z) around Z
        {
            var m = LatheY(prof, seg, name + "_tmp");
            var v = m.vertices; for (int i = 0; i < v.Length; i++) v[i] = new Vector3(v[i].x, v[i].z, v[i].y);
            m.vertices = v; var t = m.triangles; for (int i = 0; i < t.Length; i += 3) { int k = t[i]; t[i] = t[i + 1]; t[i + 1] = k; }
            m.triangles = t; m.RecalculateNormals(); m.RecalculateBounds(); m.name = name;
            return SaveMesh(m, name);
        }

        static Mesh Disk(float r, int seg, float z, string name)          // facing -Z (toward viewer), UV fits texture
        {
            var verts = new List<Vector3> { new Vector3(0, 0, z) }; var uvs = new List<Vector2> { new Vector2(0.5f, 0.5f) }; var tris = new List<int>();
            for (int s = 0; s <= seg; s++) { float a = s * Mathf.PI * 2 / seg; verts.Add(new Vector3(Mathf.Cos(a) * r, Mathf.Sin(a) * r, z)); uvs.Add(new Vector2(Mathf.Cos(a) * 0.5f + 0.5f, Mathf.Sin(a) * 0.5f + 0.5f)); }
            for (int s = 1; s <= seg; s++) tris.AddRange(new[] { 0, s + 1, s });
            return Finish(verts, uvs, tris, name);
        }

        static Mesh DiskY(float r, int seg, float y, string name)         // facing +Y
        {
            var verts = new List<Vector3> { new Vector3(0, y, 0) }; var uvs = new List<Vector2> { new Vector2(0.5f, 0.5f) }; var tris = new List<int>();
            for (int s = 0; s <= seg; s++) { float a = s * Mathf.PI * 2 / seg; verts.Add(new Vector3(Mathf.Cos(a) * r, y, Mathf.Sin(a) * r)); uvs.Add(new Vector2(Mathf.Cos(a) * r * 4 + 0.5f, Mathf.Sin(a) * r * 4 + 0.5f)); }
            for (int s = 1; s <= seg; s++) tris.AddRange(new[] { 0, s + 1, s });
            return Finish(verts, uvs, tris, name);
        }

        static Mesh Torus(float R, float r, int segU, int segV, float arcDeg, string name)   // arc in XY plane (handle)
        {
            var verts = new List<Vector3>(); var uvs = new List<Vector2>(); var tris = new List<int>();
            float arc = arcDeg * Mathf.Deg2Rad, start = -arc / 2;
            for (int u = 0; u <= segU; u++)
            {
                float a = start + arc * u / segU; var c = new Vector3(Mathf.Cos(a) * R, Mathf.Sin(a) * R, 0);
                var outDir = new Vector3(Mathf.Cos(a), Mathf.Sin(a), 0);
                for (int v = 0; v <= segV; v++)
                {
                    float b = v * Mathf.PI * 2 / segV;
                    verts.Add(c + (outDir * Mathf.Cos(b) + Vector3.forward * Mathf.Sin(b)) * r);
                    uvs.Add(new Vector2((float)u / segU, (float)v / segV));
                }
            }
            for (int u = 0; u < segU; u++) for (int v = 0; v < segV; v++)
            { int a = u * (segV + 1) + v, b = a + segV + 1; tris.AddRange(new[] { a, b, a + 1, a + 1, b, b + 1 }); }
            return Finish(verts, uvs, tris, name);
        }

        /// Curved, tapered, double-sided leaf blade rising along +Y, bending toward -Z. U across, V along (matches leaf texture).
        static Mesh BladeMesh(float len, float width, float bend, float twist, int steps, string name, bool fleshy = false)
        {
            var verts = new List<Vector3>(); var uvs = new List<Vector2>(); var tris = new List<int>();
            const int across = 4;
            for (int i = 0; i <= steps; i++)
            {
                float t = (float)i / steps;
                float w = fleshy ? width * Mathf.Max(0f, Mathf.Sin(Mathf.PI * Mathf.Lerp(0.15f, 1f, t))) * (1 - t * 0.2f)
                                 : width * Mathf.Pow(Mathf.Max(0f, Mathf.Sin(Mathf.PI * Mathf.Lerp(0.18f, 1f, t))), 0.6f) * (t < 0.92f ? 1f : (1 - t) / 0.08f);
                var spine = new Vector3(0, t * len, -bend * t * t * len);
                var tw = Quaternion.Euler(0, twist * Mathf.Rad2Deg * t, 0);
                for (int j = 0; j <= across; j++)
                {
                    float s = (float)j / across * 2 - 1;
                    float cup = (fleshy ? 0.5f : 0.18f) * w * (1 - s * s);           // V-shaped cross-section
                    verts.Add(spine + tw * new Vector3(s * w, 0, -cup));
                    uvs.Add(new Vector2(s * 0.5f + 0.5f, t));
                }
            }
            int row = across + 1, frontCount = verts.Count;
            for (int i = 0; i < steps; i++) for (int j = 0; j < across; j++)
            { int a = i * row + j, b = a + row; tris.AddRange(new[] { a, b, a + 1, a + 1, b, b + 1 }); }
            // back side (separate verts so normals face the other way)
            for (int k = 0; k < frontCount; k++) { verts.Add(verts[k]); uvs.Add(uvs[k]); }
            for (int i = 0; i < steps; i++) for (int j = 0; j < across; j++)
            { int a = frontCount + i * row + j, b = a + row; tris.AddRange(new[] { a, a + 1, b, a + 1, b + 1, b }); }
            return Finish(verts, uvs, tris, name);
        }

        static Mesh BookMesh(float t, float h, float d, int column, string name)   // spine on -Z face, mapped to atlas column
        {
            float u0 = column / 8f + 0.002f, u1 = (column + 1) / 8f - 0.002f;
            var m = new Mesh { name = name };
            var V = new List<Vector3>(); var U = new List<Vector2>(); var T = new List<int>();
            void Face(Vector3 a, Vector3 b, Vector3 c, Vector3 e, Vector2 ua, Vector2 ub, Vector2 uc, Vector2 ue)
            { int i = V.Count; V.AddRange(new[] { a, b, c, e }); U.AddRange(new[] { ua, ub, uc, ue }); T.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 }); }
            float x0 = -t / 2, x1 = t / 2, z0 = -d / 2, z1 = d / 2;
            // spine (facing -Z, toward the room): text runs bottom->top
            Face(new Vector3(x1, 0, z0), new Vector3(x0, 0, z0), new Vector3(x0, h, z0), new Vector3(x1, h, z0), new Vector2(u1, 0), new Vector2(u0, 0), new Vector2(u0, 1), new Vector2(u1, 1));
            Vector2 c0 = new Vector2(u0 + 0.01f, 0.5f), c1 = new Vector2(u0 + 0.011f, 0.5f);   // cover colour sampled from the spine
            Face(new Vector3(x0, 0, z0), new Vector3(x0, 0, z1), new Vector3(x0, h, z1), new Vector3(x0, h, z0), c0, c1, c1, c0);
            Face(new Vector3(x1, 0, z1), new Vector3(x1, 0, z0), new Vector3(x1, h, z0), new Vector3(x1, h, z1), c0, c1, c1, c0);
            Face(new Vector3(x0, h, z0), new Vector3(x0, h, z1), new Vector3(x1, h, z1), new Vector3(x1, h, z0), c0, c1, c1, c0);
            Face(new Vector3(x0, 0, z1), new Vector3(x1, 0, z1), new Vector3(x1, h, z1), new Vector3(x0, h, z1), c0, c1, c1, c0);
            m.SetVertices(V); m.SetUVs(0, U); m.SetTriangles(T, 0); m.RecalculateNormals(); m.RecalculateBounds();
            return SaveMesh(m, name);
        }

        static Mesh Finish(List<Vector3> v, List<Vector2> uv, List<int> t, string name)
        {
            var m = new Mesh { name = name };
            if (v.Count > 65000) m.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            m.SetVertices(v); m.SetUVs(0, uv); m.SetTriangles(t, 0);
            m.RecalculateNormals(); m.RecalculateTangents(); m.RecalculateBounds();
            return name.EndsWith("_tmp") ? m : SaveMesh(m, name);
        }

        static Mesh SaveMesh(Mesh m, string name)
        {
            m.RecalculateTangents();
            string p = MeshDir + "/" + name + ".asset";
            if (AssetDatabase.LoadAssetAtPath<Mesh>(p) != null) AssetDatabase.DeleteAsset(p);   // replace outright (no stale GPU data)
            m.name = name;
            AssetDatabase.CreateAsset(m, p); return m;
        }

        static GameObject MeshObj(Transform parent, string name, Mesh mesh, Material mat)
        {
            var g = new GameObject(name); g.transform.SetParent(parent, false);
            g.AddComponent<MeshFilter>().sharedMesh = mesh; g.AddComponent<MeshRenderer>().sharedMaterial = mat;
            return g;
        }

        static GameObject Box(Transform parent, string name, Vector3 center, Vector3 size, Material mat, bool collider = false)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Cube); g.name = name; g.transform.SetParent(parent, false);
            g.transform.localPosition = center; g.transform.localScale = size;
            if (!collider) Object.DestroyImmediate(g.GetComponent<Collider>());
            g.GetComponent<MeshRenderer>().sharedMaterial = mat; return g;
        }

        static GameObject Quad(Transform parent, string name, Vector3 center, float w, float h)
        {
            var g = GameObject.CreatePrimitive(PrimitiveType.Quad); g.name = name; g.transform.SetParent(parent, false);
            g.transform.localPosition = center; g.transform.localScale = new Vector3(w, h, 1);   // built-in quad faces -Z
            Object.DestroyImmediate(g.GetComponent<Collider>()); return g;
        }

        // ======================================================================= materials
        static Material Mat(string name, Color c, float smooth, float metal, Texture2D albedo = null, Texture2D normal = null, float tiling = 1f)
        {
            string p = MatDir + "/" + name + ".mat";
            var m = AssetDatabase.LoadAssetAtPath<Material>(p);
            if (!m) { m = new Material(Shader.Find("Standard")); AssetDatabase.CreateAsset(m, p); }
            m.color = c; m.SetFloat("_Glossiness", smooth); m.SetFloat("_Metallic", metal);
            m.mainTexture = albedo; m.mainTextureScale = Vector2.one * tiling;
            if (normal) { m.SetTexture("_BumpMap", normal); m.EnableKeyword("_NORMALMAP"); } else { m.SetTexture("_BumpMap", null); m.DisableKeyword("_NORMALMAP"); }
            m.enableInstancing = true; EditorUtility.SetDirty(m); return m;
        }

        static Material GlassMat()
        {
            var m = Mat("Glass_Picture", new Color(1, 1, 1, 0.06f), 0.96f, 0f);
            m.SetFloat("_Mode", 3); m.SetOverrideTag("RenderType", "Transparent");
            m.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.One); m.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha); m.SetInt("_ZWrite", 0);
            m.DisableKeyword("_ALPHATEST_ON"); m.DisableKeyword("_ALPHABLEND_ON"); m.EnableKeyword("_ALPHAPREMULTIPLY_ON"); m.renderQueue = 3000;
            EditorUtility.SetDirty(m); return m;
        }

        static Texture2D Tex(string n) => AssetDatabase.LoadAssetAtPath<Texture2D>(TexDir + "/" + n + ".png");

        static Bounds Bounds(string objectName)
        {
            var g = GameObject.Find(objectName);
            if (!g) { Debug.LogWarning("[Decor] missing " + objectName); return new Bounds(); }
            return g.GetComponent<Renderer>().bounds;
        }

        static void EnsureDir(string p)
        {
            if (AssetDatabase.IsValidFolder(p)) return;
            var parent = System.IO.Path.GetDirectoryName(p).Replace('\\', '/');
            EnsureDir(parent); AssetDatabase.CreateFolder(parent, System.IO.Path.GetFileName(p));
        }
    }
}
#endif
