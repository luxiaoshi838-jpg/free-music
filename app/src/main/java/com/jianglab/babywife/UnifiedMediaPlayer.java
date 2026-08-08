package com.jianglab.babywife;

import android.content.Context;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Handler;
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
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

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
            mainHandler.postDelayed(this, 400L);
        }
    };
    private Uri sourceUri;
    private String cacheKey = "";
    private Map<String, String> requestHeaders = Collections.emptyMap();
    private ExoPlayer player;
    private OnPreparedListener preparedListener;
    private OnCompletionListener completionListener;
    private OnErrorListener errorListener;
    private boolean preparedDelivered;
    private boolean released;

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
        runOnMain(this::prepareInternal);
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
                .setLooper(Looper.getMainLooper())
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
                    if (playbackState == Player.STATE_READY && !preparedDelivered) {
                        preparedDelivered = true;
                        OnPreparedListener listener = preparedListener;
                        if (listener != null) listener.onPrepared(UnifiedMediaPlayer.this);
                    } else if (playbackState == Player.STATE_ENDED) {
                        OnCompletionListener listener = completionListener;
                        if (listener != null) listener.onCompletion(UnifiedMediaPlayer.this);
                    }
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
        runOnMain(() -> {
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
        runOnMain(() -> {
            userRequestedPlayback = false;
            communicationPaused = false;
            if (player != null && !released) player.pause();
        });
    }

    void stop() {
        runOnMain(() -> {
            userRequestedPlayback = false;
            communicationPaused = false;
            if (player != null && !released) player.stop();
        });
    }

    void reset() {
        runOnMain(() -> {
            userRequestedPlayback = false;
            communicationPaused = false;
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
        mainHandler.removeCallbacks(communicationModeWatcher);
        // Always enqueue the real ExoPlayer release. Calling existing.release()
        // inline from a song-row MotionEvent can block Xiaomi/Android 16 input
        // dispatch long enough to trigger a 5-second ANR.
        mainHandler.post(this::releaseInternalPlayer);
    }

    boolean isPlaying() {
        return callOnMain(() -> player != null && !released && player.isPlaying(), false);
    }

    int getDuration() {
        long value = callOnMain(() -> player == null ? C.TIME_UNSET : player.getDuration(),
            C.TIME_UNSET);
        if (value == C.TIME_UNSET || value < 0L) return 0;
        return (int) Math.min(Integer.MAX_VALUE, value);
    }

    int getCurrentPosition() {
        long value = callOnMain(() -> player == null ? 0L : player.getCurrentPosition(), 0L);
        return (int) Math.max(0L, Math.min(Integer.MAX_VALUE, value));
    }

    void seekTo(int positionMs) {
        runOnMain(() -> {
            if (player != null && !released) player.seekTo(Math.max(0, positionMs));
        });
    }

    private boolean isCommunicationMode() {
        if (audioManager == null) return false;
        int mode = audioManager.getMode();
        return mode == AudioManager.MODE_IN_CALL
            || mode == AudioManager.MODE_IN_COMMUNICATION;
    }

    private void scheduleCommunicationModeWatch() {
        mainHandler.removeCallbacks(communicationModeWatcher);
        if (!released) mainHandler.post(communicationModeWatcher);
    }

    private void notifyError(int what, int extra) {
        OnErrorListener listener = errorListener;
        if (listener != null) listener.onError(this, what, extra);
    }

    private void releaseInternalPlayer() {
        ExoPlayer existing = player;
        player = null;
        if (existing != null) {
            try {
                existing.release();
            } catch (Exception ignored) {
            }
        }
    }

    private void runOnMain(Runnable action) {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            action.run();
        } else {
            mainHandler.post(action);
        }
    }

    private interface ValueCall<T> {
        T call();
    }

    private <T> T callOnMain(ValueCall<T> action, T fallback) {
        if (Looper.myLooper() == Looper.getMainLooper()) {
            try {
                return action.call();
            } catch (Throwable ignored) {
                return fallback;
            }
        }
        AtomicReference<T> result = new AtomicReference<>(fallback);
        CountDownLatch latch = new CountDownLatch(1);
        mainHandler.post(() -> {
            try {
                result.set(action.call());
            } catch (Throwable ignored) {
            } finally {
                latch.countDown();
            }
        });
        try {
            latch.await(2, TimeUnit.SECONDS);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
        }
        return result.get();
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
