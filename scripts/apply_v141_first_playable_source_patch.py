from pathlib import Path

root = Path(__file__).resolve().parents[1]
resolver_path = root / 'app/src/main/java/com/jianglab/babywife/PlayableAudioResolver.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'
project_log_path = root / 'PROJECT_LOG.md'
changelog_path = root / 'docs/CHANGELOG.md'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'v141 patch target missing: {label}')
    return text.replace(old, new, 1)


resolver = resolver_path.read_text(encoding='utf-8')
gradle = gradle_path.read_text(encoding='utf-8')
check = check_path.read_text(encoding='utf-8')
project_log = project_log_path.read_text(encoding='utf-8')
changelog = changelog_path.read_text(encoding='utf-8')

gradle = replace_once(
    gradle,
    'versionCode 2026080140\n        versionName "2026.08.04.stable-local-lyric-cache"',
    'versionCode 2026080141\n        versionName "2026.08.04.first-playable-source"',
    'version bump',
)

resolver = replace_once(
    resolver,
    '/** Resolves, downloads and validates audio using MP3 > FLAC > M4A > other priority. */\nfinal class PlayableAudioResolver {\n    private static final String[] REQUEST_FORMATS = {"mp3", "flac", "m4a", ""};',
    '/** Resolves sources in order and stops at the first candidate that passes real playback validation. */\nfinal class PlayableAudioResolver {\n    private static final String[] REQUEST_FORMATS = {""};',
    'resolver strategy and format requests',
)

resolver = replace_once(
    resolver,
    '''    private static final class Candidate {
        final JSONObject catalog;
        final String extension;
        final int priority;
        final String mimeType;

        Candidate(JSONObject catalog, String extension, int priority, String mimeType) {
            this.catalog = catalog;
            this.extension = extension;
            this.priority = priority;
            this.mimeType = mimeType == null ? "" : mimeType;
        }
    }
''',
    '''    private static final class Candidate {
        final JSONObject catalog;
        final String extension;
        final String mimeType;

        Candidate(JSONObject catalog, String extension, String mimeType) {
            this.catalog = catalog;
            this.extension = extension;
            this.mimeType = mimeType == null ? "" : mimeType;
        }
    }
''',
    'remove candidate priority',
)

resolver = replace_once(
    resolver,
    '''            for (String requestedFormat : REQUEST_FORMATS) {
                String formatLabel = requestedFormat.isEmpty()
                    ? "其他格式" : requestedFormat.toUpperCase(Locale.ROOT);
                status(callback, "正在按优先级尝试 " + formatLabel + "...");
''',
    '''            for (String requestedFormat : REQUEST_FORMATS) {
                String formatLabel = "自动格式";
                status(callback, "正在按来源顺序寻找第一个可播放资源...");
''',
    'remove format priority loop status',
)

resolver = replace_once(
    resolver,
    '''                        int priority = formatPriority(actualExtension);
                        status(callback, "候选可播放：" + displayFormat(actualExtension)
                            + "（" + Math.max(0L, probe.durationMs / 1000L) + " 秒），继续比较优先级");

                        if (best == null || priority < best.priority) {
                            if (bestFile.exists() && !bestFile.delete()) {
                                throw new IllegalStateException("无法替换更优格式候选");
                            }
                            copyFile(decodedSource, bestFile);
                            best = new Candidate(new JSONObject(catalog.toString()),
                                actualExtension, priority, probe.mimeType);
                        }
                        if (priority == 0) break outer;
''',
    '''                        status(callback, "候选可播放：" + displayFormat(actualExtension)
                            + "（" + Math.max(0L, probe.durationMs / 1000L) + " 秒），立即使用");

                        if (bestFile.exists() && !bestFile.delete()) {
                            throw new IllegalStateException("无法保存已通过校验的候选");
                        }
                        copyFile(decodedSource, bestFile);
                        best = new Candidate(new JSONObject(catalog.toString()),
                            actualExtension, probe.mimeType);
                        break outer;
''',
    'stop after first playable candidate',
)

