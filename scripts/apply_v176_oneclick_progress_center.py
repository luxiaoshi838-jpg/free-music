from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


gradle = Path("app/build.gradle")
g = gradle.read_text(encoding="utf-8")
g = g.replace("versionCode 2026080875", "versionCode 2026080876", 1)
g = g.replace(
    'versionName "2026.08.08.v175-playback-cache-format-crashlog"',
    'versionName "2026.08.08.v176-oneclick-cache-progress"',
    1,
)
if "versionCode 2026080876" not in g or 'versionName "2026.08.08.v176-oneclick-cache-progress"' not in g:
    raise SystemExit("v176 version patch failed")
gradle.write_text(g, encoding="utf-8")

path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = path.read_text(encoding="utf-8")

# Keep the mode entry compact, but move its actual visual center rightward inside
# the left reservation of the search field. 20dp width is retained from v173+.
text = replace_once(
    text,
    '        searchInput.setPadding(dp(34), 0, dp(48), 0);',
    '        searchInput.setPadding(dp(42), 0, dp(48), 0);',
    "search input left reservation",
)
text = replace_once(
    text,
    '''        searchMatchModeButton.setGravity(Gravity.CENTER_HORIZONTAL | Gravity.CENTER_VERTICAL);\n        searchMatchModeButton.setTextAlignment(View.TEXT_ALIGNMENT_CENTER);\n        searchMatchModeButton.setIncludeFontPadding(false);\n        searchMatchModeButton.setPadding(0, 0, 0, 0);''',
    '''        searchMatchModeButton.setGravity(Gravity.CENTER);\n        searchMatchModeButton.setTextAlignment(View.TEXT_ALIGNMENT_CENTER);\n        searchMatchModeButton.setIncludeFontPadding(false);\n        searchMatchModeButton.setPadding(0, 0, 0, 0);\n        searchMatchModeButton.setMinWidth(0);\n        searchMatchModeButton.setMinimumWidth(0);\n        searchMatchModeButton.setMinHeight(0);\n        searchMatchModeButton.setMinimumHeight(0);''',
    "search mode true center",
)
text = replace_once(
    text,
    '''        FrameLayout.LayoutParams searchModeParams = new FrameLayout.LayoutParams(dp(20), dp(32));\n        searchModeParams.gravity = Gravity.START | Gravity.CENTER_VERTICAL;\n        searchModeParams.setMargins(dp(4), 0, 0, 0);''',
    '''        FrameLayout.LayoutParams searchModeParams = new FrameLayout.LayoutParams(dp(20), dp(32));\n        searchModeParams.gravity = Gravity.START | Gravity.CENTER_VERTICAL;\n        // 20dp entry width stays compact; 10dp left offset centers the label\n        // visually in the reserved search-mode area instead of hugging the edge.\n        searchModeParams.setMargins(dp(10), 0, 0, 0);''',
    "search mode visual offset",
)

# Always expose current/total progress as songName(current/total). Parser/download
# callback messages must not overwrite the numeric progress.
text = replace_once(
    text,
    '''                    runOnUiThread(() -> {\n                        if (statusView != null) {\n                            statusView.setText("已有缓存任务 " + index + "/" + targets.size()\n                                + "：" + song.title + "，不重复下载");\n                        }\n                    });''',
    '''                    runOnUiThread(() -> {\n                        String progress = playlistCacheProgressText(song, index, targets.size());\n                        if (statusView != null) statusView.setText(progress + " · 复用已有缓存任务");\n                        if (playlistCacheButton != null) playlistCacheButton.setText("缓存 " + index + "/" + targets.size());\n                    });''',
    "existing task progress",
)
text = replace_once(
    text,
    '''                runOnUiThread(() -> {\n                    if (statusView != null) {\n                        statusView.setText("正在缓存 " + index + "/" + targets.size()\n                            + "：" + song.title);\n                    }\n                });''',
    '''                runOnUiThread(() -> {\n                    String progress = playlistCacheProgressText(song, index, targets.size());\n                    if (statusView != null) statusView.setText(progress);\n                    if (playlistCacheButton != null) playlistCacheButton.setText("缓存 " + index + "/" + targets.size());\n                });''',
    "active task progress",
)
text = replace_once(
    text,
    '                    NetworkMediaCache.CacheResult cached = cachePlaylistSongWithTimeout(song, cacheStartSerial);',
    '                    NetworkMediaCache.CacheResult cached = cachePlaylistSongWithTimeout(song, cacheStartSerial, index, targets.size());',
    "cache progress call",
)

