package com.jianglab.babywife;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * Isolated-process foreground service for playlist batch caching.
 * Search and normal playback stay in the main process, while this process can be
 * paused or killed without freezing the player UI.
 */
public final class PlaylistBatchCacheService extends Service {
    static final String ACTION_PROGRESS = "com.jianglab.babywife.PLAYLIST_BATCH_CACHE_PROGRESS";
    static final String EXTRA_RUNNING = "running";
    static final String EXTRA_DONE = "done";
    static final String EXTRA_TOTAL = "total";
    static final String EXTRA_SUCCESS = "success";
    static final String EXTRA_FAILED = "failed";
    static final String EXTRA_MESSAGE = "message";
    static final String EXTRA_STATUS = "status";
    static final String EXTRA_IDENTITY = "identity";
    static final String EXTRA_UPDATED_SONG_JSON = "updated_song_json";

    private static final String ACTION_START = "com.jianglab.babywife.PLAYLIST_BATCH_CACHE_START";
    private static final String ACTION_PAUSE = "com.jianglab.babywife.PLAYLIST_BATCH_CACHE_PAUSE";
    private static final String ACTION_RESTART = "com.jianglab.babywife.PLAYLIST_BATCH_CACHE_RESTART";
    private static final String EXTRA_GENERATION = "generation";
    private static final String ROOT_FOLDER = "playlist_batch_cache_v2";
    private static final String REQUEST_FILE = "request.json";
    private static final String STATE_FILE = "state.json";
    private static final String RESULTS_FOLDER = "results";
    private static final String STATUS_IDLE = "idle";
    private static final String STATUS_STARTING = "starting";
    private static final String STATUS_RUNNING = "running";
    private static final String STATUS_PAUSED = "paused";
    private static final String STATUS_COMPLETED = "completed";
    private static final String STATUS_ERROR = "error";
    private static final String CHANNEL_ID = "playlist_batch_cache_v2";
    private static final int NOTIFICATION_ID = 1515;
    private static final long WAKE_LOCK_TIMEOUT_MS = 6L * 60L * 60L * 1000L;
    private static final long HEARTBEAT_INTERVAL_MS = 5000L;
    private static final long HEARTBEAT_STALE_MS = 25000L;
    private static final long PROGRESS_STALE_MS = 90000L;

    private NotificationManager notificationManager;
    private final Handler heartbeatHandler = new Handler(Looper.getMainLooper());
    private Thread workerThread;
    private volatile boolean workerRunning;
    private volatile boolean stopRequested;
    private PowerManager.WakeLock wakeLock;
    private long generation;
    private int playlistIndex;
    private int done;
    private int total;
    private int success;
    private int failed;
    private String currentTitle = "";
    private String currentMessage = "";
    private long lastProgressMs;
    private long lastBroadcastMs;
    private long lastNotificationMs;

    static final class TaskState {
        final String status;
        final long generation;
        final int playlistIndex;
        final int done;
        final int total;
        final int success;
        final int failed;
        final String currentTitle;
        final String message;
        final long heartbeatMs;
        final long progressMs;

        TaskState(String status, long generation, int playlistIndex, int done, int total,
                  int success, int failed, String currentTitle, String message,
                  long heartbeatMs, long progressMs) {
            this.status = status == null ? STATUS_IDLE : status;
            this.generation = generation;
            this.playlistIndex = playlistIndex;
            this.done = done;
            this.total = total;
            this.success = success;
            this.failed = failed;
            this.currentTitle = currentTitle == null ? "" : currentTitle;
            this.message = message == null ? "" : message;
            this.heartbeatMs = heartbeatMs;
            this.progressMs = progressMs;
        }

        boolean belongsTo(int index) {
            return playlistIndex == index;
        }

        boolean isActive() {
            return STATUS_STARTING.equals(status) || STATUS_RUNNING.equals(status);
        }

