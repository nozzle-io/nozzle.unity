#!/usr/bin/env python3
"""Project sanity checks for the nozzle Unity package.

This is intentionally not a Unity Editor build. It validates the package,
assembly definition, native P/Invoke boundary, and recursive submodule state.
"""

from __future__ import annotations

import json
import argparse
import ctypes
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "Packages" / "org.nozzle-io.unity"
RUNTIME_ROOT = PACKAGE_ROOT / "Runtime"
NATIVE_SOURCE_ROOT = PACKAGE_ROOT / "Native~"
DOCUMENTATION_ROOT = PACKAGE_ROOT / "Documentation~"
SAMPLES_ROOT = PACKAGE_ROOT / "Samples~"
NATIVE_LIBRARY_SUFFIXES = {".dll", ".dylib", ".so"}
VALIDATION_ASMDEF_NAME = "Nozzle.UnityValidation.Editor.asmdef"
VALIDATION_ASMDEF_EXPECTED = {
    "name": "Nozzle.UnityValidation.Editor",
    "references": ["Nozzle.Unity"],
    "includePlatforms": ["Editor"],
}
REQUIRED_UNITY_PACKAGE_META_IMPORTERS = {
    "Runtime.meta": "DefaultImporter:",
    "Runtime/Native.meta": "DefaultImporter:",
    "Runtime/Nozzle.Unity.asmdef.meta": "AssemblyDefinitionImporter:",
    "Runtime/Native/NozzleNative.cs.meta": "MonoImporter:",
    "Runtime/NozzleTypes.cs.meta": "MonoImporter:",
    "Runtime/NozzleSender.cs.meta": "MonoImporter:",
    "Runtime/NozzleReceiver.cs.meta": "MonoImporter:",
    "Runtime/NozzleDiscovery.cs.meta": "MonoImporter:",
    "Runtime/NozzleRenderThreadDispatch.cs.meta": "MonoImporter:",
    "Runtime/NozzleRuntimeSupport.cs.meta": "MonoImporter:",
}



def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def require_file(path: Path) -> None:
    if not path.is_file():
        fail(f"required file is missing: {path.relative_to(ROOT)}")


def require_dir(path: Path) -> None:
    if not path.is_dir():
        fail(f"required directory is missing: {path.relative_to(ROOT)}")


def require_meta(path: Path) -> None:
    meta = Path(f"{path}.meta")
    require_file(meta)


def load_json(path: Path) -> dict:
    require_file(path)
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {error}")
    if not isinstance(data, dict):
        fail(f"JSON root must be an object: {path.relative_to(ROOT)}")
    return data


def expect_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        fail(f"{label} must be {expected!r}, got {actual!r}")


def expect_present(value: object, label: str) -> None:
    if value in (None, ""):
        fail(f"{label} must be present")


def require_text(path: Path, needle: str, label: str | None = None) -> None:
    require_file(path)
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        fail(f"{path.relative_to(ROOT)} must contain {label or needle!r}")


