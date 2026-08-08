from pathlib import Path

main = Path('app/src/main/java/com/jianglab/babywife/MainActivity.java')
text = main.read_text(encoding='utf-8')
old = '''        searchMatchModeButton.setTextSize(9);\n        searchMatchModeButton.setGravity(Gravity.CENTER);\n        searchMatchModeButton.setSingleLine(true);'''
new = '''        searchMatchModeButton.setTextSize(9);\n        searchMatchModeButton.setGravity(Gravity.CENTER_HORIZONTAL | Gravity.CENTER_VERTICAL);\n        searchMatchModeButton.setTextAlignment(View.TEXT_ALIGNMENT_CENTER);\n        searchMatchModeButton.setIncludeFontPadding(false);\n        searchMatchModeButton.setPadding(0, 0, 0, 0);\n        searchMatchModeButton.setSingleLine(true);'''
if old not in text:
    if new not in text:
        raise SystemExit('search mode label block not found')
else:
    text = text.replace(old, new, 1)
main.write_text(text, encoding='utf-8')

gradle = Path('app/build.gradle')
g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode 2026080873', 'versionCode 2026080874', 1)
g = g.replace('versionName "2026.08.08.v173-log-history"', 'versionName "2026.08.08.v174-search-mode-centered"', 1)
if 'versionCode 2026080874' not in g or 'versionName "2026.08.08.v174-search-mode-centered"' not in g:
    raise SystemExit('version bump failed')
gradle.write_text(g, encoding='utf-8')
