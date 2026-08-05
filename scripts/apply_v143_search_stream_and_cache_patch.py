from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
catalog_path = root / 'app/src/main/java/com/jianglab/babywife/CatalogSearch.java'
quick_path = root / 'app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'
project_log_path = root / 'PROJECT_LOG.md'
changelog_path = root / 'docs/CHANGELOG.md'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'v143 patch target missing: {label}')
    return text.replace(old, new, 1)


main = main_path.read_text(encoding='utf-8')
catalog = catalog_path.read_text(encoding='utf-8')
gradle = gradle_path.read_text(encoding='utf-8')
check = check_path.read_text(encoding='utf-8')
project_log = project_log_path.read_text(encoding='utf-8')
changelog = changelog_path.read_text(encoding='utf-8')

gradle = replace_once(
    gradle,
    'versionCode 2026080142\n        versionName "2026.08.04.nonblocking-media-source"',
    'versionCode 2026080143\n        versionName "2026.08.05.search-stream-and-cache"',
    'version bump',
)

old_network_branch = '''        if (song.isNetworkCatalog()) {
            stopPlayback();
            playButton.setText("▶");
            if (!playingSearchQueue && isSongInAnyPlaylist(song)) {
                playPlaylistSongFromCacheFirst(song, playToken);
            } else if (song.cachedUri != null && !song.cachedUri.trim().isEmpty()) {
                song.uri = song.cachedUri;
                statusView.setText("已读取本次搜索缓存，正在启动播放...");
                startLocalPlayback(song, playToken, null, () -> {
                    song.cachedUri = "";
                    song.uri = "";
                    statusView.setText("本次搜索缓存无法播放，立即重新获取音频...");
                    cacheAndPlay(song, playToken);
                });
            } else {
                statusView.setText("未记录缓存，立即获取音频...");
                cacheAndPlay(song, playToken);
            }
            return;
        }
'''
new_network_branch = '''        if (song.isNetworkCatalog()) {
            stopPlayback();
            playButton.setText("▶");
            if (playingSearchQueue) {
                playSearchSongFast(song, playToken);
            } else if (isSongInAnyPlaylist(song)) {
                playPlaylistSongFromCacheFirst(song, playToken);
            } else if (song.cachedUri != null && !song.cachedUri.trim().isEmpty()) {
                song.uri = song.cachedUri;
                statusView.setText("已读取记录缓存，正在启动播放...");
                startLocalPlayback(song, playToken, null, () -> {
                    song.cachedUri = "";
                    song.uri = "";
                    statusView.setText("记录缓存无法播放，立即重新获取音频...");
                    cacheAndPlay(song, playToken);
                });
            } else {
                statusView.setText("未记录缓存，立即获取音频...");
                cacheAndPlay(song, playToken);
            }
            return;
        }
'''
main = replace_once(main, old_network_branch, new_network_branch, 'split search and playlist playback')

