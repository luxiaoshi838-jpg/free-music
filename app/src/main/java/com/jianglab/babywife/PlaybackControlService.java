package com.jianglab.babywife;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.media.MediaMetadata;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.Build;
import android.os.IBinder;

/**
 * Foreground media-control and playback-resolution service.
 * Catalog resolution and audio caching run in this independent foreground
 * process so they continue while another app is visible.
 */
public final class PlaybackControlService extends Service {
    static final String ACTION_COMMAND = "com.jianglab.babywife.PLAYBACK_COMMAND";
    static final String ACTION_RESOLVE_PROGRESS = "com.jianglab.babywife.PLAYBACK_RESOLVE_PROGRESS";
    static final String ACTION_RESOLVE_RESULT = "com.jianglab.babywife.PLAYBACK_RESOLVE_RESULT";
    static final String EXTRA_COMMAND = "command";
    static final String EXTRA_SEEK_POSITION = "seek_position";
    static final String EXTRA_REQUEST_ID = "request_id";
    static final String EXTRA_MESSAGE = "message";
    static final String EXTRA_SUCCESS = "success";
    static final String EXTRA_ERROR = "error";
    static final String EXTRA_AUDIO_URI = "audio_uri";
    static final String EXTRA_LYRIC = "lyric";
    static final String EXTRA_CATALOG_JSON = "catalog_json";
    static final String EXTRA_SOURCE_CODE = "source_code";
    static final String EXTRA_SOURCE_CHANGED = "source_changed";
    static final String COMMAND_PREVIOUS = "previous";
    static final String COMMAND_TOGGLE = "toggle";
    static final String COMMAND_NEXT = "next";
    static final String COMMAND_SEEK = "seek";

    private static final String ACTION_START = "com.jianglab.babywife.MEDIA_START";
    private static final String ACTION_UPDATE = "com.jianglab.babywife.MEDIA_UPDATE";
    private static final String ACTION_PREVIOUS = "com.jianglab.babywife.MEDIA_PREVIOUS";
    private static final String ACTION_TOGGLE = "com.jianglab.babywife.MEDIA_TOGGLE";
    private static final String ACTION_NEXT = "com.jianglab.babywife.MEDIA_NEXT";
    private static final String ACTION_RESOLVE = "com.jianglab.babywife.MEDIA_RESOLVE";

    private static final String EXTRA_TITLE = "title";
    private static final String EXTRA_ARTIST = "artist";
    private static final String EXTRA_PLAYING = "playing";
    private static final String EXTRA_DURATION = "duration";
    private static final String EXTRA_POSITION = "position";

    private static final String CHANNEL_ID = "babywife_media_playback";
    private static final int NOTIFICATION_ID = 1514;

    private MediaSession mediaSession;
    private NotificationManager notificationManager;
    private String title = "尚未播放";
    private String artist = "大宝贝儿老婆";
    private boolean playing;
    private long duration;
    private long position;
    private boolean foregroundStarted;
    private Thread resolveWorker;
    private volatile long activeResolveRequestId;

    static void ensureStarted(Context context) {
        start(context, new Intent(context, PlaybackControlService.class).setAction(ACTION_START));
    }

    static void publishState(Context context, String title, String artist,
                             boolean playing, long duration, long position) {
        Intent intent = new Intent(context, PlaybackControlService.class)
            .setAction(ACTION_UPDATE)
            .putExtra(EXTRA_TITLE, title == null ? "尚未播放" : title)
            .putExtra(EXTRA_ARTIST, artist == null ? "" : artist)
            .putExtra(EXTRA_PLAYING, playing)
            .putExtra(EXTRA_DURATION, Math.max(0L, duration))
            .putExtra(EXTRA_POSITION, Math.max(0L, position));
        start(context, intent);
    }

    static void resolveForPlayback(Context context, long requestId, String title,
                                   String artist, String catalogJson) {
        Intent intent = new Intent(context, PlaybackControlService.class)
            .setAction(ACTION_RESOLVE)
            .putExtra(EXTRA_REQUEST_ID, requestId)
            .putExtra(EXTRA_TITLE, title == null ? "未知歌曲" : title)
            .putExtra(EXTRA_ARTIST, artist == null ? "" : artist)
            .putExtra(EXTRA_CATALOG_JSON, catalogJson == null ? "" : catalogJson);
        start(context, intent);
    }

