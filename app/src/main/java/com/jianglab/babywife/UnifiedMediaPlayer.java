package com.jianglab.babywife;

import android.content.Context;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.Looper;

import androidx.media3.common.AudioAttributes;
import androidx.media3.common.C;
import androidx.media3.common.MediaItem;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.common.util.UnstableApi;
import androidx.media3.datasource.DataSource;
import androidx.media3.datasource.DefaultDataSource;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.ProgressiveMediaSource;

import org.json.JSONObject;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * Small MediaPlayer-shaped adapter backed by Media3 ExoPlayer.
 *
 * MainActivity can keep its existing controls and layout while online playback
 * uses CacheDataSource. The bytes consumed by playback are written to the same
 * catalog-keyed cache and are reused on later playback instead of being fetched
 * again by a second independent downloader.
 */
@UnstableApi
final class UnifiedMediaPlayer {
    private static final HandlerThread PLAYER_THREAD;
    private static final Handler PLAYER_HANDLER;

    static {
        PLAYER_THREAD = new HandlerThread("babywife-media3-player");
        PLAYER_THREAD.start();
        PLAYER_HANDLER = new Handler(PLAYER_THREAD.getLooper());
    }

    interface OnPreparedListener {
        void onPrepared(UnifiedMediaPlayer player);
    }

    interface OnCompletionListener {
        void onCompletion(UnifiedMediaPlayer player);
    }

    interface OnErrorListener {
        boolean onError(UnifiedMediaPlayer player, int what, int extra);
    }

    private final Context appContext;
    private final AudioManager audioManager;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private boolean userRequestedPlayback;
    private boolean communicationActive;
    private boolean communicationPaused;
    private final Runnable communicationModeWatcher = new Runnable() {
        @Override
        public void run() {
            if (released) return;
            boolean active = isCommunicationMode();
            if (active && !communicationActive) {
                communicationActive = true;
                if (player != null && userRequestedPlayback) {
                    communicationPaused = true;
                    player.pause();
                }
            } else if (!active && communicationActive) {
                communicationActive = false;
                if (communicationPaused && userRequestedPlayback && player != null) {
                    player.play();
                }
                communicationPaused = false;
            }
            PLAYER_HANDLER.postDelayed(this, 400L);
        }
    };
    private Uri sourceUri;
    private String cacheKey = "";
    private Map<String, String> requestHeaders = Collections.emptyMap();
    private ExoPlayer player;
    private volatile OnPreparedListener preparedListener;
    private volatile OnCompletionListener completionListener;
    private volatile OnErrorListener errorListener;
    private boolean preparedDelivered;
    private volatile boolean released;
    private volatile boolean snapshotPlaying;
    private volatile int snapshotDurationMs;
    private volatile int snapshotPositionMs;

    UnifiedMediaPlayer(Context context) {
        appContext = context.getApplicationContext();
        audioManager = (AudioManager) appContext.getSystemService(Context.AUDIO_SERVICE);
    }

    void setWakeMode(Context context, int mode) {
        // ExoPlayer wake mode is applied when the internal player is created.
    }

    void setDataSource(Context context, Uri uri) {
        setDataSource(context, uri, "", Collections.emptyMap());
    }

    void setDataSource(Context context, Uri uri, String key,
                       Map<String, String> headers) {
        sourceUri = uri;
        cacheKey = key == null ? "" : key.trim();
        requestHeaders = headers == null
            ? Collections.emptyMap() : new HashMap<>(headers);
    }

    void setOnPreparedListener(OnPreparedListener listener) {
        preparedListener = listener;
    }

    void setOnCompletionListener(OnCompletionListener listener) {
        completionListener = listener;
    }

    void setOnErrorListener(OnErrorListener listener) {
        errorListener = listener;
    }

    void prepareAsync() {
        runOnPlayer(this::prepareInternal);
    }

