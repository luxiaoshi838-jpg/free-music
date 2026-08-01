#!/usr/bin/env python3
from pathlib import Path
import argparse


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    root = Path(parser.parse_args().root).resolve()

    service_path = root / "app/src/main/java/com/jianglab/babywife/PlaylistBatchCacheService.java"
    service_path.write_text(r'''package com.jianglab.babywife;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Foreground data-sync service for playlist batch caching.
 * The queue survives leaving the Activity, lock-screen use and background playback.
 */
public final class PlaylistBatchCacheService extends Service {
    static final String ACTION_PROGRESS = "com.jianglab.babywife.PLAYLIST_BATCH_CACHE_PROGRESS";
    static final String EXTRA_RUNNING = "running";
    static final String EXTRA_DONE = "done";
    static final String EXTRA_TOTAL = "total";
    static final String EXTRA_SUCCESS = "success";
    static final String EXTRA_FAILED = "failed";
    static final String EXTRA_MESSAGE = "message";
    static final String EXTRA_IDENTITY = "identity";
    static final String EXTRA_UPDATED_SONG_JSON = "updated_song_json";

    private static final String ACTION_START = "com.jianglab.babywife.PLAYLIST_BATCH_CACHE_START";
    private static final String EXTRA_PLAYLIST_INDEX = "playlist_index";
    private static final String PREFS_NAME = "babywife_state";
    private static final String KEY_PLAYLISTS = "playlists_v2";
    private static final String STATE_PREFS = "playlist_batch_cache_state";
    private static final String KEY_RUNNING = "running";
    private static final String KEY_PLAYLIST_INDEX = "playlist_index";
    private static final String KEY_DONE = "done";
    private static final String KEY_TOTAL = "total";
    private static final String KEY_SUCCESS = "success";
    private static final String KEY_FAILED = "failed";
    private static final String KEY_CURRENT_TITLE = "current_title";
    private static final String KEY_MESSAGE = "message";
    private static final String CHANNEL_ID = "playlist_batch_cache";
    private static final int NOTIFICATION_ID = 1515;
    private static final long WAKE_LOCK_TIMEOUT_MS = 6L * 60L * 60L * 1000L;
    private static final Object PLAYLIST_WRITE_LOCK = new Object();

    private NotificationManager notificationManager;
    private volatile boolean workerRunning = false;
    private PowerManager.WakeLock wakeLock;

    static void start(Context context, int playlistIndex) {
        Intent intent = new Intent(context, PlaylistBatchCacheService.class)
            .setAction(ACTION_START)
            .putExtra(EXTRA_PLAYLIST_INDEX, Math.max(0, playlistIndex));
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    static boolean isRunning(Context context) {
        return context.getSharedPreferences(STATE_PREFS, MODE_PRIVATE)
            .getBoolean(KEY_RUNNING, false);
    }

    static String progressLabel(Context context) {
        SharedPreferences state = context.getSharedPreferences(STATE_PREFS, MODE_PRIVATE);
        if (!state.getBoolean(KEY_RUNNING, false)) return "";
        int done = state.getInt(KEY_DONE, 0);
        int total = state.getInt(KEY_TOTAL, 0);
        String title = state.getString(KEY_CURRENT_TITLE, "");
        String prefix = total > 0 ? "后台缓存 " + done + "/" + total : "正在准备后台缓存";
        return title == null || title.trim().isEmpty() ? prefix : prefix + "：" + title;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        notificationManager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        ensureForeground(0, 0, "正在准备歌单缓存");
        int playlistIndex = intent == null
            ? getSharedPreferences(STATE_PREFS, MODE_PRIVATE).getInt(KEY_PLAYLIST_INDEX, 0)
            : intent.getIntExtra(EXTRA_PLAYLIST_INDEX, 0);
        startWorkerIfNeeded(Math.max(0, playlistIndex));
        return START_REDELIVER_INTENT;
    }

    private synchronized void startWorkerIfNeeded(int playlistIndex) {
        if (workerRunning) return;
        workerRunning = true;
        getSharedPreferences(STATE_PREFS, MODE_PRIVATE).edit()
            .putBoolean(KEY_RUNNING, true)
            .putInt(KEY_PLAYLIST_INDEX, playlistIndex)
            .putInt(KEY_DONE, 0)
            .putInt(KEY_TOTAL, 0)
            .putInt(KEY_SUCCESS, 0)
            .putInt(KEY_FAILED, 0)
            .putString(KEY_CURRENT_TITLE, "")
            .putString(KEY_MESSAGE, "正在准备歌单缓存")
            .commit();
        new Thread(() -> runBatch(playlistIndex), "PlaylistBatchCacheService").start();
    }

    private void runBatch(int playlistIndex) {
        acquireWakeLock();
        int success = 0;
        int failed = 0;
        try {
            List<BatchSong> pending = loadPendingSongs(playlistIndex);
            int total = pending.size();
            persistProgress(true, 0, total, 0, 0, "", total == 0 ? "没有需要缓存的歌曲" : "开始后台缓存");
            broadcastProgress(true, 0, total, 0, 0, total == 0 ? "没有需要缓存的歌曲" : "开始后台缓存", "", "");
            updateNotification(0, total, total == 0 ? "没有需要缓存的歌曲" : "开始后台缓存");

            for (int index = 0; index < pending.size(); index++) {
                BatchSong song = pending.get(index);
                int progress = index + 1;
                String preparing = "正在缓存 " + progress + "/" + total + "：" + song.title;
                persistProgress(true, index, total, success, failed, song.title, preparing);
                broadcastProgress(true, index, total, success, failed, preparing, "", "");
                updateNotification(index, total, song.title);
                try {
                    NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
                        this,
                        song.catalogJson,
                        true,
                        message -> {
                            String detail = "缓存 " + progress + "/" + total + "：" + song.title + " · " + message;
                            persistProgress(true, progress - 1, total, successCount(), failedCount(), song.title, detail);
                            broadcastProgress(true, progress - 1, total, successCount(), failedCount(), detail, "", "");
                            updateNotification(progress - 1, total, song.title + " · " + message);
                        }
                    );
                    String updatedJson = updateSongPreferences(song.identity, cached, false);
                    success++;
                    setCounts(success, failed);
                    String message = "已缓存 " + progress + "/" + total + "：" + song.title;
                    persistProgress(true, progress, total, success, failed, song.title, message);
                    broadcastProgress(true, progress, total, success, failed, message, song.identity, updatedJson);
                    updateNotification(progress, total, song.title);
                } catch (Exception error) {
                    String updatedJson = updateSongPreferences(song.identity, null, true);
                    failed++;
                    setCounts(success, failed);
                    String message = "缓存失败并已标红 " + progress + "/" + total + "：" + song.title;
                    persistProgress(true, progress, total, success, failed, song.title, message);
                    broadcastProgress(true, progress, total, success, failed, message, song.identity, updatedJson);
                    updateNotification(progress, total, "失败：" + song.title);
                }
            }
            String completed = "一键缓存完成：成功 " + success + " 首，失败 " + failed + " 首";
            persistProgress(false, pending.size(), pending.size(), success, failed, "", completed);
            broadcastProgress(false, pending.size(), pending.size(), success, failed, completed, "", "");
            showCompletedNotification(completed);
        } catch (Throwable error) {
            String message = "后台缓存任务异常停止：" + safeMessage(error);
            persistProgress(false, 0, 0, success, failed, "", message);
            broadcastProgress(false, 0, 0, success, failed, message, "", "");
            showCompletedNotification(message);
        } finally {
            releaseWakeLock();
            workerRunning = false;
            stopForeground(false);
            stopSelf();
        }
    }

    private volatile int callbackSuccess = 0;
    private volatile int callbackFailed = 0;

    private void setCounts(int success, int failed) {
        callbackSuccess = success;
        callbackFailed = failed;
    }

    private int successCount() {
        return callbackSuccess;
    }

    private int failedCount() {
        return callbackFailed;
    }

    private List<BatchSong> loadPendingSongs(int playlistIndex) throws Exception {
        List<BatchSong> pending = new ArrayList<>();
        String raw = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(KEY_PLAYLISTS, "[]");
        JSONArray playlists = new JSONArray(raw == null ? "[]" : raw);
        if (playlistIndex < 0 || playlistIndex >= playlists.length()) return pending;
        JSONObject playlist = playlists.optJSONObject(playlistIndex);
        JSONArray songs = playlist == null ? null : playlist.optJSONArray("songs");
        if (songs == null) return pending;
        for (int index = 0; index < songs.length(); index++) {
            JSONObject song = songs.optJSONObject(index);
            if (song == null) continue;
            String catalogJson = song.optString("catalogJson", "").trim();
            if (catalogJson.isEmpty()) continue;
            String cachedUri = song.optString("cachedUri", "").trim();
            if (!cachedUri.isEmpty() && NetworkMediaCache.validateCatalogCache(this, catalogJson)) continue;
            pending.add(new BatchSong(
                songIdentity(song),
                catalogJson,
                song.optString("title", "未知歌曲")
            ));
        }
        return pending;
    }

    private String updateSongPreferences(String identity, NetworkMediaCache.CacheResult cached,
                                         boolean failed) throws Exception {
        synchronized (PLAYLIST_WRITE_LOCK) {
            SharedPreferences preferences = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
            String raw = preferences.getString(KEY_PLAYLISTS, "[]");
            JSONArray playlists = new JSONArray(raw == null ? "[]" : raw);
            String updatedJson = "";
            for (int playlistIndex = 0; playlistIndex < playlists.length(); playlistIndex++) {
                JSONObject playlist = playlists.optJSONObject(playlistIndex);
                JSONArray songs = playlist == null ? null : playlist.optJSONArray("songs");
                if (songs == null) continue;
                for (int songIndex = 0; songIndex < songs.length(); songIndex++) {
                    JSONObject song = songs.optJSONObject(songIndex);
                    if (song == null || !identity.equals(songIdentity(song))) continue;
                    if (failed || cached == null) {
                        song.put("cachedUri", "");
                        song.put("uri", "");
                        song.put("unavailable", true);
                        song.put("autoUnavailable", true);
                    } else {
                        song.put("cachedUri", cached.audioUri == null ? "" : cached.audioUri);
                        song.put("uri", cached.audioUri == null ? "" : cached.audioUri);
                        if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
                            song.put("catalogJson", cached.catalogJson);
                        }
                        if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
                            song.put("source", CatalogSearch.labelForSource(cached.sourceCode));
                        }
                        String existingLyric = song.optString("lyric", "");
                        if (existingLyric.trim().isEmpty()
                            && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                            song.put("lyric", cached.lyric);
                            song.put("lyricLabel", song.optString("title", "未知歌曲")
                                + " · " + song.optString("artist", "未知歌手")
                                + " · " + song.optString("source", ""));
                        }
                        song.put("unavailable", false);
                        song.put("autoUnavailable", false);
                        song.put("manualUnavailable", false);
                    }
                    if (updatedJson.isEmpty()) updatedJson = song.toString();
                }
            }
            preferences.edit().putString(KEY_PLAYLISTS, playlists.toString()).commit();
            return updatedJson;
        }
    }

    private String songIdentity(JSONObject song) {
        try {
            JSONObject catalog = new JSONObject(song.optString("catalogJson", "{}"));
            String source = catalog.optString("source", "").trim().toLowerCase();
            String id = catalog.optString("id", "").trim();
            if (!source.isEmpty() && !id.isEmpty()) return source + "|" + id;
        } catch (Exception ignored) {
        }
        return (song.optString("title", "") + "|"
            + song.optString("artist", "") + "|"
            + song.optString("source", "")).toLowerCase();
    }

    private void persistProgress(boolean running, int done, int total, int success, int failed,
                                 String currentTitle, String message) {
        getSharedPreferences(STATE_PREFS, MODE_PRIVATE).edit()
            .putBoolean(KEY_RUNNING, running)
            .putInt(KEY_DONE, Math.max(0, done))
            .putInt(KEY_TOTAL, Math.max(0, total))
            .putInt(KEY_SUCCESS, Math.max(0, success))
            .putInt(KEY_FAILED, Math.max(0, failed))
            .putString(KEY_CURRENT_TITLE, currentTitle == null ? "" : currentTitle)
            .putString(KEY_MESSAGE, message == null ? "" : message)
            .commit();
    }

    private void broadcastProgress(boolean running, int done, int total, int success, int failed,
                                   String message, String identity, String updatedSongJson) {
        Intent intent = new Intent(ACTION_PROGRESS)
            .setPackage(getPackageName())
            .putExtra(EXTRA_RUNNING, running)
            .putExtra(EXTRA_DONE, done)
            .putExtra(EXTRA_TOTAL, total)
            .putExtra(EXTRA_SUCCESS, success)
            .putExtra(EXTRA_FAILED, failed)
            .putExtra(EXTRA_MESSAGE, message == null ? "" : message)
            .putExtra(EXTRA_IDENTITY, identity == null ? "" : identity)
            .putExtra(EXTRA_UPDATED_SONG_JSON, updatedSongJson == null ? "" : updatedSongJson);
        sendBroadcast(intent);
    }

    private void ensureForeground(int done, int total, String text) {
        startForeground(NOTIFICATION_ID, buildNotification(done, total, text, true));
    }

    private void updateNotification(int done, int total, String text) {
        if (notificationManager != null) {
            notificationManager.notify(NOTIFICATION_ID, buildNotification(done, total, text, true));
        }
    }

    private void showCompletedNotification(String text) {
        if (notificationManager != null) {
            notificationManager.notify(NOTIFICATION_ID, buildNotification(0, 0, text, false));
        }
    }

    private Notification buildNotification(int done, int total, String text, boolean ongoing) {
        Intent openIntent = new Intent(this, MainActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
            this,
            1515,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, CHANNEL_ID)
            : new Notification.Builder(this);
        builder.setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle(ongoing ? "正在后台缓存歌单" : "歌单缓存任务结束")
            .setContentText(text == null ? "" : text)
            .setContentIntent(contentIntent)
            .setCategory(Notification.CATEGORY_PROGRESS)
            .setOngoing(ongoing)
            .setOnlyAlertOnce(true)
            .setShowWhen(false);
        if (ongoing) builder.setProgress(Math.max(0, total), Math.max(0, done), total <= 0);
        else builder.setAutoCancel(true);
        return builder.build();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || notificationManager == null) return;
        NotificationChannel channel = new NotificationChannel(
            CHANNEL_ID,
            "歌单后台缓存",
            NotificationManager.IMPORTANCE_LOW
        );
        channel.setDescription("离开软件或锁屏后继续缓存歌单歌曲");
        channel.setShowBadge(false);
        notificationManager.createNotificationChannel(channel);
    }

    private void acquireWakeLock() {
        try {
            PowerManager manager = (PowerManager) getSystemService(POWER_SERVICE);
            if (manager == null) return;
            wakeLock = manager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,
                getPackageName() + ":playlist-batch-cache");
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire(WAKE_LOCK_TIMEOUT_MS);
        } catch (Throwable ignored) {
            wakeLock = null;
        }
    }

    private void releaseWakeLock() {
        if (wakeLock == null) return;
        try {
            if (wakeLock.isHeld()) wakeLock.release();
        } catch (Throwable ignored) {
        }
        wakeLock = null;
    }

    private String safeMessage(Throwable error) {
        if (error == null || error.getMessage() == null || error.getMessage().trim().isEmpty()) {
            return "未知错误";
        }
        return error.getMessage().trim();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        releaseWakeLock();
        super.onDestroy();
    }

    private static final class BatchSong {
        final String identity;
        final String catalogJson;
        final String title;

        BatchSong(String identity, String catalogJson, String title) {
            this.identity = identity == null ? "" : identity;
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.title = title == null || title.trim().isEmpty() ? "未知歌曲" : title;
        }
    }
}
''', encoding="utf-8")

    manifest_path = root / "app/src/main/AndroidManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")
    manifest = replace_once(
        manifest,
        '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />\n',
        '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />\n'
        '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />\n',
        "data sync foreground permission",
    )
    manifest = replace_once(
        manifest,
        '''        <service
            android:name=".PlaybackControlService"
            android:exported="false"
            android:foregroundServiceType="mediaPlayback" />
''',
        '''        <service
            android:name=".PlaybackControlService"
            android:exported="false"
            android:foregroundServiceType="mediaPlayback" />

        <service
            android:name=".PlaylistBatchCacheService"
            android:exported="false"
            android:foregroundServiceType="dataSync" />
''',
        "batch service manifest entry",
    )
    manifest_path.write_text(manifest, encoding="utf-8")

    main_path = root / "app/src/main/java/com/jianglab/babywife/MainActivity.java"
    main = main_path.read_text(encoding="utf-8")
    main = replace_once(
        main,
        '''    private boolean playbackReceiverRegistered = false;
    private long lastPublishedPlaybackSecond = -1L;''',
        '''    private boolean playbackReceiverRegistered = false;
    private boolean batchCacheReceiverRegistered = false;
    private long lastPublishedPlaybackSecond = -1L;''',
        "batch receiver registered field",
    )
    receiver_anchor = '''    private final Runnable lyricTicker = new Runnable() {'''
    receiver_code = r'''    private final BroadcastReceiver playlistBatchCacheReceiver = new BroadcastReceiver() {
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

    private final Runnable lyricTicker = new Runnable() {'''
    main = replace_once(main, receiver_anchor, receiver_code, "batch progress receiver")
    main = replace_once(
        main,
        '''        registerPlaybackControlReceiver();
        PlaybackControlService.ensureStarted(this);''',
        '''        registerPlaybackControlReceiver();
        registerPlaylistBatchCacheReceiver();
        PlaybackControlService.ensureStarted(this);''',
        "register batch receiver on create",
    )
    main = replace_once(
        main,
        '''    private MediaPlayer createWakefulMediaPlayer() {''',
        r'''    private void registerPlaylistBatchCacheReceiver() {
        if (batchCacheReceiverRegistered) return;
        IntentFilter filter = new IntentFilter(PlaylistBatchCacheService.ACTION_PROGRESS);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(playlistBatchCacheReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(playlistBatchCacheReceiver, filter);
        }
        batchCacheReceiverRegistered = true;
        playlistBatchCaching = PlaylistBatchCacheService.isRunning(this);
    }

    private void applyBatchSongUpdate(String identity, String updatedSongJson) {
        try {
            Song updated = Song.fromJson(new JSONObject(updatedSongJson));
            for (Playlist playlist : playlists) {
                for (Song item : playlist.songs) {
                    if (item != null && identity.equals(item.key())) copyBatchSongFields(item, updated);
                }
            }
            if (currentSong != null && identity.equals(currentSong.key())) {
                copyBatchSongFields(currentSong, updated);
                if (titleView != null) titleView.setText(currentSong.title);
                if (artistView != null) artistView.setText(currentSong.artist + " · " + currentSong.source);
            }
            savePlaylists();
        } catch (Exception ignored) {
        }
    }

    private void copyBatchSongFields(Song target, Song source) {
        if (target == null || source == null) return;
        target.source = source.source;
        target.lyric = source.lyric;
        target.lyricLabel = source.lyricLabel;
        target.uri = source.uri;
        target.catalogJson = source.catalogJson;
        target.cachedUri = source.cachedUri;
        target.unavailable = source.unavailable;
        target.autoUnavailable = source.autoUnavailable;
        target.manualUnavailable = source.manualUnavailable;
        target.manualAttempt = false;
    }

    private MediaPlayer createWakefulMediaPlayer() {''',
        "batch receiver helpers",
    )

    start = main.index("    private void updatePlaylistCacheButton() {")
    end = main.index("    private void renderEmptyPlayer() {", start)
    replacement = r'''    private void updatePlaylistCacheButton() {
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
    main = main[:start] + replacement + main[end:]
    main = replace_once(
        main,
        '''        if (playbackReceiverRegistered) {
            try {
                unregisterReceiver(playbackCommandReceiver);
            } catch (Exception ignored) {
            }
            playbackReceiverRegistered = false;
        }
        stopService(new Intent(this, PlaybackControlService.class));''',
        '''        if (playbackReceiverRegistered) {
            try {
                unregisterReceiver(playbackCommandReceiver);
            } catch (Exception ignored) {
            }
            playbackReceiverRegistered = false;
        }
        if (batchCacheReceiverRegistered) {
            try {
                unregisterReceiver(playlistBatchCacheReceiver);
            } catch (Exception ignored) {
            }
            batchCacheReceiverRegistered = false;
        }
        stopService(new Intent(this, PlaybackControlService.class));''',
        "unregister batch receiver",
    )
    main_path.write_text(main, encoding="utf-8")

    gradle_path = root / "app/build.gradle"
    gradle = gradle_path.read_text(encoding="utf-8")
    gradle = replace_once(gradle, "versionCode 2026080104", "versionCode 2026080105", "version code")
    gradle = replace_once(
        gradle,
        'versionName "2026.08.01.real-decoder-validation"',
        'versionName "2026.08.01.background-playlist-cache"',
        "version name",
    )
    gradle_path.write_text(gradle, encoding="utf-8")

    checks_path = root / "scripts/check_feature_requirements.py"
    checks = checks_path.read_text(encoding="utf-8")
    checks = replace_once(
        checks,
        "compat = (root / 'app/src/main/java/com/jianglab/babywife/PlaybackCompatibility.java').read_text(encoding='utf-8')\n",
        "compat = (root / 'app/src/main/java/com/jianglab/babywife/PlaybackCompatibility.java').read_text(encoding='utf-8')\n"
        "batch_service = (root / 'app/src/main/java/com/jianglab/babywife/PlaylistBatchCacheService.java').read_text(encoding='utf-8')\n"
        "manifest = (root / 'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')\n",
        "load batch service checks",
    )
    checks = replace_once(
        checks,
        '''    'playlist one-click cache and failure marking': (
        '一键缓存未缓存歌曲' in main
        and 'cacheCurrentPlaylist' in main
        and 'uncachedSongsInCurrentPlaylist' in main
        and 'markSongUnavailable(song, true)' in main
        and '缓存失败的歌曲已标红' in main
    ),''',
        '''    'playlist one-click background cache and failure marking': (
        '一键缓存未缓存歌曲' in main
        and 'cacheCurrentPlaylist' in main
        and 'PlaylistBatchCacheService.start(this, currentPlaylistIndex)' in main
        and 'PlaylistBatchCacheService.isRunning(this)' in main
        and 'FOREGROUND_SERVICE_DATA_SYNC' in manifest
        and 'android:foregroundServiceType="dataSync"' in manifest
        and 'PowerManager.PARTIAL_WAKE_LOCK' in batch_service
        and 'START_REDELIVER_INTENT' in batch_service
        and 'NetworkMediaCache.cache(' in batch_service
        and 'song.put("unavailable", true)' in batch_service
        and 'ACTION_PROGRESS' in batch_service
    ),''',
        "background batch feature check",
    )
    checks = replace_once(checks, "'versionCode 2026080104' in gradle", "'versionCode 2026080105' in gradle", "version check")
    checks_path.write_text(checks, encoding="utf-8")

    project_log = root / "PROJECT_LOG.md"
    project_log.write_text(project_log.read_text(encoding="utf-8") + "\n\n## 2026-08-01 歌单后台缓存服务\n\n- 一键缓存改由独立前台 dataSync 服务执行，离开页面、锁屏或后台播放时继续运行。\n- 服务持有部分唤醒锁、持久化进度，并在被系统重建时重新计算未完成歌曲继续处理。\n- 每首缓存结果直接写回歌单存储；失败歌曲立即标红，重新打开软件后状态仍保留。\n", encoding="utf-8")

    changelog = root / "docs/CHANGELOG.md"
    changelog.write_text(changelog.read_text(encoding="utf-8") + "\n\n## 2026-08-01 Background playlist cache service\n\n- Moved one-click playlist caching from an Activity thread into a foreground data-sync service.\n- Batch caching now continues during background playback, lock screen use, and Activity recreation.\n- Progress and per-song results are persisted; failed songs remain marked red for manual replacement.\n", encoding="utf-8")

    print("background_playlist_cache_service=added")
    print("activity_thread_batch_cache=removed")
    print("foreground_data_sync_and_wakelock=enabled")
    print("persistent_progress_and_failure_marking=enabled")


if __name__ == "__main__":
    main()
