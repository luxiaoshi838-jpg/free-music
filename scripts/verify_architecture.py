from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_ACTIVITY = ROOT / "app/src/main/java/com/jianglab/babywife/MainActivity.java"

FORBIDDEN_MARKERS = {
    "17878": "仍依赖电脑端音乐服务端口 17878",
    "10.0.2.2": "仍依赖 Android 模拟器访问宿主机地址 10.0.2.2",
    "10.0.3.2": "仍依赖逍遥/模拟器访问宿主机地址 10.0.3.2",
    "127.0.0.1:17878": "仍依赖本机回环服务",
    "android.webkit.WebView": "仍是 WebView 壳，不是独立手机版架构",
}


def main() -> int:
    if not MAIN_ACTIVITY.exists():
        print(f"missing entry file: {MAIN_ACTIVITY}")
        return 1

    text = MAIN_ACTIVITY.read_text(encoding="utf-8")
    errors = []
    for marker, reason in FORBIDDEN_MARKERS.items():
        if marker in text:
            errors.append(f"- {reason}: `{marker}`")

    if errors:
        print("APK architecture is not complete yet.")
        print("The app must run inside the Android APK before generating a release artifact.")
        print("\n".join(errors))
        return 1

    print("Architecture gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