insert_before = '    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {'
quick_methods = '''    private void playSearchSongFast(Song song, int playToken) {
        Song playlistMatch = findPlaylistSongMatch(song);
        String playlistCache = playlistMatch == null || playlistMatch.cachedUri == null
            ? "" : playlistMatch.cachedUri.trim();
        if (!playlistCache.isEmpty()) {
            song.cachedUri = playlistCache;
            song.uri = playlistCache;
            statusView.setText("已使用歌单中的同名歌曲缓存，正在启动播放...");
            startLocalPlayback(song, playToken, null, () -> {
                song.cachedUri = "";
                song.uri = "";
                playlistMatch.cachedUri = "";
                playlistMatch.uri = "";
                savePlaylists();
                statusView.setText("歌单缓存无法播放，正在尝试搜索结果真实地址...");
                trySearchPlaybackCandidate(song, playToken, 0);
            });
            return;
        }

        String sessionCache = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (!sessionCache.isEmpty()) {
            song.uri = sessionCache;
            statusView.setText("已读取搜索歌曲缓存，正在启动播放...");
            startLocalPlayback(song, playToken, null, () -> {
                song.cachedUri = "";
                song.uri = "";
                statusView.setText("搜索缓存无法播放，正在尝试真实地址...");
                trySearchPlaybackCandidate(song, playToken, 0);
            });
            return;
        }
        trySearchPlaybackCandidate(song, playToken, 0);
    }

    private void trySearchPlaybackCandidate(Song song, int playToken, int stage) {
        if (song == null || currentSong != song || playToken != playbackRequestSerial) return;
        if (stage > 2) {
            stopPlayback();
            playButton.setText("▶");
            lyricView.setText("音频未开始播放，未启动在线歌词匹配");
            statusView.setText("搜索结果、酷我和网易云均没有可播放地址");
            toast("暂时没有找到可播放资源");
            return;
        }
        String stageLabel = stage == 0 ? "搜索结果自身来源"
            : (stage == 1 ? "酷我" : "网易云");
        statusView.setText("正在解析" + stageLabel + "的真实播放地址...");
        new Thread(() -> {
            SearchQuickPlayback.Candidate candidate = null;
            try {
                candidate = SearchQuickPlayback.resolveStage(song.catalogJson, stage);
            } catch (Exception ignored) {
            }
            SearchQuickPlayback.Candidate resolved = candidate;
            runOnUiThread(() -> {
                if (currentSong != song || playToken != playbackRequestSerial) return;
                if (resolved == null || resolved.playbackUrl.isEmpty()) {
                    trySearchPlaybackCandidate(song, playToken, stage + 1);
                    return;
                }
                song.uri = resolved.playbackUrl;
                statusView.setText("已找到" + resolved.sourceLabel
                    + "真实地址，正在在线播放；播放开始后后台保存缓存...");
                startLocalPlayback(song, playToken, () -> {
                    song.catalogJson = resolved.catalogJson;
                    song.source = resolved.sourceLabel;
                    artistView.setText(song.artist + " · " + song.source);
                    saveLastSong(0);
                    statusView.setText("正在在线播放，同时后台保存“"
                        + song.title + " - " + song.artist + "”缓存...");
                    cacheSearchPlaybackAsync(song, resolved, playToken);
                }, () -> {
                    song.uri = "";
                    statusView.setText(resolved.sourceLabel + "地址无法播放，继续下一来源...");
                    trySearchPlaybackCandidate(song, playToken, stage + 1);
                });
            });
        }, "search-address-resolver").start();
    }

    private void cacheSearchPlaybackAsync(Song song, SearchQuickPlayback.Candidate candidate,
                                          int playToken) {
        new Thread(() -> {
            try {
                String storedUri = SearchQuickPlayback.cache(
                    this, candidate, song.title, song.artist, song.album);
                runOnUiThread(() -> {
                    song.cachedUri = storedUri;
                    persistSearchCacheToPlaylistCopies(song, candidate, storedUri);
                    if (currentSong == song && playToken == playbackRequestSerial) {
                        int position = 0;
                        try {
                            if (mediaPlayer != null) position = mediaPlayer.getCurrentPosition();
                        } catch (Exception ignored) {
                        }
                        saveLastSong(position);
                        statusView.setText("当前播放：" + song.title
                            + "（缓存已保存为“" + song.title + " - " + song.artist + "”）");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (currentSong == song && playToken == playbackRequestSerial) {
                        statusView.setText("当前播放正常，但后台缓存失败：" + error.getMessage());
                    }
                });
            }
        }, "search-audio-cache").start();
    }

    private void persistSearchCacheToPlaylistCopies(Song song,
                                                     SearchQuickPlayback.Candidate candidate,
                                                     String storedUri) {
        String identity = CacheStorage.logicalIdentity(song.title, song.artist);
        boolean changed = false;
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (!identity.isEmpty()
                    && identity.equals(CacheStorage.logicalIdentity(item.title, item.artist))) {
                    item.source = candidate.sourceLabel;
                    item.catalogJson = candidate.catalogJson;
                    item.cachedUri = storedUri;
                    item.uri = storedUri;
                    item.cacheFailed = false;
                    item.autoUnavailable = false;
                    item.unavailable = false;
                    changed = true;
                }
            }
        }
        if (changed) {
            savePlaylists();
            renderCurrentPlaylist();
        }
    }

'''
if insert_before not in main:
    raise SystemExit('v143 insertion point missing: quick search methods')
main = main.replace(insert_before, quick_methods + insert_before, 1)

catalog_insert = '    private static List<Track> searchOneSource(String source, String keyword) {'
catalog_method = '''    static Track findBestExactOnSource(String source, String title, String artist) {
        String sourceCode = source == null ? "" : source.trim().toLowerCase(Locale.ROOT);
        if (sourceCode.isEmpty() || normalize(title).isEmpty()) return null;
        String keyword = isUnknownArtist(artist) ? title : title + " " + artist;
        List<Track> rows = searchOneSource(sourceCode, keyword);
        Track best = null;
        int bestScore = Integer.MIN_VALUE;
        for (Track track : rows) {
            int score = replacementScore(title, artist, track);
            if (best == null || score > bestScore) {
                best = track;
                bestScore = score;
            }
        }
        return bestScore >= 700 ? best : null;
    }

'''
if catalog_insert not in catalog:
    raise SystemExit('v143 insertion point missing: catalog source lookup')