old_method = '''    private NetworkMediaCache.CacheResult cachePlaylistSongWithTimeout(Song song, int cacheStartSerial) throws Exception {\n        ExecutorService executor = Executors.newSingleThreadExecutor();\n        try {\n            Callable<NetworkMediaCache.CacheResult> task = () -> NetworkMediaCache.cache(\n                this,\n                song.catalogJson,\n                true,\n                message -> {\n                    if (foregroundPlaybackSerial != cacheStartSerial) {\n                        throw new IllegalStateException("\\u524d\\u53f0\\u64ad\\u653e\\u5df2\\u5207\\u6362\\uff0c\\u6682\\u505c\\u4e00\\u952e\\u7f13\\u5b58");\n                    }\n                    runOnUiThread(() -> statusView.setText(message));\n                }\n            );\n            Future<NetworkMediaCache.CacheResult> future = executor.submit(task);\n            return future.get(PLAYLIST_CACHE_TRACK_TIMEOUT_SECONDS, TimeUnit.SECONDS);\n        } catch (java.util.concurrent.TimeoutException error) {\n            throw new IllegalStateException("\\u5355\\u9996\\u7f13\\u5b58\\u8d85\\u8fc7 "\n                + PLAYLIST_CACHE_TRACK_TIMEOUT_SECONDS + " \\u79d2\\uff0c\\u5df2\\u8df3\\u8fc7");\n        } finally {\n            executor.shutdownNow();\n        }\n    }'''

new_method = '''    private String playlistCacheProgressText(Song song, int current, int total) {\n        String title = song == null || song.title == null || song.title.trim().isEmpty()\n            ? "未知歌曲" : song.title.trim();\n        return title + "（" + Math.max(0, current) + "/" + Math.max(0, total) + "）";\n    }\n\n    private NetworkMediaCache.CacheResult cachePlaylistSongWithTimeout(\n            Song song, int cacheStartSerial, int current, int total) throws Exception {\n        ExecutorService executor = Executors.newSingleThreadExecutor();\n        try {\n            Callable<NetworkMediaCache.CacheResult> task = () -> NetworkMediaCache.cache(\n                this,\n                song.catalogJson,\n                true,\n                message -> {\n                    if (foregroundPlaybackSerial != cacheStartSerial) {\n                        throw new IllegalStateException("\\u524d\\u53f0\\u64ad\\u653e\\u5df2\\u5207\\u6362\\uff0c\\u6682\\u505c\\u4e00\\u952e\\u7f13\\u5b58");\n                    }\n                    // Never let resolver/download text hide the required numeric progress.\n                    String progress = playlistCacheProgressText(song, current, total);\n                    runOnUiThread(() -> {\n                        if (statusView != null) statusView.setText(progress);\n                        if (playlistCacheButton != null) {\n                            playlistCacheButton.setText("缓存 " + current + "/" + total);\n                        }\n                    });\n                }\n            );\n            Future<NetworkMediaCache.CacheResult> future = executor.submit(task);\n            return future.get(PLAYLIST_CACHE_TRACK_TIMEOUT_SECONDS, TimeUnit.SECONDS);\n        } catch (java.util.concurrent.TimeoutException error) {\n            throw new IllegalStateException("\\u5355\\u9996\\u7f13\\u5b58\\u8d85\\u8fc7 "\n                + PLAYLIST_CACHE_TRACK_TIMEOUT_SECONDS + " \\u79d2\\uff0c\\u5df2\\u8df3\\u8fc7");\n        } finally {\n            executor.shutdownNow();\n        }\n    }'''
text = replace_once(text, old_method, new_method, "cache progress callback")

path.write_text(text, encoding="utf-8")