resolver = replace_once(
    resolver,
    '''            status(callback, "已选定 " + displayFormat(best.extension)
                + "，正在写入唯一正式缓存；优先级 MP3＞FLAC＞M4A＞其他");
''',
    '''            status(callback, "已找到第一个可播放资源：" + displayFormat(best.extension)
                + "，正在写入唯一正式缓存");
''',
    'final cache status without priority',
)

resolver = replace_once(
    resolver,
    '''    private static int formatPriority(String extension) {
        String value = sanitizeExtension(extension);
        if ("mp3".equals(value)) return 0;
        if ("flac".equals(value)) return 1;
        if ("m4a".equals(value) || "mp4".equals(value)) return 2;
        return 3;
    }

''',
    '',
    'remove format priority method',
)

check = replace_once(
    check,
    '''    'mp3 source preference with source-format fallback': (
        'format", "mp3' in network
        and 'AudioTranscoder.ensureMp3' in playable_resolver
        and 'MP3＞FLAC＞M4A＞其他' in playable_resolver
        and 'detectAudioExtension' in playable_resolver
        and 'ffmpeg-kit' not in gradle.lower()
        and 'FFmpegKit' not in transcoder
        and 'libmp3lame' not in transcoder
    ),
''',
    '''    'first playable source stops further downloads': (
        'REQUEST_FORMATS = {""}' in playable_resolver
        and '正在按来源顺序寻找第一个可播放资源' in playable_resolver
        and '候选可播放：' in playable_resolver
        and '，立即使用' in playable_resolver
        and 'break outer;' in playable_resolver
        and 'formatPriority' not in playable_resolver
        and 'MP3＞FLAC＞M4A＞其他' not in playable_resolver
        and '继续比较优先级' not in playable_resolver
    ),
''',
    'replace source priority requirement',
)

check = replace_once(
    check,
    '''    'all formats require real playback verification': (
        'PlayableAudioResolver.prepare' in network
        and 'PlayableAudioResolver.cachedAudioExists' in network
        and 'REQUEST_FORMATS = {"mp3", "flac", "m4a", ""}' in playable_resolver
        and 'formatPriority' in playable_resolver
        and 'MP3＞FLAC＞M4A＞其他' in playable_resolver
        and 'AudioPlaybackVerifier.probeFile' in playable_resolver
        and 'AudioPlaybackVerifier.isPlayableUri' in playable_resolver
        and 'MediaExtractor' in playback_verifier
        and 'MediaPlayer' in playback_verifier
        and 'playableCachedExtension' not in network
    ),
''',
    '''    'first returned format requires real playback verification': (
        'PlayableAudioResolver.prepare' in network
        and 'PlayableAudioResolver.cachedAudioExists' in network
        and 'REQUEST_FORMATS = {""}' in playable_resolver
        and 'AudioPlaybackVerifier.probeFile' in playable_resolver
        and 'AudioPlaybackVerifier.isPlayableUri' in playable_resolver
        and 'MediaExtractor' in playback_verifier
        and 'MediaPlayer' in playback_verifier
        and 'playableCachedExtension' not in network
    ),
''',
    'replace all-format priority verification',
)

check = replace_once(
    check,
    "    'version bumped': 'versionCode 2026080140' in gradle,",
    "    'version bumped': 'versionCode 2026080141' in gradle,",
    'feature-check version',
)

project_log += '''

## 2026-08-04 - Stop at the first playable search source

- Removed MP3, FLAC, M4A and other-format priority rounds from search playback.
- Each catalog source is now resolved and downloaded only once using its default playable response.
- The first downloaded candidate that passes real playback validation is immediately selected.
- Remaining sources are not resolved or downloaded after a playable candidate is found.
- The selected file is still the only file written to formal cache.
'''

changelog += '''

## 2026.08.04.first-playable-source

- Search playback no longer downloads every format before choosing a result.
- Sources are tried in order and the first candidate that really plays is used immediately.
- Removed MP3/FLAC/M4A format priority and all later candidate downloads after success.
- Real playback verification and the single-formal-cache rule remain enabled.
'''

resolver_path.write_text(resolver, encoding='utf-8')
gradle_path.write_text(gradle, encoding='utf-8')
check_path.write_text(check, encoding='utf-8')
project_log_path.write_text(project_log, encoding='utf-8')
changelog_path.write_text(changelog, encoding='utf-8')

print('Applied v141 first playable source repair')