        boolean isRunningFresh() {
            if (!isActive()) return false;
            long now = System.currentTimeMillis();
            return now - heartbeatMs <= HEARTBEAT_STALE_MS
                && now - progressMs <= PROGRESS_STALE_MS;
        }

        boolean isStale() {
            return isActive() && !isRunningFresh();
        }

        boolean isPaused() {
            return STATUS_PAUSED.equals(status);
        }

        boolean isError() {
            return STATUS_ERROR.equals(status);
        }

        boolean isCompleted() {
            return STATUS_COMPLETED.equals(status);
        }
    }

    static final class ResultRecord {
        final String fileName;
        final String identity;
        final String updatedSongJson;

        ResultRecord(String fileName, String identity, String updatedSongJson) {
            this.fileName = fileName == null ? "" : fileName;
            this.identity = identity == null ? "" : identity;
            this.updatedSongJson = updatedSongJson == null ? "" : updatedSongJson;
        }
    }

    static void start(Context context, int playlistIndex, String requestJson) {
        long generation = prepareRequest(context, playlistIndex, requestJson, "正在启动后台缓存");
        launch(context, ACTION_START, generation);
    }

    static void restart(Context context, int playlistIndex, String requestJson) {
        long generation = prepareRequest(context, playlistIndex, requestJson, "正在重启后台缓存");
        launch(context, ACTION_RESTART, generation);
    }

    static void pause(Context context) {
        TaskState state = readState(context);
        launch(context, ACTION_PAUSE, state.generation);
    }

    static TaskState readState(Context context) {
        try {
            JSONObject object = readJson(stateFile(context));
            return new TaskState(
                object.optString("status", STATUS_IDLE),
                object.optLong("generation", 0L),
                object.optInt("playlistIndex", -1),
                object.optInt("done", 0),
                object.optInt("total", 0),
                object.optInt("success", 0),
                object.optInt("failed", 0),
                object.optString("currentTitle", ""),
                object.optString("message", ""),
                object.optLong("heartbeatMs", 0L),
                object.optLong("progressMs", 0L)
            );
        } catch (Exception ignored) {
            return new TaskState(STATUS_IDLE, 0L, -1, 0, 0, 0, 0,
                "", "", 0L, 0L);
        }
    }

    static boolean isRunning(Context context) {
        return readState(context).isRunningFresh();
    }

    static String progressLabel(Context context) {
        TaskState state = readState(context);
        if (!state.isActive()) return "";
        String prefix = state.total > 0
            ? "后台缓存 " + state.done + "/" + state.total
            : "正在准备后台缓存";
        return state.currentTitle.trim().isEmpty()
            ? prefix : prefix + "：" + state.currentTitle;
    }

    static List<ResultRecord> readPendingResults(Context context) {
        List<ResultRecord> records = new ArrayList<>();
        File directory = resultsDir(context);
        File[] files = directory.listFiles((dir, name) -> name != null && name.endsWith(".json"));
        if (files == null || files.length == 0) return records;
        Arrays.sort(files, (left, right) -> left.getName().compareTo(right.getName()));
        for (File file : files) {
            try {
                JSONObject object = readJson(file);
                String identity = object.optString("identity", "");
                String updated = object.optString("updatedSongJson", "");
                if (!identity.isEmpty() && !updated.isEmpty()) {
                    records.add(new ResultRecord(file.getName(), identity, updated));
                }
            } catch (Exception ignored) {
            }
        }
        return records;
    }

    static void markResultsConsumed(Context context, List<ResultRecord> records) {
        if (records == null || records.isEmpty()) return;
        File directory = resultsDir(context);
        for (ResultRecord record : records) {
            if (record == null || record.fileName.isEmpty()) continue;
            File file = new File(directory, record.fileName);
            if (file.isFile() && !file.delete()) file.deleteOnExit();
        }
    }