catalog = catalog.replace(catalog_insert, catalog_method + catalog_insert, 1)

quick_source = r'''package com.jianglab.babywife;

import android.content.Context;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

import bridge.Bridge;

/**
 * Lightweight search-result playback path.
 *
 * It resolves only one address at a time, starts streaming before caching, and
 * stores the exact address that actually started playback. Playlist one-click
 * caching continues to use NetworkMediaCache and PlayableAudioResolver.
 */
final class SearchQuickPlayback {
    private static final int CONNECT_TIMEOUT_MS = 12000;
    private static final int READ_TIMEOUT_MS = 30000;
    private static final long MAX_AUDIO_BYTES = 512L * 1024L * 1024L;

    private SearchQuickPlayback() {
    }

    static final class Candidate {
        final String catalogJson;
        final String sourceCode;
        final String sourceLabel;
        final String playbackUrl;
        final String playAuth;
        final String extension;

        Candidate(String catalogJson, String sourceCode, String playbackUrl,
                  String playAuth, String extension) {
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.sourceCode = sourceCode == null ? "" : sourceCode;
            this.sourceLabel = CatalogSearch.labelForSource(this.sourceCode);
            this.playbackUrl = playbackUrl == null ? "" : playbackUrl;
            this.playAuth = playAuth == null ? "" : playAuth;
            this.extension = sanitizeExtension(extension);
        }
    }

    static Candidate resolveStage(String requestedCatalogJson, int stage) throws Exception {
        JSONObject requested = new JSONObject(requestedCatalogJson == null ? "{}" : requestedCatalogJson);
        if (stage == 0) return resolveCatalog(requested);

        String fallbackSource = stage == 1 ? "kuwo" : (stage == 2 ? "netease" : "");
        if (fallbackSource.isEmpty()) return null;
        String currentSource = requested.optString("source", "").trim().toLowerCase(Locale.ROOT);
        if (fallbackSource.equals(currentSource)) return null;

        CatalogSearch.Track alternative = CatalogSearch.findBestExactOnSource(
            fallbackSource,
            requested.optString("name", requested.optString("title", "")),
            requested.optString("artist", requested.optString("singer", ""))
        );
        if (alternative == null) return null;
        return resolveCatalog(new JSONObject(alternative.rawJson));
    }

    private static Candidate resolveCatalog(JSONObject catalog) throws Exception {
        String source = catalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
        String id = catalog.optString("id", "").trim();
        if (source.isEmpty() || id.isEmpty()) return null;

        JSONObject response = new JSONObject(Bridge.resolve(catalog.toString()));
        if (!response.optBoolean("ok", false)) return null;
        JSONObject data = response.optJSONObject("data");
        if (data == null) return null;
        String rawUrl = data.optString("url", "").trim();
        if (rawUrl.isEmpty()) return null;

        String playAuth = firstNonEmpty(data.optString("play_auth"),
            data.optString("playAuth"), data.optString("PlayAuth"));
        int authMarker = rawUrl.indexOf("#auth=");
        if (authMarker >= 0) {
            if (playAuth.isEmpty()) {
                try {
                    playAuth = java.net.URLDecoder.decode(rawUrl.substring(authMarker + 6), "UTF-8");
                } catch (Exception ignored) {
                    playAuth = rawUrl.substring(authMarker + 6);
                }
            }
            rawUrl = rawUrl.substring(0, authMarker);
        }

        data.put("source", source);
        if (data.optString("id", "").trim().isEmpty()) data.put("id", id);
        copyIfMissing(data, catalog, "name");
        copyIfMissing(data, catalog, "artist");
        copyIfMissing(data, catalog, "album");
        String extension = firstNonEmpty(data.optString("ext"), extensionFromUrl(rawUrl), "audio");
        return new Candidate(data.toString(), source, rawUrl, playAuth, extension);
    }

    static String cache(Context context, Candidate candidate, String title,
                        String artist, String album) throws Exception {
        if (context == null || candidate == null || candidate.playbackUrl.isEmpty()) {
            throw new IllegalArgumentException("搜索歌曲缓存参数无效");
        }
        String key = NetworkMediaCache.cacheKeyForCatalog(candidate.catalogJson);
        if (key.isEmpty()) throw new IllegalStateException("搜索歌曲缓存键无效");

        File tempRoot = new File(context.getCacheDir(), "search_stream_cache");
        if (!tempRoot.exists() && !tempRoot.mkdirs()) {
            throw new IllegalStateException("无法创建搜索歌曲临时缓存目录");
        }
        File partial = new File(tempRoot, key + ".part");
        File decrypted = new File(tempRoot, key + ".decrypted");
        try {
            download(candidate, partial);
            if (!partial.isFile() || partial.length() <= 0) {
                throw new IllegalStateException("搜索歌曲下载文件为空");
            }

            File source = partial;
            if (SodaM4aDecryptor.isEncryptedM4a(partial)) {
                if (candidate.playAuth.isEmpty()) {
                    throw new IllegalStateException("加密 M4A 缺少 PlayAuth");
                }
                SodaM4aDecryptor.decrypt(partial, decrypted, candidate.playAuth);
                source = decrypted;
            }

            AudioPlaybackVerifier.Probe probe = AudioPlaybackVerifier.probeFile(source);
            String extension = detectExtension(source, candidate.extension, probe.mimeType);
            String storedUri = CacheStorage.storeAudio(context, key, extension, source,
                title, artist, album, candidate.catalogJson);
            if (!CacheStorage.exists(context, storedUri)) {
                CacheStorage.deleteKey(context, key);
                throw new IllegalStateException("搜索歌曲缓存写入后不存在");
            }
            CacheStorage.deleteOtherSongCaches(context, title, artist, key);
            return storedUri;
        } finally {
            if (partial.exists()) partial.delete();
            if (decrypted.exists()) decrypted.delete();
        }
    }

    private static void download(Candidate candidate, File output) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(candidate.playbackUrl).openConnection();
        connection.setInstanceFollowRedirects(true);
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setRequestProperty("User-Agent", "Mozilla/5.0");
        if ("netease".equals(candidate.sourceCode)) {
            connection.setRequestProperty("Referer", "https://music.163.com/");
        } else if ("kuwo".equals(candidate.sourceCode)) {
            connection.setRequestProperty("Referer", "https://www.kuwo.cn/");
        }
        int code = connection.getResponseCode();
        if (code < 200 || code >= 400) {
            connection.disconnect();
            throw new IllegalStateException("音频下载响应异常：HTTP " + code);
        }
        long total = 0L;
        try (InputStream input = new BufferedInputStream(connection.getInputStream());
             OutputStream stream = new BufferedOutputStream(new FileOutputStream(output))) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                if (read == 0) continue;
                total += read;
                if (total > MAX_AUDIO_BYTES) {
                    throw new IllegalStateException("音频文件超过缓存大小限制");
                }
                stream.write(buffer, 0, read);
            }
        } finally {
            connection.disconnect();
        }
    }

    private static String detectExtension(File file, String fallback, String mimeType) {
        if (AudioTranscoder.isMp3(file)) return "mp3";
        byte[] header = new byte[96];
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            int count = input.read(header);
            if (count >= 4) {
                String first4 = new String(header, 0, 4, StandardCharsets.ISO_8859_1);
                if ("fLaC".equals(first4)) return "flac";
                if ("OggS".equals(first4)) return "ogg";
                if ("RIFF".equals(first4) && count >= 12
                    && "WAVE".equals(new String(header, 8, 4, StandardCharsets.ISO_8859_1))) return "wav";
            }
            if (count >= 8 && "ftyp".equals(
                new String(header, 4, 4, StandardCharsets.ISO_8859_1))) return "m4a";
        } catch (Exception ignored) {
        }
        String mime = mimeType == null ? "" : mimeType.toLowerCase(Locale.ROOT);
        if (mime.contains("flac")) return "flac";
        if (mime.contains("mpeg")) return "mp3";
        if (mime.contains("mp4") || mime.contains("m4a")) return "m4a";
        if (mime.contains("ogg")) return "ogg";
        if (mime.contains("wav")) return "wav";
        return sanitizeExtension(fallback);
    }

    private static String extensionFromUrl(String url) {
        if (url == null) return "";
        String clean = url;
        int query = clean.indexOf('?');
        if (query >= 0) clean = clean.substring(0, query);
        int slash = clean.lastIndexOf('/');
        int dot = clean.lastIndexOf('.');
        return dot > slash ? clean.substring(dot + 1) : "";
    }

    private static String sanitizeExtension(String value) {
        String extension = value == null ? "" : value.toLowerCase(Locale.ROOT)
            .replaceAll("[^a-z0-9]", "");
        if (extension.isEmpty()) return "audio";
        return extension.length() > 12 ? extension.substring(0, 12) : extension;
    }

    private static void copyIfMissing(JSONObject target, JSONObject source, String key) {
        if (!target.optString(key, "").trim().isEmpty()) return;
        String value = source.optString(key, "").trim();
        if (!value.isEmpty()) {
            try {
                target.put(key, value);
            } catch (Exception ignored) {
            }
        }
    }

    private static String firstNonEmpty(String... values) {
        if (values == null) return "";
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) return value.trim();
        }
        return "";
    }
}
'''
quick_path.write_text(quick_source, encoding='utf-8')

