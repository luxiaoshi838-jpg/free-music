from pathlib import Path

root = Path(__file__).resolve().parents[1]
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'
project_log_path = root / 'PROJECT_LOG.md'
changelog_path = root / 'docs/CHANGELOG.md'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'v142 patch target missing: {label}')
    return text.replace(old, new, 1)


main = main_path.read_text(encoding='utf-8')
gradle = gradle_path.read_text(encoding='utf-8')
check = check_path.read_text(encoding='utf-8')
project_log = project_log_path.read_text(encoding='utf-8')
changelog = changelog_path.read_text(encoding='utf-8')

gradle = replace_once(
    gradle,
    'versionCode 2026080141\n        versionName "2026.08.04.first-playable-source"',
    'versionCode 2026080142\n        versionName "2026.08.04.nonblocking-media-source"',
    'version bump',
)

main = replace_once(
    main,
    '''    private volatile boolean responsivenessWatchdogRunning = false;
    private volatile boolean noResponseReportWritten = false;
    private volatile long lastUiHeartbeatMs = 0L;
''',
    '''    private volatile boolean responsivenessWatchdogRunning = false;
    private volatile boolean noResponseReportWritten = false;
    private volatile long lastUiHeartbeatMs = 0L;
    private volatile boolean activityResumed = false;
    private volatile boolean windowFocused = false;
''',
    'watchdog lifecycle fields',
)

main = replace_once(
    main,
    '''    private final Runnable responsivenessHeartbeat = new Runnable() {
        @Override
        public void run() {
            lastUiHeartbeatMs = System.currentTimeMillis();
            noResponseReportWritten = false;
            if (responsivenessWatchdogRunning) {
                responsivenessHandler.postDelayed(this, UI_HEARTBEAT_INTERVAL_MS);
            }
        }
    };
''',
    '''    private final Runnable responsivenessHeartbeat = new Runnable() {
        @Override
        public void run() {
            lastUiHeartbeatMs = System.currentTimeMillis();
            noResponseReportWritten = false;
            if (responsivenessWatchdogRunning && activityResumed
                && windowFocused && isDeviceInteractive()) {
                responsivenessHandler.postDelayed(this, UI_HEARTBEAT_INTERVAL_MS);
            }
        }
    };
''',
    'foreground heartbeat',
)

main = replace_once(
    main,
    '''    @Override
    protected void onResume() {
        super.onResume();
        if (!pendingCacheFolderSelection || !fileManagementSettingsOpened) return;
        fileManagementSettingsOpened = false;
        if (hasFileManagementPermission()) {
            pendingCacheFolderSelection = false;
            chooseCacheFolder();
        } else {
            pendingCacheFolderSelection = false;
            toast("未授予文件管理权限，未更换缓存文件夹");
        }
    }

    private void scheduleStartupWork() {
''',
    '''    @Override
    protected void onResume() {
        super.onResume();
        activityResumed = true;
        lastUiHeartbeatMs = System.currentTimeMillis();
        noResponseReportWritten = false;
        if (responsivenessWatchdogRunning && windowFocused && isDeviceInteractive()) {
            responsivenessHandler.removeCallbacks(responsivenessHeartbeat);
            responsivenessHandler.post(responsivenessHeartbeat);
        }
        if (!pendingCacheFolderSelection || !fileManagementSettingsOpened) return;
        fileManagementSettingsOpened = false;
        if (hasFileManagementPermission()) {
            pendingCacheFolderSelection = false;
            chooseCacheFolder();
        } else {
            pendingCacheFolderSelection = false;
            toast("未授予文件管理权限，未更换缓存文件夹");
        }
    }

    @Override
    protected void onPause() {
        activityResumed = false;
        windowFocused = false;
        lastUiHeartbeatMs = System.currentTimeMillis();
        noResponseReportWritten = false;
        responsivenessHandler.removeCallbacks(responsivenessHeartbeat);
        super.onPause();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        windowFocused = hasFocus;
        lastUiHeartbeatMs = System.currentTimeMillis();
        noResponseReportWritten = false;
        responsivenessHandler.removeCallbacks(responsivenessHeartbeat);
        if (hasFocus && activityResumed && responsivenessWatchdogRunning
            && isDeviceInteractive()) {
            responsivenessHandler.post(responsivenessHeartbeat);
        }
    }

    private void scheduleStartupWork() {
''',
    'activity lifecycle watchdog gating',
)

