from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
quick_path = root / 'app/src/main/java/com/jianglab/babywife/SearchQuickPlayback.java'

main = main_path.read_text(encoding='utf-8')
old_call = 'this, candidate, song.title, song.artist, song.album);'
new_call = 'this, candidate, song.title, song.artist, "");'
if old_call not in main:
    raise SystemExit('v143 compile target missing: Song album call')
main = main.replace(old_call, new_call, 1)

quick = quick_path.read_text(encoding='utf-8')
old_store = '''            String storedUri = CacheStorage.storeAudio(context, key, extension, source,
                title, artist, album, candidate.catalogJson);
'''
new_store = '''            String savedAlbum = album == null ? "" : album.trim();
            if (savedAlbum.isEmpty()) {
                try {
                    savedAlbum = new JSONObject(candidate.catalogJson)
                        .optString("album", "").trim();
                } catch (Exception ignored) {
                }
            }
            String storedUri = CacheStorage.storeAudio(context, key, extension, source,
                title, artist, savedAlbum, candidate.catalogJson);
'''
if old_store not in quick:
    raise SystemExit('v143 compile target missing: cache album metadata')
quick = quick.replace(old_store, new_store, 1)

main_path.write_text(main, encoding='utf-8')
quick_path.write_text(quick, encoding='utf-8')
print('Fixed v143 album metadata compile error')
