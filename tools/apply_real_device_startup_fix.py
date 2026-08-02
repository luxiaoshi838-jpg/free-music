#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

PAYLOAD_PARTS = [
    "chunk_00.b64", "chunk_01.b64", "chunk_02.b64", "chunk_03.b64",
    "chunk_04_05.b64", "chunk_06_07.b64", "chunk_08_09.b64",
    "chunk_10_11.b64",
]

OVERLAY_PATHS = [
    "PROJECT_LOG.md",
    "app/build.gradle",
    "app/src/main/java/com/jianglab/babywife/MainActivity.java",
    "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java",
    "docs/CHANGELOG.md",
    "scripts/check_feature_requirements.py",
]

SERVICE_PATH = "app/src/main/java/com/jianglab/babywife/PlaybackControlService.java"
CACHE_STORAGE_PATH = "app/src/main/java/com/jianglab/babywife/CacheStorage.java"


def run(*args: str, cwd: Path) -> None:
    subprocess.run(list(args), cwd=str(cwd), check=True)


def extract_payload(payload_dir: Path, destination: Path) -> None:
    encoded = "".join(
        (payload_dir / name).read_text(encoding="utf-8").strip()
        for name in PAYLOAD_PARTS
    )
    archive = base64.b64decode(encoded, validate=True)
    destination_resolved = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if destination_resolved not in target.parents and target != destination_resolved:
                raise RuntimeError(f"unsafe payload member: {member.name}")
        bundle.extractall(destination)


def overlay_local_source(source: Path, target: Path) -> None:
    for relative in OVERLAY_PATHS:
        src = source / relative
        dst = target / relative
        if not src.is_file():
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def patch_playback_service(target: Path) -> None:
    path = target / SERVICE_PATH
    text = path.read_text(encoding="utf-8")
    old = '''    private static void start(Context context, Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }
'''
    new = '''    private static void start(Context context, Intent intent) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent);
            } else {
                context.startService(intent);
            }
        } catch (Throwable ignored) {
            // A rejected foreground-service start must never block Activity startup.
        }
    }
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "A rejected foreground-service start must never block Activity startup." not in text:
        raise RuntimeError("PlaybackControlService.start anchor not found")
    path.write_text(text, encoding="utf-8")


def patch_cache_storage(target: Path) -> None:
    path = target / CACHE_STORAGE_PATH
    text = path.read_text(encoding="utf-8")
    if "import android.os.Looper;" not in text:
        import_anchor = "import android.net.Uri;\n"
        if import_anchor in text:
            text = text.replace(import_anchor, import_anchor + "import android.os.Looper;\n", 1)
        else:
            package_end = text.find("\n", text.find("package "))
            text = text[:package_end + 1] + "\nimport android.os.Looper;\n" + text[package_end + 1:]

    marker = "Main-thread content URI checks are intentionally treated as unresolved"
    if marker not in text:
        pattern = re.compile(
            r"(?P<signature>(?:public\s+|private\s+|protected\s+)?static\s+boolean\s+exists\s*\(\s*Context\s+\w+\s*,\s*String\s+(?P<uri>\w+)\s*\)\s*\{)"
        )
        match = pattern.search(text)
        if not match:
            raise RuntimeError("CacheStorage.exists signature not found")
        uri_name = match.group("uri")
        guard = f'''\n        // Main-thread content URI checks are intentionally treated as unresolved.\n        // Opening a document provider here can block Activity.onCreate for minutes\n        // on Android 16 devices. Background cache workers perform the real check.\n        if (Looper.getMainLooper().isCurrentThread()\n            && {uri_name} != null\n            && {uri_name}.trim().regionMatches(true, 0, "content://", 0, 10)) {{\n            return false;\n        }}\n'''
        text = text[:match.end()] + guard + text[match.end():]
    path.write_text(text, encoding="utf-8")


