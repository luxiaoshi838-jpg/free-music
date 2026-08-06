package com.jianglab.babywife;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.media.MediaMetadata;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.Build;
import android.os.IBinder;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Foreground media-control service used by the notification shade and lock screen.
 * The Activity keeps command compatibility while this service publishes full
 * MediaSession metadata, including asynchronously loaded song artwork.
 */
public final class PlaybackControlService extends Service {
    static final String ACTION_COMMAND = "com.jianglab.babywife.PLAYBACK_COMMAND";
    static final String EXTRA_COMMAND = "command";
    static final String EXTRA_SEEK_POSITION = "seek_position";
    static final String COMMAND_PREVIOUS = "previous";
    static final String COMMAND_TOGGLE = "toggle";
    static final String COMMAND_NEXT = "next";
    static final String COMMAND_SEEK = "seek";

    private static final String ACTION_START = "com.jianglab.babywife.MEDIA_START";
    private static final String ACTION_UPDATE = "com.jianglab.babywife.MEDIA_UPDATE";
    private static final String ACTION_PREVIOUS = "com.jianglab.babywife.MEDIA_PREVIOUS";
    private static final String ACTION_TOGGLE = "com.jianglab.babywife.MEDIA_TOGGLE";
    private static final String ACTION_NEXT = "com.jianglab.babywife.MEDIA_NEXT";

    private static final String EXTRA_TITLE = "title";
    private static final String EXTRA_ARTIST = "artist";
    private static final String EXTRA_PLAYING = "playing";
    private static final String EXTRA_DURATION = "duration";
    private static final String EXTRA_POSITION = "position";
    private static final String EXTRA_CATALOG_JSON = "catalog_json";
    private static final String EXTRA_ARTWORK_URL = "artwork_url";
    private static final String EXTRA_MEDIA_URI = "media_uri";

    private static final String CHANNEL_ID = "babywife_media_playback";
    private static final int NOTIFICATION_ID = 1514;

    private final ExecutorService artworkExecutor = Executors.newSingleThreadExecutor();
    private MediaSession mediaSession;
    private NotificationManager notificationManager;
    private String title = "尚未播放";
    private String artist = "大宝贝儿老婆";
    private String catalogJson = "";
    private String artworkUrl = "";
    private String mediaUri = "";
    private String artworkIdentity = "";
    private String artworkRequestedIdentity = "";
    private volatile int artworkRequestSerial = 0;
    private Bitmap artwork;
    private boolean playing = false;
    private long duration = 0L;
    private long position = 0L;
    private boolean foregroundStarted = false;

    static void ensureStarted(Context context) {
        Intent intent = new Intent(context, PlaybackControlService.class).setAction(ACTION_START);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    static void publishState(Context context, String title, String artist,
                             boolean playing, long duration, long position) {
        publishState(context, title, artist, playing, duration, position, "", "", "");
    }

    static void publishState(Context context, String title, String artist,
                             boolean playing, long duration, long position,
                             String catalogJson, String mediaUri) {
        publishState(context, title, artist, playing, duration, position,
            catalogJson, "", mediaUri);
    }

    static void publishState(Context context, String title, String artist,
                             boolean playing, long duration, long position,
                             String catalogJson, String artworkUrl, String mediaUri) {
        Intent intent = new Intent(context, PlaybackControlService.class)
            .setAction(ACTION_UPDATE)
            .putExtra(EXTRA_TITLE, title == null ? "尚未播放" : title)
            .putExtra(EXTRA_ARTIST, artist == null ? "" : artist)
            .putExtra(EXTRA_PLAYING, playing)
            .putExtra(EXTRA_DURATION, Math.max(0L, duration))
            .putExtra(EXTRA_POSITION, Math.max(0L, position))
            .putExtra(EXTRA_CATALOG_JSON, catalogJson == null ? "" : catalogJson)
            .putExtra(EXTRA_ARTWORK_URL, artworkUrl == null ? "" : artworkUrl)
            .putExtra(EXTRA_MEDIA_URI, mediaUri == null ? "" : mediaUri);
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
        mediaSession.setFlags(MediaSession.FLAG_HANDLES_MEDIA_BUTTONS
            | MediaSession.FLAG_HANDLES_TRANSPORT_CONTROLS);
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
            title = intent.getStringExtra(EXTRA_TITLE);
            artist = intent.getStringExtra(EXTRA_ARTIST);
            playing = intent.getBooleanExtra(EXTRA_PLAYING, false);
            duration = intent.getLongExtra(EXTRA_DURATION, 0L);
            position = intent.getLongExtra(EXTRA_POSITION, 0L);
            catalogJson = safe(intent.getStringExtra(EXTRA_CATALOG_JSON));
            artworkUrl = safe(intent.getStringExtra(EXTRA_ARTWORK_URL));
            mediaUri = safe(intent.getStringExtra(EXTRA_MEDIA_URI));
            if (title == null || title.trim().isEmpty()) title = "尚未播放";
            if (artist == null) artist = "";
            updateArtworkIdentity();
        }
        updateSessionAndNotification();
        requestArtworkIfNeeded();
        return START_STICKY;
    }