    private static void start(Context context, Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        notificationManager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        createNotificationChannel();
        mediaSession = new MediaSession(this, "BabyWifePlayback");
        mediaSession.setCallback(new MediaSession.Callback() {
            @Override
            public void onPlay() {
                dispatch(COMMAND_TOGGLE, -1L);
            }

            @Override
            public void onPause() {
                dispatch(COMMAND_TOGGLE, -1L);
            }

            @Override
            public void onSkipToPrevious() {
                dispatch(COMMAND_PREVIOUS, -1L);
            }

            @Override
            public void onSkipToNext() {
                dispatch(COMMAND_NEXT, -1L);
            }

            @Override
            public void onSeekTo(long pos) {
                dispatch(COMMAND_SEEK, pos);
            }
        });
        mediaSession.setActive(true);
        updateSessionAndNotification();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? ACTION_START : intent.getAction();
        if (ACTION_PREVIOUS.equals(action)) {
            dispatch(COMMAND_PREVIOUS, -1L);
        } else if (ACTION_TOGGLE.equals(action)) {
            dispatch(COMMAND_TOGGLE, -1L);
        } else if (ACTION_NEXT.equals(action)) {
            dispatch(COMMAND_NEXT, -1L);
        } else if (ACTION_UPDATE.equals(action) && intent != null) {
            title = safe(intent.getStringExtra(EXTRA_TITLE), "尚未播放");
            artist = safe(intent.getStringExtra(EXTRA_ARTIST), "");
            playing = intent.getBooleanExtra(EXTRA_PLAYING, false);
            duration = intent.getLongExtra(EXTRA_DURATION, 0L);
            position = intent.getLongExtra(EXTRA_POSITION, 0L);
        } else if (ACTION_RESOLVE.equals(action) && intent != null) {
            startResolve(intent);
        }
        updateSessionAndNotification();
        return START_STICKY;
    }

    private synchronized void startResolve(Intent intent) {
        long requestId = intent.getLongExtra(EXTRA_REQUEST_ID, 0L);
        String catalogJson = safe(intent.getStringExtra(EXTRA_CATALOG_JSON), "");
        if (requestId == 0L || catalogJson.isEmpty()) return;
        activeResolveRequestId = requestId;
        title = safe(intent.getStringExtra(EXTRA_TITLE), "未知歌曲");
        artist = safe(intent.getStringExtra(EXTRA_ARTIST), "");
        playing = false;
        duration = 0L;
        position = 0L;
        if (resolveWorker != null) resolveWorker.interrupt();
        broadcastProgress(requestId, "正在优先寻找可播放音频…");
        resolveWorker = new Thread(() -> {
            try (NetworkMediaCache.ForegroundLease ignored =
                     NetworkMediaCache.beginForegroundWork(this)) {
                NetworkMediaCache.CacheResult result = NetworkMediaCache.cacheForPlayback(
                    this,
                    catalogJson,
                    message -> {
                        if (requestId != activeResolveRequestId) return;
                        artist = message == null || message.trim().isEmpty()
                            ? artist : message.trim();
                        updateSessionAndNotification();
                        broadcastProgress(requestId, message);
                    }
                );
                if (requestId != activeResolveRequestId) return;
                Intent output = new Intent(ACTION_RESOLVE_RESULT)
                    .setPackage(getPackageName())
                    .putExtra(EXTRA_REQUEST_ID, requestId)
                    .putExtra(EXTRA_SUCCESS, true)
                    .putExtra(EXTRA_AUDIO_URI, result.audioUri)
                    .putExtra(EXTRA_LYRIC, result.lyric)
                    .putExtra(EXTRA_CATALOG_JSON, result.catalogJson)
                    .putExtra(EXTRA_SOURCE_CODE, result.sourceCode)
                    .putExtra(EXTRA_SOURCE_CHANGED, result.sourceChanged);
                sendBroadcast(output);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            } catch (Throwable error) {
                if (requestId != activeResolveRequestId) return;
                Intent output = new Intent(ACTION_RESOLVE_RESULT)
                    .setPackage(getPackageName())
                    .putExtra(EXTRA_REQUEST_ID, requestId)
                    .putExtra(EXTRA_SUCCESS, false)
                    .putExtra(EXTRA_ERROR, safeError(error));
                sendBroadcast(output);
            }
        }, "PlaybackResolveWorker");
        resolveWorker.start();
    }

