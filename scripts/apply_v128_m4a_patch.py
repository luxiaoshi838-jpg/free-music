from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
network_path = root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java'
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
decryptor_path = root / 'app/src/main/java/com/jianglab/babywife/SodaM4aDecryptor.java'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one match, found {count}')
    return text.replace(old, new, 1)


# Network download/cache path.
network = network_path.read_text(encoding='utf-8', newline='')
network = replace_once(
    network,
    '''        if (!requestedAudioUri.isEmpty() && CacheStorage.exists(context, requestedAudioUri)\n            && playableCachedExtension(requestedAudioUri)) {''',
    '''        if (!requestedAudioUri.isEmpty() && cachedAudioExists(context, requestedAudioUri)) {''',
    'requested cached audio validation',
)
network = replace_once(
    network,
    '''        if (!existingAudioUri.isEmpty() && CacheStorage.exists(context, existingAudioUri)\n            && playableCachedExtension(existingAudioUri)) {''',
    '''        if (!existingAudioUri.isEmpty() && cachedAudioExists(context, existingAudioUri)) {''',
    'existing cached audio validation',
)
network = replace_once(
    network,
    '''        String audioUrl = choice.audioUrl();\n        File tempRoot = new File(context.getCacheDir(), "network_download");''',
    '''        String audioUrl = choice.audioUrl();\n        ResolvedAudioAddress audioAddress = ResolvedAudioAddress.parse(audioUrl,\n            firstNonEmpty(choice.resolved.optString("play_auth"), choice.resolved.optString("playAuth"),\n                choice.resolved.optString("PlayAuth")));\n        File tempRoot = new File(context.getCacheDir(), "network_download");''',
    'resolved audio address insertion',
)
network = replace_once(
    network,
    '''        String hintedExtension = sanitizeExtension(firstNonEmpty(choice.resolved.optString("ext"), extensionFromUrl(audioUrl)));\n        File partial = new File(tempRoot, key + "." + hintedExtension + ".part");\n        File mp3Partial = new File(tempRoot, key + ".mp3.ready");''',
    '''        String hintedExtension = sanitizeExtension(firstNonEmpty(choice.resolved.optString("ext"), extensionFromUrl(audioAddress.url)));\n        File partial = new File(tempRoot, key + "." + hintedExtension + ".part");\n        File mp3Partial = new File(tempRoot, key + ".mp3.ready");\n        File decryptedPartial = new File(tempRoot, key + ".m4a.decrypted");''',
    'temporary decrypt file insertion',
)
network = replace_once(
    network,
    '''            download(audioUrl, actualSource, partial, callback);\n            if (partial.length() <= 0) throw new IllegalStateException("歌曲缓存为空");\n            String actualExtension = detectAudioExtension(partial, hintedExtension);''',
    '''            download(audioAddress.url, actualSource, partial, callback);\n            if (partial.length() <= 0) throw new IllegalStateException("歌曲缓存为空");\n            File decodedSource = partial;\n            if (SodaM4aDecryptor.isEncryptedM4a(partial)) {\n                if (audioAddress.playAuth.isEmpty()) {\n                    throw new IllegalStateException("当前 M4A 为加密文件，但来源未返回 PlayAuth");\n                }\n                status(callback, "正在解密 M4A 音频...");\n                SodaM4aDecryptor.decrypt(partial, decryptedPartial, audioAddress.playAuth);\n                decodedSource = decryptedPartial;\n            }\n            String actualExtension = detectAudioExtension(decodedSource, hintedExtension);''',
    'encrypted download handling',
)
network = replace_once(
    network,
    '''            File cacheSource = partial;\n            if ("mp3".equals(actualExtension)) {\n                AudioTranscoder.ensureMp3(partial, mp3Partial);''',
    '''            File cacheSource = decodedSource;\n            if ("mp3".equals(actualExtension)) {\n                AudioTranscoder.ensureMp3(decodedSource, mp3Partial);''',
    'decoded source selection',
)
network = replace_once(
    network,
    '''            if (partial.exists()) partial.delete();\n            if (mp3Partial.exists()) mp3Partial.delete();''',
    '''            if (partial.exists()) partial.delete();\n            if (mp3Partial.exists()) mp3Partial.delete();\n            if (decryptedPartial.exists()) decryptedPartial.delete();''',
    'decrypted temporary cleanup',
)
network = replace_once(
    network,
    '''    private static final class ResolvedChoice {''',
    '''    private static final class ResolvedAudioAddress {\n        final String url;\n        final String playAuth;\n\n        ResolvedAudioAddress(String url, String playAuth) {\n            this.url = url == null ? "" : url.trim();\n            this.playAuth = playAuth == null ? "" : playAuth.trim();\n        }\n\n        static ResolvedAudioAddress parse(String rawUrl, String explicitAuth) {\n            String raw = rawUrl == null ? "" : rawUrl.trim();\n            String auth = explicitAuth == null ? "" : explicitAuth.trim();\n            int marker = raw.indexOf("#auth=");\n            if (marker >= 0) {\n                if (auth.isEmpty()) {\n                    try {\n                        auth = java.net.URLDecoder.decode(raw.substring(marker + 6), "UTF-8");\n                    } catch (Exception ignored) {\n                        auth = raw.substring(marker + 6);\n                    }\n                }\n                raw = raw.substring(0, marker);\n            }\n            return new ResolvedAudioAddress(raw, auth);\n        }\n    }\n\n    private static final class ResolvedChoice {''',
    'resolved address class',
)
network = replace_once(
    network,
    '''    static boolean cachedAudioExists(Context context, String uriText) {\n        return CacheStorage.exists(context, uriText) && playableCachedExtension(uriText);\n    }''',
    '''    static boolean cachedAudioExists(Context context, String uriText) {\n        return CacheStorage.exists(context, uriText)\n            && playableCachedExtension(uriText)\n            && !SodaM4aDecryptor.isEncryptedM4a(context, uriText);\n    }''',
    'encrypted cached audio rejection',
)
network_path.write_text(network, encoding='utf-8', newline='')