check = replace_once(
    check,
    "playback_verifier = (root / 'app/src/main/java/com/jianglab/babywife/AudioPlaybackVerifier.java').read_text(encoding='utf-8')\n",
    "playback_verifier = (root / 'app/src/main/java/com/jianglab/babywife/AudioPlaybackVerifier.java').read_text(encoding='utf-8')\nquick_playback = (root / 'app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java').read_text(encoding='utf-8')\n",
    'feature-check quick playback source',
)
check = replace_once(
    check,
    "    'version bumped': 'versionCode 2026080142' in gradle,",
    '''    'search playback streams first and caches same address in background': (
        'if (playingSearchQueue)' in main
        and 'playSearchSongFast(song, playToken);' in main
        and 'trySearchPlaybackCandidate(song, playToken, 0);' in main
        and 'startLocalPlayback(song, playToken, () -> {' in main
        and 'cacheSearchPlaybackAsync(song, resolved, playToken);' in main
        and '"search-address-resolver"' in main
        and '"search-audio-cache"' in main
        and 'SearchQuickPlayback.resolveStage' in main
        and 'SearchQuickPlayback.cache' in main
    ),
    'search playback reuses playlist cache and keeps friendly filename': (
        'findPlaylistSongMatch(song)' in main
        and '已使用歌单中的同名歌曲缓存' in main
        and 'CacheStorage.logicalIdentity(song.title, song.artist)' in main
        and 'item.cachedUri = storedUri;' in main
        and 'CacheStorage.storeAudio(context, key, extension, source' in quick_playback
        and 'String base = record.title + " - " + record.artist;' in cache
    ),
    'search fallback is selected source then kuwo then netease': (
        'stage == 0' in quick_playback
        and 'stage == 1 ? "kuwo"' in quick_playback
        and 'stage == 2 ? "netease"' in quick_playback
        and 'findBestExactOnSource' in catalog
        and 'replacementScore(title, artist, track)' in catalog
        and 'formatPriority' not in quick_playback
    ),
    'playlist one-click cache remains full cache path': (
        'cacheCurrentPlaylistOneClick' in main
        and 'NetworkMediaCache.cache(' in main[main.find('private void cacheCurrentPlaylistOneClick'):]
        and 'PlayableAudioResolver.prepare' in network
    ),
    'version bumped': 'versionCode 2026080143' in gradle,''',
    'feature-check v143 assertions',
)

