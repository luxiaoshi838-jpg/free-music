from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / "app/src/main/java/com/jianglab/babywife/MainActivity.java"
service_path = root / "app/src/main/java/com/jianglab/babywife/PlaybackControlService.java"
art_path = root / "app/src/main/java/com/jianglab/babywife/PlaybackArtworkLoader.java"
gradle_path = root / "app/build.gradle"
log_path = root / "PROJECT_LOG.md"

main = main_path.read_text(encoding="utf-8")
service = service_path.read_text(encoding="utf-8")
art = art_path.read_text(encoding="utf-8")
gradle = gradle_path.read_text(encoding="utf-8")

if "versionCode 2026080760" in gradle:
    print("v160 already applied")
    raise SystemExit(0)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)

# 1) Playlist cache status must be instant. v159's real-file verification is
# retained for playback/attachment recovery, but the visible playlist scan and
# one-click target enumeration must not query SAF once per song.
old_visibility = '''    private void updatePlaylistCacheButtonVisibility() {
        if (playlistCacheButton == null) return;
        if (playlistCacheRunning) {
            playlistCacheButton.setVisibility(View.VISIBLE);
            playlistCacheButton.setEnabled(false);
            playlistCacheButton.setText("正在缓存当前歌单…");
            return;
        }

        final Playlist playlistSnapshot = currentPlaylist();
        final int playlistIndexSnapshot = currentPlaylistIndex;
        final List<Song> songSnapshot = playlistSnapshot == null
            ? new ArrayList<>() : new ArrayList<>(playlistSnapshot.songs);
        final int requestSerial = ++playlistCacheScanSerial;

        playlistCacheButton.setVisibility(View.VISIBLE);
        playlistCacheButton.setEnabled(false);
        playlistCacheButton.setText("正在检查缓存状态…");
        try {
            playlistCacheScanExecutor.execute(() -> {
                final int missing = uncachedNetworkSongs(songSnapshot).size();
                runOnUiThread(() -> {
                    if (playlistCacheButton == null || requestSerial != playlistCacheScanSerial) return;
                    if (playlistSnapshot != currentPlaylist()
                        || playlistIndexSnapshot != currentPlaylistIndex) {
                        updatePlaylistCacheButtonVisibility();
                        return;
                    }
                    playlistCacheButton.setEnabled(true);
                    playlistCacheButton.setVisibility(missing > 0 ? View.VISIBLE : View.GONE);
                    playlistCacheButton.setText("一键缓存未缓存歌曲（" + missing + "）");
                });
            });
        } catch (RuntimeException ignored) {
            playlistCacheButton.setEnabled(true);
        }
    }'''
new_visibility = '''    private void updatePlaylistCacheButtonVisibility() {
        if (playlistCacheButton == null) return;
        if (playlistCacheRunning) {
            playlistCacheButton.setVisibility(View.VISIBLE);
            playlistCacheButton.setEnabled(false);
            playlistCacheButton.setText("正在缓存当前歌单…");
            return;
        }

        // This is deliberately a metadata/index-only pass. It never enumerates
        // the SAF cache directory, so entering a playlist cannot get stuck on
        // “正在检查缓存状态”. Real file validation still happens when playback
        // or an explicit cache attachment actually needs the file.
        List<Song> songSnapshot = new ArrayList<>(currentPlaylist().songs);
        int missing = uncachedNetworkSongs(songSnapshot).size();
        playlistCacheButton.setEnabled(true);
        playlistCacheButton.setVisibility(missing > 0 ? View.VISIBLE : View.GONE);
        playlistCacheButton.setText("一键缓存未缓存歌曲（" + missing + "）");
    }'''
main = replace_once(main, old_visibility, new_visibility, "instant playlist cache button")

main = replace_once(
    main,
    "            if (songHasPlayableCache(song)) continue;\n            result.add(song);",
    "            if (songHasRecordedCache(song)) continue;\n            result.add(song);",
    "fast uncached classification",
)
main = replace_once(
    main,
    "                if (songHasPlayableCache(song)) {\n                    done++;\n                    continue;\n                }",
    "                if (songHasRecordedCache(song)) {\n                    done++;\n                    continue;\n                }",
    "fast one-click target enumeration",
)

old_recorded = '''    private boolean songHasRecordedCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return true;
        String cached = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (!cached.isEmpty()) return true;
        String direct = song.uri == null ? "" : song.uri.trim();
        return direct.startsWith("file:") || direct.startsWith("content:");
    }'''
new_recorded = '''    private boolean songHasRecordedCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return true;
        String cached = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (!cached.isEmpty()) return true;
        String direct = song.uri == null ? "" : song.uri.trim();
        if (direct.startsWith("file:") || direct.startsWith("content:")) return true;

        // The Media3 export index is SharedPreferences-backed and therefore
        // cheap to query. Trusting its friendly URI avoids an expensive SAF
        // directory walk while still recovering the v159 red/failure flags.
        String media3Key = Media3CacheStore.keyFor(
            song.title, song.artist, song.catalogJson);
        String indexedUri = Media3PlaybackCacheIndex.friendlyUri(this, media3Key);
        if (!indexedUri.isEmpty()) {
            boolean changed = recoverCachedSongState(song, indexedUri);
            if (changed) savePlaylists();
            return true;
        }
        return false;
    }'''
