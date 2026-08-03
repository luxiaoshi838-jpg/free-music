from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
cache_path = root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java'
check_path = root / 'scripts/check_feature_requirements.py'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) == 1:
        return text.replace(old, new, 1)
    pattern = r'\r?\n'.join(re.escape(part) for part in old.split('\n'))
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise SystemExit(f'{label}: expected one match, found {len(matches)}')
    match = matches[0]
    newline = '\r\n' if '\r\n' in match.group(0) else '\n'
    return text[:match.start()] + new.replace('\n', newline) + text[match.end():]


with cache_path.open('r', encoding='utf-8', newline='') as stream:
    cache = stream.read()

cache = replace_once(
    cache,
    '''            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            DocumentEntry audio = findDocumentAudioForKey(context, tree, key, existing);
            DocumentEntry lyric = findDocumentLyricForKey(context, tree, key, existing);
            if (audio != null) {
                String ext = extensionOf(audio.name);
                String desired = friendlyBase(record) + "." + ext;
                if (!desired.equals(audio.name)) moveDocument(context, tree, audio, desired, audioMime(ext));
                record.audioFile = desired;
            } else if (existing != null) {
                record.audioFile = existing.audioFile;
            }
            if (lyric != null) {
                String desired = friendlyBase(record) + ".lrc";
                if (!desired.equals(lyric.name)) moveDocument(context, tree, lyric, desired, "text/plain");
                record.lyricFile = desired;
            } else if (existing != null) {
                record.lyricFile = existing.lyricFile;
            }''',
    '''            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            DocumentEntry audio = findDocumentAudioForKey(context, tree, key, existing);
            DocumentEntry lyric = findDocumentLyricForKey(context, tree, key, existing);
            String friendly = friendlyBaseForTree(context, tree, record, existing);
            if (audio != null) {
                String ext = extensionOf(audio.name);
                String desired = friendly + "." + ext;
                if (!desired.equals(audio.name)) moveDocument(context, tree, audio, desired, audioMime(ext));
                record.audioFile = desired;
            } else if (existing != null) {
                record.audioFile = existing.audioFile;
            }
            if (lyric != null) {
                String desired = friendly + ".lrc";
                if (!desired.equals(lyric.name)) moveDocument(context, tree, lyric, desired, "text/plain");
                record.lyricFile = desired;
            } else if (existing != null) {
                record.lyricFile = existing.lyricFile;
            }''',
    'tree friendly-name migration',
)

cache = replace_once(
    cache,
    '''        MetadataRecord existing = readMetadataFromInternal(root, key);
        File audio = findInternalAudioForKey(root, key, existing);
        File lyric = findInternalLyricForKey(root, key, existing);
        if (audio != null) {
            String ext = extensionOf(audio.getName());
            String desired = friendlyBase(record) + "." + ext;
            File target = new File(root, desired);
            if (!desired.equals(audio.getName())) moveFile(audio, target);
            record.audioFile = desired;
        } else if (existing != null) {
            record.audioFile = existing.audioFile;
        }
        if (lyric != null) {
            String desired = friendlyBase(record) + ".lrc";
            File target = new File(root, desired);
            if (!desired.equals(lyric.getName())) moveFile(lyric, target);
            record.lyricFile = desired;
        } else if (existing != null) {
            record.lyricFile = existing.lyricFile;
        }''',
    '''        MetadataRecord existing = readMetadataFromInternal(root, key);
        File audio = findInternalAudioForKey(root, key, existing);
        File lyric = findInternalLyricForKey(root, key, existing);
        String friendly = friendlyBaseForInternal(root, record, existing);
        if (audio != null) {
            String ext = extensionOf(audio.getName());
            String desired = friendly + "." + ext;
            File target = new File(root, desired);
            if (!desired.equals(audio.getName())) moveFile(audio, target);
            record.audioFile = desired;
        } else if (existing != null) {
            record.audioFile = existing.audioFile;
        }
        if (lyric != null) {
            String desired = friendly + ".lrc";
            File target = new File(root, desired);
            if (!desired.equals(lyric.getName())) moveFile(lyric, target);
            record.lyricFile = desired;
        } else if (existing != null) {
            record.lyricFile = existing.lyricFile;
        }''',
    'internal friendly-name migration',
)