project_log += '''

## 2026-08-05 - Separate instant search playback from playlist bulk caching

- Search-result taps now reuse an existing same-title-and-artist playlist cache when available.
- Without cache, the selected catalog address is streamed immediately; only on playback failure does the app try Kuwo and then NetEase.
- The exact address that actually started playback is downloaded in the background and stored with the existing `title - artist.ext` filename rule.
- Completed search caches are synchronized to matching playlist entries so adding the search result later does not require another download.
- Playlist one-click caching keeps the full NetworkMediaCache/PlayableAudioResolver validation workflow.
'''

changelog += '''

## 2026.08.05.search-stream-and-cache

- Search results start streaming from the selected source without waiting for a full download.
- Failed selected-source playback falls back only to Kuwo and then NetEase.
- The exact successfully played address is cached in the background as `song title - artist.ext`.
- Search playback reuses matching playlist cache records and synchronizes new cache URIs back to matching playlist songs.
- Playlist one-click caching remains unchanged and still performs full download and validation.
'''

main_path.write_text(main, encoding='utf-8')
catalog_path.write_text(catalog, encoding='utf-8')
gradle_path.write_text(gradle, encoding='utf-8')
check_path.write_text(check, encoding='utf-8')
project_log_path.write_text(project_log, encoding='utf-8')
changelog_path.write_text(changelog, encoding='utf-8')
print('Applied v143 search streaming plus background cache split')
