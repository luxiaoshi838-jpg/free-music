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
    main = main_path.read_text(encoding='utf-8')
    main = replace_once(
        main,
        '''            if (song == null || !song.isNetworkCatalog()) continue;
            if (song.cachedUri == null || song.cachedUri.trim().isEmpty()) uncached.add(song);
''',
        '''            if (song == null || !song.isNetworkCatalog()) continue;
            // Automatic batch failures stay available for manual replacement/playback,
            // but are not retried by every later one-click cache task.
            if ((song.cachedUri == null || song.cachedUri.trim().isEmpty())
                && !song.autoUnavailable) uncached.add(song);
''',
        'skip prior automatic failures'
    )
    main = replace_once(
        main,
        '''        new Thread(() -> {
            try {
                NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
''',
        '''        new Thread(() -> {
            try (NetworkMediaCache.ForegroundLease foregroundLease =
                     NetworkMediaCache.beginForegroundWork(this)) {
                NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
''',
        'foreground lease for cache and play'
    )
    main = replace_once(
        main,
        '''        new Thread(() -> {
            Song resolved = resolvePlayableSong(song);
            runOnUiThread(() -> {
''',
        '''        new Thread(() -> {
            Song resolved;
            try (NetworkMediaCache.ForegroundLease foregroundLease =
                     NetworkMediaCache.beginForegroundWork(this)) {
                resolved = resolvePlayableSong(song);
            }
            runOnUiThread(() -> {
''',
        'foreground lease for legacy resolve'
    )
    main = main.replace(
        '缓存任务使用独立进程，搜索和正常播放可同时进行',
        '后台缓存已降为低优先级；前台播放、读缓存和找新缓存会优先'
    )
    main_path.write_text(main, encoding='utf-8')

    network_path = root / 'app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java'
    network = network_path.read_text(encoding='utf-8')
    network = replace_once(
        network,
        'import java.util.Set;\n',
        'import java.util.Set;\nimport java.util.concurrent.atomic.AtomicInteger;\n',
        'atomic integer import'
    )
    network = replace_once(
        network,
        '''    private static final int MAX_FALLBACK_ATTEMPTS = 4;

    private NetworkMediaCache() {
''',
        '''    private static final int MAX_FALLBACK_ATTEMPTS = 4;
    private static final String PRIORITY_FOLDER = "network_cache_priority";
    private static final String FOREGROUND_LEASE_NAME = "foreground.lease";
    private static final long FOREGROUND_LEASE_VALID_MS = 8000L;
    private static final long FOREGROUND_LEASE_REFRESH_MS = 1500L;
    private static final AtomicInteger FOREGROUND_LEASE_COUNT = new AtomicInteger(0);
    private static final Object FOREGROUND_LEASE_GUARD = new Object();
    private static volatile boolean foregroundLeaseRefresherRunning;

    private NetworkMediaCache() {
''',
        'priority constants'
    )
    network = replace_once(
        network,
        '''    interface StatusCallback {
        void onStatus(String message);
    }

    static final class CacheResult {
''',
        '''    interface StatusCallback {
        void onStatus(String message);
    }

    static final class ForegroundPriorityException extends InterruptedException {
        ForegroundPriorityException() {
            super("前台播放优先，后台缓存稍后继续");
        }
    }

    static final class ForegroundLease implements AutoCloseable {
        private final Context appContext;
        private boolean closed;

        ForegroundLease(Context context) {
            appContext = context.getApplicationContext();
        }

        @Override
        public void close() {
            synchronized (FOREGROUND_LEASE_GUARD) {
                if (closed) return;
                closed = true;
                int remaining = FOREGROUND_LEASE_COUNT.decrementAndGet();
                if (remaining <= 0) {
                    FOREGROUND_LEASE_COUNT.set(0);
                    File lease = foregroundLeaseFile(appContext);
                    if (lease.isFile() && !lease.delete()) lease.deleteOnExit();
                }
            }
        }
    }

    static ForegroundLease beginForegroundWork(Context context) {
        if (context == null) throw new IllegalArgumentException("context is required");
        Context app = context.getApplicationContext();
        synchronized (FOREGROUND_LEASE_GUARD) {
            FOREGROUND_LEASE_COUNT.incrementAndGet();
            touchForegroundLease(app);
            startForegroundLeaseRefresher(app);
        }
        return new ForegroundLease(app);
    }

    static boolean foregroundWorkActive(Context context) {
        if (context == null) return false;
        File lease = foregroundLeaseFile(context.getApplicationContext());
        if (!lease.isFile()) return false;
        long age = System.currentTimeMillis() - lease.lastModified();
        if (age >= 0L && age <= FOREGROUND_LEASE_VALID_MS) return true;
        if (!lease.delete()) lease.deleteOnExit();
        return false;
    }

    static void awaitForegroundIdle(Context context) throws InterruptedException {
        while (foregroundWorkActive(context)) {
            checkInterrupted();
            Thread.sleep(200L);
        }
    }

    private static void awaitBackgroundTurn(Context context) throws InterruptedException {
        if (!isBatchCacheThread()) return;
        try {
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
        } catch (Exception ignored) {
        }
        awaitForegroundIdle(context);
    }

    private static void yieldIfForegroundRequested(Context context)
        throws ForegroundPriorityException, InterruptedException {
        checkInterrupted();
        if (isBatchCacheThread() && foregroundWorkActive(context)) {
            throw new ForegroundPriorityException();
        }
    }

    private static boolean isBatchCacheThread() {
        String name = Thread.currentThread().getName();
        return name != null && name.startsWith("PlaylistBatchCache");
    }

    private static File foregroundLeaseFile(Context context) {
        File root = new File(context.getFilesDir(), PRIORITY_FOLDER);
        if (!root.exists()) root.mkdirs();
        return new File(root, FOREGROUND_LEASE_NAME);
    }

    private static void touchForegroundLease(Context context) {
        try {
            File lease = foregroundLeaseFile(context);
            try (FileOutputStream output = new FileOutputStream(lease, false)) {
                output.write(String.valueOf(System.currentTimeMillis())
                    .getBytes(StandardCharsets.UTF_8));
                output.flush();
            }
        } catch (Exception ignored) {
        }
    }

    private static void startForegroundLeaseRefresher(Context context) {
        if (foregroundLeaseRefresherRunning) return;
        foregroundLeaseRefresherRunning = true;
        Thread refresher = new Thread(() -> {
            try {
                while (true) {
                    synchronized (FOREGROUND_LEASE_GUARD) {
                        if (FOREGROUND_LEASE_COUNT.get() <= 0) break;
                        touchForegroundLease(context);
                    }
                    Thread.sleep(FOREGROUND_LEASE_REFRESH_MS);
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            } finally {
                synchronized (FOREGROUND_LEASE_GUARD) {
                    foregroundLeaseRefresherRunning = false;
                    if (FOREGROUND_LEASE_COUNT.get() > 0) {
                        startForegroundLeaseRefresher(context);
                    }
                }
            }
        }, "ForegroundCachePriorityLease");
        refresher.setDaemon(true);
        refresher.start();
    }

    static final class CacheResult {
''',
        'foreground priority lease'
    )
    network = replace_once(
        network,
        '''        checkInterrupted();
        if (context == null) throw new IllegalArgumentException("context is required");
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
''',
        '''        checkInterrupted();
        if (context == null) throw new IllegalArgumentException("context is required");
        awaitBackgroundTurn(context);
        JSONObject requestedCatalog = canonicalCatalog(catalogJson);
''',
        'batch waits before cache task'
    )
    network = replace_once(
        network,
        '''            ResolvedChoice original = new ResolvedChoice(requestedCatalog,
                resolve(requestedCatalog.toString()));
''',
        '''            awaitBackgroundTurn(context);
            ResolvedChoice original = new ResolvedChoice(requestedCatalog,
                resolve(requestedCatalog.toString()));
''',
        'wait before original resolve'
    )
    network = replace_once(
        network,
        '''        for (CatalogSearch.Track alternative : alternatives) {
            checkInterrupted();
            if (attempted >= MAX_FALLBACK_ATTEMPTS) break;
''',
        '''        for (CatalogSearch.Track alternative : alternatives) {
            checkInterrupted();
            awaitBackgroundTurn(context);
            if (attempted >= MAX_FALLBACK_ATTEMPTS) break;
''',
        'wait before fallback resolve'
    )
    network = replace_once(
        network,
        '''        checkInterrupted();
        if (choice == null || choice.audioUrl().isEmpty()) return null;
''',
        '''        checkInterrupted();
        awaitBackgroundTurn(context);
        if (choice == null || choice.audioUrl().isEmpty()) return null;
''',
        'wait before cache choice'
    )
    network = replace_once(
        network,
        '''        try (CacheKeyLock cacheKeyLock = CacheKeyLock.acquire(context, key)) {
        String actualTitle = catalogTitle(actualCatalog);
''',
        '''        try (CacheKeyLock cacheKeyLock = CacheKeyLock.acquire(context, key)) {
        yieldIfForegroundRequested(context);
        String actualTitle = catalogTitle(actualCatalog);
''',
        'yield after song lock acquisition'
    )
    network = network.replace(
        'requestedLyric = fetchLyrics(requestedCatalog.toString());',
        'yieldIfForegroundRequested(context);\n                requestedLyric = fetchLyrics(requestedCatalog.toString());'
    )
    network = network.replace(
        'lyric = fetchLyrics(actualCatalog.toString());',
        'yieldIfForegroundRequested(context);\n                lyric = fetchLyrics(actualCatalog.toString());'
    )
    network = replace_once(
        network,
        '            download(choice.audioUrl(), actualSource, partial, callback);\n',
        '            download(context, choice.audioUrl(), actualSource, partial, callback);\n',
        'context-aware download'
    )
    network = replace_once(
        network,
        '''            if (!PlaybackCompatibility.isPlayable(partial)) {
''',
        '''            yieldIfForegroundRequested(context);
            if (!PlaybackCompatibility.isPlayable(partial)) {
''',
        'yield before real decoder probe'
    )
    network = replace_once(
        network,
        '''    private static void download(String urlText, String source, File partial, StatusCallback callback) throws Exception {
        checkInterrupted();
''',
        '''    private static void download(Context context, String urlText, String source,
                                 File partial, StatusCallback callback) throws Exception {
        checkInterrupted();
        yieldIfForegroundRequested(context);
''',
        'priority-aware download signature'
    )
    network = replace_once(
        network,
        '''                while ((count = input.read(buffer)) >= 0) {
                    checkInterrupted();
                    if (count == 0) continue;
''',
        '''                while ((count = input.read(buffer)) >= 0) {
                    checkInterrupted();
                    yieldIfForegroundRequested(context);
                    if (count == 0) continue;
''',
        'yield during batch download'
    )
    network_path.write_text(network, encoding='utf-8')

    batch_path = root / 'app/src/main/java/com/jianglab/babywife/PlaylistBatchCacheService.java'
    batch = batch_path.read_text(encoding='utf-8')
    batch = replace_once(
        batch,
        '''    private static final long PROGRESS_STALE_MS = 90000L;

    private NotificationManager notificationManager;
''',
        '''    private static final long PROGRESS_STALE_MS = 90000L;
    private static final long SONG_STALL_SKIP_MS = 45000L;

    private NotificationManager notificationManager;
''',
        'song stall timeout'
    )
    batch = replace_once(
        batch,
        '''    private long lastBroadcastMs;
    private long lastNotificationMs;

    static final class TaskState {
''',
        '''    private long lastBroadcastMs;
    private long lastNotificationMs;
    private volatile int currentRequestIndex = -1;
    private volatile String currentSongIdentity = "";
    private volatile String currentSongJson = "";
    private volatile boolean stallRecoveryRunning;

    static final class TaskState {
''',
        'stall recovery fields'
    )
    batch = replace_once(
        batch,
        '''            total = songs == null ? 0 : songs.length();
            done = 0;
            success = 0;
            failed = 0;
            currentTitle = "";
            currentMessage = total == 0 ? "没有需要缓存的歌曲" : "开始后台缓存";
            lastProgressMs = System.currentTimeMillis();
            stopRequested = false;
            workerRunning = true;
            startHeartbeat();
            workerThread = new Thread(() -> runBatch(request), "PlaylistBatchCacheWorker");
            workerThread.start();
''',
        '''            total = songs == null ? 0 : songs.length();
            TaskState previous = readState(this);
            boolean resumeSameGeneration = previous.generation == generation
                && previous.playlistIndex == playlistIndex;
            done = resumeSameGeneration ? Math.min(total, Math.max(0, previous.done)) : 0;
            success = resumeSameGeneration ? Math.max(0, previous.success) : 0;
            failed = resumeSameGeneration ? Math.max(0, previous.failed) : 0;
            currentTitle = "";
            currentRequestIndex = -1;
            currentSongIdentity = "";
            currentSongJson = "";
            stallRecoveryRunning = false;
            currentMessage = total == 0 ? "没有需要缓存的歌曲"
                : (done > 0 ? "继续后台缓存 " + done + "/" + total : "开始后台缓存");
            lastProgressMs = System.currentTimeMillis();
            stopRequested = false;
            workerRunning = true;
            startHeartbeat();
            workerThread = new Thread(() -> {
                try {
                    android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
                } catch (Exception ignored) {
                }
                runBatch(request);
            }, "PlaylistBatchCacheWorker");
            workerThread.start();
''',
        'resume cursor and low thread priority'
    )
    batch = replace_once(
        batch,
        '''            for (int index = 0; index < total; index++) {
                checkStopped();
                JSONObject row = songs.optJSONObject(index);
                if (row == null) continue;
                BatchSong song = new BatchSong(row);
                currentTitle = song.title;
''',
        '''            for (int index = done; index < total; index++) {
                checkStopped();
                JSONObject row = songs.optJSONObject(index);
                if (row == null) {
                    done = index + 1;
                    report(STATUS_RUNNING, "跳过无效缓存任务 " + done + "/" + total,
                        true, true, "", "");
                    continue;
                }
                BatchSong song = new BatchSong(row);
                currentRequestIndex = index;
                currentSongIdentity = song.identity;
                currentSongJson = song.songJson;
                currentTitle = song.title;
''',
        'resume loop and track current row'
    )
    batch = replace_once(
        batch,
        '''                    success++;
                    done++;
                    currentMessage = "已缓存 " + done + "/" + total + "：" + song.title;
                    report(STATUS_RUNNING, currentMessage, true, true, song.identity, updated);
                } catch (InterruptedException interrupted) {
                    throw interrupted;
                } catch (Exception error) {
''',
        '''                    success++;
                    done = index + 1;
                    currentMessage = "已缓存 " + done + "/" + total + "：" + song.title;
                    report(STATUS_RUNNING, currentMessage, true, true, song.identity, updated);
                    currentRequestIndex = -1;
                    currentSongIdentity = "";
                    currentSongJson = "";
                } catch (NetworkMediaCache.ForegroundPriorityException foregroundPriority) {
                    currentMessage = "前台播放优先，后台缓存已让路，稍后继续：" + song.title;
                    report(STATUS_RUNNING, currentMessage, true, true, "", "");
                    NetworkMediaCache.awaitForegroundIdle(this);
                    index--;
                } catch (InterruptedException interrupted) {
                    throw interrupted;
                } catch (Exception error) {
''',
        'foreground priority retry'
    )
    batch = replace_once(
        batch,
        '''                    failed++;
                    done++;
                    currentMessage = "缓存失败并已标红 " + done + "/" + total + "：" + song.title;
                    report(STATUS_RUNNING, currentMessage, true, true, song.identity, updated);
                }
            }
            currentTitle = "";
''',
        '''                    failed++;
                    done = index + 1;
                    currentMessage = "缓存失败并已跳过后续自动重试 " + done + "/" + total
                        + "：" + song.title;
                    report(STATUS_RUNNING, currentMessage, true, true, song.identity, updated);
                    currentRequestIndex = -1;
                    currentSongIdentity = "";
                    currentSongJson = "";
                }
            }
            currentRequestIndex = -1;
            currentSongIdentity = "";
            currentSongJson = "";
            currentTitle = "";
''',
        'failed songs skipped later'
    )
    batch = replace_once(
        batch,
        '''    private final Runnable heartbeatRunnable = new Runnable() {
        @Override
        public void run() {
            if (!workerRunning || stopRequested) return;
            report(STATUS_RUNNING, currentMessage, false, false, "", "");
            heartbeatHandler.postDelayed(this, HEARTBEAT_INTERVAL_MS);
        }
    };

    private void checkStopped() throws InterruptedException {
''',
        '''    private final Runnable heartbeatRunnable = new Runnable() {
        @Override
        public void run() {
            if (!workerRunning || stopRequested) return;
            long now = System.currentTimeMillis();
            if (NetworkMediaCache.foregroundWorkActive(PlaylistBatchCacheService.this)) {
                currentMessage = "前台播放、读取缓存或找新缓存优先，后台任务已让路";
                report(STATUS_RUNNING, currentMessage, true, true, "", "");
            } else if (currentRequestIndex >= 0
                && now - lastProgressMs >= SONG_STALL_SKIP_MS) {
                skipStalledSongAndRestart();
                return;
            } else {
                report(STATUS_RUNNING, currentMessage, false, false, "", "");
            }
            heartbeatHandler.postDelayed(this, HEARTBEAT_INTERVAL_MS);
        }
    };

    private synchronized void skipStalledSongAndRestart() {
        if (stallRecoveryRunning || currentRequestIndex < 0 || stopRequested) return;
        stallRecoveryRunning = true;
        int stalledIndex = currentRequestIndex;
        String identity = currentSongIdentity;
        String title = currentTitle;
        try {
            String updated = updateSongJson(currentSongJson, null, true);
            writeResult(stalledIndex, identity, updated);
            failed++;
            done = Math.max(done, stalledIndex + 1);
            currentMessage = "该歌曲缓存超过45秒无进展，已跳过并继续下一首：" + title;
            report(STATUS_RUNNING, currentMessage, true, true, identity, updated);
        } catch (Exception error) {
            done = Math.max(done, stalledIndex + 1);
            currentMessage = "该歌曲缓存超时，已跳过：" + title;
            report(STATUS_RUNNING, currentMessage, true, true, "", "");
        }
        currentRequestIndex = -1;
        currentSongIdentity = "";
        currentSongJson = "";
        scheduleRestart(generation);
        terminateProcess();
    }

    private void checkStopped() throws InterruptedException {
''',
        'stall watchdog and restart'
    )
    batch_path.write_text(batch, encoding='utf-8')

    gradle_path = root / 'app/build.gradle'
    gradle = gradle_path.read_text(encoding='utf-8')
    gradle = gradle.replace('versionCode 2026080107', 'versionCode 2026080109')
    gradle = gradle.replace('versionName "2026.08.01.responsive-ui-notification"',
                            'versionName "2026.08.01.low-priority-resilient-batch"')
    gradle_path.write_text(gradle, encoding='utf-8')

    checks_path = root / 'scripts/check_feature_requirements.py'
    checks = checks_path.read_text(encoding='utf-8')
    checks = checks.replace(
        "'version bumped': 'versionCode 2026080107' in gradle,",
        "'version bumped': 'versionCode 2026080109' in gradle,"
    )
    marker = "    'media player error containment': (\n"
    addition = '''    'foreground playback priority and resilient batch progression': (
        'beginForegroundWork(this)' in main
        and '&& !song.autoUnavailable' in main
        and 'ForegroundPriorityException' in network
        and 'yieldIfForegroundRequested(context)' in network
        and 'THREAD_PRIORITY_BACKGROUND' in batch_service
        and 'SONG_STALL_SKIP_MS = 45000L' in batch_service
        and 'for (int index = done; index < total; index++)' in batch_service
        and 'skipStalledSongAndRestart' in batch_service
        and '缓存失败并已跳过后续自动重试' in batch_service
    ),
'''
    if addition not in checks:
        checks = checks.replace(marker, addition + marker, 1)
    checks_path.write_text(checks, encoding='utf-8')

    with (root / 'PROJECT_LOG.md').open('a', encoding='utf-8') as output:
        output.write('''\n\n## 2026-08-01 前台播放优先与一键缓存连续推进修复\n\n- 播放页读取已有缓存、解析新来源或缓存当前歌曲时建立前台优先租约。\n- 独立一键缓存线程降为 Android 后台优先级，并在下载、解码和歌词阶段检测前台请求；检测到后释放歌曲锁并让前台先执行。\n- 自动缓存失败歌曲保留红色状态和手动替换入口，但后续一键缓存自动跳过，不再每次从同一失败歌曲开始。\n- 批量任务持久化已完成游标；缓存进程重启后从下一首继续，不回到固定开头。\n- 单首歌曲45秒无进展时自动标记失败、写入结果、重启独立缓存进程并继续下一首，避免缓存完一首后长期停滞。\n- 版本提升为 `2026080109 / 2026.08.01.low-priority-resilient-batch`，可覆盖用户上传的 `2026080108` 正式签名APK。\n''')
    with (root / 'docs/CHANGELOG.md').open('a', encoding='utf-8') as output:
        output.write('''\n\n## 2026-08-01 Foreground-priority resilient batch cache\n\n- Added a foreground cache/resolve lease so playback work preempts playlist batch caching.\n- Lowered the batch worker thread priority and cooperatively releases per-song cache locks when foreground playback needs resources.\n- Excluded prior automatic failures from future one-click cache requests while retaining manual replacement.\n- Persisted the processed cursor across isolated cache-process restarts.\n- Added a 45-second no-progress watchdog that skips the stalled track, restarts the isolated worker and continues with the next track.\n- Bumped the upgradeable build to versionCode 2026080109.\n''')

    print('low_priority_resilient_batch_fix=applied')


if __name__ == '__main__':
    main()
