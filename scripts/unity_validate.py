#!/usr/bin/env python3
"""Validate nozzle.unity with a real Unity Editor import and Player build."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from unity_release_contract import PACKAGE_NAME, PACKAGE_ROOT_RELATIVE, PLATFORMS, current_git_sha, fail

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE_ROOT = ROOT / PACKAGE_ROOT_RELATIVE
DEFAULT_PROJECT_ROOT = ROOT / "build" / "unity-validation" / "project"
DEFAULT_STAGED_PACKAGE_ROOT = ROOT / "build" / "unity-validation" / "package" / PACKAGE_NAME

TARGETS = {
    "macos": {
        "contract": "macos",
        "build_target": "StandaloneOSX",
        "build_name": "NozzleUnityValidation.app",
        "host_system": "Darwin",
    },
    "windows-x86_64": {
        "contract": "windows-x86_64",
        "build_target": "StandaloneWindows64",
        "build_name": "NozzleUnityValidation.exe",
        "host_system": "Windows",
    },
}

EDITOR_SCRIPT = r'''
using System;
using System.Collections.Generic;
using System.IO;
using Nozzle;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEditor.PackageManager;
using UnityEditor.PackageManager.UI;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace Nozzle.UnityValidation
{
    public static class NozzleUnityValidation
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

        static void Require(bool condition, string message)
        {
            if (!condition) throw new Exception(message);
        }

        static string JsonString(string value)
        {
            return "\"" + (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r") + "\"";
        }

        static void WriteReport(string path, IDictionary<string, string> values)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            using (var writer = new StreamWriter(path, false))
            {
                writer.WriteLine("{");
                int index = 0;
                foreach (var pair in values)
                {
                    string comma = index + 1 == values.Count ? "" : ",";
                    writer.WriteLine("  " + JsonString(pair.Key) + ": " + JsonString(pair.Value) + comma);
                    index++;
                }
                writer.WriteLine("}");
            }
        }

        static string ImportSamples(PackageInfo packageInfo)
        {
            Sample[] samples = Sample.FindByPackage(packageInfo.name, packageInfo.version);
            Require(samples != null && samples.Length >= 3, "expected at least three package samples");
            List<string> imported = new List<string>();
            foreach (Sample sample in samples)
            {
                bool ok = sample.Import(Sample.ImportOptions.OverridePreviousImports);
                Require(ok, "failed to import sample: " + sample.displayName);
                string importedPath = sample.importedPath.Replace('\\', '/');
                Require(!String.IsNullOrEmpty(importedPath), "sample imported path is empty: " + sample.displayName);
                Require(Directory.Exists(importedPath), "sample imported directory is missing: " + importedPath);
                imported.Add(sample.displayName + "=>" + importedPath);
            }
            return String.Join(";", imported.ToArray());
        }

        public static void ValidateAndBuild()
        {
            string buildTargetName = Arg("-nozzleValidationBuildTarget", "StandaloneOSX");
            string buildPath = Arg("-nozzleValidationBuildPath", "Build/NozzleUnityValidation.app");
            string reportPath = Arg("-nozzleValidationReport", "Logs/nozzle-unity-validation.json");
            string expectedPluginPath = Arg("-nozzleValidationExpectedPlugin", "").Replace('\\', '/');
            string validationScope = Arg("-nozzleValidationScope", "player");

            BuildTarget buildTarget = (BuildTarget)Enum.Parse(typeof(BuildTarget), buildTargetName);
            PackageInfo packageInfo = PackageInfo.FindForAssetPath("Packages/org.nozzle-io.unity/package.json");
            Require(packageInfo != null, "org.nozzle-io.unity package was not imported by Unity Package Manager");
            Require(packageInfo.name == "org.nozzle-io.unity", "imported package name mismatch: " + packageInfo.name);
            string importedSamples = ImportSamples(packageInfo);

            Type supportType = typeof(NozzleRuntimeSupport);
            Require(supportType.FullName == "Nozzle.NozzleRuntimeSupport", "Nozzle runtime assembly did not compile to the expected type");
            Require(NozzleRuntimeSupport.IsTargetGraphicsApi(GraphicsDeviceType.Metal), "Metal must be an explicitly recognized target graphics API");
            Require(NozzleRuntimeSupport.IsTargetGraphicsApi(GraphicsDeviceType.Direct3D11), "D3D11 must be an explicitly recognized target graphics API");
            Require(!NozzleRuntimeSupport.IsTargetGraphicsApi(GraphicsDeviceType.OpenGLES3), "OpenGLES3 must remain an explicit unsupported graphics API");
            Require(NozzleRuntimeSupport.GetRuntimeLimitations().Contains("no verified Unity Editor/Player runtime support"), "runtime limitations must stay explicit");

            if (validationScope == "import")
            {
                WriteReport(reportPath, new Dictionary<string, string>
                {
                    {"unity_version", Application.unityVersion},
                    {"package_name", packageInfo.name},
                    {"package_version", packageInfo.version},
                    {"package_asset_path", packageInfo.assetPath},
                    {"imported_samples", importedSamples},
                    {"validation_scope", validationScope},
                    {"runtime_supported", "not_checked_import_scope"},
                });
                Debug.Log("NOZZLE_UNITY_VALIDATION_PASS package=" + packageInfo.name + " unity=" + Application.unityVersion + " scope=" + validationScope);
                return;
            }

            NozzleRuntimeSupport.BridgeSupport support;
            bool supportCallOk = NozzleRuntimeSupport.TryGetBridgeSupport(out support);
            Require(supportCallOk, "nozzle_unity_get_support must be callable when native payload is installed: " + support.StatusMessage);
            Require(support.BridgeBinaryLoaded, "native bridge binary did not report loaded=true");
            Require(!support.RuntimeSupported, "#132 validation must not claim runtime support");
            Require(!String.IsNullOrEmpty(support.StatusMessage), "native bridge support diagnostics must include a status message");

            Require(!String.IsNullOrEmpty(expectedPluginPath), "expected native plugin path argument is required");
            PluginImporter importer = AssetImporter.GetAtPath(expectedPluginPath) as PluginImporter;
            Require(importer != null, "expected native plugin is not imported as PluginImporter: " + expectedPluginPath);
            Require(importer.GetCompatibleWithEditor(), "native plugin is not enabled for Editor: " + expectedPluginPath);
            Require(importer.GetCompatibleWithPlatform(buildTarget), "native plugin is not enabled for Player target " + buildTarget + ": " + expectedPluginPath);

            Directory.CreateDirectory("Assets/Validation");
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameObject marker = new GameObject("NozzleValidationMarker");
            marker.transform.position = Vector3.zero;
            string scenePath = "Assets/Validation/NozzleValidationScene.unity";
            EditorSceneManager.SaveScene(scene, scenePath);

            Directory.CreateDirectory(Path.GetDirectoryName(buildPath));
            BuildPlayerOptions options = new BuildPlayerOptions
            {
                scenes = new[] { scenePath },
                locationPathName = buildPath,
                target = buildTarget,
                options = BuildOptions.None,
            };
            BuildReport report = BuildPipeline.BuildPlayer(options);
            Require(report.summary.result == BuildResult.Succeeded, "Player build failed: " + report.summary.result);

            WriteReport(reportPath, new Dictionary<string, string>
            {
                {"unity_version", Application.unityVersion},
                {"package_name", packageInfo.name},
                {"package_version", packageInfo.version},
                {"package_asset_path", packageInfo.assetPath},
                {"imported_samples", importedSamples},
                {"validation_scope", validationScope},
                {"build_target", buildTarget.ToString()},
                {"build_path", buildPath},
                {"expected_plugin_path", expectedPluginPath},
                {"bridge_binary_loaded", support.BridgeBinaryLoaded.ToString()},
                {"runtime_supported", support.RuntimeSupported.ToString()},
                {"support_status", support.StatusMessage},
            });

            Debug.Log("NOZZLE_UNITY_VALIDATION_PASS package=" + packageInfo.name + " unity=" + Application.unityVersion + " build=" + buildPath + " plugin=" + expectedPluginPath);
        }
    }
}
'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unity", "--unity-editor", dest="unity", type=Path, default=None, help="Path to Unity executable. Defaults to UNITY_EDITOR/UNITY_EDITOR_PATH or known install paths.")
    parser.add_argument("--target", choices=sorted(TARGETS), default="macos")
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--package-source", choices=("file", "git", "tgz"), default="file", help="UPM dependency source to validate.")
    parser.add_argument("--validation-scope", choices=("import", "player"), default="player", help="import checks UPM import/compile/sample import only; player also requires native plugin diagnostics, Player build, and plugin inclusion.")
    parser.add_argument("--package-root", type=Path, default=SOURCE_PACKAGE_ROOT, help="Source package root to stage for --package-source file.")
    parser.add_argument("--staged-package", type=Path, default=DEFAULT_STAGED_PACKAGE_ROOT)
    parser.add_argument("--native-payload", type=Path, default=None, help="Optional native-payload/<platform> directory or native-payload root to overlay into the staged package for --package-source file.")
    parser.add_argument("--git-url", default="https://github.com/nozzle-io/nozzle.unity.git?path=/Packages/org.nozzle-io.unity", help="UPM Git URL used by --package-source git.")
    parser.add_argument("--tgz", type=Path, default=None, help="UPM .tgz package used by --package-source tgz.")
    parser.add_argument("--keep-project", action="store_true")
    parser.add_argument("--optional", action="store_true", help="Print PENDING and exit 0 instead of failing when Unity is unavailable.")
    return parser.parse_args()


def known_unity_paths() -> list[Path]:
    candidates: list[Path] = []
    for key in ("UNITY_EDITOR", "UNITY_EDITOR_PATH"):
        value = os.environ.get(key)
        if value:
            candidates.append(Path(value))
    system = platform.system()
    if system == "Darwin":
        candidates.extend(sorted(Path("/Applications/Unity/Hub/Editor").glob("*/Unity.app/Contents/MacOS/Unity"), reverse=True))
        candidates.append(Path("/Applications/Unity/Unity.app/Contents/MacOS/Unity"))
    elif system == "Windows":
        program_files = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
        for root in program_files:
            if root:
                candidates.extend(sorted(Path(root).glob("Unity/Hub/Editor/*/Editor/Unity.exe"), reverse=True))
    else:
        found = shutil.which("unity-editor") or shutil.which("Unity")
        if found:
            candidates.append(Path(found))
    return candidates


def resolve_unity(explicit: Path | None, optional: bool) -> Path:
    candidates = [explicit] if explicit else known_unity_paths()
    for candidate in candidates:
        if candidate and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    message = "Unity Editor executable not found; set UNITY_EDITOR or pass --unity"
    if optional:
        print(f"PENDING: {message}")
        raise SystemExit(0)
    fail(message)


def run(command: list[str], cwd: Path | None = None, log_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("$ " + " ".join(str(part) for part in command))
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        if log_path:
            print(f"Unity log path: {log_path}")
            if log_path.is_file():
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
                print("--- Unity log tail ---")
                print("\n".join(lines))
                print("--- end Unity log tail ---")
        fail(f"command failed with exit code {result.returncode}: {' '.join(str(part) for part in command)}")
    return result


def unity_version(unity: Path) -> str:
    result = run([str(unity), "-batchmode", "-quit", "-version"])
    for line in result.stdout.splitlines():
        line = line.strip()
        if line and any(char.isdigit() for char in line):
            return line
    return "unknown"


def copy_package_source(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    def ignore(_dir: str, names: list[str]) -> set[str]:
        return {name for name in names if name in {".git", "Library", "Temp", "Obj", "Logs", "Runtime/Plugins", "__pycache__"}}
    shutil.copytree(source, destination, ignore=ignore)
    plugins = destination / "Runtime" / "Plugins"
    if plugins.exists():
        shutil.rmtree(plugins)


def resolve_payload_dir(payload: Path, platform_key: str) -> Path:
    payload = payload.resolve()
    if (payload / platform_key).is_dir():
        return payload / platform_key
    if (payload / "native-payload" / platform_key).is_dir():
        return payload / "native-payload" / platform_key
    if payload.name == platform_key and payload.is_dir():
        return payload
    fail(f"native payload for {platform_key} not found under {payload}")


def overlay_native_payload(staged_package: Path, payload_dir: Path, expected_plugin: Path) -> None:
    if not (payload_dir / expected_plugin).is_file():
        fail(f"native payload is missing expected plugin: {payload_dir / expected_plugin}")
    for path in payload_dir.rglob("*"):
        if path.is_file():
            relative = path.relative_to(payload_dir)
            destination = staged_package / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def write_project(project: Path, package_dependency: str, target: dict[str, str], editor_version: str) -> tuple[Path, Path]:
    if project.exists():
        shutil.rmtree(project)
    (project / "Assets" / "Editor").mkdir(parents=True, exist_ok=True)
    (project / "Packages").mkdir(parents=True, exist_ok=True)
    (project / "ProjectSettings").mkdir(parents=True, exist_ok=True)
    (project / "Assets" / "Editor" / "NozzleUnityValidation.cs").write_text(EDITOR_SCRIPT, encoding="utf-8")
    manifest = {
        "dependencies": {
            PACKAGE_NAME: package_dependency,
            "com.unity.modules.imgui": "1.0.0",
            "com.unity.modules.jsonserialize": "1.0.0",
            "com.unity.modules.physics": "1.0.0",
        }
    }
    (project / "Packages" / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (project / "ProjectSettings" / "ProjectVersion.txt").write_text(f"m_EditorVersion: {editor_version}\n", encoding="utf-8")
    build_path = project / "Build" / target["build_name"]
    report_path = project / "Logs" / "nozzle-unity-validation.json"
    return build_path, report_path


def package_dependency(args: argparse.Namespace, contract_key: str) -> tuple[str, Path | None]:
    if args.package_source == "file":
        staged_package = args.staged_package.resolve()
        copy_package_source(args.package_root.resolve(), staged_package)
        if args.native_payload:
            overlay_native_payload(staged_package, resolve_payload_dir(args.native_payload, contract_key), PLATFORMS[contract_key].plugin_relative_path)
        return f"file:{staged_package.as_posix()}", staged_package
    if args.package_source == "git":
        if "?path=/Packages/org.nozzle-io.unity" not in args.git_url:
            fail("--git-url must include ?path=/Packages/org.nozzle-io.unity for UPM package-path validation")
        return args.git_url, None
    if args.package_source == "tgz":
        if not args.tgz:
            fail("--package-source tgz requires --tgz")
        tgz = args.tgz.resolve()
        if not tgz.is_file():
            fail(f"UPM tgz is missing: {tgz}")
        return f"file:{tgz.as_posix()}", tgz
    fail(f"unsupported package source: {args.package_source}")
    return "", None


def find_plugin_in_player(build_path: Path, plugin_name: str) -> list[str]:
    if build_path.is_file() and build_path.name == plugin_name:
        return [build_path.name]
    root = build_path if build_path.is_dir() else build_path.parent
    matches = sorted(path.relative_to(root).as_posix() for path in root.rglob(plugin_name)) if root.exists() else []
    return matches


def main() -> None:
    args = parse_args()
    target = TARGETS[args.target]
    contract = PLATFORMS[target["contract"]]
    if platform.system() != target["host_system"]:
        fail(f"target {args.target} requires host {target['host_system']}, current host is {platform.system()}")

    dependency, package_evidence_path = package_dependency(args, contract.key)
    if args.validation_scope == "player" and args.package_source == "file":
        expected_plugin = Path(package_evidence_path) / contract.plugin_relative_path
        if not expected_plugin.is_file():
            fail(f"expected native plugin is absent from staged package: {expected_plugin}. Build/create a native payload and pass --native-payload.")
    if args.validation_scope == "player" and args.package_source == "git":
        fail("--package-source git is source-only in this repository; use --validation-scope import, or validate Player/native plugin inclusion with --package-source file or tgz")

    unity = resolve_unity(args.unity, args.optional)
    version = unity_version(unity)
    project = args.project.resolve()
    build_path, report_path = write_project(project, dependency, target, version)
    log_path = project / "Logs" / "Editor.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        str(unity),
        "-batchmode",
        "-quit",
        "-nographics",
        "-projectPath", str(project),
        "-logFile", str(log_path),
        "-executeMethod", "Nozzle.UnityValidation.NozzleUnityValidation.ValidateAndBuild",
        "-nozzleValidationBuildTarget", target["build_target"],
        "-nozzleValidationBuildPath", str(build_path),
        "-nozzleValidationReport", str(report_path),
        "-nozzleValidationExpectedPlugin", f"Packages/{PACKAGE_NAME}/{contract.plugin_relative_path.as_posix()}",
        "-nozzleValidationScope", args.validation_scope,
    ]
    run(command, log_path=log_path)
    if not report_path.is_file():
        fail(f"Unity validation report was not written: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    matches = []
    if args.validation_scope == "player":
        matches = find_plugin_in_player(build_path, contract.plugin_relative_path.name)
        if not matches:
            fail(f"Player build output does not include {contract.plugin_relative_path.name} under {build_path}")

    result: dict[str, Any] = {
        "result": "pass",
        "unity_editor": str(unity),
        "unity_version": version,
        "target": args.target,
        "package_sha": current_git_sha(ROOT),
        "nozzle_sha": current_git_sha(ROOT / "nozzle"),
        "project_path": str(project),
        "package_source": args.package_source,
        "validation_scope": args.validation_scope,
        "package_dependency": dependency,
        "package_evidence_path": str(package_evidence_path) if package_evidence_path else "",
        "build_output": str(build_path),
        "editor_log": str(log_path),
        "unity_report": str(report_path),
        "native_plugin_matches": matches,
        "unity_report_fields": report,
    }
    print("NOZZLE_UNITY_VALIDATION_RESULT " + json.dumps(result, sort_keys=True))
    if args.keep_project:
        print(f"validation project retained for evidence: {project}")


if __name__ == "__main__":
    main()
