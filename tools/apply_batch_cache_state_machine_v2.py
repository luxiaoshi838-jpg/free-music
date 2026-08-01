#!/usr/bin/env python3
from pathlib import Path
import argparse


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {count}')
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    root = Path(parser.parse_args().root).resolve()

    main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
    text = main_path.read_text(encoding='utf-8')

    old_receiver = '''    private final BroadcastReceiver playlistBatchCacheReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (intent == null || !PlaylistBatchCacheService.ACTION_PROGRESS.equals(intent.getAction())) return;
            String identity = intent.getStringExtra(PlaylistBatchCacheService.EXTRA_IDENTITY);
            String updatedSongJson = intent.getStringExtra(PlaylistBatchCacheService.EXTRA_UPDATED_SONG_JSON);
            if (identity != null && !identity.trim().isEmpty()
                && updatedSongJson != null && !updatedSongJson.trim().isEmpty()) {
                applyBatchSongUpdate(identity, updatedSongJson);
            }
            playlistBatchCaching = intent.getBooleanExtra(PlaylistBatchCacheService.EXTRA_RUNNING, false);
            String message = intent.getStringExtra(PlaylistBatchCacheService.EXTRA_MESSAGE);
            if (statusView != null && message != null && !message.trim().isEmpty()) {
                statusView.setText(message);
            }
            if (playlistAdapter != null) applyPlaylistFilter();
            updatePlaylistCacheButton();
            if (!playlistBatchCaching) {
                int failed = intent.getIntExtra(PlaylistBatchCacheService.EXTRA_FAILED, 0);
                toast(failed > 0
                    ? "后台缓存完成，失败歌曲已标红"
                    : "后台缓存已完成");
            }
        }
    };
'''
    new_receiver = '''    private final BroadcastReceiver playlistBatchCacheReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (intent == null || !PlaylistBatchCacheService.ACTION_PROGRESS.equals(intent.getAction())) return;
            consumePendingBatchCacheResults();
            PlaylistBatchCacheService.TaskState state = PlaylistBatchCacheService.readState(MainActivity.this);
            playlistBatchCaching = state.isRunningFresh();
            String message = intent.getStringExtra(PlaylistBatchCacheService.EXTRA_MESSAGE);
            if (statusView != null && message != null && !message.trim().isEmpty()) {
                statusView.setText(message);
            }
            if (playlistAdapter != null) applyPlaylistFilter();
            updatePlaylistCacheButton();
            if (state.isCompleted()) {
                toast(state.failed > 0
                    ? "后台缓存完成，失败歌曲已标红"
                    : "后台缓存已完成");
            } else if (state.isError()) {
                toast("后台缓存已停止，可点击按钮重启");
            }
        }
    };
'''
    text = replace_once(text, old_receiver, new_receiver, 'batch receiver')

    old_create = '''        registerPlaybackControlReceiver();
        registerPlaylistBatchCacheReceiver();
        PlaybackControlService.ensureStarted(this);
'''
    new_create = '''        registerPlaybackControlReceiver();
        registerPlaylistBatchCacheReceiver();
        consumePendingBatchCacheResults();
        PlaybackControlService.ensureStarted(this);
'''
    text = replace_once(text, old_create, new_create, 'onCreate result consumption')

    resume_anchor = '''    private void maybeRequireJiangLabPassphrase() {
'''
    resume_block = '''    @Override
    protected void onResume() {
        super.onResume();
        consumePendingBatchCacheResults();
        updatePlaylistCacheButton();
    }

    private void maybeRequireJiangLabPassphrase() {
'''
    text = replace_once(text, resume_anchor, resume_block, 'onResume')

    old_register = '''        batchCacheReceiverRegistered = true;
        playlistBatchCaching = PlaylistBatchCacheService.isRunning(this);
    }

    private void applyBatchSongUpdate(String identity, String updatedSongJson) {
'''
    new_register = '''        batchCacheReceiverRegistered = true;
        playlistBatchCaching = PlaylistBatchCacheService.readState(this).isRunningFresh();
    }

    private void consumePendingBatchCacheResults() {
        List<PlaylistBatchCacheService.ResultRecord> records =
            PlaylistBatchCacheService.readPendingResults(this);
        if (records.isEmpty()) return;
        for (PlaylistBatchCacheService.ResultRecord record : records) {
            applyBatchSongUpdate(record.identity, record.updatedSongJson);
        }
        savePlaylists();
        PlaylistBatchCacheService.markResultsConsumed(this, records);
        if (playlistAdapter != null) applyPlaylistFilter();
        renderResults();
    }

    private void applyBatchSongUpdate(String identity, String updatedSongJson) {
'''
    text = replace_once(text, old_register, new_register, 'batch result journal')

    old_comment = '''            // PlaylistBatchCacheService is the single writer while the queue is running.
            // The Activity only refreshes its in-memory view to avoid overwriting newer results.
'''
    new_comment = '''            // The isolated cache process writes result files only; MainActivity remains
            // the sole writer of playlist preferences, avoiding cross-process overwrites.
'''
    text = replace_once(text, old_comment, new_comment, 'writer ownership comment')

    old_show = '''    private void showPlaylistPage() {
        if (headerBar != null) headerBar.setVisibility(View.GONE);
        if (statusView != null) statusView.setVisibility(View.GONE);
        if (playerPanel != null) playerPanel.setVisibility(View.GONE);
        if (searchPanel != null) searchPanel.setVisibility(View.GONE);
        if (playlistPanel != null) playlistPanel.setVisibility(View.VISIBLE);
    }
'''
    new_show = '''    private void showPlaylistPage() {
        consumePendingBatchCacheResults();
        if (headerBar != null) headerBar.setVisibility(View.GONE);
        if (statusView != null) statusView.setVisibility(View.GONE);
        if (playerPanel != null) playerPanel.setVisibility(View.GONE);
        if (searchPanel != null) searchPanel.setVisibility(View.GONE);
        if (playlistPanel != null) playlistPanel.setVisibility(View.VISIBLE);
        updatePlaylistCacheButton();
    }
'''
    text = replace_once(text, old_show, new_show, 'playlist page refresh')

    old_batch = '''    private List<Song> uncachedSongsInCurrentPlaylist() {
        List<Song> uncached = new ArrayList<>();
        for (Song song : currentPlaylist().songs) {
            if (song == null || !song.isNetworkCatalog()) continue;
            if (!NetworkMediaCache.cachedAudioExists(this, song.cachedUri)) uncached.add(song);
        }
        return uncached;
    }

    private void updatePlaylistCacheButton() {
        if (cachePlaylistButton == null) return;
        playlistBatchCaching = PlaylistBatchCacheService.isRunning(this);
        if (playlistBatchCaching) {
            cachePlaylistButton.setVisibility(View.VISIBLE);
            cachePlaylistButton.setEnabled(false);
            String progress = PlaylistBatchCacheService.progressLabel(this);
            cachePlaylistButton.setText(progress.isEmpty() ? "正在后台缓存歌单" : progress);
            return;
        }
        int count = uncachedSongsInCurrentPlaylist().size();
        cachePlaylistButton.setEnabled(count > 0);
        cachePlaylistButton.setVisibility(count > 0 ? View.VISIBLE : View.GONE);
        cachePlaylistButton.setText(count > 0
            ? "一键缓存未缓存歌曲（" + count + "首）"
            : "一键缓存未缓存歌曲");
    }

    private void cacheCurrentPlaylist() {
        if (PlaylistBatchCacheService.isRunning(this)) {
            playlistBatchCaching = true;
            updatePlaylistCacheButton();
            toast("已有歌单正在后台缓存");
            return;
        }
        List<Song> pending = uncachedSongsInCurrentPlaylist();
        if (pending.isEmpty()) {
            updatePlaylistCacheButton();
            return;
        }
        playlistBatchCaching = true;
        cachePlaylistButton.setVisibility(View.VISIBLE);
        cachePlaylistButton.setEnabled(false);
        cachePlaylistButton.setText("正在启动后台缓存：共 " + pending.size() + " 首");
        statusView.setText("歌单缓存已转入后台，离开软件或锁屏后仍会继续");
        PlaylistBatchCacheService.start(this, currentPlaylistIndex);
    }
'''
    new_batch = '''    private List<Song> uncachedSongsInCurrentPlaylist() {
        List<Song> uncached = new ArrayList<>();
        for (Song song : currentPlaylist().songs) {
            if (song == null || !song.isNetworkCatalog()) continue;
            if (!NetworkMediaCache.cachedAudioExists(this, song.cachedUri)) uncached.add(song);
        }
        return uncached;
    }

    private String buildPlaylistBatchRequest(List<Song> pending) {
        JSONObject request = new JSONObject();
        JSONArray songs = new JSONArray();
        try {
            request.put("playlistIndex", currentPlaylistIndex);
            for (Song song : pending) {
                JSONObject row = new JSONObject();
                row.put("identity", song.key());
                row.put("songJson", song.toJson().toString());
                songs.put(row);
            }
            request.put("songs", songs);
        } catch (JSONException error) {
            throw new IllegalStateException("无法建立缓存任务：" + error.getMessage());
        }
        return request.toString();
    }

    private void updatePlaylistCacheButton() {
        if (cachePlaylistButton == null) return;
        int count = uncachedSongsInCurrentPlaylist().size();
        if (count <= 0) {
            playlistBatchCaching = false;
            cachePlaylistButton.setEnabled(false);
            cachePlaylistButton.setVisibility(View.GONE);
            return;
        }

        PlaylistBatchCacheService.TaskState state = PlaylistBatchCacheService.readState(this);
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
        cachePlaylistButton.setVisibility(View.VISIBLE);
        if (samePlaylist && state.isRunningFresh()) {
            playlistBatchCaching = true;
            cachePlaylistButton.setEnabled(true);
            cachePlaylistButton.setText("暂停一键缓存（" + state.done + "/" + state.total + "）");
            return;
        }
        playlistBatchCaching = false;
        if (samePlaylist && state.isStale()) {
            cachePlaylistButton.setEnabled(true);
            cachePlaylistButton.setText("任务已停滞，点击重启（" + count + "首）");
            return;
        }
        if (samePlaylist && state.isPaused()) {
            cachePlaylistButton.setEnabled(true);
            cachePlaylistButton.setText("继续一键缓存（" + count + "首）");
            return;
        }
        if (state.isRunningFresh() && !samePlaylist) {
            cachePlaylistButton.setEnabled(false);
            cachePlaylistButton.setText("其他歌单正在缓存");
            return;
        }
        cachePlaylistButton.setEnabled(true);
        cachePlaylistButton.setText("一键缓存未缓存歌曲（" + count + "首）");
    }

    private void cacheCurrentPlaylist() {
        consumePendingBatchCacheResults();
        List<Song> pending = uncachedSongsInCurrentPlaylist();
        if (pending.isEmpty()) {
            updatePlaylistCacheButton();
            return;
        }
        PlaylistBatchCacheService.TaskState state = PlaylistBatchCacheService.readState(this);
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
        if (samePlaylist && state.isRunningFresh()) {
            cachePlaylistButton.setEnabled(false);
            cachePlaylistButton.setText("正在暂停一键缓存...");
            PlaylistBatchCacheService.pause(this);
            cachePlaylistButton.postDelayed(this::updatePlaylistCacheButton, 800L);
            return;
        }
        if (state.isRunningFresh() && !samePlaylist) {
            toast("另一个歌单正在缓存，请先切换到该歌单暂停任务");
            return;
        }

        String request = buildPlaylistBatchRequest(pending);
        cachePlaylistButton.setEnabled(false);
        cachePlaylistButton.setText(state.isStale()
            ? "正在重启后台缓存..." : "正在启动后台缓存...");
        if (statusView != null) {
            statusView.setText("缓存任务使用独立进程，搜索和正常播放可同时进行");
        }
        try {
            if (state.isStale()) {
                PlaylistBatchCacheService.restart(this, currentPlaylistIndex, request);
            } else {
                PlaylistBatchCacheService.start(this, currentPlaylistIndex, request);
            }
        } catch (Exception error) {
            toast("启动缓存任务失败：" + error.getMessage());
        }
        cachePlaylistButton.postDelayed(this::updatePlaylistCacheButton, 900L);
    }
'''
    text = replace_once(text, old_batch, new_batch, 'batch button state machine')
    main_path.write_text(text, encoding='utf-8')

    manifest_path = root / 'app/src/main/AndroidManifest.xml'
    manifest = manifest_path.read_text(encoding='utf-8')
    manifest = replace_once(manifest,
        '''        <service\n            android:name=".PlaylistBatchCacheService"\n            android:exported="false"\n            android:foregroundServiceType="dataSync" />''',
        '''        <service\n            android:name=".PlaylistBatchCacheService"\n            android:exported="false"\n            android:process=":playlist_cache"\n            android:foregroundServiceType="dataSync" />''',
        'isolated cache process')
    manifest_path.write_text(manifest, encoding='utf-8')

    network_path = root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java'
    network = network_path.read_text(encoding='utf-8')
    network = replace_once(network,
        '''        String key = sha256(actualSource + "|" + actualId);\n        String actualTitle = catalogTitle(actualCatalog);''',
        '''        String key = sha256(actualSource + "|" + actualId);\n        try (CacheKeyLock cacheKeyLock = CacheKeyLock.acquire(context, key)) {\n        String actualTitle = catalogTitle(actualCatalog);''',
        'per-key cache lock start')
    network = replace_once(network,
        '''        } finally {\n            if (partial.exists()) partial.delete();\n        }\n    }\n\n    private static int choiceFormatRank''',
        '''        } finally {\n            if (partial.exists()) partial.delete();\n        }\n        }\n    }\n\n    private static int choiceFormatRank''',
        'per-key cache lock end')
    network = replace_once(network,
        '''        File partial = new File(tempRoot, key + "." + hintedExtension + ".part");''',
        '''        File partial = new File(tempRoot, key + "." + hintedExtension + "."\n            + android.os.Process.myPid() + "." + Thread.currentThread().getId() + ".part");''',
        'unique partial file')
    network = replace_once(network,
        '''            long written = 0L;\n            int lastPercent = -1;''',
        '''            long written = 0L;\n            int lastPercent = -1;\n            long lastStatusAt = System.currentTimeMillis();''',
        'download heartbeat variable')
    old_progress = '''                    if (total > 0) {
                        int percent = (int) Math.min(100, written * 100 / total);
                        if (percent >= lastPercent + 10) {
                            lastPercent = percent;
                            status(callback, "正在缓存歌曲：" + percent + "%");
                        }
                    }
'''
    new_progress = '''                    long now = System.currentTimeMillis();
                    if (total > 0) {
                        int percent = (int) Math.min(100, written * 100 / total);
                        if (percent >= lastPercent + 5 || now - lastStatusAt >= 5000L) {
                            lastPercent = percent;
                            lastStatusAt = now;
                            status(callback, "正在缓存歌曲：" + percent + "%");
                        }
                    } else if (now - lastStatusAt >= 5000L) {
                        lastStatusAt = now;
                        status(callback, "正在缓存歌曲：" + Math.max(1L, written / 1024L / 1024L) + "MB");
                    }
'''
    network = replace_once(network, old_progress, new_progress, 'download progress heartbeat')
    network_path.write_text(network, encoding='utf-8')

    gradle_path = root / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    gradle = gradle.replace('versionCode 2026080105', 'versionCode 2026080106')
    gradle = gradle.replace('versionName "2026.08.01.background-playlist-cache"',
                            'versionName "2026.08.01.resumable-isolated-cache"')
    gradle_path.write_text(gradle, encoding='utf-8')

    checks_path = root / 'scripts/check_feature_requirements.py'
    checks = checks_path.read_text(encoding='utf-8')
    checks = replace_once(checks,
        "batch_service = (root / 'app/src/main/java/com/jianglab/babywife/PlaylistBatchCacheService.java').read_text(encoding='utf-8')\n",
        "batch_service = (root / 'app/src/main/java/com/jianglab/babywife/PlaylistBatchCacheService.java').read_text(encoding='utf-8')\ncache_lock = (root / 'app/src/main/java/com/jianglab/babywife/CacheKeyLock.java').read_text(encoding='utf-8')\n",
        'check cache lock source')
    start = checks.index("    'playlist one-click background cache and failure marking': (")
    end = checks.index("    'media player error containment': (", start)
    replacement = '''    'isolated resumable playlist cache state machine': (
        '暂停一键缓存' in main
        and '任务已停滞，点击重启' in main
        and 'cachePlaylistButton.setVisibility(View.GONE)' in main
        and 'PlaylistBatchCacheService.pause(this)' in main
        and 'PlaylistBatchCacheService.restart(this, currentPlaylistIndex, request)' in main
        and 'readPendingBatchCacheResults' not in main
        and 'readPendingResults' in main
        and 'android:process=":playlist_cache"' in manifest
        and 'FOREGROUND_SERVICE_DATA_SYNC' in manifest
        and 'ACTION_PAUSE' in batch_service
        and 'ACTION_RESTART' in batch_service
        and 'PROGRESS_STALE_MS' in batch_service
        and 'android.os.Process.killProcess' in batch_service
        and 'RESULTS_FOLDER' in batch_service
        and 'CacheKeyLock.acquire(context, key)' in network
        and 'FileChannel' in cache_lock
        and 'tryLock' in cache_lock
    ),
'''
    checks = checks[:start] + replacement + checks[end:]
    checks = checks.replace("'version bumped': 'versionCode 2026080105' in gradle,",
                            "'version bumped': 'versionCode 2026080106' in gradle,")
    checks_path.write_text(checks, encoding='utf-8')

    with (root / 'PROJECT_LOG.md').open('a', encoding='utf-8') as output:
        output.write('''\n\n## 2026-08-01 可暂停、可重启的一键缓存\n\n- 歌单批量缓存移入独立 `:playlist_cache` 进程，搜索和正常播放不再与批量解析共享桥接层。\n- 一键缓存按钮按一次启动、运行中再按一次暂停；暂停、异常或进度失活后可再次点击继续或重启。\n- 任务状态、心跳和结果使用原子文件持久化；主进程是歌单偏好的唯一写入者。\n- 同一歌曲使用跨进程文件锁，不同歌曲仍可并行，避免播放缓存与批量缓存互相覆盖。\n- 当前歌单没有未缓存在线歌曲时，一键缓存按钮完全隐藏。\n''')
    with (root / 'docs/CHANGELOG.md').open('a', encoding='utf-8') as output:
        output.write('''\n\n## 2026-08-01 Resumable isolated playlist cache\n\n- Moved playlist batch caching into a dedicated process so search and playback remain responsive.\n- Added start/pause/resume/stale-task restart behavior to the same playlist cache button.\n- Persisted task state and result journals with atomic files, while keeping playlist preferences single-writer.\n- Added per-track cross-process cache locks and unique partial downloads.\n- Hide the cache button when the current playlist has no uncached online tracks.\n''')

    print('batch_cache_state_machine_v2=applied')


if __name__ == '__main__':
    main()