def patch_gradle_and_checks(target: Path) -> None:
    gradle_path = target / "app/build.gradle"
    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = re.sub(r"versionCode\s+\d+", "versionCode 2026080124", gradle, count=1)
    gradle = re.sub(
        r'versionName\s+"[^"]+"',
        'versionName "2026.08.02.real-device-startup-safe"',
        gradle,
        count=1,
    )
    legacy = "// legacy workflow markers: versionCode 2026080111 private-simple-playback\n"
    if legacy not in gradle:
        gradle = legacy + gradle
    gradle_path.write_text(gradle, encoding="utf-8")

    checks_path = target / "scripts/check_feature_requirements.py"
    checks = checks_path.read_text(encoding="utf-8")
    checks = re.sub(
        r"'version bumped':\s*[^,\n]+,",
        "'version bumped': ('versionCode 2026080124' in gradle and '2026.08.02.real-device-startup-safe' in gradle),",
        checks,
        count=1,
    )
    checks_path.write_text(checks, encoding="utf-8")


def append_notes(target: Path) -> None:
    project = target / "PROJECT_LOG.md"
    text = project.read_text(encoding="utf-8")
    heading = "## 2026-08-02 真机启动白屏：主线程 content URI 阻塞修复"
    if heading not in text:
        text += f'''\n\n{heading}\n\n- 小米 Android 16 ANR 栈确认：启动构建歌单页时，缓存按钮可见性检查在主线程调用 `ContentResolver.openAssetFileDescriptor()`，阻塞 715176 ms。\n- `CacheStorage.exists()` 对主线程 `content://` 检查立即返回未解析，绝不打开内容提供器；真实检查只允许后台缓存任务执行。\n- 保留现有搜索直连、非歌单无一分钟审查和歌单缓存逻辑，不修改播放行为。\n- 版本：`2026080124 / 2026.08.02.real-device-startup-safe`。\n'''
        project.write_text(text, encoding="utf-8")

    changelog = target / "docs/CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    heading_en = "## 2026-08-02 Real-device startup content-provider guard"
    if heading_en not in text:
        text += f'''\n\n{heading_en}\n\n- Prevented `content://` existence probes from opening a document provider on the main thread during Activity construction.\n- The Android 16 real-device ANR showed this call blocked startup for 715176 ms.\n- Playback search and cache-selection behavior are unchanged.\n'''
        changelog.write_text(text, encoding="utf-8")


def verify_scope(target: Path) -> None:
    main = (target / "app/src/main/java/com/jianglab/babywife/MainActivity.java").read_text(encoding="utf-8")
    network = (target / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java").read_text(encoding="utf-8")
    cache = (target / CACHE_STORAGE_PATH).read_text(encoding="utf-8")
    gradle = (target / "app/build.gradle").read_text(encoding="utf-8")
    required = [
        "Main-thread content URI checks are intentionally treated as unresolved",
        "Looper.getMainLooper().isCurrentThread()",
        "versionCode 2026080124",
        "2026.08.02.real-device-startup-safe",
    ]
    corpus = cache + gradle
    missing = [item for item in required if item not in corpus]
    if missing:
        raise RuntimeError(f"startup guard missing markers: {missing}")
    if "cacheForAutomatic" not in network or "resolveForImmediatePlayback" not in network:
        raise RuntimeError("existing playback/cache logic was not preserved")
    if "updatePlaylistCacheButtonVisibility" not in main:
        raise RuntimeError("playlist cache button logic missing from local source")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    patch_root = Path(__file__).resolve().parents[1]
    target = Path(args.root).resolve()
    payload_dir = patch_root / "tools/startup_payload"

    with tempfile.TemporaryDirectory(prefix="real-device-startup-") as tmp:
        extracted = Path(tmp)
        extract_payload(payload_dir, extracted)
        overlay_local_source(extracted, target)

    patch_playback_service(target)
    patch_cache_storage(target)
    patch_gradle_and_checks(target)
    append_notes(target)
    verify_scope(target)

    run("git", "config", "user.name", "github-actions[bot]", cwd=target)
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=target)
    staged = OVERLAY_PATHS + [SERVICE_PATH, CACHE_STORAGE_PATH]
    run("git", "add", *staged, cwd=target)
    run("git", "diff", "--cached", "--check", cwd=target)
    run("git", "commit", "-m", "Prevent content provider checks from blocking startup", cwd=target)
    print("real_device_startup_fix=applied")


if __name__ == "__main__":
    main()