    private void updateArtworkIdentity() {
        String next = PlaybackArtworkLoader.identity(
            title, artist, catalogJson, mediaUri)
            + "|art=" + artworkUrl.trim();
        if (next.equals(artworkIdentity)) return;
        artworkIdentity = next;
        artworkRequestedIdentity = "";
        artwork = null;
        artworkRequestSerial++;
    }

    private void requestArtworkIfNeeded() {
        final String identity = artworkIdentity;
        if (identity.isEmpty() || identity.equals(artworkRequestedIdentity)) return;
        artworkRequestedIdentity = identity;
        final int requestSerial = ++artworkRequestSerial;
        final String requestTitle = title;
        final String requestArtist = artist;
        final String requestCatalog = catalogJson;
        final String requestArtworkUrl = artworkUrl;
        final String requestUri = mediaUri;
        artworkExecutor.execute(() -> {
            Bitmap loaded = PlaybackArtworkLoader.load(
                this, requestTitle, requestArtist, requestCatalog,
                requestArtworkUrl, requestUri);
            runOnMainThread(() -> {
                if (requestSerial != artworkRequestSerial
                    || !identity.equals(artworkIdentity)) return;
                artwork = loaded;
                updateSessionAndNotification();
            });
        });
    }

    private void runOnMainThread(Runnable action) {
        if (android.os.Looper.myLooper() == android.os.Looper.getMainLooper()) {
            action.run();
        } else {
            new android.os.Handler(android.os.Looper.getMainLooper()).post(action);
        }
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

        MediaMetadata.Builder metadata = new MediaMetadata.Builder()
            .putString(MediaMetadata.METADATA_KEY_TITLE, title)
            .putString(MediaMetadata.METADATA_KEY_ARTIST, artist)
            .putString(MediaMetadata.METADATA_KEY_DISPLAY_TITLE, title)
            .putString(MediaMetadata.METADATA_KEY_DISPLAY_SUBTITLE, artist)
            .putLong(MediaMetadata.METADATA_KEY_DURATION, Math.max(0L, duration));
        if (artwork != null) {
            metadata.putBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART, artwork)
                .putBitmap(MediaMetadata.METADATA_KEY_ART, artwork)
                .putBitmap(MediaMetadata.METADATA_KEY_DISPLAY_ICON, artwork);
        }
        mediaSession.setMetadata(metadata.build());

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
            this,
            10,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification.Action previous = new Notification.Action.Builder(
            android.R.drawable.ic_media_previous,
            "上一首",
            servicePendingIntent(ACTION_PREVIOUS, 11)
        ).build();
        Notification.Action toggle = new Notification.Action.Builder(
            playing ? android.R.drawable.ic_media_pause : android.R.drawable.ic_media_play,
            playing ? "暂停" : "播放",
            servicePendingIntent(ACTION_TOGGLE, 12)
        ).build();
        Notification.Action next = new Notification.Action.Builder(
            android.R.drawable.ic_media_next,
            "下一首",
            servicePendingIntent(ACTION_NEXT, 13)
        ).build();

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, CHANNEL_ID)
            : new Notification.Builder(this);
        builder
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
                .setShowActionsInCompactView(0, 1, 2));
        if (artwork != null) {
            builder.setLargeIcon(artwork)
                .setColor(PlaybackArtworkLoader.averageColor(artwork));
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                builder.setColorized(true);
            }
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder.setColorized(false);
        }
        return builder.build();
    }

    private PendingIntent servicePendingIntent(String action, int requestCode) {
        Intent intent = new Intent(this, PlaybackControlService.class).setAction(action);
        return PendingIntent.getService(
            this,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || notificationManager == null) return;
        NotificationChannel channel = new NotificationChannel(
            CHANNEL_ID,
            "音乐播放控制",
            NotificationManager.IMPORTANCE_LOW
        );
        channel.setDescription("锁屏和通知栏的音乐播放控制");
        channel.setShowBadge(false);
        channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        notificationManager.createNotificationChannel(channel);
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        artworkRequestSerial++;
        artworkExecutor.shutdownNow();
        if (mediaSession != null) {
            mediaSession.setActive(false);
            mediaSession.release();
            mediaSession = null;
        }
        super.onDestroy();
    }
}
