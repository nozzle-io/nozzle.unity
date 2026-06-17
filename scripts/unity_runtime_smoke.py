#!/usr/bin/env python3
"""Run local Unity runtime frame smoke against nozzle-tester-cli.

This is intentionally a local/manual smoke helper for Unity-header runtime
artifacts. Public runtime-enabled package production is tracked separately.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from unity_validate import TARGETS, known_unity_paths, overlay_native_payload, resolve_payload_dir, resolve_unity
from unity_release_contract import PACKAGE_NAME, PACKAGE_ROOT_RELATIVE, PLATFORMS, current_git_sha, fail, package_manifest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE_ROOT = ROOT / PACKAGE_ROOT_RELATIVE
DEFAULT_PROJECT_ROOT = ROOT / "build" / "unity-runtime-smoke" / "project"

RUNTIME_SMOKE_ASMDEF = {
    "name": "Nozzle.UnityRuntimeSmoke",
    "rootNamespace": "Nozzle.UnityRuntimeSmoke",
    "references": ["Nozzle.Unity"],
    "includePlatforms": [],
    "excludePlatforms": [],
    "allowUnsafeCode": False,
    "overrideReferences": False,
    "precompiledReferences": [],
    "autoReferenced": True,
    "defineConstraints": [],
    "versionDefines": [],
    "noEngineReferences": False,
}

PLAYER_SCRIPT = r'''
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using Nozzle;
using UnityEngine;
using UnityEngine.Rendering;

namespace Nozzle.UnityRuntimeSmoke
{
    public sealed class NozzleUnityRuntimeSmoke : MonoBehaviour
    {
        string mode;
        string senderName;
        string reportPath;
        string rawPath;
        string readyPath;
        int width;
        int height;
        int frames;
        int maxFrames;
        int frameCounter;
        NozzleSender sender;
        Texture2D sourceTexture;
        NozzleReceiver receiver;
        RenderTexture targetTexture;
        bool readbackStarted;
        bool completed;
        readonly Dictionary<string, object> report = new Dictionary<string, object>();

        static string Arg(string name, string fallback = "")
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i + 1 < args.Length; ++i)
            {
                if (args[i] == name) return args[i + 1];
            }
            return fallback;
        }

        static int IntArg(string name, int fallback)
        {
            int value;
            return Int32.TryParse(Arg(name, ""), out value) ? value : fallback;
        }

        static void SetPrivate(object target, string fieldName, object value)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null) throw new Exception("missing field " + fieldName + " on " + target.GetType().FullName);
            field.SetValue(target, value);
        }

        static string JsonString(string value)
        {
            return "\"" + (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r") + "\"";
        }

        static string JsonValue(object value)
        {
            if (value == null) return "null";
            if (value is bool b) return b ? "true" : "false";
            if (value is int || value is uint || value is long || value is ulong) return Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture);
            if (value is string s) return JsonString(s);
            return JsonString(value.ToString());
        }

        void WriteReport(string result, string reason = "")
        {
            if (completed) return;
            completed = true;
            report["result"] = result;
            report["reason"] = reason;
            report["mode"] = mode;
            report["sender_name"] = senderName;
            report["width"] = width;
            report["height"] = height;
            report["frames_requested"] = frames;
            report["unity_version"] = Application.unityVersion;
            NozzleRuntimeSupport.BridgeSupport support;
            if (NozzleRuntimeSupport.TryGetBridgeSupport(out support))
            {
                report["runtime_supported"] = support.RuntimeSupported;
                report["unity_headers_compiled"] = support.UnityHeadersCompiled;
                report["unity_graphics_device_available"] = support.UnityGraphicsDeviceAvailable;
                report["render_thread_events_available"] = support.RenderThreadEventsAvailable;
                report["direct_nozzle_c_abi_available"] = support.DirectNozzleCAbiAvailable;
                report["support_status"] = support.StatusMessage;
            }
            Directory.CreateDirectory(Path.GetDirectoryName(reportPath));
            using (var writer = new StreamWriter(reportPath, false))
            {
                writer.WriteLine("{");
                int index = 0;
                foreach (var pair in report)
                {
                    string comma = index + 1 == report.Count ? "" : ",";
                    writer.WriteLine("  " + JsonString(pair.Key) + ": " + JsonValue(pair.Value) + comma);
                    index++;
                }
                writer.WriteLine("}");
            }
            Debug.Log("NOZZLE_UNITY_RUNTIME_SMOKE_RESULT " + result + " mode=" + mode + " report=" + reportPath + " reason=" + reason);
            Application.Quit(result == "pass" ? 0 : 1);
        }

        static byte ToByte(float value)
        {
            if (value <= 0.0f) return 0;
            if (1.0f <= value) return 255;
            return (byte)Mathf.RoundToInt(value * 255.0f);
        }

        static int MarkerSize(int w, int h)
        {
            int minimum = Math.Min(w, h);
            if (minimum == 0) return 0;
            int size = Math.Max(1, minimum / 8);
            return Math.Min(size, 24);
        }

        static Color32 ExpectedPixel(int x, int y, int w, int h, ulong frameIndex)
        {
            if (w == 0 || h == 0) return new Color32(0, 0, 0, 0);
            float fx = w <= 1 ? 0.0f : (float)x / (float)(w - 1);
            float fy = h <= 1 ? 0.0f : (float)y / (float)(h - 1);
            float r = Mathf.Repeat(0.11f + fx * 0.53f + (float)(frameIndex % 17UL) * 0.031f, 1.0f);
            float g = Mathf.Repeat(0.17f + fy * 0.61f + (float)(((ulong)x + frameIndex) % 13UL) * 0.019f, 1.0f);
            float b = Mathf.Repeat(0.23f + (1.0f - fx) * 0.37f + (float)(((ulong)y + frameIndex) % 11UL) * 0.023f, 1.0f);
            float a = 1.0f;
            int size = MarkerSize(w, h);
            if (size != 0 && x < size && y < size) return new Color32(255, 13, 13, 255);
            if (size != 0 && w - size <= x && y < size) return new Color32(13, 255, 13, 255);
            if (size != 0 && x < size && h - size <= y) return new Color32(13, 13, 255, 255);
            if (size != 0 && w - size <= x && h - size <= y) return new Color32(255, 255, 13, 255);

            int redLeft = w / 5;
            int redRight = Math.Min(w, redLeft + Math.Max(1, w / 12));
            if (redLeft <= x && x < redRight)
            {
                r = 1.0f;
                g *= 0.15f;
                b *= 0.15f;
            }

            int blueTop = (h * 3) / 5;
            int blueBottom = Math.Min(h, blueTop + Math.Max(1, h / 12));
            if (blueTop <= y && y < blueBottom)
            {
                r *= 0.15f;
                g *= 0.15f;
                b = 1.0f;
            }

            int alphaLeft = w / 2;
            int alphaTop = h / 3;
            int alphaRight = Math.Min(w, alphaLeft + Math.Max(1, w / 5));
            int alphaBottom = Math.Min(h, alphaTop + Math.Max(1, h / 5));
            if (alphaLeft <= x && x < alphaRight && alphaTop <= y && y < alphaBottom)
            {
                r = 1.0f;
                g = 0.0f;
                b = 1.0f;
                a = 0.35f;
            }

            int movingSize = Math.Max(1, Math.Min(w, h) / 16);
            int travelWidth = w <= movingSize ? 1 : w - movingSize;
            int travelHeight = h <= movingSize ? 1 : h - movingSize;
            int movingX = travelWidth == 1 ? 0 : (int)((frameIndex * 7UL) % (ulong)travelWidth);
            int movingY = travelHeight == 1 ? 0 : (int)((frameIndex * 5UL) % (ulong)travelHeight);
            if (movingX <= x && x < Math.Min(w, movingX + movingSize) && movingY <= y && y < Math.Min(h, movingY + movingSize))
            {
                r = 1.0f;
                g = 1.0f;
                b = 1.0f;
                a = 1.0f;
            }

            return new Color32(ToByte(r), ToByte(g), ToByte(b), ToByte(a));
        }

        static void FillPattern(Texture2D texture, int w, int h, ulong frameIndex)
        {
            Color32[] pixels = new Color32[w * h];
            for (int y = 0; y < h; ++y)
            {
                for (int x = 0; x < w; ++x)
                {
                    pixels[y * w + x] = ExpectedPixel(x, y, w, h, frameIndex);
                }
            }
            texture.SetPixels32(pixels);
            texture.Apply(false, false);
        }

        static int CountMismatches(Color32[] pixels, int w, int h, ulong frameIndex, bool flipY, bool swapRB, bool includeAlpha)
        {
            int mismatches = 0;
            for (int y = 0; y < h; ++y)
            {
                for (int x = 0; x < w; ++x)
                {
                    Color32 got = pixels[y * w + x];
                    if (swapRB)
                    {
                        byte tmp = got.r;
                        got.r = got.b;
                        got.b = tmp;
                    }
                    int expectedY = flipY ? h - 1 - y : y;
                    Color32 want = ExpectedPixel(x, expectedY, w, h, frameIndex);
                    int tolerance = 2;
                    if (Math.Abs(got.r - want.r) > tolerance || Math.Abs(got.g - want.g) > tolerance || Math.Abs(got.b - want.b) > tolerance || (includeAlpha && Math.Abs(got.a - want.a) > tolerance))
                    {
                        mismatches++;
                    }
                }
            }
            return mismatches;
        }

        void Start()
        {
            mode = Arg("-nozzleSmokeMode", "receiver");
            senderName = Arg("-nozzleSmokeName", "unity_runtime_smoke");
            reportPath = Arg("-nozzleSmokeReport", Path.Combine(Application.temporaryCachePath, "nozzle-unity-runtime-smoke.json"));
            rawPath = Arg("-nozzleSmokeRaw", "");
            readyPath = Arg("-nozzleSmokeReady", "");
            width = IntArg("-nozzleSmokeWidth", 320);
            height = IntArg("-nozzleSmokeHeight", 240);
            frames = IntArg("-nozzleSmokeFrames", 1);
            maxFrames = Math.Max(180, IntArg("-nozzleSmokeMaxFrames", 600));
            Application.targetFrameRate = 60;
            QualitySettings.vSyncCount = 0;

            if (mode == "sender") StartSender();
            else if (mode == "receiver") StartReceiver();
            else WriteReport("fail", "unknown_mode");
        }

        void StartSender()
        {
            sourceTexture = new Texture2D(width, height, TextureFormat.RGBA32, false, true);
            FillPattern(sourceTexture, width, height, 0);
            GameObject senderObject = new GameObject("NozzleRuntimeSmokeSender");
            senderObject.SetActive(false);
            sender = senderObject.AddComponent<NozzleSender>();
            SetPrivate(sender, "senderName", senderName);
            SetPrivate(sender, "applicationName", "nozzle-unity-runtime-smoke");
            SetPrivate(sender, "ringBufferSize", (uint)3);
            SetPrivate(sender, "sourceTexture", sourceTexture);
            SetPrivate(sender, "format", NozzleTextureFormat.RGBA8_UNORM);
            senderObject.SetActive(true);
            report["sender_texture_format"] = "RGBA32/RGBA8_UNORM";
        }

        void StartReceiver()
        {
            targetTexture = new RenderTexture(width, height, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
            targetTexture.Create();
            GameObject receiverObject = new GameObject("NozzleRuntimeSmokeReceiver");
            receiverObject.SetActive(false);
            receiver = receiverObject.AddComponent<NozzleReceiver>();
            SetPrivate(receiver, "senderName", senderName);
            SetPrivate(receiver, "applicationName", "nozzle-unity-runtime-smoke");
            SetPrivate(receiver, "targetTexture", targetTexture);
            SetPrivate(receiver, "targetFormat", NozzleTextureFormat.RGBA8_UNORM);
            receiverObject.SetActive(true);
            report["receiver_texture_format"] = "ARGB32/RGBA8_UNORM";
        }

        void Update()
        {
            frameCounter++;
            if (completed) return;
            if (frameCounter > maxFrames)
            {
                WriteReport("fail", "timeout");
                return;
            }

            if (mode == "sender")
            {
                if (frameCounter == 30 && !String.IsNullOrEmpty(readyPath) && !File.Exists(readyPath))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(readyPath));
                    File.WriteAllText(readyPath, "ready\n");
                    report["ready_frame"] = frameCounter;
                    Debug.Log("NOZZLE_UNITY_RUNTIME_SMOKE_SENDER_READY name=" + senderName + " ready=" + readyPath);
                }
                return;
            }

            if (mode == "receiver" && receiver != null && receiver.IsConnected && !readbackStarted)
            {
                readbackStarted = true;
                StartCoroutine(ReadbackAndVerify());
            }
        }

        IEnumerator ReadbackAndVerify()
        {
            yield return new WaitForEndOfFrame();
            RenderTexture previous = RenderTexture.active;
            RenderTexture.active = targetTexture;
            Texture2D readback = new Texture2D(width, height, TextureFormat.RGBA32, false, true);
            readback.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
            readback.Apply(false, false);
            RenderTexture.active = previous;

            Color32[] pixels = readback.GetPixels32();
            if (!String.IsNullOrEmpty(rawPath))
            {
                byte[] raw = readback.GetRawTextureData();
                Directory.CreateDirectory(Path.GetDirectoryName(rawPath));
                File.WriteAllBytes(rawPath, raw);
                report["raw_path"] = rawPath;
                report["raw_bytes"] = raw.Length;
            }

            ulong observedFrame = receiver.LastFrameInfo.FrameIndex;
            int normal = CountMismatches(pixels, width, height, observedFrame, false, false, true);
            int flipped = CountMismatches(pixels, width, height, observedFrame, true, false, true);
            int rbSwap = CountMismatches(pixels, width, height, observedFrame, false, true, true);
            int alphaIgnored = CountMismatches(pixels, width, height, observedFrame, false, false, false);
            report["observed_frame_index"] = observedFrame;
            report["observed_width"] = receiver.LastFrameInfo.Width;
            report["observed_height"] = receiver.LastFrameInfo.Height;
            report["observed_format"] = receiver.LastFrameInfo.Format.ToString();
            report["mismatches_normal"] = normal;
            report["mismatches_flipped"] = flipped;
            report["mismatches_rb_swap"] = rbSwap;
            report["mismatches_alpha_ignored"] = alphaIgnored;
            report["dimensions_ok"] = receiver.LastFrameInfo.Width == width && receiver.LastFrameInfo.Height == height;
            report["orientation_ok"] = normal == 0 && flipped != 0;
            report["channel_order_ok"] = normal == 0 && rbSwap != 0;
            report["alpha_ok"] = normal == alphaIgnored;
            WriteReport(normal == 0 ? "pass" : "fail", normal == 0 ? "receiver_verified" : "pattern_mismatch");
        }
    }
}
'''

EDITOR_SCRIPT = r'''
using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Nozzle.UnityRuntimeSmoke.Editor
{
    public static class NozzleUnityRuntimeSmokeBuilder
    {
        static string Arg(string name, string fallback = "")
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int i = 0; i + 1 < args.Length; ++i)
            {
                if (args[i] == name) return args[i + 1];
            }
            return fallback;
        }

        public static void Build()
        {
            string buildTargetName = Arg("-nozzleSmokeBuildTarget", "StandaloneOSX");
            string buildPath = Arg("-nozzleSmokeBuildPath", "Build/NozzleUnityRuntimeSmoke.app");
            BuildTarget target = (BuildTarget)Enum.Parse(typeof(BuildTarget), buildTargetName);
            Directory.CreateDirectory("Assets/RuntimeSmokeScene");
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameObject host = new GameObject("NozzleUnityRuntimeSmokeHost");
            host.AddComponent<Nozzle.UnityRuntimeSmoke.NozzleUnityRuntimeSmoke>();
            string scenePath = "Assets/RuntimeSmokeScene/NozzleUnityRuntimeSmoke.unity";
            EditorSceneManager.SaveScene(scene, scenePath);
            Directory.CreateDirectory(Path.GetDirectoryName(buildPath));
            BuildPlayerOptions options = new BuildPlayerOptions
            {
                scenes = new[] { scenePath },
                locationPathName = buildPath,
                target = target,
                options = BuildOptions.None,
            };
            var report = BuildPipeline.BuildPlayer(options);
            if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
            {
                throw new Exception("Nozzle Unity runtime smoke Player build failed: " + report.summary.result);
            }
            Debug.Log("NOZZLE_UNITY_RUNTIME_SMOKE_BUILD_PASS build=" + buildPath);
        }
    }
}
'''


def run(command: list[str], *, cwd: Path | None = None, log_path: Path | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    print("$ " + " ".join(str(part) for part in command))
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=timeout)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        if log_path and log_path.is_file():
            print(f"--- log tail: {log_path} ---")
            print("\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-120:]))
            print("--- end log tail ---")
        fail(f"command failed with exit code {result.returncode}: {' '.join(str(part) for part in command)}")
    return result


def copy_package_source(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    def ignore(_dir: str, names: list[str]) -> set[str]:
        return {name for name in names if name in {".git", "Library", "Temp", "Obj", "Logs", "Runtime/Plugins", "__pycache__"}}
    shutil.copytree(source, destination, ignore=ignore)
    plugins = destination / "Runtime" / "Plugins"
    if plugins.exists():
        shutil.rmtree(plugins)


def write_project(project: Path, dependency: str, editor_version: str) -> Path:
    if project.exists():
        shutil.rmtree(project)
    (project / "Assets" / "RuntimeSmoke").mkdir(parents=True, exist_ok=True)
    (project / "Assets" / "Editor").mkdir(parents=True, exist_ok=True)
    (project / "Packages").mkdir(parents=True, exist_ok=True)
    (project / "ProjectSettings").mkdir(parents=True, exist_ok=True)
    (project / "Assets" / "RuntimeSmoke" / "NozzleUnityRuntimeSmoke.cs").write_text(PLAYER_SCRIPT, encoding="utf-8")
    (project / "Assets" / "RuntimeSmoke" / "Nozzle.UnityRuntimeSmoke.asmdef").write_text(json.dumps(RUNTIME_SMOKE_ASMDEF, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (project / "Assets" / "Editor" / "NozzleUnityRuntimeSmokeBuilder.cs").write_text(EDITOR_SCRIPT, encoding="utf-8")
    manifest = {
        "dependencies": {
            PACKAGE_NAME: dependency,
            "com.unity.modules.imgui": "1.0.0",
            "com.unity.modules.jsonserialize": "1.0.0",
            "com.unity.modules.physics": "1.0.0",
        }
    }
    (project / "Packages" / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (project / "ProjectSettings" / "ProjectVersion.txt").write_text(f"m_EditorVersion: {editor_version}\n", encoding="utf-8")
    return project / "Build" / "NozzleUnityRuntimeSmoke.app"


def unity_version(unity: Path) -> str:
    result = run([str(unity), "-batchmode", "-quit", "-version"])
    for line in result.stdout.splitlines():
        if any(ch.isdigit() for ch in line):
            return line.strip()
    return "unknown"


def build_player(unity: Path, project: Path, build_path: Path) -> None:
    log_path = project / "Logs" / "Build.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    run([
        str(unity), "-batchmode", "-quit", "-force-metal",
        "-projectPath", str(project),
        "-logFile", str(log_path),
        "-executeMethod", "Nozzle.UnityRuntimeSmoke.Editor.NozzleUnityRuntimeSmokeBuilder.Build",
        "-nozzleSmokeBuildTarget", "StandaloneOSX",
        "-nozzleSmokeBuildPath", str(build_path),
    ], log_path=log_path, timeout=900)


def player_executable(app: Path) -> Path:
    exe = app / "Contents" / "MacOS" / app.stem
    if exe.is_file():
        return exe
    candidates = list((app / "Contents" / "MacOS").glob("*"))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    fail(f"Player executable not found under {app}")
    return exe


def wait_for_file(path: Path, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file():
            return
        time.sleep(0.1)
    fail(f"timed out waiting for {path}")


def run_sender_case(player: Path, tester_cli: Path, evidence_dir: Path, width: int, height: int) -> dict[str, Any]:
    name = f"unity_sender_{uuid.uuid4().hex[:10]}_{width}x{height}"
    sender_report = evidence_dir / f"sender-player-{width}x{height}.json"
    sender_ready = evidence_dir / f"sender-player-{width}x{height}.ready"
    receiver_evidence = evidence_dir / f"receiver-cli-{width}x{height}.json"
    proc = subprocess.Popen([
        str(player), "-batchmode", "-force-metal",
        "-nozzleSmokeMode", "sender",
        "-nozzleSmokeName", name,
        "-nozzleSmokeWidth", str(width),
        "-nozzleSmokeHeight", str(height),
        "-nozzleSmokeFrames", "1",
        "-nozzleSmokeReport", str(sender_report),
        "-nozzleSmokeReady", str(sender_ready),
        "-nozzleSmokeMaxFrames", "3600",
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        wait_for_file(sender_ready, 20.0)
        result = run([
            str(tester_cli), "receiver",
            "--name", name,
            "--width", str(width),
            "--height", str(height),
            "--format", "rgba8_unorm",
            "--frames", "1",
            "--timeout-ms", "10000",
            "--evidence", str(receiver_evidence),
        ], timeout=20)
        return {
            "case": "unity_sender_to_nozzle_tester_receiver",
            "width": width,
            "height": height,
            "sender_name": name,
            "sender_ready": str(sender_ready),
            "receiver_evidence": str(receiver_evidence),
            "receiver_returncode": result.returncode,
        }
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                out, _ = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, _ = proc.communicate(timeout=5)
        else:
            out, _ = proc.communicate(timeout=5)
        if out:
            (evidence_dir / f"sender-player-{width}x{height}.log").write_text(out, encoding="utf-8")


def run_receiver_case(player: Path, tester_cli: Path, evidence_dir: Path, width: int, height: int) -> dict[str, Any]:
    name = f"tester_sender_{uuid.uuid4().hex[:10]}_{width}x{height}"
    sender_evidence = evidence_dir / f"sender-cli-{width}x{height}.json"
    receiver_report = evidence_dir / f"receiver-player-{width}x{height}.json"
    receiver_raw = evidence_dir / f"receiver-player-{width}x{height}.rgba"
    sender = subprocess.Popen([
        str(tester_cli), "sender",
        "--name", name,
        "--width", str(width),
        "--height", str(height),
        "--format", "rgba8_unorm",
        "--frames", "600",
        "--delay-ms", "16",
        "--hold-ms", "0",
        "--evidence", str(sender_evidence),
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        time.sleep(2.0)
        result = run([
            str(player), "-batchmode", "-force-metal",
            "-nozzleSmokeMode", "receiver",
            "-nozzleSmokeName", name,
            "-nozzleSmokeWidth", str(width),
            "-nozzleSmokeHeight", str(height),
            "-nozzleSmokeFrames", "1",
            "-nozzleSmokeReport", str(receiver_report),
            "-nozzleSmokeRaw", str(receiver_raw),
            "-nozzleSmokeMaxFrames", "900",
        ], timeout=60)
        report = json.loads(receiver_report.read_text(encoding="utf-8")) if receiver_report.is_file() else {}
        return {
            "case": "nozzle_tester_sender_to_unity_receiver",
            "width": width,
            "height": height,
            "sender_name": name,
            "sender_evidence": str(sender_evidence),
            "receiver_report": str(receiver_report),
            "receiver_raw": str(receiver_raw),
            "receiver_returncode": result.returncode,
            "receiver_result": report.get("result"),
            "receiver_reason": report.get("reason"),
        }
    finally:
        if sender.poll() is None:
            sender.terminate()
            try:
                out, _ = sender.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                sender.kill()
                out, _ = sender.communicate(timeout=5)
        else:
            out, _ = sender.communicate(timeout=5)
        if out:
            (evidence_dir / f"sender-cli-{width}x{height}.log").write_text(out, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unity", type=Path, default=None)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--native-payload", type=Path, required=True)
    parser.add_argument("--tester-cli", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "build" / "unity-runtime-smoke" / "evidence")
    parser.add_argument("--sizes", nargs="*", default=["320x240", "641x479"])
    parser.add_argument("--directions", nargs="*", choices=("receiver", "sender"), default=["receiver"], help="receiver = nozzle-tester sender -> Unity receiver; sender = Unity sender -> nozzle-tester receiver (experimental until sender frame-index synchronization is proven).")
    parser.add_argument("--keep-project", action="store_true")
    args = parser.parse_args()

    if not args.tester_cli.is_file():
        fail(f"nozzle-tester-cli not found: {args.tester_cli}")
    unity = resolve_unity(args.unity, optional=False)
    version = unity_version(unity)
    staged_package = (ROOT / "build" / "unity-runtime-smoke" / "package" / PACKAGE_NAME).resolve()
    copy_package_source(SOURCE_PACKAGE_ROOT, staged_package)
    overlay_native_payload(staged_package, resolve_payload_dir(args.native_payload, "macos"), PLATFORMS["macos"].plugin_relative_path)
    manifest = package_manifest(staged_package)
    if manifest.get("name") != PACKAGE_NAME:
        fail(f"staged package name mismatch: {manifest.get('name')!r}")

    project = args.project.resolve()
    build_path = write_project(project, f"file:{staged_package.as_posix()}", version)
    build_player(unity, project, build_path)
    player = player_executable(build_path)

    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for size in args.sizes:
        if "x" not in size:
            fail(f"invalid size {size!r}; expected WIDTHxHEIGHT")
        width_s, height_s = size.split("x", 1)
        width = int(width_s)
        height = int(height_s)
        if "sender" in args.directions:
            results.append(run_sender_case(player, args.tester_cli.resolve(), args.evidence_dir, width, height))
        if "receiver" in args.directions:
            results.append(run_receiver_case(player, args.tester_cli.resolve(), args.evidence_dir, width, height))

    summary = {
        "result": "pass",
        "repo_sha": current_git_sha(ROOT),
        "nozzle_sha": current_git_sha(ROOT / "nozzle"),
        "unity_editor": str(unity),
        "unity_version": version,
        "player": str(player),
        "staged_package": str(staged_package),
        "native_payload": str(args.native_payload.resolve()),
        "tester_cli": str(args.tester_cli.resolve()),
        "directions": args.directions,
        "results": results,
    }
    summary_path = args.evidence_dir / "unity-runtime-smoke-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("NOZZLE_UNITY_RUNTIME_SMOKE_SUMMARY " + json.dumps(summary, sort_keys=True))
    if not args.keep_project:
        pass


if __name__ == "__main__":
    main()