# Do not directly prepare an old encrypted v127 cache after app restore.
main = main_path.read_text(encoding='utf-8', newline='')
main = replace_once(
    main,
    '''        if (currentSong.isNetworkCatalog()) {\n            if (currentSong.cachedUri != null && !currentSong.cachedUri.trim().isEmpty()) {\n                currentSong.uri = currentSong.cachedUri;\n            } else {''',
    '''        if (currentSong.isNetworkCatalog()) {\n            if (currentSong.cachedUri != null && !currentSong.cachedUri.trim().isEmpty()\n                && NetworkMediaCache.cachedAudioExists(this, currentSong.cachedUri)) {\n                currentSong.uri = currentSong.cachedUri;\n            } else {\n                currentSong.cachedUri = "";\n                currentSong.uri = "";''',
    'restored encrypted cache rejection',
)
main_path.write_text(main, encoding='utf-8', newline='')

# Add URI/content-provider inspection for caches created by v127.
decryptor = decryptor_path.read_text(encoding='utf-8')
decryptor = replace_once(
    decryptor,
    '''import android.util.Base64;''',
    '''import android.content.Context;\nimport android.net.Uri;\nimport android.util.Base64;''',
    'decryptor Android imports',
)
decryptor = replace_once(
    decryptor,
    '''import java.io.BufferedOutputStream;\nimport java.io.File;''',
    '''import java.io.BufferedOutputStream;\nimport java.io.ByteArrayOutputStream;\nimport java.io.File;''',
    'decryptor byte-array import',
)
decryptor = replace_once(
    decryptor,
    '''    static boolean isEncryptedM4a(File file) {''',
    '''    static boolean isEncryptedM4a(Context context, String uriText) {\n        if (context == null || uriText == null || uriText.trim().isEmpty()) return false;\n        try {\n            Uri uri = Uri.parse(uriText);\n            if ("file".equalsIgnoreCase(uri.getScheme())) {\n                return isEncryptedM4a(new File(uri.getPath()));\n            }\n            if ("content".equalsIgnoreCase(uri.getScheme())) {\n                try (java.io.InputStream input = context.getContentResolver().openInputStream(uri)) {\n                    return input != null && streamContainsEncryptionMarkers(input);\n                }\n            }\n        } catch (Exception ignored) {\n        }\n        return false;\n    }\n\n    private static boolean streamContainsEncryptionMarkers(java.io.InputStream input) throws Exception {\n        ByteArrayOutputStream output = new ByteArrayOutputStream();\n        byte[] buffer = new byte[64 * 1024];\n        long remaining = MAX_MOOV_BYTES;\n        while (remaining > 0) {\n            int count = input.read(buffer, 0, (int) Math.min(buffer.length, remaining));\n            if (count < 0) break;\n            if (count == 0) continue;\n            output.write(buffer, 0, count);\n            remaining -= count;\n        }\n        byte[] data = output.toByteArray();\n        return indexOf(data, ascii("enca"), 0, data.length) >= 0\n            && indexOf(data, ascii("senc"), 0, data.length) >= 0\n            && indexOf(data, ascii("cenc"), 0, data.length) >= 0;\n    }\n\n    static boolean isEncryptedM4a(File file) {''',
    'cached URI encryption detector',
)
decryptor_path.write_text(decryptor, encoding='utf-8')

