from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)

path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = path.read_text(encoding="utf-8")

anchor = '''    private void persistResolvedCatalogToPlaylistCopies(Song song, String originalKey) {\n        if (song == null || originalKey == null || originalKey.isEmpty()) return;\n        for (Playlist playlist : playlists) {\n            for (Song item : playlist.songs) {\n                if (item == song || item.key().equals(originalKey)) {\n                    item.source = song.source;\n                    item.catalogJson = song.catalogJson;\n                    item.artworkUrl = song.artworkUrl;\n                    item.cachedUri = song.cachedUri;\n                    item.uri = song.uri;\n                }\n            }\n        }\n    }'''
replacement = '''    private void persistResolvedCatalogToPlaylistCopies(Song song, String originalKey) {\n        if (song == null || originalKey == null || originalKey.isEmpty()) return;\n        syncReplacementMetadataToPlaylistCopies(song, originalKey);\n    }\n\n    private void syncReplacementMetadataToPlaylistCopies(Song song, String originalKey) {\n        if (song == null) return;\n        String oldKey = originalKey == null ? "" : originalKey;\n        String logical = dedupeKey(song);\n        for (Playlist playlist : playlists) {\n            for (Song item : playlist.songs) {\n                if (item == null) continue;\n                boolean sameObject = item == song;\n                boolean sameOldKey = !oldKey.isEmpty() && item.key().equals(oldKey);\n                boolean sameLogical = !logical.isEmpty() && dedupeKey(item).equals(logical);\n                if (!sameObject && !sameOldKey && !sameLogical) continue;\n\n                item.title = song.title;\n                item.artist = song.artist;\n                item.source = song.source;\n                item.catalogJson = song.catalogJson;\n                item.artworkUrl = song.artworkUrl;\n                item.cachedUri = song.cachedUri;\n                item.uri = song.uri;\n                item.lyric = song.lyric;\n                item.lyricLabel = song.lyricLabel;\n                item.unavailable = song.unavailable;\n                item.autoUnavailable = song.autoUnavailable;\n                item.manualUnavailable = song.manualUnavailable;\n                item.manualAttempt = song.manualAttempt;\n                item.cacheFailed = song.cacheFailed;\n            }\n        }\n        applyPlaylistFilter();\n        if (playlistAdapter != null) playlistAdapter.notifyDataSetChanged();\n        if (resultAdapter != null) resultAdapter.notifyDataSetChanged();\n        updatePlaylistCacheButtonVisibility();\n        savePlaylists();\n    }'''
text = replace_once(text, anchor, replacement, "playlist metadata sync helper")

# Confirm replacement: once the new title/artist/source/catalog have been assigned,
# write the complete replacement metadata back into the playlist immediately.
old = '''        target.cacheFailed = false;\n        clearPendingLyricPreview();\n        savePlaylists();\n        renderCurrentPlaylist();\n        switchPlaybackToPlaylistSong(target);'''
new = '''        target.cacheFailed = false;\n        syncReplacementMetadataToPlaylistCopies(target, originalKey);\n        clearPendingLyricPreview();\n        renderCurrentPlaylist();\n        switchPlaybackToPlaylistSong(target);'''
text = replace_once(text, old, new, "confirm replacement sync")

# Existing replacement-cache and resolved-playback paths already call
# persistResolvedCatalogToPlaylistCopies(). The helper above upgrades those calls to
# synchronize title/artist/source/catalog/artwork/cache/status as one operation.

path.write_text(text, encoding="utf-8")