    private static long prepareRequest(Context context, int playlistIndex, String requestJson,
                                       String message) {
        try {
            JSONObject request = new JSONObject(requestJson == null ? "{}" : requestJson);
            long generation = Math.max(System.currentTimeMillis(),
                readState(context).generation + 1L);
            request.put("generation", generation);
            request.put("playlistIndex", Math.max(0, playlistIndex));
            JSONArray songs = request.optJSONArray("songs");
            int total = songs == null ? 0 : songs.length();
            writeJsonAtomically(requestFile(context), request);
            long now = System.currentTimeMillis();
            writeState(context, new TaskState(STATUS_STARTING, generation,
                Math.max(0, playlistIndex), 0, total, 0, 0, "", message,
                now, now));
            return generation;
        } catch (Exception error) {
            throw new IllegalStateException("无法建立歌单缓存任务：" + safeMessage(error));
        }
    }

    private static void launch(Context context, String action, long generation) {
        Context app = context.getApplicationContext();
        Intent intent = new Intent(app, PlaylistBatchCacheService.class)
            .setAction(action)
            .putExtra(EXTRA_GENERATION, generation);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            app.startForegroundService(intent);
        } else {
            app.startService(intent);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        notificationManager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? ACTION_START : intent.getAction();
        long requestedGeneration = intent == null
            ? readState(this).generation
            : intent.getLongExtra(EXTRA_GENERATION, readState(this).generation);
        ensureForeground(0, 0, "正在准备歌单缓存");
        if (ACTION_PAUSE.equals(action)) {
            pauseAndTerminate();
            return START_NOT_STICKY;
        }
        if (ACTION_RESTART.equals(action)) {
            scheduleRestart(requestedGeneration);
            terminateProcess();
            return START_NOT_STICKY;
        }
        startWorkerIfNeeded(requestedGeneration);
        return START_REDELIVER_INTENT;
    }

    private synchronized void startWorkerIfNeeded(long requestedGeneration) {
        if (workerRunning) {
            if (generation == requestedGeneration) return;
            scheduleRestart(requestedGeneration);
            terminateProcess();
            return;
        }
        try {
            JSONObject request = readJson(requestFile(this));
            generation = request.optLong("generation", requestedGeneration);
            playlistIndex = request.optInt("playlistIndex", 0);
            JSONArray songs = request.optJSONArray("songs");
            total = songs == null ? 0 : songs.length();
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
        } catch (Exception error) {
            TaskState state = readState(this);
            generation = state.generation;
            playlistIndex = state.playlistIndex;
            currentMessage = "读取缓存任务失败：" + safeMessage(error);
            report(STATUS_ERROR, currentMessage, true, true, "", "");
            stopForeground(false);
            stopSelf();
        }
    }