    private void broadcastProgress(long requestId, String message) {
        Intent progress = new Intent(ACTION_RESOLVE_PROGRESS)
            .setPackage(getPackageName())
            .putExtra(EXTRA_REQUEST_ID, requestId)
            .putExtra(EXTRA_MESSAGE, message == null ? "" : message);
        sendBroadcast(progress);
    }

    private void dispatch(String command, long seekPosition) {
        Intent intent = new Intent(ACTION_COMMAND)
            .setPackage(getPackageName())
            .putExtra(EXTRA_COMMAND, command);
        if (seekPosition >= 0L) intent.putExtra(EXTRA_SEEK_POSITION, seekPosition);
        sendBroadcast(intent);
    }

    private void updateSessionAndNotification() {
        if (mediaSession == null) return;
        long actions = PlaybackState.ACTION_PLAY
            | PlaybackState.ACTION_PAUSE
            | PlaybackState.ACTION_PLAY_PAUSE
            | PlaybackState.ACTION_SKIP_TO_PREVIOUS
            | PlaybackState.ACTION_SKIP_TO_NEXT
            | PlaybackState.ACTION_SEEK_TO;
        int state = playing ? PlaybackState.STATE_PLAYING : PlaybackState.STATE_PAUSED;
        mediaSession.setPlaybackState(new PlaybackState.Builder()
            .setActions(actions)
            .setState(state, Math.max(0L, position), playing ? 1.0f : 0.0f)
            .build());
        mediaSession.setMetadata(new MediaMetadata.Builder()
            .putString(MediaMetadata.METADATA_KEY_TITLE, title)
            .putString(MediaMetadata.METADATA_KEY_ARTIST, artist)
            .putLong(MediaMetadata.METADATA_KEY_DURATION, Math.max(0L, duration))
            .build());

        Notification notification = buildNotification();
        if (!foregroundStarted) {
            startForeground(NOTIFICATION_ID, notification);
            foregroundStarted = true;
        } else if (notificationManager != null) {
            notificationManager.notify(NOTIFICATION_ID, notification);
        }
    }

    private Notification buildNotification() {
        Intent openIntent = new Intent(this, MainActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
            this, 10, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Action previous = new Notification.Action.Builder(
            android.R.drawable.ic_media_previous, "上一首",
            servicePendingIntent(ACTION_PREVIOUS, 11)).build();
        Notification.Action toggle = new Notification.Action.Builder(
            playing ? android.R.drawable.ic_media_pause : android.R.drawable.ic_media_play,
            playing ? "暂停" : "播放",
            servicePendingIntent(ACTION_TOGGLE, 12)).build();
        Notification.Action next = new Notification.Action.Builder(
            android.R.drawable.ic_media_next, "下一首",
            servicePendingIntent(ACTION_NEXT, 13)).build();

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, CHANNEL_ID)
            : new Notification.Builder(this);
        return builder
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle(title)
            .setContentText(artist)
            .setContentIntent(contentIntent)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .setCategory(Notification.CATEGORY_TRANSPORT)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setShowWhen(false)
            .addAction(previous)
            .addAction(toggle)
            .addAction(next)
            .setStyle(new Notification.MediaStyle()
                .setMediaSession(mediaSession.getSessionToken())
                .setShowActionsInCompactView(0, 1, 2))
            .build();
    }

    private PendingIntent servicePendingIntent(String action, int requestCode) {
        Intent intent = new Intent(this, PlaybackControlService.class).setAction(action);
        return PendingIntent.getService(this, requestCode, intent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || notificationManager == null) return;
        NotificationChannel channel = new NotificationChannel(
            CHANNEL_ID, "音乐播放控制", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("锁屏控制、后台寻找歌曲和音乐播放状态");
        channel.setShowBadge(false);
        channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        notificationManager.createNotificationChannel(channel);
    }

    private static String safe(String value, String fallback) {
        return value == null || value.trim().isEmpty() ? fallback : value.trim();
    }

    private static String safeError(Throwable error) {
        if (error == null) return "歌曲寻找失败";
        String message = error.getMessage();
        return message == null || message.trim().isEmpty()
            ? error.getClass().getSimpleName() : message.trim();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        activeResolveRequestId++;
        if (resolveWorker != null) resolveWorker.interrupt();
        resolveWorker = null;
        if (mediaSession != null) {
            mediaSession.setActive(false);
            mediaSession.release();
            mediaSession = null;
        }
        super.onDestroy();
    }
}