main = replace_once(main, old_recorded, new_recorded, "fast recorded cache index")

# 2) Lock-screen/notification media card: keep the previous artwork while the
# next cover loads, use a dark colorized fallback instead of white, and keep
# the standard media controls limited to previous / play-pause / next. No
# favorite/heart action is added.
service = replace_once(
    service,
    "import android.graphics.Bitmap;\n",
    "import android.graphics.Bitmap;\nimport android.graphics.Color;\n",
    "notification color import",
)
service = replace_once(
    service,
    "    private static final int NOTIFICATION_ID = 1514;\n",
    "    private static final int NOTIFICATION_ID = 1514;\n    private static final int FALLBACK_MEDIA_COLOR = Color.rgb(34, 31, 40);\n",
    "dark media fallback constant",
)
service = replace_once(
    service,
    '''        artworkIdentity = next;
        artworkRequestedIdentity = "";
        artwork = null;
        artworkRequestSerial++;''',
    '''        artworkIdentity = next;
        artworkRequestedIdentity = "";
        // Keep the previous cover visible until the new one finishes loading;
        // otherwise every track change flashes a white media card.
        artworkRequestSerial++;''',
    "retain artwork during async switch",
)
old_notification_art = '''        if (artwork != null) {
            builder.setLargeIcon(artwork)
                .setColor(PlaybackArtworkLoader.averageColor(artwork));
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                builder.setColorized(true);
            }
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder.setColorized(false);
        }
        return builder.build();'''
new_notification_art = '''        int mediaColor = artwork == null
            ? FALLBACK_MEDIA_COLOR : darkMediaColor(PlaybackArtworkLoader.averageColor(artwork));
        builder.setColor(mediaColor);
        if (artwork != null) {
            // High-resolution square art is supplied to both MediaSession and
            // the notification. Android/OEM lock screens can then crop/enlarge
            // it as the media-card backdrop instead of falling back to white.
            builder.setLargeIcon(artwork);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder.setColorized(true);
        }
        return builder.build();'''
service = replace_once(service, old_notification_art, new_notification_art,
                       "dark colorized media notification")
service = replace_once(
    service,
    '''    private PendingIntent servicePendingIntent(String action, int requestCode) {''',
    '''    private int darkMediaColor(int color) {
        if (color == 0) return FALLBACK_MEDIA_COLOR;
        int red = Math.max(18, Color.red(color) * 58 / 100);
        int green = Math.max(18, Color.green(color) * 58 / 100);
        int blue = Math.max(22, Color.blue(color) * 58 / 100);
        return Color.rgb(red, green, blue);
    }

    private PendingIntent servicePendingIntent(String action, int requestCode) {''',
    "dark media color helper",
)

# Slightly larger source bitmap gives system lock-screen crop/zoom more detail.
art = replace_once(art, "    private static final int TARGET_SIZE = 960;",
                   "    private static final int TARGET_SIZE = 1280;",
                   "larger playback artwork")

# 3) New version based strictly on v159.
gradle = replace_once(
    gradle,
    "        versionCode 2026080759\n        versionName \"2026.08.07.v159-cache-state-recovery\"",
    "        versionCode 2026080760\n        versionName \"2026.08.07.v160-fast-cache-dark-media\"",
    "v160 version",
)

required = [
    "versionCode 2026080760",
    "versionName \"2026.08.07.v160-fast-cache-dark-media\"",
    "if (songHasRecordedCache(song)) continue;",
    "Media3PlaybackCacheIndex.friendlyUri(this, media3Key)",
    "FALLBACK_MEDIA_COLOR",
    "builder.setColorized(true);",
    "TARGET_SIZE = 1280",
]
combined = main + "\n" + service + "\n" + art + "\n" + gradle
for token in required:
    if token not in combined:
        raise SystemExit("missing v160 token: " + token)
if "正在检查缓存状态" in main:
    raise SystemExit("slow playlist cache checking text still present")
if "favorite" in service.lower() or "heart" in service.lower():
    raise SystemExit("unexpected favorite/heart action in PlaybackControlService")

main_path.write_text(main, encoding="utf-8")
service_path.write_text(service, encoding="utf-8")
art_path.write_text(art, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")

entry = '''\n## 2026-08-07 · v160\n- 基线：v159 `8a6314ff0570ce68a29a4e5f542b948bfa2b07b2`。\n- 歌单缓存状态改为内存/SharedPreferences 索引快速判断，不再在进入歌单时逐曲枚举 SAF 缓存目录；保留 v159 的真实文件恢复逻辑用于播放和显式挂载。\n- 锁屏/通知栏媒体卡保持上一张封面直到新封面完成加载；无封面阶段强制深色 colorized 背景，避免白底；封面缓存目标提升到 1280 px。\n- 播放控制仍仅上一首 / 播放暂停 / 下一首，不增加爱心/收藏动作。\n'''
log = log_path.read_text(encoding="utf-8")
if "## 2026-08-07 · v160" not in log:
    log_path.write_text(log.rstrip() + "\n" + entry, encoding="utf-8")

print("v160 patch applied")