    private void runBatch(JSONObject request) {
        acquireWakeLock();
        try {
            JSONArray songs = request.optJSONArray("songs");
            total = songs == null ? 0 : songs.length();
            report(STATUS_RUNNING, currentMessage, true, true, "", "");
            for (int index = 0; index < total; index++) {
                checkStopped();
                JSONObject row = songs.optJSONObject(index);
                if (row == null) continue;
                BatchSong song = new BatchSong(row);
                currentTitle = song.title;
                currentMessage = "正在缓存 " + (index + 1) + "/" + total + "：" + song.title;
                report(STATUS_RUNNING, currentMessage, true, true, "", "");
                try {
                    NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
                        this,
                        song.catalogJson,
                        true,
                        message -> {
                            checkStoppedUnchecked();
                            currentMessage = "缓存 " + (done + 1) + "/" + total
                                + "：" + song.title + " · " + message;
                            report(STATUS_RUNNING, currentMessage, true, true, "", "");
                        }
                    );
                    checkStopped();
                    String updated = updateSongJson(song.songJson, cached, false);
                    writeResult(index, song.identity, updated);
                    success++;
                    done++;
                    currentMessage = "已缓存 " + done + "/" + total + "：" + song.title;
                    report(STATUS_RUNNING, currentMessage, true, true, song.identity, updated);
                } catch (InterruptedException interrupted) {
                    throw interrupted;
                } catch (Exception error) {
                    String updated = updateSongJson(song.songJson, null, true);
                    writeResult(index, song.identity, updated);
                    failed++;
                    done++;
                    currentMessage = "缓存失败并已标红 " + done + "/" + total + "：" + song.title;
                    report(STATUS_RUNNING, currentMessage, true, true, song.identity, updated);
                }
            }
            currentTitle = "";
            currentMessage = "一键缓存完成：成功 " + success + " 首，失败 " + failed + " 首";
            report(STATUS_COMPLETED, currentMessage, true, true, "", "");
            showFinishedNotification(currentMessage);
        } catch (InterruptedException ignored) {
            if (!STATUS_PAUSED.equals(readState(this).status)) {
                currentMessage = "缓存任务已暂停，可点击按钮继续";
                report(STATUS_PAUSED, currentMessage, true, true, "", "");
            }
        } catch (Throwable error) {
            currentMessage = "后台缓存任务异常停止：" + safeMessage(error);
            report(STATUS_ERROR, currentMessage, true, true, "", "");
            showFinishedNotification(currentMessage);
        } finally {
            releaseWakeLock();
            stopHeartbeat();
            workerRunning = false;
            workerThread = null;
            if (!stopRequested) {
                stopForeground(false);
                stopSelf();
            }
        }
    }

    private void pauseAndTerminate() {
        TaskState state = readState(this);
        generation = state.generation;
        playlistIndex = state.playlistIndex;
        done = state.done;
        total = state.total;
        success = state.success;
        failed = state.failed;
        currentTitle = state.currentTitle;
        lastProgressMs = state.progressMs;
        currentMessage = "一键缓存已暂停，再按一次继续";
        report(STATUS_PAUSED, currentMessage, true, true, "", "");
        terminateProcess();
    }

    private void scheduleRestart(long requestedGeneration) {
        try {
            Intent startIntent = new Intent(this, PlaylistBatchCacheService.class)
                .setAction(ACTION_START)
                .putExtra(EXTRA_GENERATION, requestedGeneration);
            PendingIntent pendingIntent = PendingIntent.getService(
                this,
                1516,
                startIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
            );
            AlarmManager alarmManager = (AlarmManager) getSystemService(ALARM_SERVICE);
            if (alarmManager != null) {
                alarmManager.set(AlarmManager.ELAPSED_REALTIME_WAKEUP,
                    SystemClock.elapsedRealtime() + 800L, pendingIntent);
            } else {
                pendingIntent.send();
            }
        } catch (Exception ignored) {
        }
    }

    private void terminateProcess() {
        stopRequested = true;
        if (workerThread != null) workerThread.interrupt();
        stopHeartbeat();
        releaseWakeLock();
        stopForeground(true);
        stopSelf();
        android.os.Process.killProcess(android.os.Process.myPid());
    }

    private String updateSongJson(String originalSongJson, NetworkMediaCache.CacheResult cached,
                                  boolean unavailable) throws Exception {
        JSONObject song = new JSONObject(originalSongJson == null ? "{}" : originalSongJson);
        if (unavailable || cached == null) {
            song.put("cachedUri", "");
            song.put("uri", "");
            song.put("unavailable", true);
            song.put("autoUnavailable", true);
            return song.toString();
        }
        song.put("cachedUri", cached.audioUri == null ? "" : cached.audioUri);
        song.put("uri", cached.audioUri == null ? "" : cached.audioUri);
        if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
            song.put("catalogJson", cached.catalogJson);
        }
        if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
            song.put("source", CatalogSearch.labelForSource(cached.sourceCode));
        }
        if (song.optString("lyric", "").trim().isEmpty()
            && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
            song.put("lyric", cached.lyric);
            song.put("lyricLabel", song.optString("title", "未知歌曲")
                + " · " + song.optString("artist", "未知歌手")
                + " · " + song.optString("source", ""));
        }
        song.put("unavailable", false);
        song.put("autoUnavailable", false);
        song.put("manualUnavailable", false);
        return song.toString();
    }

    private void writeResult(int index, String identity, String updatedSongJson) throws Exception {
        JSONObject result = new JSONObject();
        result.put("generation", generation);
        result.put("identity", identity == null ? "" : identity);
        result.put("updatedSongJson", updatedSongJson == null ? "" : updatedSongJson);
        result.put("createdAt", System.currentTimeMillis());
        String name = String.format(Locale.ROOT, "%020d_%05d_%s.json",
            generation, index, shortHash(identity));
        writeJsonAtomically(new File(resultsDir(this), name), result);
    }

    private synchronized void report(String status, String message, boolean progressChanged,
                                     boolean broadcast, String identity, String updatedSongJson) {
        if (!isCurrentGeneration(this, generation)) return;
        long now = System.currentTimeMillis();
        if (progressChanged) lastProgressMs = now;
        TaskState state = new TaskState(status, generation, playlistIndex, done, total,
            success, failed, currentTitle, message, now, lastProgressMs);
        writeState(this, state);
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
    }

    private void broadcastProgress(TaskState state, String identity, String updatedSongJson) {
        Intent intent = new Intent(ACTION_PROGRESS)
            .setPackage(getPackageName())
            .putExtra(EXTRA_RUNNING, state.isRunningFresh())
            .putExtra(EXTRA_DONE, state.done)
            .putExtra(EXTRA_TOTAL, state.total)
            .putExtra(EXTRA_SUCCESS, state.success)
            .putExtra(EXTRA_FAILED, state.failed)
            .putExtra(EXTRA_STATUS, state.status)
            .putExtra(EXTRA_MESSAGE, state.message)
            .putExtra(EXTRA_IDENTITY, identity == null ? "" : identity)
            .putExtra(EXTRA_UPDATED_SONG_JSON, updatedSongJson == null ? "" : updatedSongJson);
        sendBroadcast(intent);
    }

    private void startHeartbeat() {
        heartbeatHandler.removeCallbacks(heartbeatRunnable);
        heartbeatHandler.postDelayed(heartbeatRunnable, HEARTBEAT_INTERVAL_MS);
    }

    private void stopHeartbeat() {
        heartbeatHandler.removeCallbacks(heartbeatRunnable);
    }

    private final Runnable heartbeatRunnable = new Runnable() {
        @Override
        public void run() {
            if (!workerRunning || stopRequested) return;
            report(STATUS_RUNNING, currentMessage, false, false, "", "");
            heartbeatHandler.postDelayed(this, HEARTBEAT_INTERVAL_MS);
        }
    };

    private void checkStopped() throws InterruptedException {
        if (stopRequested || Thread.currentThread().isInterrupted()) {
            throw new InterruptedException("歌单缓存任务已暂停");
        }
    }

    private void checkStoppedUnchecked() {
        if (stopRequested || Thread.currentThread().isInterrupted()) {
            throw new IllegalStateException("歌单缓存任务已暂停");
        }
    }

    private void ensureForeground(int done, int total, String text) {
        startForeground(NOTIFICATION_ID, buildNotification(done, total, text, true));
    }

    private void updateNotification(int done, int total, String text) {
        if (notificationManager != null) {
            notificationManager.notify(NOTIFICATION_ID, buildNotification(done, total, text, true));
        }
    }

    private void showFinishedNotification(String text) {
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
        if (ongoing) {
            builder.setProgress(Math.max(0, total), Math.max(0, done), total <= 0);
            Intent pauseIntent = new Intent(this, PlaylistBatchCacheService.class)
                .setAction(ACTION_PAUSE)
                .putExtra(EXTRA_GENERATION, generation);
            PendingIntent pausePending = PendingIntent.getService(this, 1517, pauseIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            builder.addAction(android.R.drawable.ic_media_pause, "暂停", pausePending);
        } else {
            builder.setAutoCancel(true);
        }
        return builder.build();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || notificationManager == null) return;
        NotificationChannel channel = new NotificationChannel(
            CHANNEL_ID,
            "歌单后台缓存",
            NotificationManager.IMPORTANCE_LOW
        );
        channel.setDescription("独立进程缓存歌单歌曲，可暂停、继续和重启");
        channel.setShowBadge(false);
        notificationManager.createNotificationChannel(channel);
    }

    private void acquireWakeLock() {
        try {
            PowerManager manager = (PowerManager) getSystemService(POWER_SERVICE);
            if (manager == null) return;
            wakeLock = manager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,
                getPackageName() + ":playlist-batch-cache-v2");
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

    private static File root(Context context) {
        File directory = new File(context.getFilesDir(), ROOT_FOLDER);
        if (!directory.exists()) directory.mkdirs();
        return directory;
    }

    private static File requestFile(Context context) {
        return new File(root(context), REQUEST_FILE);
    }

    private static File stateFile(Context context) {
        return new File(root(context), STATE_FILE);
    }

    private static File resultsDir(Context context) {
        File directory = new File(root(context), RESULTS_FOLDER);
        if (!directory.exists()) directory.mkdirs();
        return directory;
    }

    private static boolean isCurrentGeneration(Context context, long generation) {
        try {
            return readJson(requestFile(context)).optLong("generation", -1L) == generation;
        } catch (Exception ignored) {
            return false;
        }
    }

    private static void writeState(Context context, TaskState state) {
        try {
            JSONObject object = new JSONObject();
            object.put("status", state.status);
            object.put("generation", state.generation);
            object.put("playlistIndex", state.playlistIndex);
            object.put("done", state.done);
            object.put("total", state.total);
            object.put("success", state.success);
            object.put("failed", state.failed);
            object.put("currentTitle", state.currentTitle);
            object.put("message", state.message);
            object.put("heartbeatMs", state.heartbeatMs);
            object.put("progressMs", state.progressMs);
            writeJsonAtomically(stateFile(context), object);
        } catch (Exception ignored) {
        }
    }

    private static JSONObject readJson(File file) throws Exception {
        if (file == null || !file.isFile()) return new JSONObject();
        StringBuilder builder = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(
            new FileInputStream(file), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) builder.append(line);
        }
        return builder.length() == 0 ? new JSONObject() : new JSONObject(builder.toString());
    }

    private static void writeJsonAtomically(File file, JSONObject object) throws Exception {
        File parent = file.getParentFile();
        if (parent != null && !parent.exists()) parent.mkdirs();
        File partial = new File(parent, file.getName() + ".part." + android.os.Process.myPid());
        try (FileOutputStream output = new FileOutputStream(partial)) {
            output.write(object.toString().getBytes(StandardCharsets.UTF_8));
            output.getFD().sync();
        }
        if (file.exists() && !file.delete()) {
            throw new IllegalStateException("无法替换任务状态文件");
        }
        if (!partial.renameTo(file)) {
            try (FileInputStream input = new FileInputStream(partial);
                 FileOutputStream output = new FileOutputStream(file)) {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = input.read(buffer)) >= 0) {
                    if (count > 0) output.write(buffer, 0, count);
                }
                output.getFD().sync();
            }
            if (!partial.delete()) partial.deleteOnExit();
        }
    }

    private static String shortHash(String value) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] bytes = digest.digest((value == null ? "" : value)
            .getBytes(StandardCharsets.UTF_8));
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < 8; i++) {
            builder.append(String.format(Locale.ROOT, "%02x", bytes[i] & 0xff));
        }
        return builder.toString();
    }

    private static String safeMessage(Throwable error) {
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
        stopHeartbeat();
        super.onDestroy();
    }

    private static final class BatchSong {
        final String identity;
        final String songJson;
        final String catalogJson;
        final String title;

        BatchSong(JSONObject row) throws Exception {
            identity = row.optString("identity", "");
            songJson = row.optString("songJson", "{}");
            JSONObject song = new JSONObject(songJson);
            catalogJson = song.optString("catalogJson", "");
            title = song.optString("title", "未知歌曲");
        }
    }
}