main = replace_once(
    main,
    '''        report.append("thread=").append(threadName == null ? "" : threadName).append('\\n');
        report.append("playContext=").append(playingSearchQueue ? "search" : "playlist").append('\\n');
''',
    '''        report.append("thread=").append(threadName == null ? "" : threadName).append('\\n');
        report.append("activityResumed=").append(activityResumed).append('\\n');
        report.append("windowFocused=").append(windowFocused).append('\\n');
        report.append("deviceInteractive=").append(isDeviceInteractive()).append('\\n');
        report.append("playContext=").append(playingSearchQueue ? "search" : "playlist").append('\\n');
''',
    'report lifecycle context',
)

main = replace_once(
    main,
    '''    private void startResponsivenessWatchdog() {
        if (responsivenessWatchdogRunning) return;
        responsivenessWatchdogRunning = true;
        lastUiHeartbeatMs = System.currentTimeMillis();
        responsivenessHandler.post(responsivenessHeartbeat);
        Thread watchdog = new Thread(() -> {
            while (responsivenessWatchdogRunning) {
                try {
                    Thread.sleep(NO_RESPONSE_CHECK_INTERVAL_MS);
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                    return;
                }
                long gap = System.currentTimeMillis() - lastUiHeartbeatMs;
                if (gap >= NO_RESPONSE_THRESHOLD_MS && !noResponseReportWritten) {
                    noResponseReportWritten = true;
                    persistNoResponseReport(gap);
                }
            }
        }, "ui-responsiveness-watchdog");
        watchdog.setDaemon(true);
        watchdog.start();
    }

    private String trimForReport(String value, int maxLength) {
''',
    '''    private void startResponsivenessWatchdog() {
        if (responsivenessWatchdogRunning) return;
        responsivenessWatchdogRunning = true;
        lastUiHeartbeatMs = System.currentTimeMillis();
        if (activityResumed && windowFocused && isDeviceInteractive()) {
            responsivenessHandler.post(responsivenessHeartbeat);
        }
        Thread watchdog = new Thread(() -> {
            while (responsivenessWatchdogRunning) {
                try {
                    Thread.sleep(NO_RESPONSE_CHECK_INTERVAL_MS);
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                    return;
                }
                long now = System.currentTimeMillis();
                if (!activityResumed || !windowFocused || !isDeviceInteractive()) {
                    lastUiHeartbeatMs = now;
                    noResponseReportWritten = false;
                    continue;
                }
                long gap = now - lastUiHeartbeatMs;
                if (gap >= NO_RESPONSE_THRESHOLD_MS && !noResponseReportWritten) {
                    noResponseReportWritten = true;
                    persistNoResponseReport(gap);
                }
            }
        }, "ui-responsiveness-watchdog");
        watchdog.setDaemon(true);
        watchdog.start();
    }

    private boolean isDeviceInteractive() {
        try {
            PowerManager manager = (PowerManager) getSystemService(POWER_SERVICE);
            return manager == null || manager.isInteractive();
        } catch (Exception ignored) {
            return true;
        }
    }

    private String trimForReport(String value, int maxLength) {
''',
    'foreground-only watchdog',
)

