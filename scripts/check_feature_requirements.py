#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "app/src/main/java/com/jianglab/babywife/MainActivity.java").read_text(encoding="utf-8")
CACHE = (ROOT / "app/src/main/java/com/jianglab/babywife/CacheStorage.java").read_text(encoding="utf-8")
NETWORK = (ROOT / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java").read_text(encoding="utf-8")
PICKER = (ROOT / "app/src/main/java/com/jianglab/babywife/SongVersionPicker.java").read_text(encoding="utf-8")
CATALOG = (ROOT / "app/src/main/java/com/jianglab/babywife/CatalogSearch.java").read_text(encoding="utf-8")
BUILD = (ROOT / "app/build.gradle").read_text(encoding="utf-8")
PROJECT_LOG = (ROOT / "PROJECT_LOG.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FEATURE_CHECK_FAILED: {message}")


def main() -> None:
    require('makeRoundButton("\\uD83E\\uDDF9"' in MAIN, "broom button is missing")
    require("confirmClearTransientCache" in MAIN and "clearTransient" in NETWORK,
            "transient cache cleanup is incomplete")
    require("addCurrentButton.setVisibility(View.GONE)" in MAIN,
            "player action buttons are not hidden by default")
    require("switchPlaybackToPlaylist" in MAIN and "playingSearchQueue = false" in MAIN,
            "search-to-playlist queue transition is missing")
    require("song.unavailable ? Color.rgb(255, 96, 96)" in MAIN,
            "unavailable playlist rows are not red")
    require("autoUnavailable" in MAIN and "onUnavailable()" in PICKER,
            "two-stage unavailable marking is missing")
    require("replacementScore" in CATALOG and "canResolveCatalog" in NETWORK,
            "replacement search is not relaxed and playability-verified")
    require('TRANSIENT_FOLDER = "缓存"' in CACHE and "ACTION_OPEN_DOCUMENT_TREE" in MAIN,
            "configurable cache root or cache folder is missing")
    require("CacheStorage.renameFolder" in MAIN and "promoteToPlaylist" in MAIN,
            "playlist cache folder migration is missing")
    require("title.setText(\"\")" in MAIN and 'title.setText("设置")' not in MAIN,
            "settings title is still visible")
    require("REQUEST_IMPORT_PLAYLIST_CSV" in MAIN and "目录JSON" in MAIN and "歌词内容" in MAIN,
            "CSV import/export round-trip fields are incomplete")
    require("JIANG_LAB_GATE_ENABLED" in BUILD and "JIANG_LAB_PASSPHRASE_SHA256" in BUILD,
            "JiangLab private passphrase injection is missing")
    require("requiresJiangLabVerification" in MAIN and "constantTimeEquals" in MAIN,
            "JiangLab first-launch verification is missing")
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".aar", ".jar"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        require(("姜Lab" + "欢迎你") not in text, f"plain JiangLab passphrase leaked in {path.relative_to(ROOT)}")
    marker = "2026-07-26.2"
    require(marker in PROJECT_LOG and marker in CHANGELOG,
            "local and online project logs are not synchronized")
    require(not re.search(r"JIANG_LAB_PASSPHRASE_SHA256\s*=\s*[0-9a-fA-F]{64}",
                          (ROOT / "private.properties.example").read_text(encoding="utf-8")),
            "real JiangLab hash was committed")
    print("Feature requirement check passed.")


if __name__ == "__main__":
    main()
