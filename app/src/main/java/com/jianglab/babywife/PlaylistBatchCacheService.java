package com.jianglab.babywife;

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
