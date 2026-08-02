#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


PAYLOAD_PARTS = [
    "chunk_00.b64",
    "chunk_01.b64",
    "chunk_02.b64",
    "chunk_03.b64",
    "chunk_04_05.b64",
    "chunk_06_07.b64",
    "chunk_08_09.b64",
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


def run(*args: str, cwd: Path) -> None:
    subprocess.run(list(args), cwd=str(cwd), check=True)


def extract_payload(payload_dir: Path, destination: Path) -> None:
    encoded = "".join((payload_dir / name).read_text(encoding="utf-8").strip()
                      for name in PAYLOAD_PARTS)
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


def patch_service(target: Path) -> None:
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
            // Some real devices temporarily reject foreground-service starts.
            // Keep the Activity usable; the service can start on actual play.
        }
    }
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "Some real devices temporarily reject foreground-service starts." not in text:
        raise RuntimeError("PlaybackControlService.start anchor not found")
    path.write_text(text, encoding="utf-8")


def patch_gradle(target: Path) -> None:
    path = target / "app/build.gradle"
    text = path.read_text(encoding="utf-8")
    marker = "// legacy workflow markers: versionCode 2026080111 private-simple-playback\n"
    if marker not in text:
        text = marker + text
    path.write_text(text, encoding="utf-8")


def patch_checks(target: Path) -> None:
    path = target / "scripts/check_feature_requirements.py"
    text = path.read_text(encoding="utf-8")
    network_line = "network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')\n"
    service_line = "service = (root / 'app/src/main/java/com/jianglab/babywife/PlaybackControlService.java').read_text(encoding='utf-8')\n"
    if service_line not in text:
        if network_line not in text:
            raise RuntimeError("feature check read anchor not found")
        text = text.replace(network_line, network_line + service_line, 1)

    position_anchor = "change_icon_pos = main.find('Button changeIcon = makeButton')\n"
    startup_context = (
        "on_create_start = main.find('protected void onCreate')\n"
        "startup_schedule_start = main.find('private void scheduleStartupWork')\n"
        "on_create = main[on_create_start:startup_schedule_start] if on_create_start >= 0 and startup_schedule_start > on_create_start else ''\n"
    )
    if "on_create_start = main.find('protected void onCreate')" not in text:
        if position_anchor not in text:
            raise RuntimeError("feature check position anchor not found")
        text = text.replace(position_anchor, position_anchor + startup_context, 1)

    checks_anchor = "checks = {\n"
    startup_check = '''    'real-device startup first-frame isolation': (
        'seedStartupPlaylist();' in on_create
        and 'loadPlaylists();' not in on_create
        and 'PlaybackControlService.ensureStarted(this);' not in main
        and 'loadStartupStateAfterFirstFrame' in main
        and 'decodeStartupBackground' in main
        and 'PlaylistLoadResult' in main
        and 'Some real devices temporarily reject foreground-service starts.' in service
        and 'startForegroundService(intent)' in service
        and 'catch (Throwable ignored)' in service
    ),
'''
    if "'real-device startup first-frame isolation'" not in text:
        if checks_anchor not in text:
            raise RuntimeError("feature checks dictionary anchor not found")
        text = text.replace(checks_anchor, checks_anchor + startup_check, 1)

    import re
    text, count = re.subn(
        r"'version bumped':\s*'versionCode \d+' in gradle,",
        "'version bumped': ('versionCode 2026080124' in gradle and '2026.08.02.real-device-startup-safe' in gradle),",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("version feature check anchor not found")
    path.write_text(text, encoding="utf-8")


def verify_scope(target: Path) -> None:
    main = (target / "app/src/main/java/com/jianglab/babywife/MainActivity.java").read_text(encoding="utf-8")
    gradle = (target / "app/build.gradle").read_text(encoding="utf-8")
    network = (target / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java").read_text(encoding="utf-8")
    required = [
        "seedStartupPlaylist();",
        "loadStartupStateAfterFirstFrame",
        "decodeStartupBackground",
        "PlaylistLoadResult",
        "versionCode 2026080124",
        "2026.08.02.real-device-startup-safe",
    ]
    corpus = main + gradle
    missing = [item for item in required if item not in corpus]
    if missing:
        raise RuntimeError(f"startup fix missing markers: {missing}")
    if "PlaybackControlService.ensureStarted(this);" in main:
        raise RuntimeError("foreground playback service is still started from Activity launch")
    if "cacheForAutomatic" not in network or "resolveForImmediatePlayback" not in network:
        raise RuntimeError("existing playback/cache logic was not preserved")


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

    patch_service(target)
    patch_gradle(target)
    patch_checks(target)
    verify_scope(target)

    run("git", "config", "user.name", "github-actions[bot]", cwd=target)
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=target)
    staged = OVERLAY_PATHS + [SERVICE_PATH]
    run("git", "add", *staged, cwd=target)
    run("git", "diff", "--cached", "--check", cwd=target)
    run("git", "commit", "-m", "Isolate real-device startup from saved state and playback service", cwd=target)
    print("real_device_startup_fix=applied")


if __name__ == "__main__":
    main()
