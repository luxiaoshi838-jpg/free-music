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

    text = replace_once(
        text,
        'import java.util.Locale;\n',
        'import java.util.Locale;\nimport java.util.concurrent.atomic.AtomicBoolean;\n',
        'atomic boolean import'
    )

    text = replace_once(
        text,
        '''    private boolean playbackReceiverRegistered = false;
    private boolean batchCacheReceiverRegistered = false;
    private long lastPublishedPlaybackSecond = -1L;
''',
        '''    private boolean playbackReceiverRegistered = false;
    private boolean batchCacheReceiverRegistered = false;
    private final AtomicBoolean batchCacheSyncRunning = new AtomicBoolean(false);
    private volatile boolean batchCacheSyncAgain = false;
    private volatile PlaylistBatchCacheService.TaskState cachedBatchTaskState;
    private long lastPublishedPlaybackSecond = -1L;
''',
        'batch sync fields'
    )

    old_receiver = '''    private final BroadcastReceiver playlistBatchCacheReceiver = new BroadcastReceiver() {
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
    new_receiver = '''    private final BroadcastReceiver playlistBatchCacheReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (intent == null || !PlaylistBatchCacheService.ACTION_PROGRESS.equals(intent.getAction())) return;
            String message = intent.getStringExtra(PlaylistBatchCacheService.EXTRA_MESSAGE);
            if (statusView != null && message != null && !message.trim().isEmpty()) {
                statusView.setText(message);
            }
            // Never scan files, parse JSON, rewrite playlists or redraw lists inside
            // BroadcastReceiver.onReceive(). Coalesce all of that work off the UI thread.
            requestBatchCacheSync(true);
        }
    };
'''
    text = replace_once(text, old_receiver, new_receiver, 'lightweight batch receiver')

    text = replace_once(
        text,
        '''        registerPlaybackControlReceiver();
        registerPlaylistBatchCacheReceiver();
        consumePendingBatchCacheResults();
        PlaybackControlService.ensureStarted(this);
''',
        '''        registerPlaybackControlReceiver();
        registerPlaylistBatchCacheReceiver();
        requestBatchCacheSync(true);
        PlaybackControlService.ensureStarted(this);
''',
        'async startup sync'
    )

    text = replace_once(
        text,
        '''    protected void onResume() {
        super.onResume();
        consumePendingBatchCacheResults();
        updatePlaylistCacheButton();
    }
''',
        '''    protected void onResume() {
        super.onResume();
        updatePlaylistCacheButton();
        requestBatchCacheSync(true);
    }
