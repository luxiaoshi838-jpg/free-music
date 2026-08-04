from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'
project_log_path = root / 'PROJECT_LOG.md'
changelog_path = root / 'docs/CHANGELOG.md'


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'Cannot find {label} in {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def append_once(path: Path, marker: str, body: str) -> None:
    text = path.read_text(encoding='utf-8')
    if marker in text:
        return
    path.write_text(text.rstrip() + '\n\n' + body.rstrip() + '\n', encoding='utf-8')

replace_once(
    gradle_path,
    'versionCode 2026080137\n        versionName "2026.08.04.no-playback-cache-scan"',
    'versionCode 2026080138\n        versionName "2026.08.04.restore-search-add-playlist"',
    'v138 version',
)

replace_once(
    main_path,
    '        boolean playlistContext = existsInPlaylist && !playingSearchQueue;\n'
    '        boolean fromSearchOnly = song != null && playingSearchQueue && !existsInPlaylist;\n'
    '        if (addCurrentButton != null) {\n'
    '            addCurrentButton.setVisibility(fromSearchOnly ? View.VISIBLE : View.GONE);\n'
    '        }',
    '        boolean playlistContext = existsInPlaylist && !playingSearchQueue;\n'
    '        boolean fromSearch = song != null && playingSearchQueue;\n'
    '        if (addCurrentButton != null) {\n'
    '            addCurrentButton.setText("加入当前歌单");\n'
    '            addCurrentButton.setVisibility(fromSearch ? View.VISIBLE : View.GONE);\n'
    '        }',
    'search add playlist visibility',
)

check = check_path.read_text(encoding='utf-8')
check = check.replace(
    "    'version bumped': 'versionCode 2026080137' in gradle,",
    "    'search result always exposes add-to-playlist action': (\n"
    "        'boolean fromSearch = song != null && playingSearchQueue;' in main\n"
    "        and 'addCurrentButton.setText(\"加入当前歌单\");' in main\n"
    "        and 'addCurrentButton.setVisibility(fromSearch ? View.VISIBLE : View.GONE);' in main\n"
    "        and 'fromSearchOnly' not in main\n"
    "        and 'searchResultsList.setOnItemLongClickListener' in main\n"
    "    ),\n"
    "    'version bumped': 'versionCode 2026080138' in gradle,"
)
check_path.write_text(check, encoding='utf-8')

append_once(
    project_log_path,
    'Restore add-to-playlist action for every search result',
    '''## 2026-08-04 - Restore add-to-playlist action for every search result

- Restored the visible `加入当前歌单` action whenever the player was opened from search results.
- The action is no longer hidden merely because a matching title/artist exists in any playlist.
- Duplicate handling remains inside the actual target-playlist insertion logic.
- Long-pressing a search result still adds it to the target playlist.''',
)
append_once(
    changelog_path,
    'restore-search-add-playlist',
    '''## 2026.08.04.restore-search-add-playlist

- Restored the `加入当前歌单` option for songs opened from search results.
- Existing matches in other playlists no longer hide the option.
- Duplicate detection still prevents duplicate entries in the selected target playlist.''',
)

print('v138 restore search add-to-playlist patch applied')