    private void prepareInternal() {
        if (released || sourceUri == null) {
            notifyError(PlaybackException.ERROR_CODE_IO_UNSPECIFIED, 0);
            return;
        }
        releaseInternalPlayer();
        preparedDelivered = false;
        try {
            DefaultHttpDataSource.Factory httpFactory = new DefaultHttpDataSource.Factory()
                .setConnectTimeoutMs(12000)
                .setReadTimeoutMs(30000)
                .setAllowCrossProtocolRedirects(true)
                .setUserAgent(requestHeaders.containsKey("User-Agent")
                    ? requestHeaders.get("User-Agent")
                    : "Mozilla/5.0 (Android) AppleWebKit/537.36");
            if (!requestHeaders.isEmpty()) {
                httpFactory.setDefaultRequestProperties(requestHeaders);
            }
            DefaultDataSource.Factory upstream = new DefaultDataSource.Factory(
                appContext, httpFactory);
            DataSource.Factory sourceFactory = cacheKey.isEmpty()
                ? upstream : Media3CacheStore.dataSourceFactory(appContext, upstream);

            ExoPlayer next = new ExoPlayer.Builder(appContext)
                .setLooper(PLAYER_THREAD.getLooper())
                .build();
            AudioAttributes audioAttributes = new AudioAttributes.Builder()
                .setUsage(C.USAGE_MEDIA)
                .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
                .build();
            // Let Media3 request and manage Android audio focus. If another app
            // starts video/music/call audio, playback pauses or ducks as Android
            // requests; transient focus gain resumes only when playWhenReady is
            // still true, so a user-initiated pause is never auto-resumed.
            next.setAudioAttributes(audioAttributes, true);
            next.setWakeMode(C.WAKE_MODE_NETWORK);
            next.addListener(new Player.Listener() {
                @Override
                public void onPlaybackStateChanged(int playbackState) {
                    if (next != player || released) return;
                    updateSnapshot();
                    if (playbackState == Player.STATE_READY && !preparedDelivered) {
                        preparedDelivered = true;
                        OnPreparedListener listener = preparedListener;
                        if (listener != null) {
                            mainHandler.post(() -> {
                                if (!released && preparedListener == listener) {
                                    listener.onPrepared(UnifiedMediaPlayer.this);
                                }
                            });
                        }
                    } else if (playbackState == Player.STATE_ENDED) {
                        OnCompletionListener listener = completionListener;
                        if (listener != null) {
                            mainHandler.post(() -> {
                                if (!released && completionListener == listener) {
                                    listener.onCompletion(UnifiedMediaPlayer.this);
                                }
                            });
                        }
                    }
                }

                @Override
                public void onIsPlayingChanged(boolean isPlaying) {
                    snapshotPlaying = isPlaying;
                    updateSnapshot();
                }

                @Override
                public void onPlayerError(PlaybackException error) {
                    if (next != player || released) return;
                    int extra = error.getCause() == null
                        ? 0 : error.getCause().getClass().getName().hashCode();
                    notifyError(error.errorCode, extra);
                }
            });
            player = next;
            scheduleCommunicationModeWatch();

            MediaItem.Builder itemBuilder = new MediaItem.Builder().setUri(sourceUri);
            if (!cacheKey.isEmpty()) itemBuilder.setCustomCacheKey(cacheKey);
            MediaItem item = itemBuilder.build();
            ProgressiveMediaSource mediaSource = new ProgressiveMediaSource.Factory(sourceFactory)
                .createMediaSource(item);
            next.setMediaSource(mediaSource);
            next.prepare();
        } catch (Throwable error) {
            notifyError(PlaybackException.ERROR_CODE_IO_UNSPECIFIED,
                error.getClass().getName().hashCode());
        }
    }

    void start() {
        runOnPlayer(() -> {
            userRequestedPlayback = true;
            scheduleCommunicationModeWatch();
            if (player == null || released) return;
            if (isCommunicationMode()) {
                communicationActive = true;
                communicationPaused = true;
                player.pause();
                return;
            }
            player.play();
        });
    }

    void pause() {
        runOnPlayer(() -> {
            userRequestedPlayback = false;
            communicationPaused = false;
            snapshotPlaying = false;
            if (player != null && !released) player.pause();
        });
    }

    void stop() {
        runOnPlayer(() -> {
            userRequestedPlayback = false;
            communicationPaused = false;
            snapshotPlaying = false;
            if (player != null && !released) player.stop();
        });
    }

    void reset() {
        runOnPlayer(() -> {
            userRequestedPlayback = false;
            communicationPaused = false;
            snapshotPlaying = false;
            if (player != null && !released) {
                player.stop();
                player.clearMediaItems();
            }
        });
    }

