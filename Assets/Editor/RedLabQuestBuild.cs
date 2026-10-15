// Reproducible Quest 3/3S build for RedLab Twin (Meta Horizon Store, ALPHA channel).
// Menu: RedLab > Build Quest APK (release)   |   RedLab > Build Quest APK (debug, sideload only)
// Batchmode: Unity.exe -batchmode -quit -projectPath D:\TelTech -buildTarget Android -executeMethod RedLabQuestBuild.Release
//
// The release key NEVER lives in this repo. Put it in %USERPROFILE%\.tredlab-keys\keystore.env:
//   REDLAB_KEYSTORE=C:\Users\<you>\.tredlab-keys\redlab-release.keystore
//   REDLAB_KEYSTORE_PASS=...
//   REDLAB_KEY_ALIAS=...
//   REDLAB_KEY_PASS=...          (optional, defaults to the keystore password)
// Environment variables with the same names override the file.
// Version code: REDLAB_VERSION_CODE env var, otherwise the current one + 1. It must be higher than every upload.
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class RedLabQuestBuild
{
    const string PackageName = "com.tredlab.redlabtwin";
    const string ProductName = "RedLab Twin";
    const string OutputDir = "Build";

    [MenuItem("RedLab/Build Quest APK (release)")]
    public static void Release() => Build(true);

    [MenuItem("RedLab/Build Quest APK (debug, sideload only)")]
    public static void Debug() => Build(false);

    static void Build(bool release)
    {
        if (!BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.Android, BuildTarget.Android))
            throw new Exception("Android Build Support is not installed for this Unity version (Unity Hub > Installs > Add modules).");

        if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.Android)
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);

        ApplyStoreSettings();

        int code = PlayerSettings.Android.bundleVersionCode;
        var envCode = Environment.GetEnvironmentVariable("REDLAB_VERSION_CODE");
        if (!string.IsNullOrEmpty(envCode)) code = int.Parse(envCode);
        else if (release) code += 1;
        PlayerSettings.Android.bundleVersionCode = code;

        if (release) ApplyReleaseKey();
        else PlayerSettings.Android.useCustomKeystore = false;

        try
        {
            Directory.CreateDirectory(OutputDir);
            var path = Path.Combine(OutputDir, release ? $"RedLabTwin-Quest-{code}.apk" : "RedLabTwin-Quest-debug.apk");
            var options = new BuildPlayerOptions
            {
                scenes = EnabledScenes(),
                locationPathName = path,
                target = BuildTarget.Android,
                targetGroup = BuildTargetGroup.Android,
                options = release ? BuildOptions.None : BuildOptions.Development,
            };
            var report = BuildPipeline.BuildPlayer(options);
            if (report.summary.result != BuildResult.Succeeded)
                throw new Exception("Build failed: " + report.summary.result);
            UnityEngine.Debug.Log($"[RedLab] {(release ? "RELEASE" : "DEBUG")} APK: {Path.GetFullPath(path)} (versionCode {code}, {report.summary.totalSize / (1024 * 1024)} MB)");
        }
        finally
        {
            // Never leave key paths or passwords in ProjectSettings.asset (it is committed).
            PlayerSettings.Android.useCustomKeystore = false;
            PlayerSettings.Android.keystoreName = "";
            PlayerSettings.Android.keystorePass = "";
            PlayerSettings.Android.keyaliasName = "";
            PlayerSettings.Android.keyaliasPass = "";
            AssetDatabase.SaveAssets();
        }
    }

    // Meta Horizon Store requirements: arm64 only, IL2CPP, targetSdk 34, installLocation auto, INTERNET kept.
    static void ApplyStoreSettings()
    {
        var g = BuildTargetGroup.Android;
        PlayerSettings.companyName = "TRedLab";
        PlayerSettings.productName = ProductName;
        PlayerSettings.SetApplicationIdentifier(g, PackageName);
        PlayerSettings.SetScriptingBackend(g, ScriptingImplementation.IL2CPP);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
        PlayerSettings.Android.minSdkVersion = (AndroidSdkVersions)32;
        PlayerSettings.Android.targetSdkVersion = (AndroidSdkVersions)34;
        PlayerSettings.Android.preferredInstallLocation = AndroidPreferredInstallLocation.Auto;
        PlayerSettings.Android.forceInternetPermission = true;
        PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft; // Meta Store requires landscape
        PlayerSettings.colorSpace = ColorSpace.Linear;
        EditorUserBuildSettings.development = false;
        EditorUserBuildSettings.allowDebugging = false;
    }

    static void ApplyReleaseKey()
    {
        var keyFile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".tredlab-keys", "keystore.env");
        var values = new Dictionary<string, string>();
        if (File.Exists(keyFile))
            foreach (var raw in File.ReadAllLines(keyFile))
            {
                var line = raw.Trim();
                if (line.Length == 0 || line.StartsWith("#") || !line.Contains("=")) continue;
                var i = line.IndexOf('=');
                values[line.Substring(0, i).Trim()] = line.Substring(i + 1).Trim().Trim('"');
            }
        string Get(string k) { var e = Environment.GetEnvironmentVariable(k); return !string.IsNullOrEmpty(e) ? e : (values.TryGetValue(k, out var v) ? v : null); }

        var ks = Get("REDLAB_KEYSTORE");
        var pass = Get("REDLAB_KEYSTORE_PASS");
        var alias = Get("REDLAB_KEY_ALIAS");
        var keyPass = Get("REDLAB_KEY_PASS") ?? pass;
        if (string.IsNullOrEmpty(ks) || !File.Exists(ks) || string.IsNullOrEmpty(pass) || string.IsNullOrEmpty(alias))
            throw new Exception($"Release keystore not configured. Create {keyFile} (see header of RedLabQuestBuild.cs). Refusing to build a store APK with the debug key.");

        PlayerSettings.Android.useCustomKeystore = true;
        PlayerSettings.Android.keystoreName = ks;
        PlayerSettings.Android.keystorePass = pass;
        PlayerSettings.Android.keyaliasName = alias;
        PlayerSettings.Android.keyaliasPass = keyPass;
    }

    static string[] EnabledScenes()
    {
        var list = new List<string>();
        foreach (var s in EditorBuildSettings.scenes) if (s.enabled) list.Add(s.path);
        if (list.Count == 0) throw new Exception("No scenes enabled in Build Settings.");
        return list.ToArray();
    }
}
#endif
