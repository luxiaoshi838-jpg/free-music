from pathlib import Path

ROOT = Path('.')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)


# MainActivity metadata propagation and cache recognition fallback.
path = ROOT / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
text = path.read_text(encoding='utf-8')

text = replace_once(text,
'''                    item.source = candidate.sourceLabel;
                    item.catalogJson = candidate.catalogJson;
                    item.cachedUri = storedUri;''',
'''                    item.source = candidate.sourceLabel;
                    item.catalogJson = candidate.catalogJson;
                    item.artworkUrl = !song.artworkUrl.isEmpty()
                        ? song.artworkUrl
                        : PlaybackArtworkLoader.extractArtworkUrl(candidate.catalogJson);
                    item.cachedUri = storedUri;''',
'persist cache artwork')

text = replace_once(text,
'''                    item.source = song.source;
                    item.catalogJson = song.catalogJson;
                    item.cachedUri = song.cachedUri;''',
'''                    item.source = song.source;
                    item.catalogJson = song.catalogJson;
                    item.artworkUrl = song.artworkUrl;
                    item.cachedUri = song.cachedUri;''',
'persist resolved artwork')

text = replace_once(text,
'''        if (commit.catalogJson != null && !commit.catalogJson.trim().isEmpty()) {
            song.catalogJson = commit.catalogJson;
        }''',
'''        if (commit.catalogJson != null && !commit.catalogJson.trim().isEmpty()) {
            song.catalogJson = commit.catalogJson;
            song.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(commit.catalogJson);
        }''',
'commit resolved artwork')

text = replace_once(text,
'''                    item.catalogJson = pendingSongCatalogJson;
                    item.uri = "";''',
'''                    item.catalogJson = pendingSongCatalogJson;
                    item.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(pendingSongCatalogJson);
                    item.uri = "";''',
'replace playlist artwork')

text = replace_once(text,
'''        target.catalogJson = pendingSongCatalogJson;
        target.uri = "";''',
'''        target.catalogJson = pendingSongCatalogJson;
        target.artworkUrl = PlaybackArtworkLoader.extractArtworkUrl(pendingSongCatalogJson);
        target.uri = "";''',
'replace target artwork')

text = replace_once(text,
'''        String uri = key.isEmpty() ? "" : CacheStorage.findAudioUri(this, key);
        song.cachedUri = uri;
        if (!uri.isEmpty()) song.uri = uri;''',
'''        String uri = key.isEmpty() ? "" : CacheStorage.findAudioUri(this, key);
        if (uri.isEmpty()) {
            String media3Key = Media3CacheStore.keyFor(
                song.title, song.artist, song.catalogJson);
            uri = Media3PlaybackCacheIndex.friendlyUri(this, media3Key);
        }
        song.cachedUri = CacheFileState.exists(this, uri) ? uri : "";
        if (!song.cachedUri.isEmpty()) song.uri = song.cachedUri;''',
'refresh friendly cache fallback')

text = replace_once(text,
'''        String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (recorded.isEmpty()) {''',
'''        attachExistingFriendlyCache(song);
        String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (recorded.isEmpty()) {''',
'playlist cache recognition')

path.write_text(text, encoding='utf-8')

# Artwork service identity must change when an explicit artwork URL appears.
path = ROOT / 'app/src/main/java/com/jianglab/babywife/PlaybackControlService.java'
text = path.read_text(encoding='utf-8')
text = replace_once(text,
'''        String next = PlaybackArtworkLoader.identity(
            title, artist, catalogJson, mediaUri);''',
'''        String next = PlaybackArtworkLoader.identity(
            title, artist, catalogJson, mediaUri)
            + "|art=" + artworkUrl.trim();''',
'artwork identity includes URL')
path.write_text(text, encoding='utf-8')

print('v155 follow-up applied')
