#!/usr/bin/env python3
from pathlib import Path
import argparse
import re


def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"method not found: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"method brace not found: {signature}")
    depth = 0
    in_string = False
    escaped = False
    quote = ""
    index = brace
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
        else:
            if char in ('"', "'"):
                in_string = True
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[:start] + replacement + text[index + 1:]
        index += 1
    raise RuntimeError(f"unbalanced method: {signature}")


def patch_main(root: Path) -> None:
    path = root / "app/src/main/java/com/jianglab/babywife/MainActivity.java"
    text = path.read_text(encoding="utf-8")

    field_anchor = "    private volatile boolean playlistCacheRunning = false;"
    field_line = "    private volatile int playlistCacheScanSerial = 0;"
    if field_line not in text:
        if field_anchor not in text:
            raise RuntimeError("playlist cache field anchor missing")
        text = text.replace(field_anchor, field_anchor + "\n" + field_line, 1)

    update_method = '''    private void updatePlaylistCacheButtonVisibility() {
        if (playlistCacheButton == null) return;
        final Playlist playlist = currentPlaylist();
        final List<Song> snapshot = playlist == null
            ? new ArrayList<>()
            : new ArrayList<>(playlist.songs);
        final int scanSerial = ++playlistCacheScanSerial;

        // Cache probes may enter ContentResolver and block for minutes on
        // Xiaomi/Android 16. Never perform them while building or refreshing UI.
        playlistCacheButton.setVisibility(View.VISIBLE);
        playlistCacheButton.setEnabled(false);
        playlistCacheButton.setText("正在统计未缓存歌曲…");

        new Thread(() -> {
            int missing = 0;
            for (Song song : snapshot) {
                if (song == null || !song.isNetworkCatalog()) continue;
                if (!songHasPlayableCache(song)) missing++;
            }
            final int finalMissing = missing;
            runOnUiThread(() -> {
                if (scanSerial != playlistCacheScanSerial
                    || playlistCacheButton == null) return;
                playlistCacheButton.setVisibility(
                    finalMissing > 0 ? View.VISIBLE : View.GONE);
                playlistCacheButton.setEnabled(
                    finalMissing > 0 && !playlistCacheRunning);
                playlistCacheButton.setText(
                    "一键缓存未缓存歌曲（" + finalMissing + "）");
            });
        }, "PlaylistCacheVisibilityScan").start();
    }'''
    text = replace_method(
        text,
        "    private void updatePlaylistCacheButtonVisibility()",
        update_method,
    )

    click_method = '''    private void cacheCurrentPlaylistOneClick() {
        final Playlist playlist = currentPlaylist();
        if (playlist == null || playlist.songs.isEmpty()) {
            toast("当前歌单为空");
            return;
        }
        if (playlistCacheRunning) {
            toast("当前歌单正在缓存");
            return;
        }

        // Building the target list performs the same ContentResolver/cache
        // probes. Keep that scan and the existing strict cache workflow off UI.
        playlistCacheRunning = true;
        if (playlistCacheButton != null) {
            playlistCacheButton.setEnabled(false);
            playlistCacheButton.setText("正在统计未缓存歌曲…");
        }
        statusView.setText("正在统计未缓存歌曲：" + playlist.name);

        final List<Song> snapshot = new ArrayList<>(playlist.songs);
        new Thread(() -> {
            List<Song> targets = new ArrayList<>();
            for (Song song : snapshot) {
                if (song == null || !song.isNetworkCatalog()) continue;
                if (songHasPlayableCache(song)) continue;
                targets.add(song);
            }
            if (targets.isEmpty()) {
                runOnUiThread(() -> {
                    playlistCacheRunning = false;
                    updatePlaylistCacheButtonVisibility();
                    toast("当前歌单都已缓存");
                });
                return;
            }

            int cacheStartSerial = foregroundPlaybackSerial;
            runOnUiThread(() -> statusView.setText(
                "开始缓存未缓存歌曲：" + playlist.name + "，共 "
                    + targets.size() + " 首"));

            int done = 0;
            int skipped = 0;
            int failed = 0;
            boolean pausedForPlayback = false;
            for (int i = 0; i < targets.size(); i++) {
                if (foregroundPlaybackSerial != cacheStartSerial) {
                    pausedForPlayback = true;
                    break;
                }
                Song song = targets.get(i);
                if (song == null || !song.isNetworkCatalog()) {
                    skipped++;
                    continue;
                }
                if (songHasPlayableCache(song)) {
                    done++;
                    continue;
                }
                if (song.cacheFailed) {
                    skipped++;
                    continue;
                }
                final int index = i + 1;
                runOnUiThread(() -> statusView.setText(
                    "正在缓存 " + index + "/" + targets.size() + "：" + song.title));
                try {
                    NetworkMediaCache.CacheResult cached =
                        cachePlaylistSongWithTimeout(song, cacheStartSerial);
                    if (foregroundPlaybackSerial != cacheStartSerial) {
                        pausedForPlayback = true;
                        break;
                    }
                    song.cachedUri = cached.audioUri;
                    song.uri = cached.audioUri;
                    if (cached.catalogJson != null
                        && !cached.catalogJson.trim().isEmpty()) {
                        song.catalogJson = cached.catalogJson;
                    }
                    if (cached.sourceCode != null
                        && !cached.sourceCode.trim().isEmpty()) {
                        song.source = CatalogSearch.labelForSource(cached.sourceCode);
                    }
                    if ((song.lyric == null || song.lyric.trim().isEmpty())
                        && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                        song.lyric = cached.lyric;
                    }
                    song.cacheFailed = false;
                    song.unavailable = false;
                    song.autoUnavailable = false;
                    song.manualUnavailable = false;
                    done++;
                } catch (Exception error) {
                    if (foregroundPlaybackSerial != cacheStartSerial) {
                        pausedForPlayback = true;
                        break;
                    }
                    song.cacheFailed = true;
                    song.unavailable = true;
                    failed++;
                }
            }

            int finalDone = done;
            int finalSkipped = skipped;
            int finalFailed = failed;
            boolean finalPausedForPlayback = pausedForPlayback;
            runOnUiThread(() -> {
                playlistCacheRunning = false;
                savePlaylists();
                renderCurrentPlaylist();
                if (finalPausedForPlayback) {
                    statusView.setText("已因前台播放切换而暂停一键缓存");
                } else {
                    statusView.setText("一键缓存完成：成功 " + finalDone
                        + "，跳过 " + finalSkipped + "，新失败 " + finalFailed);
                }
            });
        }, "PlaylistCacheTargetScan").start();
    }'''
    text = replace_method(
        text,
        "    private void cacheCurrentPlaylistOneClick()",
        click_method,
    )

    forbidden = [
        "int missing = uncachedNetworkSongs(currentPlaylist()).size();",
        "List<Song> targets = uncachedNetworkSongs(playlist);",
    ]
    for item in forbidden:
        if item in text:
            raise RuntimeError(f"main-thread cache scan remains: {item}")
    for marker in (
        "PlaylistCacheVisibilityScan",
        "PlaylistCacheTargetScan",
        "playlistCacheScanSerial",
    ):
        if marker not in text:
            raise RuntimeError(f"cache scan marker missing: {marker}")
    path.write_text(text, encoding="utf-8")


