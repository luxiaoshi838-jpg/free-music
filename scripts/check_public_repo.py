#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "settings.gradle",
    "build.gradle",
    "gradle.properties",
    "app/build.gradle",
    "app/src/main/AndroidManifest.xml",
    "app/src/main/java/com/jianglab/babywife/MainActivity.java",
    "app/src/main/res/drawable/default_background.xml",
    "app/src/main/res/mipmap/ic_launcher.xml",
    "app/src/main/res/mipmap/ic_launcher_round.xml",
]
FORBIDDEN_SUFFIXES = {".jks", ".keystore", ".p12", ".pfx", ".pem", ".key", ".apk", ".aab"}
FORBIDDEN_TEXT = {
    "storePassword": "embedded signing password",
    "keyPassword": "embedded key password",
    "BEGIN PRIVATE KEY": "private key",
    "github_pat_": "GitHub token",
    "ghp_": "GitHub token",
    "applicationIdSuffix": "brand flavor",
    "lidacaizhu": "private brand resource",
    "jianglab": "private brand resource",
    "niubi": "private brand resource",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))

    main_java = (ROOT / REQUIRED[5]).read_text(encoding="utf-8")
    if "public class MainActivity extends Activity" not in main_java:
        fail("MainActivity entry class is invalid")
    if main_java.count("public class MainActivity") != 1:
        fail("MainActivity was assembled more than once")
    if len(main_java.splitlines()) < 1500:
        fail("MainActivity appears truncated")

    build_text = (ROOT / "app/build.gradle").read_text(encoding="utf-8")
    if 'applicationId "com.jianglab.babywife"' not in build_text:
        fail("public package id changed")
    if "productFlavors" in build_text or "signingConfigs" in build_text:
        fail("private brand or signing configuration is present")

    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"forbidden file: {path.relative_to(ROOT)}")
            continue
        if path.stat().st_size > 5_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for marker, label in FORBIDDEN_TEXT.items():
            if marker in text:
                findings.append(f"{label}: {path.relative_to(ROOT)}")
    if findings:
        fail("; ".join(findings))

    temp_parts = list((ROOT / ".bootstrap").glob("MainActivity.part*")) if (ROOT / ".bootstrap").exists() else []
    if temp_parts:
        fail("temporary MainActivity parts remain")

    print("Public repository check passed.")
    print(f"MainActivity lines={len(main_java.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
