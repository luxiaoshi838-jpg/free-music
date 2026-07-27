"""Regression check for the eight-column playlist CSV header."""
from pathlib import Path

main = (Path(__file__).resolve().parents[1]
        / 'app/src/main/java/com/jianglab/babywife/MainActivity.java').read_text(encoding='utf-8')

headers = ['歌名', '歌手', '专辑', '时长秒', '平台', '平台代码', '歌曲ID', '歌词版本']
expected = {
    'title': 0,
    'artist': 1,
    'album': 2,
    'duration': 3,
    'sourceLabel': 4,
    'sourceCode': 5,
    'songId': 6,
    'lyricLabel': 7,
}

def normalize(value: str) -> str:
    return (value.replace('\ufeff', '').strip().lower()
            .replace(' ', '').replace('_', '').replace('-', '')
            .replace('（', '(').replace('）', ')'))

def map_header(header):
    columns = {}
    for i, raw in enumerate(header):
        key = normalize(raw)
        if '歌曲id' in key or key in {'id', 'songid'}:
            columns['songId'] = i
        elif key in {'歌名', '歌曲名', '歌曲标题', 'title', 'name'}:
            columns['title'] = i
        elif '歌手' in key or '演唱' in key or key in {'artist', 'singer'}:
            columns['artist'] = i
        elif '专辑' in key or key == 'album':
            columns['album'] = i
        elif '时长' in key or key in {'duration', 'time'}:
            columns['duration'] = i
        elif '平台代码' in key or key == 'sourcecode':
            columns['sourceCode'] = i
        elif '平台' in key or key in {'source', 'platform'}:
            columns['sourceLabel'] = i
        elif '歌词' in key or key in {'lyric', 'lyriclabel', 'lyricversion'}:
            columns['lyricLabel'] = i
    return columns

actual = map_header(headers)
if actual != expected:
    raise SystemExit(f'CSV mapping mismatch: {actual!r}')
if main.find('key.contains("歌曲id")') > main.find('key.equals("歌名")'):
    raise SystemExit('Java mapping checks title before song ID')
if 'key.contains("歌曲")' in main:
    raise SystemExit('Generic 歌曲 matching would let 歌曲ID overwrite title')
print('CSV mapping regression check passed:', actual)
