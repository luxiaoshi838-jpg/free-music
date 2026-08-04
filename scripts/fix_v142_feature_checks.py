from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'scripts/check_feature_requirements.py'
text = path.read_text(encoding='utf-8')

old_encryption = "        and 'NetworkMediaCache.cachedAudioExists(this, currentSong.cachedUri)' in main\n"
new_encryption = "        and 'SodaM4aDecryptor.isEncryptedM4a(partial)' in playable_resolver\n"
if old_encryption not in text:
    if new_encryption not in text:
        raise SystemExit('v142 encrypted M4A check target missing')
else:
    text = text.replace(old_encryption, new_encryption, 1)

old_status = "        and '缓存已就绪，正在启动播放' in main\n"
new_status = "        and '缓存已就绪，正在异步打开音频' in main\n"
if old_status not in text:
    if new_status not in text:
        raise SystemExit('v142 async cache status check target missing')
else:
    text = text.replace(old_status, new_status, 1)

path.write_text(text, encoding='utf-8')
print('Updated stale v140 checks to v142 async playback requirements')
