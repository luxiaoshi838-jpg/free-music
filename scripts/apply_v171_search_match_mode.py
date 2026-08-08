from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise SystemExit(f"anchor missing: {label}")


gradle = Path("app/build.gradle")
g = gradle.read_text(encoding="utf-8")
g = g.replace("versionCode 2026080870", "versionCode 2026080871")
g = g.replace(
    'versionName "2026.08.08.v170-playlist-sort-added-time"',
    'versionName "2026.08.08.v171-search-match-mode"',
)
gradle.write_text(g, encoding="utf-8")

main = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = main.read_text(encoding="utf-8")

text = replace_once(
    text,
    '    private static final String KEY_SEARCH_SOURCE = "search_source";\n',
    '    private static final String KEY_SEARCH_SOURCE = "search_source";\n'
    '    private static final String KEY_SEARCH_MATCH_MODE = "search_match_mode";\n',
    "search mode preference key",
)

text = replace_once(
    text,
    '    private EditText searchInput;\n    private Spinner sourceSpinner;\n',
    '    private EditText searchInput;\n'
    '    private TextView searchMatchModeButton;\n'
    '    private Spinner sourceSpinner;\n',
    "search mode UI field",
)

text = replace_once(
    text,
    '    private String savedSearchSource = "\\u5feb\\u901f\\u641c\\u7d22";\n',
    '    private String savedSearchSource = "\\u5feb\\u901f\\u641c\\u7d22";\n'
    '    private String savedSearchMatchMode = "默认";\n'
    '    private String activeSearchMatchMode = "默认";\n',
    "search mode state fields",
)

load_anchor = '''        if (savedSearchSource == null || savedSearchSource.trim().isEmpty()) {\n            savedSearchSource = "\\u5feb\\u901f\\u641c\\u7d22";\n        }\n    }\n\n    private int clampPlayMode(int value) {'''
load_replacement = '''        if (savedSearchSource == null || savedSearchSource.trim().isEmpty()) {\n            savedSearchSource = "\\u5feb\\u901f\\u641c\\u7d22";\n        }\n        savedSearchMatchMode = normalizeSearchMatchMode(\n            prefs.getString(KEY_SEARCH_MATCH_MODE, "默认"));\n        activeSearchMatchMode = savedSearchMatchMode;\n    }\n\n    private String normalizeSearchMatchMode(String mode) {\n        if ("歌名".equals(mode) || "歌手".equals(mode)) return mode;\n        return "默认";\n    }\n\n    private void saveSearchMatchMode(String mode) {\n        savedSearchMatchMode = normalizeSearchMatchMode(mode);\n        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)\n            .edit()\n            .putString(KEY_SEARCH_MATCH_MODE, savedSearchMatchMode)\n            .apply();\n        if (searchMatchModeButton != null) {\n            searchMatchModeButton.setText(savedSearchMatchMode);\n        }\n    }\n\n    private void showSearchMatchModeDialog() {\n        final String[] modes = {"默认", "歌名", "歌手"};\n        int selected = "歌名".equals(savedSearchMatchMode) ? 1\n            : ("歌手".equals(savedSearchMatchMode) ? 2 : 0);\n        new AlertDialog.Builder(this)\n            .setTitle("搜索模式")\n            .setSingleChoiceItems(modes, selected, (dialog, which) -> {\n                if (which >= 0 && which < modes.length) {\n                    saveSearchMatchMode(modes[which]);\n                }\n                dialog.dismiss();\n            })\n            .setNegativeButton("取消", null)\n            .show();\n    }\n\n    private int clampPlayMode(int value) {'''
text = replace_once(text, load_anchor, load_replacement, "load/save search mode")

text = replace_once(
    text,
    '        searchInput.setPadding(dp(22), 0, dp(48), 0);\n',
    '        searchInput.setPadding(dp(72), 0, dp(48), 0);\n',
    "search box left padding",
)

