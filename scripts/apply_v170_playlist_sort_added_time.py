from pathlib import Path
import re

main = Path('app/src/main/java/com/jianglab/babywife/MainActivity.java')
text = main.read_text(encoding='utf-8')

gradle = Path('app/build.gradle')
g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode 2026080869', 'versionCode 2026080870')
g = g.replace('versionName "2026.08.08.v169-replacement-cache-fast-navigation"',
              'versionName "2026.08.08.v170-playlist-sort-added-time"')
gradle.write_text(g, encoding='utf-8')

# Persist the actual time a song joins a playlist. A value of 0 means a
# pre-v170 historical item whose exact add time is unknowable.
if '        long addedAt;\n' not in text:
    anchor = '        String cachedUri;\n'
    if anchor not in text:
        raise SystemExit('Song cachedUri field anchor missing')
    text = text.replace(anchor, anchor + '        long addedAt;\n', 1)

if '            this.addedAt = 0L;\n' not in text:
    anchor = '            this.cachedUri = cachedUri == null ? "" : cachedUri;\n'
    if anchor not in text:
        raise SystemExit('Song constructor cachedUri anchor missing')
    text = text.replace(anchor, anchor + '            this.addedAt = 0L;\n', 1)

if '                object.put("addedAt", addedAt);\n' not in text:
    anchor = '                object.put("cachedUri", cachedUri);\n'
    if anchor not in text:
        raise SystemExit('Song toJson cachedUri anchor missing')
    text = text.replace(anchor, anchor + '                object.put("addedAt", addedAt);\n', 1)

if '            song.addedAt = Math.max(0L, object.optLong("addedAt", 0L));\n' not in text:
    anchor = '            song.cacheFailed = object.optBoolean("cacheFailed", false);\n'
    if anchor not in text:
        raise SystemExit('Song fromJson cacheFailed anchor missing')
    text = text.replace(anchor, anchor + '            song.addedAt = Math.max(0L, object.optLong("addedAt", 0L));\n', 1)

# Manual add: the timestamp is the moment the song is actually appended to
# this playlist, not the search/result creation time.
manual_anchor = '        playlist.songs.add(playlistSong);\n        int addedIndex = playlist.songs.size() - 1;\n'
manual_new = ('        playlist.songs.add(playlistSong);\n'
              '        playlistSong.addedAt = System.currentTimeMillis();\n'
              '        int addedIndex = playlist.songs.size() - 1;\n')
if manual_new not in text:
    if manual_anchor not in text:
        raise SystemExit('manual playlist add anchor missing')
    text = text.replace(manual_anchor, manual_new, 1)

# Local-file additions are also real playlist-add events.
folder_anchor = '                localPlaylist().songs.add(song);\n                added++;\n'
folder_new = ('                song.addedAt = System.currentTimeMillis();\n'
              '                localPlaylist().songs.add(song);\n'
              '                added++;\n')
if folder_new not in text and folder_anchor in text:
    text = text.replace(folder_anchor, folder_new, 1)

single_local_anchor = '        localPlaylist().songs.add(song);\n        return true;\n'
single_local_new = ('        song.addedAt = System.currentTimeMillis();\n'
                    '        localPlaylist().songs.add(song);\n'
                    '        return true;\n')
if single_local_new not in text and single_local_anchor in text:
    text = text.replace(single_local_anchor, single_local_new, 1)

# Every song from one imported playlist is one import batch and therefore gets
# exactly the same add timestamp. This deliberately applies to both URL and CSV
# playlist imports. Existing v169 code has two playlists.add(imported) sites.
if 'stampImportedPlaylistBatch(imported);' not in text:
    pattern = re.compile(r'(?m)^(\s*)playlists\.add\(imported\);$')
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        raise SystemExit(f'expected at least 2 imported playlist append sites, got {len(matches)}')
    text = pattern.sub(lambda m: m.group(1) + 'stampImportedPlaylistBatch(imported);\n' + m.group(1) + 'playlists.add(imported);', text)

# Keep the existing arrow glyph/style exactly; only append two options.
old_options = '        final String[] options = {"歌名↑", "歌名↓", "歌手↑", "歌手↓"};\n'
new_options = '        final String[] options = {"歌名↑", "歌名↓", "歌手↑", "歌手↓", "添加时间↑", "添加时间↓"};\n'
if old_options in text:
    text = text.replace(old_options, new_options, 1)
elif new_options not in text:
    raise SystemExit('playlist sort option anchor missing')