# Version and regression checks.
gradle = root / 'app/build.gradle'
gradle_text = gradle.read_text(encoding='utf-8')
gradle_text = gradle_text.replace('versionCode 2026080127', 'versionCode 2026080128')
gradle_text = gradle_text.replace('versionName "2026.08.03.m4a-source-support"',
                                  'versionName "2026.08.03.m4a-decryption"')
gradle.write_text(gradle_text, encoding='utf-8')

check_path = root / 'scripts/check_feature_requirements.py'
check = check_path.read_text(encoding='utf-8')
check = replace_once(
    check,
    "transcoder = (root / 'app/src/main/java/com/jianglab/babywife/AudioTranscoder.java').read_text(encoding='utf-8')",
    "transcoder = (root / 'app/src/main/java/com/jianglab/babywife/AudioTranscoder.java').read_text(encoding='utf-8')\nsoda_decryptor = (root / 'app/src/main/java/com/jianglab/babywife/SodaM4aDecryptor.java').read_text(encoding='utf-8')",
    'decryptor test fixture',
)
check = replace_once(
    check,
    "    'settings width and status bar':",
    "    'encrypted soda m4a decrypted': (\n        'ResolvedAudioAddress.parse' in network\n        and '#auth=' in network\n        and 'SodaM4aDecryptor.decrypt' in network\n        and 'SodaM4aDecryptor.isEncryptedM4a(context, uriText)' in network\n        and 'AES/CTR/NoPadding' in soda_decryptor\n        and 'PlayAuth' in soda_decryptor\n        and 'enca' in soda_decryptor and 'mp4a' in soda_decryptor\n        and 'NetworkMediaCache.cachedAudioExists(this, currentSong.cachedUri)' in main\n    ),\n    'settings width and status bar':",
    'encrypted m4a requirement',
)
check = check.replace("'versionCode 2026080127'", "'versionCode 2026080128'")
check_path.write_text(check, encoding='utf-8')

changelog = root / 'docs/CHANGELOG.md'
with changelog.open('a', encoding='utf-8') as output:
    output.write('\n\n## v128 - 2026-08-03\n'
                 '- Fixed Soda Music M4A playback by extracting PlayAuth from the resolved URL and decrypting CENC/AES-CTR audio before caching.\n'
                 '- Existing encrypted M4A caches from v127 are detected as invalid and replaced on the next playback.\n')
project_log = root / 'PROJECT_LOG.md'
with project_log.open('a', encoding='utf-8') as output:
    output.write('\n\n## 2026-08-03 - Decrypt encrypted M4A before playback\n'
                 '- Confirmed the supplied sample is CENC-encrypted AAC in an M4A container.\n'
                 '- Ported the dependency library PlayAuth and AES-CTR decryption path to Android cache handling.\n'
                 '- Invalidates encrypted v127 cache entries and bumps all four brands to v128.\n')

print('Applied v128 encrypted M4A playback patch')
