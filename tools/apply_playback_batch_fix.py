#!/usr/bin/env python3
from pathlib import Path
import argparse
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 1:
        return text.replace(old, new, 1)
    if count == 0 and new in text:
        return text
    raise RuntimeError(f"{label}: expected one anchor, found {count}")


def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"method anchor missing: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"method brace missing: {signature}")
    depth = 0
    in_string = False
    escaped = False
    quote = ""
    for index in range(brace, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue
        if char in ('"', "'"):
            in_string = True
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement.rstrip() + text[index + 1:]
    raise RuntimeError(f"method end missing: {signature}")


def write_compatibility_class(root: Path) -> None:
    target = root / "app/src/main/java/com/jianglab/babywife/PlaybackCompatibility.java"
    target.write_text(r'''package com.jianglab.babywife;

import android.content.Context;
import android.media.MediaCodecList;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.net.Uri;

import java.io.File;
import java.nio.ByteBuffer;
import java.util.Locale;

/** Checks whether this Android device can decode and seek a cached audio file. */
final class PlaybackCompatibility {
    private static final long MIN_DURATION_US = 60_000_000L;
    private static final long SEEK_PROBE_LIMIT_US = 30_000_000L;
    private static final int SAMPLE_PROBE_BYTES = 256 * 1024;

    private PlaybackCompatibility() {
    }

    static boolean isPlayable(File file) {
        if (file == null || !file.isFile() || file.length() <= 0L) return false;
        MediaExtractor extractor = new MediaExtractor();
        try {
            extractor.setDataSource(file.getAbsolutePath());
            return inspect(extractor);
        } catch (Throwable ignored) {
            return false;
        } finally {
            try { extractor.release(); } catch (Throwable ignored) { }
        }
    }

    static boolean isPlayable(Context context, String uriText) {
        if (context == null || uriText == null || uriText.trim().isEmpty()) return false;
        MediaExtractor extractor = new MediaExtractor();
        try {
            Uri uri = Uri.parse(uriText);
            if ("file".equalsIgnoreCase(uri.getScheme())) {
                String path = uri.getPath();
                if (path == null || path.isEmpty()) return false;
                extractor.setDataSource(path);
            } else {
                extractor.setDataSource(context, uri, null);
            }
            return inspect(extractor);
        } catch (Throwable ignored) {
            return false;
        } finally {
            try { extractor.release(); } catch (Throwable ignored) { }
        }
    }

    private static boolean inspect(MediaExtractor extractor) {
        int audioTrack = -1;
        MediaFormat audioFormat = null;
        for (int index = 0; index < extractor.getTrackCount(); index++) {
            MediaFormat format = extractor.getTrackFormat(index);
            String mime = format.getString(MediaFormat.KEY_MIME);
            if (mime != null && mime.toLowerCase(Locale.ROOT).startsWith("audio/")) {
                audioTrack = index;
                audioFormat = format;
                break;
            }
        }
        if (audioTrack < 0 || audioFormat == null) return false;

        long durationUs = audioFormat.containsKey(MediaFormat.KEY_DURATION)
            ? audioFormat.getLong(MediaFormat.KEY_DURATION) : 0L;
        if (durationUs < MIN_DURATION_US) return false;

        String mime = audioFormat.getString(MediaFormat.KEY_MIME);
        if (mime == null || mime.trim().isEmpty()) return false;
        if (!"audio/raw".equalsIgnoreCase(mime)) {
            try {
                String decoder = new MediaCodecList(MediaCodecList.REGULAR_CODECS)
                    .findDecoderForFormat(audioFormat);
                if (decoder == null || decoder.trim().isEmpty()) return false;
            } catch (Throwable ignored) {
                return false;
            }
        }

        extractor.selectTrack(audioTrack);
        if (!hasReadableSample(extractor)) return false;

        long seekTargetUs = Math.min(durationUs / 2L, SEEK_PROBE_LIMIT_US);
        if (seekTargetUs >= 5_000_000L) {
            extractor.seekTo(seekTargetUs, MediaExtractor.SEEK_TO_CLOSEST_SYNC);
            long sampleTimeUs = extractor.getSampleTime();
            if (sampleTimeUs < 0L || !hasReadableSample(extractor)) return false;
            if (seekTargetUs >= 10_000_000L && sampleTimeUs < 2_000_000L) return false;
        }
        return true;
    }

    private static boolean hasReadableSample(MediaExtractor extractor) {
        ByteBuffer buffer = ByteBuffer.allocate(SAMPLE_PROBE_BYTES);
        return extractor.readSampleData(buffer, 0) > 0;
    }
}
''', encoding="utf-8")


def patch_network(root: Path) -> None:
    path = root / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''            long actualDuration = mediaDurationMs(partial);
            if (actualDuration < MIN_AUTOMATIC_DURATION_MS) {
                if (actualDuration <= 0L) throw new IllegalStateException("设备无法识别候选音频或确认时长");
                throw new IllegalStateException("候选音频只有" + Math.max(1L, actualDuration / 1000L) + "秒");
            }

            // 不向音频文件写入歌名、歌手、专辑或其他标签；歌曲信息由歌单保存。''',
        '''            long actualDuration = mediaDurationMs(partial);
            if (actualDuration < MIN_AUTOMATIC_DURATION_MS) {
                if (actualDuration <= 0L) throw new IllegalStateException("设备无法识别候选音频或确认时长");
                throw new IllegalStateException("候选音频只有" + Math.max(1L, actualDuration / 1000L) + "秒");
            }
            if (!PlaybackCompatibility.isPlayable(partial)) {
                throw new IllegalStateException("当前设备无法稳定解码或拖动该音频格式");
            }

            // 不向音频文件写入歌名、歌手、专辑或其他标签；歌曲信息由歌单保存。''',
        "download playback validation",
    )

    text = replace_once(
        text,
        '''        }

        Exception primaryError = null;
        status(callback, "正在使用歌单原来源解析歌曲...");''',
        '''        }
        if (!requestedAudioUri.isEmpty() && CacheStorage.exists(context, requestedAudioUri)) {
            status(callback, "旧缓存无法稳定播放，正在重新匹配...");
            CacheStorage.deleteKey(context, requestedKey);
            requestedAudioUri = "";
            requestedLyric = "";
        }

        Exception primaryError = null;
        status(callback, "正在使用歌单原来源解析歌曲...");''',
        "requested invalid cache cleanup",
    )

    text = replace_once(
        text,
        '''        }

        File tempRoot = new File(context.getCacheDir(), "network_download");''',
        '''        }
        if (!existingAudioUri.isEmpty() && CacheStorage.exists(context, existingAudioUri)) {
            status(callback, "已有缓存无法稳定播放，正在重新下载...");
            CacheStorage.deleteKey(context, key);
            lyric = "";
            lyricFromCache = false;
        }

        File tempRoot = new File(context.getCacheDir(), "network_download");''',
        "resolved invalid cache cleanup",
    )

    text = replace_method(
        text,
        "    private static boolean isAcceptableCachedAudio(Context context, String uriText) {",
        r'''    private static boolean isAcceptableCachedAudio(Context context, String uriText) {
        return context != null
            && uriText != null
            && !uriText.trim().isEmpty()
            && CacheStorage.exists(context, uriText)
            && PlaybackCompatibility.isPlayable(context, uriText);
    }''',
    )

    text = replace_once(
        text,
        '''    static boolean cachedAudioExists(Context context, String uriText) {
        return CacheStorage.exists(context, uriText);
    }''',
        '''    static boolean cachedAudioExists(Context context, String uriText) {
        return isAcceptableCachedAudio(context, uriText);
    }''',
        "cached audio compatibility",
    )

    required = [
        "PlaybackCompatibility.isPlayable(partial)",
        "当前设备无法稳定解码或拖动该音频格式",
        "旧缓存无法稳定播放，正在重新匹配",
        "return isAcceptableCachedAudio(context, uriText);",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("network compatibility contract missing: " + ", ".join(missing))
    path.write_text(text, encoding="utf-8")


def patch_main(root: Path) -> None:
    path = root / "app/src/main/java/com/jianglab/babywife/MainActivity.java"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '''    private ListView playlistSongsList;
    private EditText playlistSearchInput;
    private final List<Song> playlistFilteredSongs = new ArrayList<>();''',
        '''    private ListView playlistSongsList;
    private EditText playlistSearchInput;
    private Button cachePlaylistButton;
    private final List<Song> playlistFilteredSongs = new ArrayList<>();
    private boolean playlistBatchCaching = false;''',
        "playlist cache fields",
    )

    text = replace_once(
        text,
        '''        panel.addView(playlistSongsList, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        applyPlaylistFilter();
        return panel;''',
        '''        panel.addView(playlistSongsList, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        cachePlaylistButton = makeButton("一键缓存未缓存歌曲", true);
        cachePlaylistButton.setTextSize(14);
        cachePlaylistButton.setVisibility(View.GONE);
        cachePlaylistButton.setOnClickListener(view -> cacheCurrentPlaylist());
        LinearLayout.LayoutParams cacheButtonParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(46));
        cacheButtonParams.setMargins(0, dp(8), 0, 0);
        panel.addView(cachePlaylistButton, cacheButtonParams);
        applyPlaylistFilter();
        updatePlaylistCacheButton();
        return panel;''',
        "playlist cache button",
    )

    text = replace_once(
        text,
        '''    private void renderCurrentPlaylist() {
        applyPlaylistFilter();
        renderPlaylists();
        if (statusView != null) {''',
        '''    private void renderCurrentPlaylist() {
        applyPlaylistFilter();
        renderPlaylists();
        updatePlaylistCacheButton();
        if (statusView != null) {''',
        "render cache button",
    )

    batch_methods = r'''    private List<Song> uncachedSongsInCurrentPlaylist() {
        List<Song> uncached = new ArrayList<>();
        for (Song song : currentPlaylist().songs) {
            if (song == null || !song.isNetworkCatalog()) continue;
            if (!NetworkMediaCache.cachedAudioExists(this, song.cachedUri)) uncached.add(song);
        }
        return uncached;
    }

    private void updatePlaylistCacheButton() {
        if (cachePlaylistButton == null) return;
        int count = uncachedSongsInCurrentPlaylist().size();
        if (playlistBatchCaching) {
            cachePlaylistButton.setVisibility(View.VISIBLE);
            cachePlaylistButton.setEnabled(false);
            return;
        }
        cachePlaylistButton.setEnabled(count > 0);
        cachePlaylistButton.setVisibility(count > 0 ? View.VISIBLE : View.GONE);
        cachePlaylistButton.setText(count > 0
            ? "一键缓存未缓存歌曲（" + count + "首）"
            : "一键缓存未缓存歌曲");
    }

    private void cacheCurrentPlaylist() {
        if (playlistBatchCaching) return;
        final Playlist targetPlaylist = currentPlaylist();
        final int targetPlaylistIndex = currentPlaylistIndex;
        final List<Song> pending = uncachedSongsInCurrentPlaylist();
        if (pending.isEmpty()) {
            updatePlaylistCacheButton();
            return;
        }
        playlistBatchCaching = true;
        updatePlaylistCacheButton();
        cachePlaylistButton.setText("正在缓存 0/" + pending.size());
        new Thread(() -> {
            int success = 0;
            int failed = 0;
            for (int index = 0; index < pending.size(); index++) {
                Song song = pending.get(index);
                final int progress = index + 1;
                runOnUiThread(() -> {
                    if (cachePlaylistButton != null) {
                        cachePlaylistButton.setText("正在缓存 " + progress + "/" + pending.size()
                            + "：" + song.title);
                    }
                });
                try {
                    String originalKey = song.key();
                    NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
                        this,
                        song.catalogJson,
                        true,
                        message -> runOnUiThread(() -> {
                            if (statusView != null && currentPlaylistIndex == targetPlaylistIndex) {
                                statusView.setText("批量缓存 " + progress + "/" + pending.size()
                                    + "：" + song.title + " · " + message);
                            }
                        })
                    );
                    song.cachedUri = cached.audioUri;
                    song.uri = cached.audioUri;
                    if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
                        song.catalogJson = cached.catalogJson;
                    }
                    if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
                        song.source = CatalogSearch.labelForSource(cached.sourceCode);
                    }
                    if ((song.lyric == null || song.lyric.trim().isEmpty())
                        && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                        song.lyric = cached.lyric;
                        song.lyricLabel = song.title + " · " + song.artist + " · " + song.source;
                    }
                    persistResolvedCatalogToPlaylistCopies(song, originalKey);
                    song.autoUnavailable = false;
                    song.manualUnavailable = false;
                    song.manualAttempt = false;
                    markSongUnavailable(song, false);
                    success++;
                } catch (Exception error) {
                    song.cachedUri = "";
                    song.uri = "";
                    song.autoUnavailable = true;
                    song.manualAttempt = false;
                    markSongUnavailable(song, true);
                    failed++;
                }
                savePlaylists();
                runOnUiThread(() -> {
                    if (currentPlaylistIndex == targetPlaylistIndex) {
                        applyPlaylistFilter();
                        updatePlaylistCacheButton();
                    }
                });
            }
            final int completedSuccess = success;
            final int completedFailed = failed;
            runOnUiThread(() -> {
                playlistBatchCaching = false;
                savePlaylists();
                if (currentPlaylistIndex == targetPlaylistIndex && currentPlaylist() == targetPlaylist) {
                    renderCurrentPlaylist();
                } else {
                    updatePlaylistCacheButton();
                }
                if (statusView != null) {
                    statusView.setText("一键缓存完成：成功 " + completedSuccess
                        + " 首，失败 " + completedFailed + " 首");
                }
                if (completedFailed > 0) {
                    toast("缓存失败的歌曲已标红，请点击歌曲后手动替换版本");
                } else {
                    toast("当前歌单未缓存歌曲已全部缓存完成");
                }
            });
        }).start();
    }

'''
    if batch_methods not in text:
        pos = text.find("    private void renderEmptyPlayer() {")
        if pos < 0:
            raise RuntimeError("batch insertion anchor missing")
        text = text[:pos] + batch_methods + text[pos:]

    text = replace_once(
        text,
        '''            mediaPlayer = createWakefulMediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(currentSong.uri));
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());
            mediaPlayer.prepare();''',
        '''            mediaPlayer = createWakefulMediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(currentSong.uri));
            attachPlaybackErrorHandler(mediaPlayer, currentSong);
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());
            mediaPlayer.prepare();''',
        "restore error listener",
    )

    text = replace_once(
        text,
        '''            mediaPlayer = createWakefulMediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(song.uri));
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());''',
        '''            mediaPlayer = createWakefulMediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(song.uri));
            attachPlaybackErrorHandler(mediaPlayer, song);
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());''',
        "playback error listener",
    )

    text = replace_method(
        text,
        "    private void togglePlayback() {",
        r'''    private void togglePlayback() {
        if (mediaPlayer == null) {
            if (currentSong != null) {
                playSong(currentSong);
            } else if (!currentPlaylist().songs.isEmpty()) {
                playSongFromPlaylist(0);
            } else {
                toast("请先导入或选择歌曲");
            }
            publishPlaybackControlState(true);
            return;
        }
        try {
            if (mediaPlayer.isPlaying()) {
                mediaPlayer.pause();
                playButton.setText("▶");
                saveLastSong(mediaPlayer.getCurrentPosition());
                lyricHandler.removeCallbacks(lyricTicker);
            } else {
                mediaPlayer.start();
                playButton.setText("Ⅱ");
                lyricHandler.post(lyricTicker);
            }
            publishPlaybackControlState(true);
        } catch (IllegalStateException error) {
            handlePlaybackFailure(currentSong, "播放器状态异常，已停止该音频");
        }
    }''',
    )

    playback_helpers = r'''    private void attachPlaybackErrorHandler(MediaPlayer player, Song song) {
        if (player == null) return;
        player.setOnErrorListener((failedPlayer, what, extra) -> {
            runOnUiThread(() -> handlePlaybackFailure(song,
                "音频解码或拖动失败（" + what + "/" + extra + "）"));
            return true;
        });
    }

    private void handlePlaybackFailure(Song song, String reason) {
        stopPlayback();
        if (playButton != null) playButton.setText("▶");
        if (song != null && song.isNetworkCatalog()) {
            NetworkMediaCache.deleteCatalogCache(this, song.catalogJson);
            song.cachedUri = "";
            song.uri = "";
            song.autoUnavailable = true;
            song.manualAttempt = false;
            markSongUnavailable(song, true);
            savePlaylists();
            renderCurrentPlaylist();
        }
        if (statusView != null) statusView.setText(reason + "；请手动替换歌曲版本");
        toast("该版本无法稳定播放，已移除缓存并标红");
    }

'''
    if playback_helpers not in text:
        pos = text.find("    private void togglePlayback() {")
        if pos < 0:
            raise RuntimeError("playback helper anchor missing")
        text = text[:pos] + playback_helpers + text[pos:]

    text = replace_once(
        text,
        '''        song.unavailable = false;
        savePlaylists();''',
        '''        song.unavailable = false;
        song.autoUnavailable = false;
        song.manualUnavailable = false;
        savePlaylists();''',
        "clear red on playlist add",
    )

    required = [
        "Button cachePlaylistButton",
        "一键缓存未缓存歌曲",
        "private void cacheCurrentPlaylist()",
        "markSongUnavailable(song, true);",
        "attachPlaybackErrorHandler(mediaPlayer, song);",
        "handlePlaybackFailure",
        "音频解码或拖动失败",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("main playback/batch contract missing: " + ", ".join(missing))
    path.write_text(text, encoding="utf-8")


def patch_checks_and_version(root: Path) -> None:
    checks_path = root / "scripts/check_feature_requirements.py"
    checks = checks_path.read_text(encoding="utf-8")
    checks = replace_once(
        checks,
        "network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')\n",
        "network = (root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java').read_text(encoding='utf-8')\ncompat = (root / 'app/src/main/java/com/jianglab/babywife/PlaybackCompatibility.java').read_text(encoding='utf-8')\n",
        "compat check input",
    )
    checks = replace_once(
        checks,
        "    'audio file tags untouched': ('AudioMetadataWriter.apply' not in network and '不向音频文件写入歌名' in network),\n",
        "    'device playback compatibility validation': (\n        'MediaExtractor' in compat\n        and 'MediaCodecList' in compat\n        and 'seekTo' in compat\n        and 'PlaybackCompatibility.isPlayable(partial)' in network\n        and 'return isAcceptableCachedAudio(context, uriText);' in network\n    ),\n    'playlist one-click cache and failure marking': (\n        '一键缓存未缓存歌曲' in main\n        and 'cacheCurrentPlaylist' in main\n        and 'uncachedSongsInCurrentPlaylist' in main\n        and 'markSongUnavailable(song, true)' in main\n        and '缓存失败的歌曲已标红' in main\n    ),\n    'media player error containment': (\n        'attachPlaybackErrorHandler' in main\n        and 'handlePlaybackFailure' in main\n        and 'setOnErrorListener' in main\n    ),\n    'audio file tags untouched': ('AudioMetadataWriter.apply' not in network and '不向音频文件写入歌名' in network),\n",
        "new checks",
    )
    checks = re.sub(
        r"'version bumped': 'versionCode \d+' in gradle",
        "'version bumped': 'versionCode 2026080103' in gradle",
        checks,
        count=1,
    )
    checks_path.write_text(checks, encoding="utf-8")

    gradle_path = root / "app/build.gradle"
    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = re.sub(r"versionCode\s+\d+", "versionCode 2026080103", gradle, count=1)
    gradle = re.sub(
        r'versionName\s+"[^"]+"',
        'versionName "2026.08.01.playback-compat-batch-cache"',
        gradle,
        count=1,
    )
    gradle_path.write_text(gradle, encoding="utf-8")


def append_logs(root: Path) -> None:
    project_path = root / "PROJECT_LOG.md"
    project = project_path.read_text(encoding="utf-8")
    entry = '''\n## 2026-08-01 播放兼容性与歌单一键缓存\n\n- 正常 M4A 继续支持，不按扩展名一刀切；缓存完成前检查音轨、设备解码器、开头样本与中段定位。\n- 旧缓存若只能读出时长但不能稳定解码或拖动，会自动删除并重新匹配。\n- MediaPlayer 增加错误监听，解码或拖动失败时立即释放播放器、删除异常缓存并标红歌曲，避免继续操作导致崩溃。\n- 当前歌单页面底部新增“一键缓存未缓存歌曲”，仅在存在未缓存在线歌曲时显示。\n- 批量缓存按歌曲串行执行，不改变当前播放；自动缓存失败的歌曲立即标红，便于进入播放器手动替换版本。\n'''
    if "播放兼容性与歌单一键缓存" not in project:
        project_path.write_text(project.rstrip() + "\n" + entry, encoding="utf-8")

    changelog_path = root / "docs/CHANGELOG.md"
    changelog = changelog_path.read_text(encoding="utf-8")
    entry_en = '''\n## 2026-08-01 Playback compatibility and playlist batch cache\n\n- Kept support for valid M4A files while validating the audio track, device decoder, readable samples, and mid-file seeking before accepting a cache.\n- Invalid existing caches are removed and resolved again instead of being accepted by duration metadata alone.\n- Added MediaPlayer error containment so decode or seek failures release the player, remove the broken cache, and mark the song for manual replacement.\n- Added a conditional one-click cache button at the bottom of the current playlist.\n- Batch caching runs sequentially without changing playback; automatic failures are shown in red for manual version selection.\n'''
    if "Playback compatibility and playlist batch cache" not in changelog:
        changelog_path.write_text(changelog.rstrip() + "\n" + entry_en, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    write_compatibility_class(root)
    patch_network(root)
    patch_main(root)
    patch_checks_and_version(root)
    append_logs(root)
    print("m4a_valid_files_supported=pass")
    print("device_decode_and_seek_validation=pass")
    print("playlist_batch_cache_button=pass")
    print("batch_failures_marked_red=pass")
    print("media_player_error_containment=pass")


if __name__ == "__main__":
    main()
