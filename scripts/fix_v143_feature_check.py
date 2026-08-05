from pathlib import Path

path = Path(__file__).resolve().parent / 'check_feature_requirements.py'
text = path.read_text(encoding='utf-8')
old = "        and '本次搜索缓存' in main\n"
new = "        and '已使用歌单中的同名歌曲缓存' in main\n        and '搜索歌曲缓存' in main\n"
if old not in text:
    raise SystemExit('v143 old search-cache check not found')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Updated playback-path check for v143 search cache wording')