    void release() {
        if (released) return;
        released = true;
        userRequestedPlayback = false;
        communicationPaused = false;
        preparedListener = null;
        completionListener = null;
        errorListener = null;
        PLAYER_HANDLER.removeCallbacks(communicationModeWatcher);
        snapshotPlaying = false;
        // ExoPlayer.release() now runs on the dedicated Media3 looper. Even if a
        // device codec/cache teardown is slow, it cannot block MotionEvent/layout.
        PLAYER_HANDLER.post(this::releaseInternalPlayer);
    }

    boolean isPlaying() {
        requestSnapshot();
        return snapshotPlaying;
    }

    int getDuration() {
        requestSnapshot();
        return Math.max(0, snapshotDurationMs);
    }

    int getCurrentPosition() {
        requestSnapshot();
        return Math.max(0, snapshotPositionMs);
    }

    void seekTo(int positionMs) {
        int safe = Math.max(0, positionMs);
        snapshotPositionMs = safe;
        runOnPlayer(() -> {
            if (player != null && !released) player.seekTo(safe);
        });
    }

    private boolean isCommunicationMode() {
        if (audioManager == null) return false;
        int mode = audioManager.getMode();
        return mode == AudioManager.MODE_IN_CALL
            || mode == AudioManager.MODE_IN_COMMUNICATION;
    }

    private void scheduleCommunicationModeWatch() {
        PLAYER_HANDLER.removeCallbacks(communicationModeWatcher);
        if (!released) PLAYER_HANDLER.post(communicationModeWatcher);
    }

    private void notifyError(int what, int extra) {
        OnErrorListener listener = errorListener;
        if (listener == null) return;
        mainHandler.post(() -> {
            if (!released && errorListener == listener) {
                listener.onError(this, what, extra);
            }
        });
    }

    private void releaseInternalPlayer() {
        ExoPlayer existing = player;
        player = null;
        snapshotPlaying = false;
        snapshotDurationMs = 0;
        snapshotPositionMs = 0;
        if (existing != null) {
            try {
                existing.release();
            } catch (Exception ignored) {
            }
        }
    }

    private void requestSnapshot() {
        if (!released) PLAYER_HANDLER.post(this::updateSnapshot);
    }

    private void updateSnapshot() {
        ExoPlayer current = player;
        if (current == null || released) {
            snapshotPlaying = false;
            return;
        }
        try {
            snapshotPlaying = current.isPlaying();
            long duration = current.getDuration();
            snapshotDurationMs = duration == C.TIME_UNSET || duration < 0L
                ? 0 : (int) Math.min(Integer.MAX_VALUE, duration);
            long position = current.getCurrentPosition();
            snapshotPositionMs = (int) Math.max(0L, Math.min(Integer.MAX_VALUE, position));
        } catch (Throwable ignored) {
        }
    }

    private void runOnPlayer(Runnable action) {
        if (Looper.myLooper() == PLAYER_THREAD.getLooper()) {
            action.run();
        } else {
            PLAYER_HANDLER.post(action);
        }
    }

    static Map<String, String> requestHeadersFor(String catalogJson) {
        Map<String, String> headers = new HashMap<>();
        headers.put("User-Agent", "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Chrome/131 Mobile Safari/537.36");
        headers.put("Accept", "audio/*,application/octet-stream;q=0.9,*/*;q=0.1");
        headers.put("Accept-Encoding", "identity");
        String source = "";
        try {
            source = new JSONObject(catalogJson == null ? "{}" : catalogJson)
                .optString("source", "").trim().toLowerCase();
        } catch (Exception ignored) {
        }
        if ("kugou".equals(source)) headers.put("Referer", "https://www.kugou.com/");
        else if ("kuwo".equals(source)) headers.put("Referer", "http://www.kuwo.cn/");
        else if ("netease".equals(source)) headers.put("Referer", "https://music.163.com/");
        else if ("qq".equals(source)) headers.put("Referer", "https://y.qq.com/");
        else if ("migu".equals(source)) headers.put("Referer", "https://music.migu.cn/");
        else if ("soda".equals(source)) headers.put("Referer", "https://music.douyin.com/");
        return headers;
    }
}