old_prepare = '''    private void prepareLastSong(int position) {
        if (currentSong == null) {
            if (playButton != null) playButton.setText("▶");
            resetPlaybackProgress();
            return;
        }
        updateLyricActionVisibility(currentSong);
        showSongLyrics(currentSong);
        if (currentSong.isNetworkCatalog()) {
            if (currentSong.cachedUri != null && !currentSong.cachedUri.trim().isEmpty()
                && NetworkMediaCache.cachedAudioExists(this, currentSong.cachedUri)) {
                currentSong.uri = currentSong.cachedUri;
            } else {
                currentSong.cachedUri = "";
                currentSong.uri = "";
                if (playButton != null) playButton.setText("▶");
                statusView.setText("网络歌曲目录已恢复，点击播放时再缓存");
                resetPlaybackProgress();
                return;
            }
        }
        if (currentSong.uri == null || currentSong.uri.isEmpty()) {
            if (playButton != null) playButton.setText("▶");
            resetPlaybackProgress();
            return;
        }
        try {
            stopPlayback();
            mediaPlayer = createWakefulMediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(currentSong.uri));
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());
            mediaPlayer.prepare();
            if (position > 0) mediaPlayer.seekTo(position);
            updatePlaybackProgress();
            playButton.setText("▶");
        } catch (Exception ignored) {
            stopPlayback();
            playButton.setText("▶");
        }
    }
'''
new_prepare = '''    private void prepareLastSong(int position) {
        if (currentSong == null) {
            if (playButton != null) playButton.setText("▶");
            resetPlaybackProgress();
            return;
        }
        updateLyricActionVisibility(currentSong);
        if (currentSong.isNetworkCatalog()) {
            String recorded = currentSong.cachedUri == null ? "" : currentSong.cachedUri.trim();
            currentSong.uri = recorded;
        }
        if (playButton != null) playButton.setText("▶");
        resetPlaybackProgress();
        statusView.setText("已恢复上次歌曲，点击播放时再异步打开音频");
    }
'''
main = replace_once(main, old_prepare, new_prepare, 'remove synchronous last-song preparation')

old_start = '''    private void startLocalPlayback(Song song, int playToken, Runnable onStarted, Runnable onFailed) {
        try {
            stopPlayback();
            mediaPlayer = createWakefulMediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(song.uri));
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());
            mediaPlayer.setOnErrorListener((player, what, extra) -> {
                if (currentSong == song && playToken == playbackRequestSerial) {
                    stopPlayback();
                    playButton.setText("▶");
                    statusView.setText("播放失败：当前来源不可用");
                    if (onFailed != null) onFailed.run();
                    publishPlaybackControlState(true);
                }
                return true;
            });
            boolean online = song.uri.startsWith("http://") || song.uri.startsWith("https://");
            statusView.setText(online ? "正在打开在线音频..." : "缓存已就绪，正在启动播放...");
            mediaPlayer.setOnPreparedListener(player -> {
                try {
                    if (currentSong != song || playToken != playbackRequestSerial) return;
                    player.start();
                    onPlaybackStarted(song, onStarted);
                } catch (Exception error) {
                    stopPlayback();
                    playButton.setText("▶");
                    statusView.setText("播放失败：" + error.getMessage());
                    if (onFailed != null) onFailed.run();
                }
            });
            mediaPlayer.prepareAsync();
        } catch (Exception ex) {
            stopPlayback();
            playButton.setText("▶");
            if (onFailed != null) onFailed.run();
            toast("播放失败：" + ex.getMessage());
        }
    }
'''
new_start = '''    private void startLocalPlayback(Song song, int playToken, Runnable onStarted, Runnable onFailed) {
        stopPlayback();
        String playbackUri = song.uri == null ? "" : song.uri.trim();
        boolean online = playbackUri.startsWith("http://") || playbackUri.startsWith("https://");
        statusView.setText(online ? "正在异步打开在线音频..." : "缓存已就绪，正在异步打开音频...");
        new Thread(() -> {
            MediaPlayer preparedPlayer = null;
            try {
                preparedPlayer = createWakefulMediaPlayer();
                preparedPlayer.setDataSource(this, Uri.parse(playbackUri));
                MediaPlayer readyPlayer = preparedPlayer;
                runOnUiThread(() -> {
                    if (currentSong != song || playToken != playbackRequestSerial) {
                        try {
                            readyPlayer.release();
                        } catch (Exception ignored) {
                        }
                        return;
                    }
                    mediaPlayer = readyPlayer;
                    mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());
                    mediaPlayer.setOnErrorListener((player, what, extra) -> {
                        if (currentSong == song && playToken == playbackRequestSerial) {
                            stopPlayback();
                            playButton.setText("▶");
                            statusView.setText("播放失败：当前来源不可用");
                            if (onFailed != null) onFailed.run();
                            publishPlaybackControlState(true);
                        }
                        return true;
                    });
                    mediaPlayer.setOnPreparedListener(player -> {
                        try {
                            if (currentSong != song || playToken != playbackRequestSerial) return;
                            player.start();
                            onPlaybackStarted(song, onStarted);
                        } catch (Exception error) {
                            stopPlayback();
                            playButton.setText("▶");
                            statusView.setText("播放失败：" + error.getMessage());
                            if (onFailed != null) onFailed.run();
                        }
                    });
                    try {
                        mediaPlayer.prepareAsync();
                    } catch (Exception error) {
                        stopPlayback();
                        playButton.setText("▶");
                        statusView.setText("播放失败：" + error.getMessage());
                        if (onFailed != null) onFailed.run();
                    }
                });
            } catch (Exception ex) {
                if (preparedPlayer != null) {
                    try {
                        preparedPlayer.release();
                    } catch (Exception ignored) {
                    }
                }
                runOnUiThread(() -> {
                    if (currentSong != song || playToken != playbackRequestSerial) return;
                    stopPlayback();
                    playButton.setText("▶");
                    statusView.setText("打开音频失败：" + ex.getMessage());
                    if (onFailed != null) onFailed.run();
                });
            }
        }, "media-source-open").start();
    }
'''
main = replace_once(main, old_start, new_start, 'off-main media data source open')