cache = replace_once(
    cache,
    '''            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            if (existing != null) record.audioFile = existing.audioFile;
            removeDocumentsForKey(context, tree, key, true, false, false);
            String name = friendlyBase(record) + ".lrc";''',
    '''            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            if (existing != null) record.audioFile = existing.audioFile;
            String friendly = friendlyBaseForTree(context, tree, record, existing);
            removeDocumentsForKey(context, tree, key, true, false, false);
            String name = friendly + ".lrc";''',
    'tree lyric filename',
)

cache = replace_once(
    cache,
    '''        MetadataRecord existing = readMetadataFromInternal(root, key);
        if (existing != null) record.audioFile = existing.audioFile;
        removeInternalForKey(root, key, true, false, false);
        String name = friendlyBase(record) + ".lrc";''',
    '''        MetadataRecord existing = readMetadataFromInternal(root, key);
        if (existing != null) record.audioFile = existing.audioFile;
        String friendly = friendlyBaseForInternal(root, record, existing);
        removeInternalForKey(root, key, true, false, false);
        String name = friendly + ".lrc";''',
    'internal lyric filename',
)

cache = replace_once(
    cache,
    '''        String safeExtension = sanitizeExtension(extension);
        MetadataRecord record = metadata(key, title, artist, album, catalogJson);
        String fileName = friendlyBase(record) + "." + safeExtension;
        Uri tree = selectedTree(context);''',
    '''        String safeExtension = sanitizeExtension(extension);
        MetadataRecord record = metadata(key, title, artist, album, catalogJson);
        Uri tree = selectedTree(context);''',
    'remove global audio filename',
)

cache = replace_once(
    cache,
    '''            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            if (existing != null) record.lyricFile = existing.lyricFile;
            removeDocumentsForKey(context, tree, key, false, true, false);
            Uri target = createOrReplaceDocument(context, tree, fileName, audioMime(safeExtension));''',
    '''            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            if (existing != null) record.lyricFile = existing.lyricFile;
            String fileName = friendlyBaseForTree(context, tree, record, existing) + "." + safeExtension;
            removeDocumentsForKey(context, tree, key, false, true, false);
            Uri target = createOrReplaceDocument(context, tree, fileName, audioMime(safeExtension));''',
    'tree audio filename',
)

cache = replace_once(
    cache,
    '''        MetadataRecord existing = readMetadataFromInternal(root, key);
        if (existing != null) record.lyricFile = existing.lyricFile;
        removeInternalForKey(root, key, false, true, false);
        File target = new File(root, fileName);''',
    '''        MetadataRecord existing = readMetadataFromInternal(root, key);
        if (existing != null) record.lyricFile = existing.lyricFile;
        String fileName = friendlyBaseForInternal(root, record, existing) + "." + safeExtension;
        removeInternalForKey(root, key, false, true, false);
        File target = new File(root, fileName);''',
    'internal audio filename',
)

