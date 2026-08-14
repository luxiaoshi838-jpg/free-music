package com.jianglab.babywife;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;

import androidx.media3.common.Player;

/** Stores non-crash playback failures in the existing copyable problem-report slot. */
final class PlaybackProblemReporter {
    private static final String PREFS_NAME = "babywife_state";
    private static final String KEY_REPORT = "last_crash_report";
    private static final String KEY_REPORT_TIME = "last_crash_report_time";
    private static final String KEY_REPORT_DISMISSED = "last_crash_report_dismissed";
    private static final String KEY_HISTORY = "problem_report_history_v1";
    private static final int MAX_HISTORY = 10;

    private PlaybackProblemReporter() {
    }

    static void store(Context context, String reason, UnifiedMediaPlayer player,
                      int what, int extra, String queueType,
                      int playlistIndex, int songIndex, String playlistName,
                      String title, String artist, String source,
                      String uri, String cachedUri, String catalogJson,
                      boolean activityResumed, boolean windowFocused,
                      boolean deviceInteractive, boolean preparing,
                      boolean expectedPlaying, boolean userPaused,
                      String recentActions) {
        if (context == null) return;
        try {
            StringBuilder report = new StringBuilder();
            report.append("Playback interruption report\n");
            report.append("time=").append(System.currentTimeMillis()).append('\n');
            report.append("package=").append(context.getPackageName()).append('\n');
            report.append("versionCode=").append(BuildConfig.VERSION_CODE).append('\n');
            report.append("versionName=").append(BuildConfig.VERSION_NAME).append('\n');
            report.append("device=").append(Build.MANUFACTURER).append(' ')
                .append(Build.MODEL).append(" / Android ").append(Build.VERSION.RELEASE)
                .append(" sdk=").append(Build.VERSION.SDK_INT).append('\n');
            report.append("playerEngine=Media3 ExoPlayer shared cache\n");
            report.append("reason=").append(safe(reason)).append('\n');
            report.append("what=").append(what).append('\n');
            report.append("extra=").append(extra).append('\n');
            report.append("activityResumed=").append(activityResumed).append('\n');
            report.append("windowFocused=").append(windowFocused).append('\n');
            report.append("deviceInteractive=").append(deviceInteractive).append('\n');
            report.append("preparing=").append(preparing).append('\n');
            report.append("expectedPlaying=").append(expectedPlaying).append('\n');
            report.append("userPaused=").append(userPaused).append('\n');
            report.append("queue=").append(safe(queueType)).append('\n');
            report.append("playlistIndex=").append(playlistIndex).append('\n');
            report.append("songIndex=").append(songIndex).append('\n');
            report.append("playlist=").append(safe(playlistName)).append('\n');
            report.append("song=").append(safe(title)).append(" / ")
                .append(safe(artist)).append(" / ").append(safe(source)).append('\n');
            report.append("positionMs=").append(position(player)).append('\n');
            report.append("durationMs=").append(duration(player)).append('\n');
            report.append("isPlaying=").append(isPlaying(player)).append('\n');
            report.append("snapshotAgeMs=").append(snapshotAge(player)).append('\n');
            int playbackState = playbackState(player);
            report.append("playbackState=").append(playbackStateName(playbackState))
                .append(" (").append(playbackState).append(")\n");
            report.append("playWhenReady=").append(playWhenReady(player)).append('\n');
            report.append("suppressionReason=").append(suppressionReason(player)).append('\n');
            report.append("uri=").append(trim(uri, 800)).append('\n');
            report.append("cachedUri=").append(trim(cachedUri, 800)).append('\n');
            report.append("catalog=").append(trim(catalogJson, 1800)).append('\n');
            if (recentActions != null && !recentActions.trim().isEmpty()) {
                report.append("\nRecent actions (oldest -> newest):\n")
                    .append(trim(recentActions, 14000)).append('\n');
            }

            String text = trim(report.toString(), 60000);
            long now = System.currentTimeMillis();
            SharedPreferences preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
            org.json.JSONArray oldHistory;
            try {
                oldHistory = new org.json.JSONArray(preferences.getString(KEY_HISTORY, "[]"));
            } catch (Throwable ignored) {
                oldHistory = new org.json.JSONArray();
            }
            org.json.JSONArray next = new org.json.JSONArray();
            try {
                org.json.JSONObject newest = new org.json.JSONObject();
                newest.put("name", new java.text.SimpleDateFormat(
                    "yyyyMMdd_HHmmss", java.util.Locale.ROOT).format(new java.util.Date(now)));
                newest.put("time", now);
                newest.put("text", text);
                next.put(newest);
                for (int i = 0; i < oldHistory.length() && next.length() < MAX_HISTORY; i++) {
                    org.json.JSONObject item = oldHistory.optJSONObject(i);
                    if (item != null) next.put(item);
                }
            } catch (Throwable ignored) {
            }
            preferences.edit()
                .putString(KEY_HISTORY, next.toString())
                .putString(KEY_REPORT, text)
                .putLong(KEY_REPORT_TIME, now)
                .putBoolean(KEY_REPORT_DISMISSED, false)
                .commit();
        } catch (Throwable ignored) {
        }
    }

    private static long position(UnifiedMediaPlayer player) {
        if (player == null) return -1L;
        try {
            return player.getCurrentPosition();
        } catch (Exception ignored) {
            return -1L;
        }
    }

    private static long duration(UnifiedMediaPlayer player) {
        if (player == null) return -1L;
        try {
            return player.getDuration();
        } catch (Exception ignored) {
            return -1L;
        }
    }

    private static boolean isPlaying(UnifiedMediaPlayer player) {
        if (player == null) return false;
        try {
            return player.isPlaying();
        } catch (Exception ignored) {
            return false;
        }
    }

    private static long snapshotAge(UnifiedMediaPlayer player) {
        if (player == null) return -1L;
        try { return player.getSnapshotAgeMs(); } catch (Exception ignored) { return -1L; }
    }

    private static int playbackState(UnifiedMediaPlayer player) {
        if (player == null) return Player.STATE_IDLE;
        try { return player.getPlaybackStateSnapshot(); }
        catch (Exception ignored) { return Player.STATE_IDLE; }
    }

    private static boolean playWhenReady(UnifiedMediaPlayer player) {
        if (player == null) return false;
        try { return player.getPlayWhenReadySnapshot(); }
        catch (Exception ignored) { return false; }
    }

    private static int suppressionReason(UnifiedMediaPlayer player) {
        if (player == null) return Player.PLAYBACK_SUPPRESSION_REASON_NONE;
        try { return player.getPlaybackSuppressionReasonSnapshot(); }
        catch (Exception ignored) { return Player.PLAYBACK_SUPPRESSION_REASON_NONE; }
    }

    private static String playbackStateName(int state) {
        if (state == Player.STATE_BUFFERING) return "BUFFERING";
        if (state == Player.STATE_READY) return "READY";
        if (state == Player.STATE_ENDED) return "ENDED";
        return "IDLE";
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }

    private static String trim(String value, int maximum) {
        String safe = safe(value);
        if (safe.length() <= maximum) return safe;
        return safe.substring(0, maximum) + "\n...[truncated "
            + (safe.length() - maximum) + " chars]";
    }
}