check = replace_once(
    check,
    "    'version bumped': 'versionCode 2026080141' in gradle,",
    "    'version bumped': 'versionCode 2026080142' in gradle,",
    'feature-check version',
)

insert_before = "    'version bumped': 'versionCode 2026080142' in gradle,"
new_checks = '''    'content uri data source opens off main thread': (
        '"media-source-open"' in main
        and 'preparedPlayer.setDataSource(this, Uri.parse(playbackUri));' in main
        and main.find('new Thread(() -> {', main.find('private void startLocalPlayback'))
            < main.find('preparedPlayer.setDataSource(this, Uri.parse(playbackUri));', main.find('private void startLocalPlayback'))
        and 'mediaPlayer.setDataSource(this, Uri.parse(song.uri));' not in main
        and 'mediaPlayer.prepare();' not in main[main.find('private void prepareLastSong'):main.find('private void playSong')]
        and 'NetworkMediaCache.cachedAudioExists(this, currentSong.cachedUri)' not in main[main.find('private void prepareLastSong'):main.find('private void playSong')]
    ),
    'watchdog only monitors interactive foreground window': (
        'activityResumed = false' in main
        and 'windowFocused = false' in main
        and 'protected void onPause()' in main
        and 'onWindowFocusChanged(boolean hasFocus)' in main
        and '!activityResumed || !windowFocused || !isDeviceInteractive()' in main
        and 'deviceInteractive=' in main
    ),
'''
if insert_before not in check:
    raise SystemExit('v142 check insertion point missing')
check = check.replace(insert_before, new_checks + insert_before, 1)

project_log += '''

## 2026-08-04 - Prevent external content URI playback from blocking the UI

- Moved MediaPlayer data-source opening for file/content/http URIs to a worker thread.
- Main thread now only receives the prepared MediaPlayer object and calls prepareAsync.
- Removed the dormant synchronous last-song cache validation and MediaPlayer.prepare path.
- Responsiveness watchdog now runs only while the activity is resumed, focused and the device is interactive.
- Added lifecycle state to no-response reports to distinguish foreground ANRs from screen/background suspension.
'''

changelog += '''

## 2026.08.04.nonblocking-media-source

- Fixed possible long UI freezes when opening cached audio through Android document-provider content URIs.
- Opening the MediaPlayer data source now happens off the main thread.
- Removed synchronous restored-song preparation.
- No-response monitoring pauses while the app is backgrounded, unfocused or the screen is not interactive.
- Includes first-playable-source search behavior from v141.
'''

main_path.write_text(main, encoding='utf-8')
gradle_path.write_text(gradle, encoding='utf-8')
check_path.write_text(check, encoding='utf-8')
project_log_path.write_text(project_log, encoding='utf-8')
changelog_path.write_text(changelog, encoding='utf-8')
print('Applied v142 nonblocking media source and foreground watchdog repair')
