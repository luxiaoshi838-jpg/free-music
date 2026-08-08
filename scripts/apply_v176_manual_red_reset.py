from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)

path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = path.read_text(encoding="utf-8")

old_existing = '''        if (existingIndex >= 0) {\n            if (currentSong == song) switchPlaybackToPlaylist(playlist, existingIndex);\n            toast((isLocalPlaylist(playlist) ? "\\u672c\\u5730\\u6b4c\\u5355\\u5df2\\u6709\\uff1a" : "\\u5f53\\u524d\\u5728\\u7ebf\\u6b4c\\u5355\\u5df2\\u6709\\uff1a") + song.title);\n            return;\n        }'''
new_existing = '''        if (existingIndex >= 0) {\n            Song existing = playlist.songs.get(existingIndex);\n            clearManualCacheFailureState(existing);\n            if (currentSong == song) {\n                clearManualCacheFailureState(song);\n                switchPlaybackToPlaylist(playlist, existingIndex);\n            }\n            savePlaylists();\n            renderCurrentPlaylist();\n            toast((isLocalPlaylist(playlist) ? "\\u672c\\u5730\\u6b4c\\u5355\\u5df2\\u6709\\uff1a" : "\\u5f53\\u524d\\u5728\\u7ebf\\u6b4c\\u5355\\u5df2\\u6709\\uff1a") + song.title);\n            return;\n        }'''
text = replace_once(text, old_existing, new_existing, "existing manual add resets red")

old_new = '''        int addedIndex = playlist.songs.size() - 1;\n        playlistSong.unavailable = false;\n        playlistSong.cacheFailed = false;\n        savePlaylists();'''
new_new = '''        int addedIndex = playlist.songs.size() - 1;\n        clearManualCacheFailureState(playlistSong);\n        if (currentSong == song) clearManualCacheFailureState(song);\n        savePlaylists();'''
text = replace_once(text, old_new, new_new, "new manual add resets red")

helper_anchor = '''    private Song copySongForPlaylist(Song song) {'''
helper = '''    private void clearManualCacheFailureState(Song song) {\n        if (song == null) return;\n        song.unavailable = false;\n        song.autoUnavailable = false;\n        song.manualUnavailable = false;\n        song.manualAttempt = false;\n        song.cacheFailed = false;\n    }\n\n    private Song copySongForPlaylist(Song song) {'''
text = replace_once(text, helper_anchor, helper, "manual red reset helper")

path.write_text(text, encoding="utf-8")
