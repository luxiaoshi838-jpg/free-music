from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one match, found {count}')
    return text.replace(old, new, 1)


def replace_in_section(text: str, start: str, end: str, old: str, new: str, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f'{label}: start marker missing')
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        raise SystemExit(f'{label}: end marker missing')
    section = text[start_index:end_index]
    section = replace_once(section, old, new, label)
    return text[:start_index] + section + text[end_index:]


main = main_path.read_text(encoding='utf-8')
main = replace_in_section(
    main,
    '    private void confirmDeletePlaylistSong(Song song) {',
    '    private void addSongToCurrentPlaylist',
    '            .setPositiveButton("\\u590d\\u5236", (dialog, which) -> {',
    '            .setPositiveButton("\\u786e\\u5b9a", (dialog, which) -> {',
    'delete-song confirmation label',
)
main = replace_in_section(
    main,
    '    private void promptText(String title, String hint, String initial, TextCallback callback) {',
    '    private void deleteCurrentPlaylist() {',
    '            .setPositiveButton("\\u590d\\u5236", (dialog, which) -> {',
    '            .setPositiveButton("\\u786e\\u5b9a", (dialog, which) -> {',
    'text-dialog confirmation label',
)
main = replace_in_section(
    main,
    '    private void deleteCurrentPlaylist() {',
    '    private void clearCurrentPlaylist() {',
    '            .setPositiveButton("\\u590d\\u5236", (dialog, which) -> {',
    '            .setPositiveButton("\\u786e\\u5b9a", (dialog, which) -> {',
    'delete-playlist confirmation label',
)
main = replace_in_section(
    main,
    '    private void mergePlaylistsIntoCurrent() {',
    '    private boolean containsSong(Playlist playlist, Song song) {',
    '            .setPositiveButton("\\u590d\\u5236", (dialog, which) -> {',
    '            .setPositiveButton("\\u5408\\u5e76", (dialog, which) -> {',
    'merge-playlist confirmation label',
)
main_path.write_text(main, encoding='utf-8')

gradle = gradle_path.read_text(encoding='utf-8')
gradle = replace_once(gradle, 'versionCode 2026080129', 'versionCode 2026080130', 'version code')
gradle = replace_once(
    gradle,
    'versionName "2026.08.03.search-priority-cache-name"',
    'versionName "2026.08.03.dialog-confirm-labels"',
    'version name',
)
gradle_path.write_text(gradle, encoding='utf-8')

check = check_path.read_text(encoding='utf-8')
check = replace_once(check, "'versionCode 2026080129' in gradle", "'versionCode 2026080130' in gradle", 'version check')
check = replace_once(
    check,
    "    'settings width and status bar': ('0.70f' in main and 'setStatusBarColor(opening ? Color.rgb(22, 24, 34)' in main and 'statusBarHeight() + dp(20)' in main),",
    "    'dialog action labels match operations': (\n"
    "        'setTitle(\"删除歌曲\")' in main\n"
    "        and main[main.find('private void confirmDeletePlaylistSong'):main.find('private void addSongToCurrentPlaylist')].find('setPositiveButton(\"\\\\u786e\\\\u5b9a\"') >= 0\n"
    "        and main[main.find('private void promptText'):main.find('private void deleteCurrentPlaylist')].find('setPositiveButton(\"\\\\u786e\\\\u5b9a\"') >= 0\n"
    "        and main[main.find('private void deleteCurrentPlaylist'):main.find('private void clearCurrentPlaylist')].find('setPositiveButton(\"\\\\u786e\\\\u5b9a\"') >= 0\n"
    "        and main[main.find('private void mergePlaylistsIntoCurrent'):main.find('private boolean containsSong')].find('setPositiveButton(\"\\\\u5408\\\\u5e76\"') >= 0\n"
    "        and main.count('setPositiveButton(\"\\\\u590d\\\\u5236\"') == 1\n"
    "    ),\n"
    "    'settings width and status bar': ('0.70f' in main and 'setStatusBarColor(opening ? Color.rgb(22, 24, 34)' in main and 'statusBarHeight() + dp(20)' in main),",
    'dialog label checks',
)
check_path.write_text(check, encoding='utf-8')

with (root / 'docs/CHANGELOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- v130: correct dialog action labels: deleting a song, deleting a playlist, and text-entry dialogs now use “确定”; merging playlists uses “合并”.\n')
with (root / 'PROJECT_LOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- v130 fixes an accidental UI-label replacement where destructive and edit confirmation dialogs displayed “复制”. The real crash-report copy action remains unchanged.\n')

print('Applied v130 dialog action label patch')