def patch_version(root: Path) -> None:
    path = root / "app/build.gradle"
    text = path.read_text(encoding="utf-8")
    text, count_code = re.subn(
        r"versionCode\s+2026080124",
        "versionCode 2026080125",
        text,
        count=1,
    )
    text, count_name = re.subn(
        r'versionName\s+"2026\.08\.02\.real-device-startup-safe"',
        'versionName "2026.08.02.playlist-cache-scan-off-main"',
        text,
        count=1,
    )
    if count_code != 1 or count_name != 1:
        raise RuntimeError("startup-safe version anchors missing")
    path.write_text(text, encoding="utf-8")


def patch_checks(root: Path) -> None:
    path = root / "scripts/check_feature_requirements.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("versionCode 2026080124", "versionCode 2026080125")
    text = text.replace(
        "2026.08.02.real-device-startup-safe",
        "2026.08.02.playlist-cache-scan-off-main",
    )
    checks_anchor = "checks = {\n"
    check = '''    'playlist cache probes stay off main thread': (
        'PlaylistCacheVisibilityScan' in main
        and 'PlaylistCacheTargetScan' in main
        and 'playlistCacheScanSerial' in main
        and 'int missing = uncachedNetworkSongs(currentPlaylist()).size();' not in main
        and 'List<Song> targets = uncachedNetworkSongs(playlist);' not in main
    ),
'''
    if "'playlist cache probes stay off main thread'" not in text:
        if checks_anchor not in text:
            raise RuntimeError("feature checks anchor missing")
        text = text.replace(checks_anchor, checks_anchor + check, 1)
    path.write_text(text, encoding="utf-8")


def append_logs(root: Path) -> None:
    project = root / "PROJECT_LOG.md"
    if project.is_file():
        text = project.read_text(encoding="utf-8")
        marker = "## 2026-08-02 真机白屏：歌单缓存检查移出主线程"
        if marker not in text:
            project.write_text(text + f'''\n\n{marker}\n\n- ANR报告显示 `buildPlaylistPage -> updatePlaylistCacheButtonVisibility -> CacheStorage.exists` 在主线程经 ContentResolver 阻塞715176ms。\n- 页面构建和歌单刷新不再同步逐首检查缓存；首帧后由 `PlaylistCacheVisibilityScan` 统计并更新按钮。\n- 点击一键缓存时，待缓存列表也由 `PlaylistCacheTargetScan` 在线程中生成。\n- 搜索播放、播放源直传、非歌单替换及一分钟缓存规则未改。\n- 版本提升为 `2026080125 / 2026.08.02.playlist-cache-scan-off-main`。\n''', encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    patch_main(root)
    patch_version(root)
    patch_checks(root)
    append_logs(root)
    print("playlist_cache_main_thread_fix=applied")


if __name__ == "__main__":
    main()
