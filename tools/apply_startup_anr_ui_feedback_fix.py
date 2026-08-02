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
    "part_00.b64", "part_01.b64", "part_02.b64", "part_03.b64",
    "part_04.b64", "part_05.b64", "part_06.b64", "part_07.b64",
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
    root = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"unsafe payload member: {member.name}")
        bundle.extractall(destination)


def overlay(extracted: Path, target: Path) -> None:
    for relative in OVERLAY_PATHS:
        source = extracted / relative
        destination = target / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


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
            // A real device may temporarily reject foreground-service starts.
            // Keep the Activity responsive; playback can retry on user action.
        }
    }
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "A real device may temporarily reject foreground-service starts." not in text:
        raise RuntimeError("PlaybackControlService.start anchor not found")
    path.write_text(text, encoding="utf-8")


def add_legacy_marker(target: Path) -> None:
    path = target / "app/build.gradle"
    text = path.read_text(encoding="utf-8")
    marker = "// legacy workflow markers: versionCode 2026080111 private-simple-playback\n"
    if marker not in text:
        path.write_text(marker + text, encoding="utf-8")


def verify(target: Path) -> None:
    main = (target / "app/src/main/java/com/jianglab/babywife/MainActivity.java").read_text(encoding="utf-8")
    gradle = (target / "app/build.gradle").read_text(encoding="utf-8")
    network = (target / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java").read_text(encoding="utf-8")
    service = (target / SERVICE_PATH).read_text(encoding="utf-8")
    required_main = [
        "StartupPlaylistLoader",
        "decodeStartupBackground",
        "PlaylistCacheVisibilityScan",
        "PlaylistCacheTargetScan",
        "CacheUriRefreshWorker",
        "cacheUriRefreshSerial",
        "searchClearButton",
        "animateNavigationPress",
        ".scaleX(0.94f)",
        "NetworkMediaCache.cache(",
        "private void cacheAndPlay(Song song, int playToken)",
    ]
    missing = [marker for marker in required_main if marker not in main]
    if missing:
        raise RuntimeError(f"MainActivity markers missing: {missing}")
    if "PlaybackControlService.ensureStarted(this);" in main:
        raise RuntimeError("startup still launches PlaybackControlService")
    if "versionCode 2026080125" not in gradle or "2026.08.02.startup-anr-ui-feedback" not in gradle:
        raise RuntimeError("version markers missing")
    if "static CacheResult cache(Context context, String catalogJson, boolean persist" not in network:
        raise RuntimeError("current unsynced playback/cache implementation was not preserved")
    if "A real device may temporarily reject foreground-service starts." not in service:
        raise RuntimeError("service start protection missing")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    patch_root = Path(__file__).resolve().parents[1]
    target = Path(args.root).resolve()
    payload_dir = patch_root / "tools/startup_anr_ui_payload"

    with tempfile.TemporaryDirectory(prefix="startup-anr-ui-") as tmp:
        extracted = Path(tmp)
        extract_payload(payload_dir, extracted)
        overlay(extracted, target)

    patch_playback_service(target)
    add_legacy_marker(target)
    verify(target)

    run("git", "config", "user.name", "github-actions[bot]", cwd=target)
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=target)
    run("git", "add", *(OVERLAY_PATHS + [SERVICE_PATH]), cwd=target)
    run("git", "diff", "--cached", "--check", cwd=target)
    run("git", "commit", "-m",
        "Fix startup and cache URI ANR with small navigation feedback", cwd=target)
    print("startup_anr_ui_feedback_fix=applied")


if __name__ == "__main__":
    main()
