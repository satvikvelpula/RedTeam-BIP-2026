// Standard (metallic) surface shader that renders both faces, with correct lighting on the back face.
// Used for thin single-sided meshes such as the roller-shade fabric.
Shader "IVAR/Standard Double Sided"
{
    Properties
    {
        _Color ("Color", Color) = (1,1,1,1)
        _MainTex ("Albedo", 2D) = "white" {}
        [Normal] _BumpMap ("Normal Map", 2D) = "bump" {}
        _BumpScale ("Normal Strength", Float) = 1.0
        _Glossiness ("Smoothness", Range(0,1)) = 0.2
        [Gamma] _Metallic ("Metallic", Range(0,1)) = 0.0
        _Translucency ("Back-light glow", Range(0,1)) = 0.25
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        Cull Off

        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows addshadow
        #pragma target 3.0

        sampler2D _MainTex, _BumpMap;
        fixed4 _Color;
        half _Glossiness, _Metallic, _BumpScale, _Translucency;

        struct Input
        {
            float2 uv_MainTex;
            float2 uv_BumpMap;
            fixed facing : VFACE;
        };

        void surf (Input IN, inout SurfaceOutputStandard o)
        {
            fixed4 c = tex2D(_MainTex, IN.uv_MainTex) * _Color;
            o.Albedo = c.rgb;
            o.Metallic = _Metallic;
            o.Smoothness = _Glossiness;
            float3 n = UnpackScaleNormal(tex2D(_BumpMap, IN.uv_BumpMap), _BumpScale);
            n.z *= (IN.facing > 0) ? 1 : -1;          // flip for the back face
            o.Normal = n;
            o.Emission = c.rgb * _Translucency * 0.15; // thin fabric lets a little light through
            o.Alpha = 1;
        }
        ENDCG
    }
    FallBack "Diffuse"
}
