from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {".apk", ".aab", ".idsig", ".jks", ".keystore", ".p12", ".pfx", ".pem", ".key"}
FORBIDDEN_TEXT = [
    "store" + "Password",
    "key" + "Password",
    "babywife" + "-stable",
    "BEGIN " + "PRIVATE KEY",
    "BEGIN " + "RSA PRIVATE KEY",
    "BEGIN " + "EC PRIVATE KEY",
]
BRANDS = {
    "babywifeclassic": "assembleBabywifeclassicDebug",
    "lidacaizhu": "assembleLidacaizhuDebug",
    "jianglab": "assembleJianglabDebug",
    "niubi": "assembleNiubiDebug",
}
CORE_FILES = [
    "app/build.gradle",
    "settings.gradle",
    "app/libs/musicbridge.aar",
    "app/src/main/AndroidManifest.xml",
    "app/src/main/java/com/jianglab/babywife/MainActivity.java",
    "app/src/main/java/com/jianglab/babywife/CatalogSearch.java",
    "app/src/main/java/com/jianglab/babywife/LyricVersionPicker.java",
    "app/src/main/java/com/jianglab/babywife/SongVersionPicker.java",
    "app/src/main/java/com/jianglab/babywife/PlaylistLyricMatcher.java",
    "app/src/main/java/com/jianglab/babywife/PlaybackControlService.java",
]


def fail(message: str) -> None:
    print(f"PUBLIC_REPO_CHECK_FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> None:
    for path in ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            fail(f"forbidden file committed: {path.relative_to(ROOT)}")

    for rel in CORE_FILES:
        path = ROOT / rel
        if not path.exists():
            fail(f"missing required file: {rel}")
        if path.is_file() and path.stat().st_size == 0:
            fail(f"empty required file: {rel}")

    build_gradle = read_text(ROOT / "app/build.gradle")
    if "flavorDimensions" not in build_gradle or "productFlavors" not in build_gradle:
        fail("app/build.gradle does not define four brand flavors")
    for brand in BRANDS:
        if not re.search(rf"\b{re.escape(brand)}\s*\{{", build_gradle):
            fail(f"missing product flavor: {brand}")
        if not (ROOT / "app/src" / brand / "res/values/strings.xml").exists():
            fail(f"missing brand strings.xml: {brand}")
        if not (ROOT / "app/src" / brand / "res/drawable-nodpi/default_background.jpg").exists():
            fail(f"missing brand background: {brand}")

    for token in FORBIDDEN_TEXT:
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or not path.is_file():
                continue
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".aar"}:
                continue
            if token in read_text(path):
                fail(f"forbidden text '{token}' in {path.relative_to(ROOT)}")

    xml_files = list((ROOT / "app/src").rglob("*.xml"))
    for path in xml_files:
        try:
            ET.parse(path)
        except Exception as exc:
            fail(f"invalid XML {path.relative_to(ROOT)}: {exc}")

    print("Public four-brand repository check passed.")
    print(f"brands={','.join(BRANDS)}")
    print(f"xml_files={len(xml_files)}")


if __name__ == "__main__":
    main()