# Replace only the sorter/helper region. English/Latin stays before Han for
# both arrows; the arrow changes order within each script group. Add-time ties
# always use ascending song name, so one imported batch is name-sorted.
start = text.find('    private void sortCurrentPlaylist(int mode, String label) {')
end = text.find('    private String playlistSortText(String value) {', start)
if start < 0 or end < 0:
    raise SystemExit('sortCurrentPlaylist region missing')
helper_end = text.find('\n    }', end)
if helper_end < 0:
    raise SystemExit('playlistSortText end missing')
helper_end += len('\n    }')

replacement = r'''    private void sortCurrentPlaylist(int mode, String label) {
        Playlist playlist = currentPlaylist();
        if (playlist.songs.size() < 2) {
            toast("当前歌单无需排序");
            return;
        }
        final boolean byAddedTime = mode == 4 || mode == 5;
        final boolean byArtist = mode == 2 || mode == 3;
        final boolean descending = mode == 1 || mode == 3 || mode == 5;
        final java.text.Collator collator = java.text.Collator.getInstance(java.util.Locale.CHINA);
        collator.setStrength(java.text.Collator.PRIMARY);

        Collections.sort(playlist.songs, new Comparator<Song>() {
            @Override
            public int compare(Song left, Song right) {
                if (byAddedTime) {
                    int timeResult = Long.compare(left.addedAt, right.addedAt);
                    if (descending) timeResult = -timeResult;
                    if (timeResult != 0) return timeResult;

                    // Same import batch/same timestamp: always name ascending.
                    int nameResult = comparePlaylistText(left.title, right.title, false, collator);
                    if (nameResult != 0) return nameResult;
                    return comparePlaylistText(left.artist, right.artist, false, collator);
                }

                String leftPrimary = byArtist ? left.artist : left.title;
                String rightPrimary = byArtist ? right.artist : right.title;
                int result = comparePlaylistText(leftPrimary, rightPrimary, descending, collator);
                if (result != 0) return result;

                String leftSecondary = byArtist ? left.title : left.artist;
                String rightSecondary = byArtist ? right.title : right.artist;
                result = comparePlaylistText(leftSecondary, rightSecondary, false, collator);
                if (result != 0) return result;
                return comparePlaylistText(left.source, right.source, false, collator);
            }
        });

        if (!playingSearchQueue) {
            currentSongIndex = currentSong == null ? -1 : playlist.songs.indexOf(currentSong);
        }
        savePlaylists();
        renderCurrentPlaylist();
        if (playlistSongsList != null) playlistSongsList.setSelection(0);
        toast("当前歌单已按" + label + "排序");
    }

    private void stampImportedPlaylistBatch(Playlist playlist) {
        if (playlist == null || playlist.songs.isEmpty()) return;
        long batchAddedAt = System.currentTimeMillis();
        for (Song song : playlist.songs) {
            if (song != null) song.addedAt = batchAddedAt;
        }
    }

    private int comparePlaylistText(String leftValue,
                                    String rightValue,
                                    boolean descending,
                                    java.text.Collator collator) {
        String left = playlistSortText(leftValue);
        String right = playlistSortText(rightValue);
        int leftGroup = playlistSortGroup(left);
        int rightGroup = playlistSortGroup(right);

        // Script group order is fixed regardless of ↑/↓: Latin first, Han next.
        if (leftGroup != rightGroup) return Integer.compare(leftGroup, rightGroup);

        int result = collator.compare(left, right);
        if (descending) result = -result;
        return result;
    }

    private int playlistSortGroup(String value) {
        String normalized = playlistSortText(value);
        for (int offset = 0; offset < normalized.length();) {
            int codePoint = normalized.codePointAt(offset);
            offset += Character.charCount(codePoint);
            if (!Character.isLetterOrDigit(codePoint)) continue;
            Character.UnicodeScript script = Character.UnicodeScript.of(codePoint);
            if (script == Character.UnicodeScript.LATIN || Character.isDigit(codePoint)) return 0;
            if (script == Character.UnicodeScript.HAN) return 1;
            return 2;
        }
        return 3;
    }

    private String playlistSortText(String value) {
        if (value == null) return "";
        return java.text.Normalizer.normalize(value.trim(), java.text.Normalizer.Form.NFKC)
            .toLowerCase(java.util.Locale.ROOT);
    }'''
text = text[:start] + replacement + text[helper_end:]

main.write_text(text, encoding='utf-8')