box_anchor = '''        searchBox.addView(searchInput, new FrameLayout.LayoutParams(\n            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));\n\n        TextView clearSearchButton = new TextView(this);'''
box_replacement = '''        searchBox.addView(searchInput, new FrameLayout.LayoutParams(\n            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));\n\n        searchMatchModeButton = new TextView(this);\n        searchMatchModeButton.setText(savedSearchMatchMode);\n        searchMatchModeButton.setTextColor(TEXT_MUTED);\n        searchMatchModeButton.setTextSize(12);\n        searchMatchModeButton.setGravity(Gravity.CENTER);\n        searchMatchModeButton.setSingleLine(true);\n        searchMatchModeButton.setContentDescription("搜索模式");\n        searchMatchModeButton.setOnClickListener(view -> showSearchMatchModeDialog());\n        attachSubtlePressFeedback(searchMatchModeButton);\n        FrameLayout.LayoutParams searchModeParams = new FrameLayout.LayoutParams(dp(56), dp(32));\n        searchModeParams.gravity = Gravity.START | Gravity.CENTER_VERTICAL;\n        searchModeParams.setMargins(dp(6), 0, 0, 0);\n        searchBox.addView(searchMatchModeButton, searchModeParams);\n\n        TextView clearSearchButton = new TextView(this);'''
text = replace_once(text, box_anchor, box_replacement, "search mode control in search box")

text = replace_once(
    text,
    '        String mode = String.valueOf(sourceSpinner.getSelectedItem());\n        activeSearchKeyword = keyword;\n',
    '        String mode = String.valueOf(sourceSpinner.getSelectedItem());\n'
    '        activeSearchMatchMode = normalizeSearchMatchMode(savedSearchMatchMode);\n'
    '        activeSearchKeyword = keyword;\n',
    "activate selected search mode",
)

# Filter every online batch before it reaches the visible result list.
text = replace_once(
    text,
    '            for (CatalogSearch.Track track : batch.tracks) rows.add(Song.fromCatalog(track));\n',
    '            for (CatalogSearch.Track track : batch.tracks) {\n'
    '                Song row = Song.fromCatalog(track);\n'
    '                if (searchMatchModeAccepts(row, activeSearchKeyword, activeSearchMatchMode)) {\n'
    '                    rows.add(row);\n'
    '                }\n'
    '            }\n',
    "online batch search filtering",
)

method_anchor = '    private void loadNextSearchBatch(boolean firstBatch) {'
filter_methods = '''    private boolean searchMatchModeAccepts(Song song, String keyword, String mode) {\n        if (song == null) return false;\n        String query = normalizeSearchMatchText(keyword);\n        if (query.isEmpty()) return true;\n        String title = normalizeSearchMatchText(song.title);\n        String artist = normalizeSearchMatchText(song.artist);\n        String selectedMode = normalizeSearchMatchMode(mode);\n\n        String[] tokens = query.split("\\\\s+");\n        for (String token : tokens) {\n            if (token == null || token.isEmpty()) continue;\n            if ("歌名".equals(selectedMode)) {\n                if (!title.contains(token)) return false;\n            } else if ("歌手".equals(selectedMode)) {\n                if (!artist.contains(token)) return false;\n            } else if (!title.contains(token) && !artist.contains(token)) {\n                return false;\n            }\n        }\n        return true;\n    }\n\n    private String normalizeSearchMatchText(String value) {\n        if (value == null) return "";\n        return java.text.Normalizer.normalize(\n            value.trim(), java.text.Normalizer.Form.NFKC)\n            .toLowerCase(java.util.Locale.ROOT);\n    }\n\n'''
if filter_methods not in text:
    if method_anchor not in text:
        raise SystemExit("anchor missing: loadNextSearchBatch for filter methods")
    text = text.replace(method_anchor, filter_methods + method_anchor, 1)

# Make local-source search obey the same field targeting when it uses Song.matches().
# We keep Song.matches() itself unchanged because it is also used in non-search contexts.
local_patterns = [
    ('if (song.matches(keyword)) searchResults.add(song);',
     'if (song.matches(keyword) && searchMatchModeAccepts(song, keyword, activeSearchMatchMode)) searchResults.add(song);'),
    ('if (item.matches(keyword)) searchResults.add(item);',
     'if (item.matches(keyword) && searchMatchModeAccepts(item, keyword, activeSearchMatchMode)) searchResults.add(item);'),
]
for old, new in local_patterns:
    if old in text:
        text = text.replace(old, new)

main.write_text(text, encoding="utf-8")