def extract_method_body(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        fail(f"method signature is missing: {signature}")
    brace_start = text.find("{", start)
    if brace_start < 0:
        fail(f"method body is missing for: {signature}")
    depth = 0
    for index in range(brace_start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace_start + 1:index]
    fail(f"method body is unterminated for: {signature}")
    return ""


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def check_package_manifest() -> None:
    manifest = load_json(PACKAGE_ROOT / "package.json")
    expect_equal(manifest.get("name"), "org.nozzle-io.unity", "package name")
    expect_present(manifest.get("unity"), "package unity minimum version")
    expect_present(manifest.get("license"), "package license")

    repository = manifest.get("repository")
    if not isinstance(repository, dict):
        fail("package repository must be an object")
    repository_url = repository.get("url")
    if not isinstance(repository_url, str) or "nozzle-io/nozzle.unity" not in repository_url:
        fail("package repository.url must reference nozzle-io/nozzle.unity")

    samples = manifest.get("samples")
    if not isinstance(samples, list) or len(samples) < 3:
        fail("package samples must list the current UPM sample stubs")
    sample_paths = {sample.get("path") for sample in samples if isinstance(sample, dict)}
    expected_sample_paths = {
        "Samples~/SenderSample",
        "Samples~/ReceiverSample",
        "Samples~/DiscoveryDiagnostics",
    }
    if sample_paths != expected_sample_paths:
        fail(f"package samples paths must be {sorted(expected_sample_paths)!r}, got {sorted(sample_paths)!r}")


def check_asmdef() -> None:
    asmdef = load_json(RUNTIME_ROOT / "Nozzle.Unity.asmdef")
    expect_equal(asmdef.get("name"), "Nozzle.Unity", "asmdef name")
    expect_equal(asmdef.get("rootNamespace"), "Nozzle", "asmdef rootNamespace")
    expect_equal(asmdef.get("allowUnsafeCode"), True, "asmdef allowUnsafeCode")


def check_unity_package_meta_contract() -> None:
    seen_guids: dict[str, str] = {}
    for rel, importer in REQUIRED_UNITY_PACKAGE_META_IMPORTERS.items():
        meta_path = PACKAGE_ROOT / rel
        require_file(meta_path)
        text = meta_path.read_text(encoding="utf-8")
        if importer not in text:
            fail(f"{rel} must use {importer.rstrip(':')} metadata")
        if rel in {"Runtime.meta", "Runtime/Native.meta"} and "folderAsset: yes" not in text:
            fail(f"{rel} must contain folderAsset: yes")
        guid_line = next((line for line in text.splitlines() if line.startswith("guid: ")), "")
        guid = guid_line.removeprefix("guid: ")
        if len(guid) != 32 or any(char not in "0123456789abcdef" for char in guid):
            fail(f"{rel} must contain a stable 32-hex guid")
        if guid in seen_guids:
            fail(f"Unity .meta guid collision: {rel} and {seen_guids[guid]} both use {guid}")
        seen_guids[guid] = rel


def check_runtime_sources() -> None:
    required_runtime_files = [
        RUNTIME_ROOT / "NozzleTypes.cs",
        RUNTIME_ROOT / "NozzleSender.cs",
        RUNTIME_ROOT / "NozzleReceiver.cs",
        RUNTIME_ROOT / "NozzleDiscovery.cs",
        RUNTIME_ROOT / "NozzleRuntimeSupport.cs",
        RUNTIME_ROOT / "NozzleRenderThreadDispatch.cs",
        RUNTIME_ROOT / "Native" / "NozzleNative.cs",
    ]
    for path in required_runtime_files:
        require_file(path)

    runtime_sources = sorted(RUNTIME_ROOT.rglob("*.cs"))
    if not runtime_sources:
        fail(f"no runtime C# files found under {RUNTIME_ROOT.relative_to(ROOT)}")

    for path in runtime_sources:
        require_text(path, "namespace Nozzle")

    native = RUNTIME_ROOT / "Native" / "NozzleNative.cs"
    native_text = native.read_text(encoding="utf-8")
    require_text(native, 'const string LIBRARY = "nozzle_unity"')
    require_text(native, "[DllImport(LIBRARY)]")
    if 'const string LIBRARY = "nozzle"' in native_text:
        fail("NozzleNative.cs must not bind directly to DllImport(\"nozzle\")")

    forbidden_direct_symbols = [
        "nozzle_sender_create",
        "nozzle_receiver_create",
        "nozzle_frame_get_info",
        "nozzle_frame_copy_to_native_texture",
        "nozzle_enumerate_senders",
    ]
    for symbol in forbidden_direct_symbols:
        if symbol in native_text and f"nozzle_unity_{symbol.removeprefix('nozzle_')}" not in native_text:
            fail(f"NozzleNative.cs must route through nozzle_unity bridge, found stale direct symbol {symbol}")

    required_bridge_symbols = [
        "nozzle_unity_get_support",
        "nozzle_unity_get_render_event_func",
        "nozzle_unity_sender_create",
        "nozzle_unity_sender_publish_native_texture",
        "nozzle_unity_sender_enqueue_publish_native_texture",
        "nozzle_unity_sender_cancel_operations",
        "nozzle_unity_receiver_create",
        "nozzle_unity_receiver_acquire_frame",
        "nozzle_unity_frame_get_info",
        "nozzle_unity_frame_copy_to_native_texture",
        "nozzle_unity_receiver_enqueue_acquire_and_copy_native_texture",
        "nozzle_unity_receiver_cancel_operations",
        "nozzle_unity_operation_get_status",
        "nozzle_unity_operation_release",
        "nozzle_unity_queue_get_diagnostics",
        "nozzle_unity_discovery_enumerate_senders",
    ]
    for symbol in required_bridge_symbols:
        require_text(native, symbol, f"bridge symbol {symbol}")

    support = RUNTIME_ROOT / "NozzleRuntimeSupport.cs"
    require_text(support, "BundledNativePlugin = false")
    require_text(support, "UnityNativeBridgeSource = true")
    require_text(support, "UnityRuntimeVerified = false")
    require_text(support, "RequireBridgeRuntime")
    require_text(support, "runtime support")

    dispatch = RUNTIME_ROOT / "NozzleRenderThreadDispatch.cs"
    require_text(dispatch, "ManagedNativeTextureOperationsImplemented = true")
    require_text(dispatch, "GL.IssuePluginEvent")
    require_text(dispatch, "CommandBuffer.IssuePluginEvent")
    require_text(dispatch, "nozzle_unity_get_render_event_func")
    require_text(dispatch, "PendingOperation")
    require_text(dispatch, "StrongTextureReference")
    require_text(dispatch, "TryEnqueueSenderPublish")
    require_text(dispatch, "TryEnqueueReceiverAcquireAndCopy")
    require_text(dispatch, "nozzle_unity_sender_enqueue_publish_native_texture")
    require_text(dispatch, "nozzle_unity_receiver_enqueue_acquire_and_copy_native_texture")
    require_text(dispatch, "nozzle_unity_operation_get_status")
    require_text(dispatch, "nozzle_unity_operation_release")
    require_text(dispatch, "nozzle_unity_sender_cancel_operations")
    require_text(dispatch, "nozzle_unity_receiver_cancel_operations")
    require_text(dispatch, "STATUS_BUSY")
    require_text(dispatch, "release deferred")
    require_text(dispatch, "RegisterDeferredSenderDestroy")
    require_text(dispatch, "RegisterDeferredReceiverDestroy")
    require_text(dispatch, "NozzleDeferredCleanupHost")
    require_text(dispatch, "DrainDeferredDestroys")
    require_text(dispatch, "deferredDestroys")
    require_text(dispatch, "DestroyDeferredHandle")
    require_text(dispatch, "DontDestroyOnLoad")
    require_text(dispatch, "DestroyedCallback")

    for component in [
        RUNTIME_ROOT / "NozzleSender.cs",
        RUNTIME_ROOT / "NozzleReceiver.cs",
        RUNTIME_ROOT / "NozzleDiscovery.cs",
    ]:
        require_text(component, "RequireBridgeRuntime")
        text = component.read_text(encoding="utf-8")
        if "WarnExperimentalRuntime" in text:
            fail(f"{component.relative_to(ROOT)} still uses stale direct-runtime warning path")

    for component in [
        RUNTIME_ROOT / "NozzleSender.cs",
        RUNTIME_ROOT / "NozzleReceiver.cs",
    ]:
        require_text(component, "RequireNativeTextureOperationDispatch")

    sender_text = (RUNTIME_ROOT / "NozzleSender.cs").read_text(encoding="utf-8")
    sender_update = extract_method_body(sender_text, "void Update()")
    if "nozzle_unity_sender_publish_native_texture" in sender_update:
        fail("NozzleSender.Update must enqueue render-thread operations, not call publish_native_texture directly")
    if "TryEnqueueSenderPublish" not in sender_update:
        fail("NozzleSender.Update must enqueue sender publish operations")
    sender_disable = extract_method_body(sender_text, "void OnDisable()")
    sender_enable = extract_method_body(sender_text, "void OnEnable()")
    if "deferredDestroyPending" not in sender_text or "reinitializeAfterDeferredDestroy" not in sender_text:
        fail("NozzleSender must track deferred teardown state separately from initialized")
    if "deferredDestroyPending" not in sender_enable or "reinitializeAfterDeferredDestroy = true" not in sender_enable:
        fail("NozzleSender.OnEnable must defer fresh native create while prior handle teardown is pending")
    if "InitializeNativeSender()" not in sender_enable:
        fail("NozzleSender.OnEnable must funnel native creation through an explicit initializer")
    if "RegisterDeferredSenderDestroy(handle, ref pendingPublish, OnDeferredDestroyComplete)" not in sender_disable:
        fail("NozzleSender.OnDisable must hand busy destroy cleanup to the static deferred cleanup owner")
    if "handle = null;" not in sender_disable or "initialized = false;" not in sender_disable:
        fail("NozzleSender.OnDisable must detach disabled components from deferred native handles")
    if "deferredDestroyPending = true" not in sender_disable:
        fail("NozzleSender.OnDisable must mark deferred teardown before detaching the native handle")
    sender_deferred_complete = extract_method_body(sender_text, "void OnDeferredDestroyComplete()")
    if "deferredDestroyPending = false" not in sender_deferred_complete:
        fail("NozzleSender deferred cleanup completion must clear deferredDestroyPending")
    if "InitializeNativeSender()" not in sender_deferred_complete or "isActiveAndEnabled" not in sender_deferred_complete:
        fail("NozzleSender deferred cleanup completion must gate delayed reinitialization on active/enabled state")

    receiver_text = (RUNTIME_ROOT / "NozzleReceiver.cs").read_text(encoding="utf-8")
    receiver_update = extract_method_body(receiver_text, "void Update()")
    forbidden_receiver_update_symbols = [
        "nozzle_unity_receiver_acquire_frame",
        "nozzle_unity_frame_get_info",
        "nozzle_unity_frame_copy_to_native_texture",
        "nozzle_unity_frame_release",
    ]
    for symbol in forbidden_receiver_update_symbols:
        if symbol in receiver_update:
            fail(f"NozzleReceiver.Update must not call blocking/direct native frame symbol {symbol}")
    if "TryEnqueueReceiverAcquireAndCopy" not in receiver_update:
        fail("NozzleReceiver.Update must enqueue receiver acquire/copy operations")
    receiver_disable = extract_method_body(receiver_text, "void OnDisable()")
    receiver_enable = extract_method_body(receiver_text, "void OnEnable()")
    if "deferredDestroyPending" not in receiver_text or "reinitializeAfterDeferredDestroy" not in receiver_text:
        fail("NozzleReceiver must track deferred teardown state separately from initialized")
    if "deferredDestroyPending" not in receiver_enable or "reinitializeAfterDeferredDestroy = true" not in receiver_enable:
        fail("NozzleReceiver.OnEnable must defer fresh native create while prior handle teardown is pending")
    if "InitializeNativeReceiver()" not in receiver_enable:
        fail("NozzleReceiver.OnEnable must funnel native creation through an explicit initializer")
    if "RegisterDeferredReceiverDestroy(handle, ref pendingAcquireCopy, OnDeferredDestroyComplete)" not in receiver_disable:
        fail("NozzleReceiver.OnDisable must hand busy destroy cleanup to the static deferred cleanup owner")
    if "handle = null;" not in receiver_disable or "initialized = false;" not in receiver_disable:
        fail("NozzleReceiver.OnDisable must detach disabled components from deferred native handles")
    if "deferredDestroyPending = true" not in receiver_disable:
        fail("NozzleReceiver.OnDisable must mark deferred teardown before detaching the native handle")
    receiver_deferred_complete = extract_method_body(receiver_text, "void OnDeferredDestroyComplete()")
    if "deferredDestroyPending = false" not in receiver_deferred_complete:
        fail("NozzleReceiver deferred cleanup completion must clear deferredDestroyPending")
    if "InitializeNativeReceiver()" not in receiver_deferred_complete or "isActiveAndEnabled" not in receiver_deferred_complete:
        fail("NozzleReceiver deferred cleanup completion must gate delayed reinitialization on active/enabled state")
    require_text(dispatch, "TimeoutMs = 0", "non-blocking render-thread receiver enqueue")


def check_docs_and_samples() -> None:
    root_readme = ROOT / "README.md"
    package_readme = PACKAGE_ROOT / "README.md"
    for path in [root_readme, package_readme]:
        require_text(path, "?path=/Packages/org.nozzle-io.unity", "package-path Git URL")
        require_text(path, "nozzle_unity", "bridge ABI wording")
        require_text(path, "does not bundle", "no bundled native plugin warning")
        require_text(path, "no Unity Editor/Player runtime support", "runtime support limitation")

    require_text(PACKAGE_ROOT / "CHANGELOG.md", "nozzle_unity")
    require_file(PACKAGE_ROOT / "LICENSE.md")
    require_file(PACKAGE_ROOT / "Third Party Notices.md")

    required_docs = [
        DOCUMENTATION_ROOT / "supported-platforms.md",
        DOCUMENTATION_ROOT / "graphics-api-support.md",
        DOCUMENTATION_ROOT / "troubleshooting.md",
    ]
    require_dir(DOCUMENTATION_ROOT)
    require_meta(DOCUMENTATION_ROOT)
    for path in required_docs:
        require_file(path)
        require_meta(path)
        require_text(path, "native", "native runtime limitation")
        require_text(path, "nozzle_unity", "bridge runtime limitation")

    required_sample_readmes = [
        SAMPLES_ROOT / "SenderSample" / "README.md",
        SAMPLES_ROOT / "ReceiverSample" / "README.md",
        SAMPLES_ROOT / "DiscoveryDiagnostics" / "README.md",
    ]
    require_dir(SAMPLES_ROOT)
    require_meta(SAMPLES_ROOT)
    for path in required_sample_readmes:
        require_file(path)
        require_meta(path)
        require_text(path, "stub")

    plugins_root = RUNTIME_ROOT / "Plugins"
    native_plugins = []
    if plugins_root.exists():
        native_plugins = [
            path
            for path in plugins_root.rglob("*")
            if path.suffix.lower() in NATIVE_LIBRARY_SUFFIXES or path.suffix.lower() == ".bundle"
        ]
    if not native_plugins:
        require_text(package_readme, "No compiled native plugin")
        require_text(DOCUMENTATION_ROOT / "troubleshooting.md", "DllNotFoundException: nozzle_unity")



def check_unity_validate_generated_project_contract() -> None:
    script_path = ROOT / "scripts" / "unity_validate.py"
    namespace: dict[str, object] = {"__file__": str(script_path), "__name__": "__nozzle_unity_validate_contract__"}
    scripts_root = str((ROOT / "scripts").resolve())
    added_path = False
    if scripts_root not in sys.path:
        sys.path.insert(0, scripts_root)
        added_path = True
    try:
        exec(compile(script_path.read_text(encoding="utf-8"), str(script_path), "exec"), namespace)
    finally:
        if added_path:
            sys.path.remove(scripts_root)
    write_project = namespace.get("write_project")
    package_lock_identity = namespace.get("package_lock_identity")
    targets = namespace.get("TARGETS")
    if not callable(write_project) or not callable(package_lock_identity) or not isinstance(targets, dict) or "macos" not in targets:
        fail("unity_validate.py must expose write_project(), package_lock_identity(), and TARGETS for generated-project contract checks")

    with tempfile.TemporaryDirectory(prefix="nozzle-unity-sanity-project-") as tmp:
        project = Path(tmp) / "project"
        write_project(project, "file:/tmp/org.nozzle-io.unity", targets["macos"], "6000.4.11f1")
        validation_script = project / "Assets" / "Editor" / "NozzleUnityValidation.cs"
        validation_asmdef = project / "Assets" / "Editor" / VALIDATION_ASMDEF_NAME
        if not validation_script.is_file():
            fail(f"unity_validate.py must generate Assets/Editor/NozzleUnityValidation.cs, missing {validation_script}")
        if not validation_asmdef.is_file():
            fail(f"unity_validate.py must generate {VALIDATION_ASMDEF_NAME} beside the validation script")
        data = load_json(validation_asmdef)
        for key, expected in VALIDATION_ASMDEF_EXPECTED.items():
            if data.get(key) != expected:
                fail(f"generated {VALIDATION_ASMDEF_NAME} {key} must be {expected!r}, got {data.get(key)!r}")
        if data.get("autoReferenced") is not True:
            fail(f"generated {VALIDATION_ASMDEF_NAME} must remain autoReferenced for Unity executeMethod discovery")
        if "Nozzle.Unity" not in data.get("references", []):
            fail(f"generated {VALIDATION_ASMDEF_NAME} must explicitly reference Nozzle.Unity")

        tgz = Path(tmp) / "org.nozzle-io.unity-test.tgz"
        tgz.write_bytes(b"not-a-real-tgz; package_lock_identity only checks lock metadata")
        lock_dir = project / "Packages"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / "packages-lock.json"
        lock_path.write_text(
            json.dumps(
                {
                    "dependencies": {
                        "org.nozzle-io.unity": {
                            "version": f"file:{tgz.resolve().as_posix()}",
                            "depth": 0,
                            "source": "local-tarball",
                            "dependencies": {},
                        }
                    }
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        identity = package_lock_identity(
            project,
            {
                "source": "tgz",
                "path": str(tgz),
                "filename": tgz.name,
                "sha256": "dummy",
            },
        )
        if identity.get("resolved_dependency") != f"file:{tgz.resolve().as_posix()}":
            fail("unity_validate.py must accept Unity packages-lock source=local-tarball for tgz dependencies")


def check_native_bridge_sources() -> None:
    required_native_files = [
        NATIVE_SOURCE_ROOT / "README.md",
        NATIVE_SOURCE_ROOT / "include" / "nozzle_unity" / "nozzle_unity_bridge.h",
        NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_common.cpp",
        NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_stub.cpp",
        NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_unity.cpp",
        NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_environment.hpp",
    ]
    for path in required_native_files:
        require_file(path)

    header = NATIVE_SOURCE_ROOT / "include" / "nozzle_unity" / "nozzle_unity_bridge.h"
    for symbol in [
        "NOZZLE_UNITY_ABI_VERSION",
        "NOZZLE_UNITY_EVENT_SENDER_PUBLISH_NATIVE_TEXTURE",
        "NOZZLE_UNITY_EVENT_RECEIVER_ACQUIRE_AND_COPY_NATIVE_TEXTURE",
        "nozzle_unity_get_support",
        "nozzle_unity_get_render_event_func",
        "nozzle_unity_sender_create",
        "nozzle_unity_sender_enqueue_publish_native_texture",
        "nozzle_unity_sender_cancel_operations",
        "nozzle_unity_receiver_create",
        "nozzle_unity_receiver_enqueue_acquire_and_copy_native_texture",
        "nozzle_unity_receiver_cancel_operations",
        "nozzle_unity_operation_get_status",
        "nozzle_unity_operation_release",
        "nozzle_unity_queue_get_diagnostics",
        "nozzle_unity_discovery_enumerate_senders",
    ]:
        require_text(header, symbol, f"bridge header export {symbol}")

    unity_source = NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_unity.cpp"
    require_text(unity_source, "UnityPluginLoad")
    require_text(unity_source, "UnityPluginUnload")
    require_text(unity_source, "IUnityGraphics")
    require_text(unity_source, "nozzle_unity_process_render_event(event_id)")
    require_text(unity_source, "nozzle_unity_cancel_all_operations")

    common_source = NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_common.cpp"
    require_text(common_source, "pending_operation_ids")
    require_text(common_source, "operation_records")
    require_text(common_source, "find_operation_record")
    require_text(common_source, "nozzle_unity_status_busy")
    require_text(common_source, "nozzle_unity_process_render_event")
    require_text(common_source, "nozzle_unity_cancel_all_operations")
    require_text(common_source, "bridge_runtime_available")
    require_text(common_source, "nozzle_sender_publish_native_texture")
    require_text(common_source, "nozzle_frame_copy_to_native_texture")
    require_text(common_source, "nozzle_unity_operation_state_running")

    stub_source = NATIVE_SOURCE_ROOT / "src" / "nozzle_unity_bridge_stub.cpp"
    require_text(stub_source, "built without Unity Native Plugin API headers")

    cmake = ROOT / "CMakeLists.txt"
    require_text(cmake, "NOZZLE_UNITY_USE_UNITY_HEADERS")
    require_text(cmake, "NOZZLE_UNITY_PLUGIN_API_DIR")
    require_text(cmake, "nozzle_unity_bridge_stub.cpp")
    require_text(cmake, "nozzle_unity_bridge_unity.cpp")
    require_text(cmake, "nozzle_unity_bridge_metal.mm")
    require_text(cmake, "nozzle_unity_package_artifact")
    require_text(cmake, "NOZZLE_UNITY_ARTIFACT_ROOT")

    required_release_scripts = [
        ROOT / "scripts" / "create_native_payload.py",
        ROOT / "scripts" / "validate_native_payload.py",
        ROOT / "scripts" / "package_upm_tgz.py",
        ROOT / "scripts" / "validate_upm_tgz.py",
        ROOT / "scripts" / "unity_validate.py",
        ROOT / "scripts" / "resolve_release_channel.py",
        ROOT / "scripts" / "publish_release_assets.py",
        ROOT / "scripts" / "unity_release_contract.py",
    ]
    for path in required_release_scripts:
        require_file(path)
    contract = ROOT / "scripts" / "unity_release_contract.py"
    require_text(contract, "PluginImporter")
    require_text(contract, "deterministic_guid")
    require_text(contract, "Windows dependency inspection requires dumpbin")
    require_text(contract, "runtime_supported")
    require_text(contract, "SUPPORT_MODES")
    require_text(ROOT / "scripts" / "create_native_payload.py", "--support-mode")
    require_text(ROOT / "scripts" / "validate_native_payload.py", "--support-mode")
    require_text(ROOT / "scripts" / "validate_upm_tgz.py", "Static UPM archive / manifest preflight")
    unity_validate = ROOT / "scripts" / "unity_validate.py"
    require_text(unity_validate, "UNITY_EDITOR")
    require_text(unity_validate, "UNITY_EDITOR_PATH")
    require_text(unity_validate, "--package-source")
    require_text(unity_validate, "--validation-scope")
    require_text(unity_validate, "--expect-runtime-supported")
    require_text(unity_validate, "-nozzleValidationExpectRuntimeSupported")
    require_text(unity_validate, "--tgz-payload-root")
    require_text(unity_validate, "packages-lock.json")
    require_text(unity_validate, "requested_revision")
    require_text(unity_validate, "artifact_sha256")
    require_text(unity_validate, "package_identity")
    require_text(unity_validate, "Sample.FindByPackage")
    require_text(unity_validate, "PackageInfo.FindForAssetPath")
    require_text(unity_validate, "BuildPipeline.BuildPlayer")
    require_text(unity_validate, "PluginImporter")
    require_text(unity_validate, "native_plugin_matches")
    require_text(unity_validate, "Unity log tail")
    require_text(unity_validate, "NOZZLE_UNITY_VALIDATION_RESULT")
    require_text(unity_validate, "VALIDATION_ASMDEF")
    require_text(unity_validate, "Nozzle.UnityValidation.Editor.asmdef")
    require_text(unity_validate, '"references": ["Nozzle.Unity"]', "validation asmdef must explicitly reference package runtime asmdef")
    require_text(unity_validate, '"includePlatforms": ["Editor"]', "validation asmdef must be Editor-only")


def run_cmake_configure(build_dir: Path, definitions: list[str]) -> None:
    configure = subprocess.run(
        [
            "cmake",
            "-S",
            str(ROOT),
            "-B",
            str(build_dir),
            *definitions,
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if configure.stdout:
        print(configure.stdout, end="")
    if configure.stderr:
        print(configure.stderr, end="", file=sys.stderr)
    if configure.returncode != 0:
        fail(f"cmake configure failed for {display_path(build_dir)} with exit code {configure.returncode}")


def run_cmake_build(build_dir: Path, target: str, config: str | None = None) -> None:
    command = ["cmake", "--build", str(build_dir), "--target", target]
    if config:
        command.extend(["--config", config])
    build = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if build.stdout:
        print(build.stdout, end="")
    if build.stderr:
        print(build.stderr, end="", file=sys.stderr)
    if build.returncode != 0:
        fail(f"cmake build target {target!r} failed for {display_path(build_dir)} with exit code {build.returncode}")


def check_native_bridge_stub_build() -> None:
    build_dir = ROOT / "build" / "project-sanity-nozzle-unity-stub"
    run_cmake_configure(build_dir, ["-DNOZZLE_UNITY_BUILD_NOZZLE_CORE=OFF"])
    run_cmake_build(build_dir, "nozzle_unity")



class NativeSupportInfo(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("bridge_binary_loaded", ctypes.c_uint32),
        ("runtime_supported", ctypes.c_uint32),
        ("unity_headers_compiled", ctypes.c_uint32),
        ("unity_graphics_device_available", ctypes.c_uint32),
        ("render_thread_events_available", ctypes.c_uint32),
        ("direct_nozzle_c_abi_available", ctypes.c_uint32),
        ("status_message", ctypes.c_char * 256),
    ]


class NativeSenderPublishDesc(ctypes.Structure):
    _fields_ = [
        ("sender", ctypes.c_void_p),
        ("native_texture", ctypes.c_void_p),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("texture_format", ctypes.c_int32),
        ("managed_generation", ctypes.c_uint64),
    ]


class NativeOperationStatus(ctypes.Structure):
    _fields_ = [
        ("operation_id", ctypes.c_uint64),
        ("managed_generation", ctypes.c_uint64),
        ("kind", ctypes.c_int32),
        ("state", ctypes.c_int32),
        ("result", ctypes.c_int32),
        ("frame_index", ctypes.c_uint64),
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("texture_format", ctypes.c_int32),
        ("status_message", ctypes.c_char * 256),
    ]


def load_native_library(native_plugin: Path) -> ctypes.CDLL:
    try:
        if platform.system() == "Windows":
            return ctypes.WinDLL(str(native_plugin))
        return ctypes.CDLL(str(native_plugin))
    except OSError as error:
        fail(f"failed to load native artifact plugin {display_path(native_plugin)}: {error}")


def check_exported_symbols(native_plugin: Path, library: ctypes.CDLL) -> None:
    required_exports = [
        "nozzle_unity_get_support",
        "nozzle_unity_get_version",
        "nozzle_unity_get_render_event_func",
        "nozzle_unity_sender_create",
        "nozzle_unity_sender_publish_native_texture",
        "nozzle_unity_sender_enqueue_publish_native_texture",
        "nozzle_unity_sender_cancel_operations",
        "nozzle_unity_operation_get_status",
        "nozzle_unity_operation_release",
        "nozzle_unity_queue_get_diagnostics",
        "nozzle_unity_receiver_create",
        "nozzle_unity_receiver_acquire_frame",
        "nozzle_unity_frame_get_info",
        "nozzle_unity_frame_copy_to_native_texture",
        "nozzle_unity_discovery_enumerate_senders",
    ]
    for symbol in required_exports:
        try:
            getattr(library, symbol)
        except AttributeError:
            fail(f"native artifact plugin {display_path(native_plugin)} is missing exported symbol {symbol}")


def check_native_support_contract(native_plugin: Path, library: ctypes.CDLL) -> None:
    get_support = library.nozzle_unity_get_support
    get_support.argtypes = [ctypes.POINTER(NativeSupportInfo)]
    get_support.restype = ctypes.c_int32

    support = NativeSupportInfo()
    status = get_support(ctypes.byref(support))
    if status != 0:
        fail(f"nozzle_unity_get_support returned {status} for {display_path(native_plugin)}")
    if support.abi_version != 1:
        fail(f"native artifact ABI version must be 1, got {support.abi_version}")
    if support.bridge_binary_loaded != 1:
        fail(f"native artifact bridge_binary_loaded must be 1, got {support.bridge_binary_loaded}")
    if support.runtime_supported != 0:
        fail(f"CI-staged stub/native ABI artifact must report runtime_supported = 0, got {support.runtime_supported}")
    if support.unity_headers_compiled != 0:
        fail(f"default CI artifact must be the stub/native ABI build with unity_headers_compiled = 0, got {support.unity_headers_compiled}")
    if support.render_thread_events_available != 0:
        fail(f"stub/native ABI artifact must report render_thread_events_available = 0, got {support.render_thread_events_available}")

    message = bytes(support.status_message).split(b"\0", 1)[0].decode("utf-8", errors="replace")
    if "CI stub" not in message or "runtime" not in message:
        fail(f"native artifact support message must identify the CI stub runtime-disabled boundary, got {message!r}")
    print(
        "Native artifact support: "
        f"abi={support.abi_version}, runtime_supported={support.runtime_supported}, "
        f"unity_headers_compiled={support.unity_headers_compiled}, "
        f"render_thread_events_available={support.render_thread_events_available}, "
        f"direct_nozzle_c_abi_available={support.direct_nozzle_c_abi_available}, "
        f"message={message!r}"
    )


def check_operation_lifetime_contract(native_plugin: Path, library: ctypes.CDLL) -> None:
    enqueue = library.nozzle_unity_sender_enqueue_publish_native_texture
    enqueue.argtypes = [ctypes.POINTER(NativeSenderPublishDesc), ctypes.POINTER(ctypes.c_uint64)]
    enqueue.restype = ctypes.c_int32

    get_status = library.nozzle_unity_operation_get_status
    get_status.argtypes = [ctypes.c_uint64, ctypes.POINTER(NativeOperationStatus)]
    get_status.restype = ctypes.c_int32

    release = library.nozzle_unity_operation_release
    release.argtypes = [ctypes.c_uint64]
    release.restype = ctypes.c_int32

    cancel = library.nozzle_unity_sender_cancel_operations
    cancel.argtypes = [ctypes.c_void_p]
    cancel.restype = ctypes.c_int32

    fake_sender = ctypes.c_void_p(0x1)
    desc = NativeSenderPublishDesc(
        sender=fake_sender,
        native_texture=ctypes.c_void_p(0x2),
        width=16,
        height=16,
        texture_format=4,
        managed_generation=123,
    )
    operation_id = ctypes.c_uint64(0)
    status = enqueue(ctypes.byref(desc), ctypes.byref(operation_id))
    if status != 0 or operation_id.value == 0:
        fail(f"operation lifetime enqueue failed for {display_path(native_plugin)}: status={status}, op={operation_id.value}")

    op_status = NativeOperationStatus()
    status = get_status(operation_id.value, ctypes.byref(op_status))
    if status != 0 or op_status.state != 1:
        fail(f"queued operation must remain queryable before release: status={status}, state={op_status.state}")

    status = release(operation_id.value)
    if status != 4:
        fail(f"release of queued operation must return busy instead of dropping lifetime state, got {status}")

    op_status_after_busy = NativeOperationStatus()
    status = get_status(operation_id.value, ctypes.byref(op_status_after_busy))
    if status != 0 or op_status_after_busy.state != 1:
        fail(
            "queued operation disappeared after busy release: "
            f"status={status}, state={op_status_after_busy.state}"
        )

    status = cancel(fake_sender)
    if status != 0:
        fail(f"cancel of queued operation failed: status={status}")

    canceled_status = NativeOperationStatus()
    status = get_status(operation_id.value, ctypes.byref(canceled_status))
    if status != 0 or canceled_status.state != 5:
        fail(f"canceled operation must remain queryable until explicit release: status={status}, state={canceled_status.state}")

    status = release(operation_id.value)
    if status != 0:
        fail(f"release of terminal operation failed: status={status}")

    released_status = NativeOperationStatus()
    status = get_status(operation_id.value, ctypes.byref(released_status))
    if status == 0:
        fail("released terminal operation must not remain queryable after release")

    print(f"Operation lifetime contract: queued release busy, cancel terminal, release clears for {display_path(native_plugin)}")


def inspect_loader_dependencies(native_plugin: Path) -> None:
    system = platform.system()
    if system == "Darwin":
        command = ["otool", "-L", str(native_plugin)]
    elif system == "Linux":
        command = ["ldd", str(native_plugin)]
    elif system == "Windows":
        dumpbin = shutil.which("dumpbin")
        if dumpbin is None:
            fail("Windows loader dependency inspection requires dumpbin; configure a Visual Studio developer environment instead of skipping")
        command = [dumpbin, "/DEPENDENTS", str(native_plugin)]
    else:
        print(f"Skipping loader dependency inspection on unsupported host {system}.")
        return

    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        fail(f"loader dependency inspection failed for {display_path(native_plugin)} with exit code {result.returncode}")

def expected_artifact_plugin_fragment() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path("Runtime") / "Plugins" / "macOS"
    if system == "Windows":
        return Path("Runtime") / "Plugins" / "Windows" / "x86_64"
    if system == "Linux":
        return Path("Runtime") / "Plugins" / "Linux" / "x86_64"
    return Path("Runtime") / "Plugins" / system


def check_native_artifact(artifact_root: Path) -> None:
    require_dir(artifact_root)
    artifact_package_root = artifact_root / "Packages" / "org.nozzle-io.unity"
    require_dir(artifact_package_root)
    require_file(artifact_package_root / "package.json")
    require_file(artifact_package_root / "Native~" / "include" / "nozzle_unity" / "nozzle_unity_bridge.h")
    require_file(artifact_package_root / "Native~" / "src" / "nozzle_unity_bridge_common.cpp")

    plugins_root = artifact_package_root / "Runtime" / "Plugins"
    require_dir(plugins_root)
    native_plugins = [
        path
        for path in plugins_root.rglob("*")
        if path.is_file() and path.suffix.lower() in NATIVE_LIBRARY_SUFFIXES
    ]
    if len(native_plugins) != 1:
        fail(
            f"native artifact must contain exactly one nozzle_unity plugin binary under "
            f"{display_path(plugins_root)}, got {[display_path(path) for path in native_plugins]!r}"
        )

    native_plugin = native_plugins[0]
    if "nozzle_unity" not in native_plugin.name:
        fail(f"native artifact plugin must be named for nozzle_unity, got {native_plugin.name!r}")

    expected_fragment = expected_artifact_plugin_fragment()
    relative_plugin = native_plugin.relative_to(artifact_package_root)
    if expected_fragment not in relative_plugin.parents:
        fail(
            f"native artifact plugin path must be under {expected_fragment}, "
            f"got {relative_plugin}"
        )

    library = load_native_library(native_plugin)
    check_exported_symbols(native_plugin, library)
    check_native_support_contract(native_plugin, library)
    check_operation_lifetime_contract(native_plugin, library)
    inspect_loader_dependencies(native_plugin)

    package_readme = artifact_package_root / "README.md"
    troubleshooting = artifact_package_root / "Documentation~" / "troubleshooting.md"
    require_text(package_readme, "CI-staged stub/native ABI artifact")
    require_text(package_readme, "no Unity Editor/Player runtime support claim")
    require_text(troubleshooting, "runtime_supported = 0")


def check_submodules() -> None:
    result = subprocess.run(
        ["git", "submodule", "status", "--recursive"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        fail(f"git submodule status --recursive failed with exit code {result.returncode}")

    for line in result.stdout.splitlines():
        if line.startswith(("-", "+", "U")):
            fail(f"submodule is not cleanly initialized at recorded gitlink: {line}")

    require_file(ROOT / "nozzle" / "include" / "nozzle" / "nozzle_c.h")
    require_file(ROOT / "nozzle" / "CMakeLists.txt")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--native-artifact",
        type=Path,
        help="Validate a staged UPM package plus built nozzle_unity native bridge artifact.",
    )
    parser.add_argument(
        "--skip-stub-build",
        action="store_true",
        help="Skip the local CMake stub build check.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("nozzle.unity: Project Sanity only; no Unity Editor build/test coverage.")
    check_package_manifest()
    check_asmdef()
    check_unity_package_meta_contract()
    check_runtime_sources()
    check_unity_validate_generated_project_contract()
    check_native_bridge_sources()
    check_docs_and_samples()
    check_submodules()
    if args.skip_stub_build:
        print("Skipping CMake stub build check by request.")
    else:
        check_native_bridge_stub_build()
    if args.native_artifact is not None:
        check_native_artifact(args.native_artifact.resolve())
    print("Project sanity checks passed.")


if __name__ == "__main__":
    main()
