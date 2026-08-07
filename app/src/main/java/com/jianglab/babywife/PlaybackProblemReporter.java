package com.jianglab.babywife;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;

/** Stores non-crash playback failures in the existing copyable problem-report slot. */
final class PlaybackProblemReporter {
    private static final String PREFS_NAME = "babywife_state";
    private static final String KEY_REPORT = "last_crash_report";
    private static final String KEY_REPORT_TIME = "last_crash_report_time";
    private static final String KEY_REPORT_DISMISSED = "last_crash_report_dismissed";

    private PlaybackProblemReporter() {
    }

    static void store(Context context, String reason, UnifiedMediaPlayer player,
                      int what, int extra, String queueType,
                      int playlistIndex, int songIndex, String playlistName,
                      String title, String artist, String source,
                      String uri, String cachedUri, String catalogJson,
                      boolean activityResumed, boolean windowFocused,
                      boolean deviceInteractive, boolean preparing,
                      boolean expectedPlaying, boolean userPaused) {
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
            report.append("uri=").append(trim(uri, 800)).append('\n');
            report.append("cachedUri=").append(trim(cachedUri, 800)).append('\n');
            report.append("catalog=").append(trim(catalogJson, 1800)).append('\n');

            String text = trim(report.toString(), 60000);
            SharedPreferences preferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
            preferences.edit()
                .putString(KEY_REPORT, text)
                .putLong(KEY_REPORT_TIME, System.currentTimeMillis())
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