cache = replace_once(
    cache,
    '''    private static String friendlyBase(MetadataRecord record) {
        String shortKey = record.key.length() >= 8 ? record.key.substring(0, 8) : record.key;
        String base = record.title + " - " + record.artist + " [" + shortKey + "]";
        if (base.length() > 150) base = base.substring(0, 150).trim();
        return base;
    }

    private static String metadataName(String key) {''',
    '''    private static String friendlyBase(MetadataRecord record) {
        String base = record.title + " - " + record.artist;
        if (base.length() > 140) base = base.substring(0, 140).trim();
        return base;
    }

    private static String friendlyBaseForInternal(File root, MetadataRecord record,
                                                  MetadataRecord existing) {
        Set<String> occupied = new HashSet<>();
        File[] files = root == null ? null : root.listFiles();
        if (files != null) {
            for (File file : files) {
                if (!file.isFile()) continue;
                String name = file.getName();
                if (isMetadataName(name) || name.endsWith(".part") || name.endsWith(".move_part")) continue;
                if (existing != null && (name.equals(existing.audioFile) || name.equals(existing.lyricFile))) continue;
                occupied.add(fileBase(name).toLowerCase(Locale.ROOT));
            }
        }
        return chooseFriendlyBase(record, existing, occupied);
    }

    private static String friendlyBaseForTree(Context context, Uri tree, MetadataRecord record,
                                              MetadataRecord existing) throws Exception {
        Set<String> occupied = new HashSet<>();
        for (DocumentEntry entry : listDocumentsStrict(context, tree, true)) {
            String name = entry.name;
            if (isMetadataName(name) || name.endsWith(".part") || name.endsWith(".move_part")) continue;
            if (existing != null && (name.equals(existing.audioFile) || name.equals(existing.lyricFile))) continue;
            occupied.add(fileBase(name).toLowerCase(Locale.ROOT));
        }
        return chooseFriendlyBase(record, existing, occupied);
    }

    private static String chooseFriendlyBase(MetadataRecord record, MetadataRecord existing,
                                             Set<String> occupied) {
        String plain = friendlyBase(record);
        String current = existingFriendlyBase(plain, existing);
        if (!current.isEmpty() && !occupied.contains(current.toLowerCase(Locale.ROOT))) return current;
        for (int index = 1; index <= 9999; index++) {
            String candidate = index == 1 ? plain : plain + " (" + index + ")";
            if (!occupied.contains(candidate.toLowerCase(Locale.ROOT))) return candidate;
        }
        throw new IllegalStateException("歌曲缓存文件名冲突过多");
    }

    private static String existingFriendlyBase(String plain, MetadataRecord existing) {
        if (existing == null) return "";
        String audioBase = fileBase(existing.audioFile);
        if (isFriendlyVariant(plain, audioBase)) return audioBase;
        String lyricBase = fileBase(existing.lyricFile);
        return isFriendlyVariant(plain, lyricBase) ? lyricBase : "";
    }

    private static boolean isFriendlyVariant(String plain, String candidate) {
        if (candidate == null || candidate.isEmpty()) return false;
        if (candidate.equals(plain)) return true;
        if (!candidate.startsWith(plain + " (") || !candidate.endsWith(")")) return false;
        String number = candidate.substring(plain.length() + 2, candidate.length() - 1);
        if (number.isEmpty()) return false;
        for (int i = 0; i < number.length(); i++) {
            if (!Character.isDigit(number.charAt(i))) return false;
        }
        return true;
    }

    private static String fileBase(String name) {
        if (name == null || name.isEmpty()) return "";
        int dot = name.lastIndexOf('.');
        return dot > 0 ? name.substring(0, dot) : name;
    }

    private static String metadataName(String key) {''',
    'friendly filename helpers',
)

with cache_path.open('w', encoding='utf-8', newline='') as stream:
    stream.write(cache)

check = check_path.read_text(encoding='utf-8')
check = replace_once(
    check,
    '''    'friendly cache filenames': (
        'friendlyBase' in cache
        and '" - " + record.artist' in cache
        and 'record.audioFile' in cache
        and 'record.lyricFile' in cache
        and 'META_PREFIX = ".babywife_"' in cache
    ),''',
    '''    'friendly cache filenames': (
        'friendlyBase' in cache
        and 'record.title + " - " + record.artist' in cache
        and '" [" + shortKey + "]"' not in cache
        and 'friendlyBaseForInternal' in cache
        and 'friendlyBaseForTree' in cache
        and 'plain + " (" + index + ")"' in cache
        and 'record.audioFile' in cache
        and 'record.lyricFile' in cache
        and 'META_PREFIX = ".babywife_"' in cache
    ),''',
    'friendly filename regression check',
)
check_path.write_text(check, encoding='utf-8')

with (root / 'docs/CHANGELOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- Cache audio and lyric files now use `歌曲名 - 歌手` without an opaque hash suffix; true name collisions use `(2)`, `(3)`, etc.\n')
with (root / 'PROJECT_LOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- Corrected user-visible cache filenames from `歌曲名 - 歌手 [哈希]` to `歌曲名 - 歌手`; old managed cache names migrate on the next access, with numeric suffixes only for real collisions.\n')

print('Applied v128 cache filename patch')