''',
        'async resume sync'
    )

    old_register_and_consume = '''        batchCacheReceiverRegistered = true;
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
    new_register_and_consume = '''        batchCacheReceiverRegistered = true;
        requestBatchCacheSync(false);
    }

    private void requestBatchCacheSync(boolean includeResults) {
        if (!batchCacheSyncRunning.compareAndSet(false, true)) {
            if (includeResults) batchCacheSyncAgain = true;
            return;
        }
        final Context appContext = getApplicationContext();
        new Thread(() -> {
            PlaylistBatchCacheService.TaskState state =
                PlaylistBatchCacheService.readState(appContext);
            List<PlaylistBatchCacheService.ResultRecord> records = includeResults
                ? PlaylistBatchCacheService.readPendingResults(appContext)
                : Collections.emptyList();
            Map<String, Song> updates = new HashMap<>();
            for (PlaylistBatchCacheService.ResultRecord record : records) {
                if (record == null || record.identity == null || record.identity.trim().isEmpty()) continue;
                try {
                    updates.put(record.identity, Song.fromJson(new JSONObject(record.updatedSongJson)));
                } catch (Exception ignored) {
                }
            }
            runOnUiThread(() -> {
                cachedBatchTaskState = state;
                boolean changed = applyBatchSongUpdates(updates);
                if (changed) {
                    savePlaylists();
                    if (playlistAdapter != null) applyPlaylistFilter();
                    if (resultAdapter != null) resultAdapter.notifyDataSetChanged();
                }
                updatePlaylistCacheButton();
                if (!records.isEmpty()) {
                    new Thread(() -> PlaylistBatchCacheService.markResultsConsumed(
                        appContext, records), "PlaylistBatchResultCleanup").start();
                }
                batchCacheSyncRunning.set(false);
                if (batchCacheSyncAgain) {
                    batchCacheSyncAgain = false;
                    requestBatchCacheSync(true);
                }
            });
        }, "PlaylistBatchUiSync").start();
    }

    private boolean applyBatchSongUpdates(Map<String, Song> updates) {
        if (updates == null || updates.isEmpty()) return false;
        boolean changed = false;
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == null) continue;
                Song updated = updates.get(item.key());
                if (updated == null) continue;
                copyBatchSongFields(item, updated);
                changed = true;
            }
        }
        for (Song item : searchResults) {
            if (item == null) continue;
            Song updated = updates.get(item.key());
            if (updated != null) copyBatchSongFields(item, updated);
        }
        if (currentSong != null) {
            Song updated = updates.get(currentSong.key());
            if (updated != null) {
                copyBatchSongFields(currentSong, updated);
                if (titleView != null) titleView.setText(currentSong.title);
                if (artistView != null) artistView.setText(currentSong.artist + " · " + currentSong.source);
            }
        }
        return changed;
    }

    private void applyBatchSongUpdate(String identity, String updatedSongJson) {
'''
    text = replace_once(text, old_register_and_consume, new_register_and_consume,
                        'background result synchronization')

    text = replace_once(
        text,
        '''    private void showPlaylistPage() {
        consumePendingBatchCacheResults();
        if (headerBar != null) headerBar.setVisibility(View.GONE);
        if (statusView != null) statusView.setVisibility(View.GONE);
        if (playerPanel != null) playerPanel.setVisibility(View.GONE);
        if (searchPanel != null) searchPanel.setVisibility(View.GONE);
        if (playlistPanel != null) playlistPanel.setVisibility(View.VISIBLE);
        updatePlaylistCacheButton();
    }
''',
        '''    private void showPlaylistPage() {
        if (headerBar != null) headerBar.setVisibility(View.GONE);
        if (statusView != null) statusView.setVisibility(View.GONE);
        if (playerPanel != null) playerPanel.setVisibility(View.GONE);
        if (searchPanel != null) searchPanel.setVisibility(View.GONE);
        if (playlistPanel != null) playlistPanel.setVisibility(View.VISIBLE);
        updatePlaylistCacheButton();
        requestBatchCacheSync(true);
    }
''',
        'instant playlist page switch'
    )

    text = replace_once(
        text,
        '''            if (song == null || !song.isNetworkCatalog()) continue;
            if (!NetworkMediaCache.cachedAudioExists(this, song.cachedUri)) uncached.add(song);
''',
        '''            if (song == null || !song.isNetworkCatalog()) continue;
            if (song.cachedUri == null || song.cachedUri.trim().isEmpty()) uncached.add(song);
''',
        'no storage probing on UI thread'
    )

    text = replace_once(
        text,
        '''        PlaylistBatchCacheService.TaskState state = PlaylistBatchCacheService.readState(this);
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
''',
        '''        PlaylistBatchCacheService.TaskState state = cachedBatchTaskState;
        if (state == null) {
            cachePlaylistButton.setEnabled(true);
            cachePlaylistButton.setText("一键缓存未缓存歌曲（" + count + "首）");
            requestBatchCacheSync(false);
            return;
        }
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
''',
        'cached button task state'
    )

    text = replace_once(
        text,
        '''    private void cacheCurrentPlaylist() {
        consumePendingBatchCacheResults();
        List<Song> pending = uncachedSongsInCurrentPlaylist();
''',
        '''    private void cacheCurrentPlaylist() {
        List<Song> pending = uncachedSongsInCurrentPlaylist();
''',
        'nonblocking cache button click'
    )

    text = replace_once(
        text,
        '''        PlaylistBatchCacheService.TaskState state = PlaylistBatchCacheService.readState(this);
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
        if (samePlaylist && state.isRunningFresh()) {
''',
        '''        PlaylistBatchCacheService.TaskState state = cachedBatchTaskState;
        if (state == null) {
            requestBatchCacheSync(false);
            cachePlaylistButton.setText("正在读取缓存任务状态...");
            cachePlaylistButton.postDelayed(() -> requestBatchCacheSync(false), 350L);
            return;
        }
        boolean samePlaylist = state.belongsTo(currentPlaylistIndex);
        if (samePlaylist && state.isRunningFresh()) {
''',
        'cached state for button action'
    )

    text = text.replace(
        'cachePlaylistButton.postDelayed(this::updatePlaylistCacheButton, 800L);',
        'cachePlaylistButton.postDelayed(() -> requestBatchCacheSync(false), 500L);'
    )
    text = text.replace(
        'cachePlaylistButton.postDelayed(this::updatePlaylistCacheButton, 900L);',
        'cachePlaylistButton.postDelayed(() -> requestBatchCacheSync(false), 600L);'
    )

    old_play_start = '''        currentSong = song;
        saveLastSong(0);
        titleView.setText(song.title);
        artistView.setText(song.artist + " · " + song.source);
        updateLyricActionVisibility(song);
        statusView.setText("当前选择：" + song.title);
        showSongLyrics(song);
        publishPlaybackControlState(true);
'''
    new_play_start = '''        currentSong = song;
        // Push the new track identity before lyric parsing, list rendering or any
        // cache work. PlaybackControlService runs in its own process.
        publishPlaybackControlState(true);
        saveLastSong(0);
        titleView.setText(song.title);
        artistView.setText(song.artist + " · " + song.source);
        updateLyricActionVisibility(song);
        statusView.setText("当前选择：" + song.title);
        lyricHandler.post(() -> {
            if (currentSong == song) showSongLyrics(song);
        });
'''
    text = replace_once(text, old_play_start, new_play_start, 'early notification update')

    main_path.write_text(text, encoding='utf-8')

    service_path = root / 'app/src/main/java/com/jianglab/babywife/PlaylistBatchCacheService.java'
    service = service_path.read_text(encoding='utf-8')
    service = replace_once(
        service,
        '''    private String currentTitle = "";
    private String currentMessage = "";
    private long lastProgressMs;
''',
        '''    private String currentTitle = "";
    private String currentMessage = "";
    private long lastProgressMs;
    private long lastBroadcastMs;
    private long lastNotificationMs;
''',
        'broadcast throttle fields'
    )
    old_report = '''        writeState(this, state);
        if (broadcast) broadcastProgress(state, identity, updatedSongJson);
        if (STATUS_RUNNING.equals(status) || STATUS_STARTING.equals(status)) {
            updateNotification(done, total, message);
        }
'''
    new_report = '''        writeState(this, state);
        boolean terminal = STATUS_PAUSED.equals(status) || STATUS_COMPLETED.equals(status)
            || STATUS_ERROR.equals(status);
        boolean hasResult = identity != null && !identity.trim().isEmpty();
        if (broadcast && (terminal || hasResult || now - lastBroadcastMs >= 1200L)) {
            lastBroadcastMs = now;
            broadcastProgress(state, identity, updatedSongJson);
        }
        if ((STATUS_RUNNING.equals(status) || STATUS_STARTING.equals(status))
            && (hasResult || now - lastNotificationMs >= 1000L)) {
            lastNotificationMs = now;
            updateNotification(done, total, message);
        }
'''
    service = replace_once(service, old_report, new_report, 'progress broadcast throttling')
    service_path.write_text(service, encoding='utf-8')

    manifest_path = root / 'app/src/main/AndroidManifest.xml'
    manifest = manifest_path.read_text(encoding='utf-8')
    manifest = replace_once(
        manifest,
        '''        <service
            android:name=".PlaybackControlService"
            android:exported="false"
            android:foregroundServiceType="mediaPlayback" />''',
        '''        <service
            android:name=".PlaybackControlService"
            android:exported="false"
            android:process=":playback_control"
            android:foregroundServiceType="mediaPlayback" />''',
        'isolated playback notification process'
    )
    manifest_path.write_text(manifest, encoding='utf-8')

    gradle_path = root / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    gradle = gradle.replace('versionCode 2026080106', 'versionCode 2026080107')
    gradle = gradle.replace('versionName "2026.08.01.resumable-isolated-cache"',
                            'versionName "2026.08.01.responsive-ui-notification"')
    gradle_path.write_text(gradle, encoding='utf-8')

    checks_path = root / 'scripts/check_feature_requirements.py'
    checks = checks_path.read_text(encoding='utf-8')
    checks = checks.replace(
        "'version bumped': 'versionCode 2026080106' in gradle,",
        "'version bumped': 'versionCode 2026080107' in gradle,"
    )
    marker = "    'media player error containment': (\n"
    addition = '''    'nonblocking batch result merge and isolated notification': (
        'requestBatchCacheSync(true)' in main
        and 'PlaylistBatchUiSync' in main
        and 'batchCacheSyncRunning.compareAndSet(false, true)' in main
        and 'readPendingResults(appContext)' in main
        and 'consumePendingBatchCacheResults' not in main
        and 'song.cachedUri == null || song.cachedUri.trim().isEmpty()' in main
        and 'publishPlaybackControlState(true);\\n        saveLastSong(0);' in main
        and 'android:process=":playback_control"' in manifest
        and 'lastBroadcastMs' in batch_service
        and 'now - lastBroadcastMs >= 1200L' in batch_service
    ),
'''
    if addition not in checks:
        checks = checks.replace(marker, addition + marker, 1)
    checks_path.write_text(checks, encoding='utf-8')

    with (root / 'PROJECT_LOG.md').open('a', encoding='utf-8') as output:
        output.write('''\n\n## 2026-08-01 主界面卡顿与播放通知修复\n\n- 缓存进度广播不再在主线程扫描结果文件、解析 JSON、重写歌单和重绘列表。\n- 缓存状态与结果使用合并后的后台同步线程读取，主线程只应用已解析结果。\n- 打开软件、返回页面和点击当前歌单时先立即显示页面，再异步刷新缓存状态。\n- 一键缓存按钮统计不再逐首访问缓存文件系统。\n- 播放通知服务移入独立 `:playback_control` 进程，切歌时在歌词和列表处理前立即更新歌名。\n- 缓存进度广播与通知刷新增加节流，避免高频消息挤占主进程。\n''')
    with (root / 'docs/CHANGELOG.md').open('a', encoding='utf-8') as output:
        output.write('''\n\n## 2026-08-01 Responsive UI and playback notification\n\n- Moved batch result file scanning and parsing off the Android main thread.\n- Coalesced cache progress refreshes and stopped redrawing lists for every callback.\n- Made playlist/search navigation render immediately before asynchronous cache refresh.\n- Removed per-song storage probes from the cache button UI path.\n- Moved playback notification handling into a dedicated process and published track changes before lyric rendering.\n- Throttled batch progress broadcasts and notification updates.\n''')

    print('ui_responsiveness_notification_fix=applied')


if __name__ == '__main__':
    main()
