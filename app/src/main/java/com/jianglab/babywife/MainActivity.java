package com.jianglab.babywife;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ComponentName;
import android.content.pm.PackageManager;
import android.content.pm.PackageInfo;
import android.content.pm.Signature;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.text.Layout;
import android.text.Editable;
import android.text.SpannableString;
import android.text.TextWatcher;
import android.text.Spanned;
import android.text.TextUtils;
import android.text.style.ForegroundColorSpan;
import android.text.style.RelativeSizeSpan;
import android.text.style.StyleSpan;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.AbsListView;
import android.widget.ArrayAdapter;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.Locale;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;

public class MainActivity extends Activity {
    private static final String PREFS_NAME = "babywife_state";
    private static final String KEY_CRASH_REPORT = "last_crash_report";
    private static final String KEY_CRASH_REPORT_TIME = "last_crash_report_time";
    private static final String KEY_CRASH_REPORT_DISMISSED = "last_crash_report_dismissed";
    private static final String KEY_PLAYLISTS = "playlists_v2";
    private static final String KEY_CURRENT_PLAYLIST = "current_playlist";
    private static final String KEY_BACKGROUND_URI = "background_uri";
    private static final String KEY_BACKGROUND_MODE = "background_mode";
    private static final String BACKGROUND_MODE_DEFAULT = "default";
    private static final String BACKGROUND_MODE_LEGACY = "legacy";
    private static final String BACKGROUND_MODE_CUSTOM = "custom";
    private static final String KEY_LAST_PLAYLIST = "last_playlist";
    private static final String KEY_LAST_SONG = "last_song";
    private static final String KEY_LAST_POSITION = "last_position";
    private static final String KEY_LAST_CONTEXT = "last_context";
    private static final String KEY_LAST_SEARCH_SONG = "last_search_song";
    private static final String KEY_JIANGLAB_VERIFIED = "jianglab_verified";
    private static final String KEY_PLAY_MODE = "play_mode";
    private static final String KEY_SEARCH_SOURCE = "search_source";
    private static final int REQUEST_BACKGROUND_IMAGE = 7301;
    private static final int REQUEST_AUDIO_FILES = 7302;
    private static final int REQUEST_AUDIO_FOLDER = 7303;
    private static final int REQUEST_EXPORT_PLAYLIST = 7304;
    private static final int REQUEST_IMPORT_PLAYLIST_CSV = 7305;
    private static final int REQUEST_CACHE_FOLDER = 7306;
    private static final String KEY_LAUNCHER_ICON = "launcher_icon";
    private static final int REPLACEMENT_NONE = 0;
    private static final int REPLACEMENT_LYRIC = 1;
    private static final int REPLACEMENT_SONG = 2;
    private static final int MAX_IMPORT_COUNT = 1000;
    private static final int MIN_LYRIC_EDGE_BLANK_LINES = 6;
    private static final float ACTIVE_LYRIC_SCALE = 20f / 18f;
    private static final int PLAYLIST_CACHE_TRACK_TIMEOUT_SECONDS = 45;
    private static final long NO_RESPONSE_THRESHOLD_MS = 12000L;
    private static final long NO_RESPONSE_CHECK_INTERVAL_MS = 3000L;
    private static final long UI_HEARTBEAT_INTERVAL_MS = 1000L;

    private static final int ACCENT = Color.rgb(255, 78, 92);
    private static final int ACCENT_SOFT = Color.rgb(255, 128, 112);
    private static final int GLASS_DARK = Color.argb(116, 18, 20, 30);
    private static final int GLASS_LIGHT = Color.argb(42, 255, 255, 255);
    private static final int TEXT_MAIN = Color.WHITE;
    private static final int TEXT_MUTED = Color.argb(210, 235, 238, 246);

    private final List<Song> searchResults = new ArrayList<>();
    private final List<Playlist> playlists = new ArrayList<>();
    private int currentPlaylistIndex = 0;

    private SongListAdapter resultAdapter;
    private SongListAdapter playlistAdapter;
    private ArrayAdapter<String> playlistSpinnerAdapter;
    private ArrayAdapter<String> playlistManagerAdapter;
    private TextView titleView;
    private TextView artistView;
    private TextView lyricView;
    private Button songVersionButton;
    private Button lyricVersionButton;
    private Button confirmLyricButton;
    private SeekBar progressSeekBar;
    private TextView progressTimeView;
    private ScrollView lyricsScroll;
    private TextView statusView;
    private TextView searchStatusView;
    private Button currentPlaylistButton;
    private Button playButton;
    private Button modeButton;
    private Button addCurrentButton;
    private Button playlistCacheButton;
    private Button cacheLocationButton;
    private Button uninstallCleanupButton;
    private EditText searchInput;
    private Spinner sourceSpinner;
    private Spinner playlistSpinner;
    private ListView playlistManagerList;
    private ListView searchResultsList;
    private ListView playlistSongsList;
    private EditText playlistSearchInput;
    private final List<Song> playlistFilteredSongs = new ArrayList<>();
    private TextView searchPageStatusView;
    private TextView searchLoadMoreView;
    private CatalogSearch.Session activeSearchSession;
    private boolean searchPageLoading = false;
    private boolean searchNearBottom = false;
    private String activeSearchKeyword = "";
    private FrameLayout shellView;
    private LinearLayout drawerPanel;
    private int normalStatusBarColor;
    private View drawerDismissView;
    private LinearLayout headerBar;
    private LinearLayout searchPanel;
    private LinearLayout playerPanel;
    private LinearLayout playlistPanel;
    private ImageView backgroundView;
    private MediaPlayer mediaPlayer;
    private Song currentSong;
    private int currentSongIndex = -1;
    private boolean playingSearchQueue = false;
    private int searchSongIndex = -1;
    private int playMode = 0;
    private String savedSearchSource = "\u5feb\u901f\u641c\u7d22";
    private final Random random = new Random();
    private final Handler lyricHandler = new Handler(Looper.getMainLooper());
    private final Handler responsivenessHandler = new Handler(Looper.getMainLooper());
    private final List<LyricLine> lyricLines = new ArrayList<>();
    private boolean userLyricTouch = false;
    private boolean autoScrollingLyrics = false;
    private boolean userSeeking = false;
    private Song pendingLyricSong;
    private String pendingLyric = "";
    private String pendingLyricLabel = "";
    private Song pendingSongTarget;
    private String pendingSongOriginalKey = "";
    private String pendingSongTitle = "";
    private String pendingSongArtist = "";
    private String pendingSongSource = "";
    private String pendingSongCatalogJson = "";
    private int pendingReplacementType = REPLACEMENT_NONE;
    private int pendingExportPlaylistIndex = -1;
    private boolean pendingCacheFolderSelection = false;
    private boolean fileManagementSettingsOpened = false;
    private final Set<String> lyricMatchingSongs = new HashSet<>();
    private int highlightedLyricIndex = -1;
    private int lyricEdgeBlankLineCount = MIN_LYRIC_EDGE_BLANK_LINES;
    private boolean playbackReceiverRegistered = false;
    private int playbackRequestSerial = 0;
    private volatile int foregroundPlaybackSerial = 0;
    private volatile boolean playlistCacheRunning = false;
    private final ExecutorService playlistCacheScanExecutor = Executors.newSingleThreadExecutor();
    private volatile int playlistCacheScanSerial = 0;
    private volatile boolean responsivenessWatchdogRunning = false;
    private volatile boolean noResponseReportWritten = false;
    private volatile long lastUiHeartbeatMs = 0L;
    private long lastPublishedPlaybackSecond = -1L;
    private boolean lastPublishedPlaying = false;
    private String lastPublishedSongKey = "";
    private final BroadcastReceiver playbackCommandReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (intent == null) return;
            String command = intent.getStringExtra(PlaybackControlService.EXTRA_COMMAND);
            if (PlaybackControlService.COMMAND_PREVIOUS.equals(command)) {
                playPlaylistOffset(-1);
            } else if (PlaybackControlService.COMMAND_TOGGLE.equals(command)) {
                togglePlayback();
            } else if (PlaybackControlService.COMMAND_NEXT.equals(command)) {
                playPlaylistOffset(1);
            } else if (PlaybackControlService.COMMAND_SEEK.equals(command)) {
                long seek = intent.getLongExtra(PlaybackControlService.EXTRA_SEEK_POSITION, -1L);
                if (seek >= 0L && mediaPlayer != null) {
                    try {
                        mediaPlayer.seekTo((int) Math.min(Integer.MAX_VALUE, seek));
                        updatePlaybackProgress();
                        publishPlaybackControlState(true);
                    } catch (Exception ignored) {
                    }
                }
            }
        }
    };
    private final Runnable lyricTicker = new Runnable() {
        @Override
        public void run() {
            updatePlaybackProgress();
            updateLyricProgress();
            lyricHandler.postDelayed(this, 600);
        }
    };
    private final Runnable responsivenessHeartbeat = new Runnable() {
        @Override
        public void run() {
            lastUiHeartbeatMs = System.currentTimeMillis();
            noResponseReportWritten = false;
            if (responsivenessWatchdogRunning) {
                responsivenessHandler.postDelayed(this, UI_HEARTBEAT_INTERVAL_MS);
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        installCrashReporter();
        normalStatusBarColor = getWindow().getStatusBarColor();
        loadPlaylists();
        loadSavedUiSettings();
        setContentView(buildContentView());
        attachPressFeedbackTree(shellView);
        maybeRequireJiangLabPassphrase();
        registerPlaybackControlReceiver();
        PlaybackControlService.ensureStarted(this);
        renderPlaylists();
        renderCurrentPlaylist();
        scheduleStartupWork();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!pendingCacheFolderSelection || !fileManagementSettingsOpened) return;
        fileManagementSettingsOpened = false;
        if (hasFileManagementPermission()) {
            pendingCacheFolderSelection = false;
            chooseCacheFolder();
        } else {
            pendingCacheFolderSelection = false;
            toast("未授予文件管理权限，未更换缓存文件夹");
        }
    }

    private void scheduleStartupWork() {
        Handler startupHandler = new Handler(Looper.getMainLooper());
        Runnable work = () -> {
            restoreLastSong(false);
            normalizeAllCacheFilesAsync();
            publishPlaybackControlState(true);
            showPendingCrashReport();
            startResponsivenessWatchdog();
        };
        if (shellView != null) {
            shellView.postDelayed(work, 1500);
        } else {
            startupHandler.postDelayed(work, 1500);
        }
    }

    private void normalizeAllCacheFilesAsync() {
        new Thread(() -> {
            CacheStorage.normalizeAllFriendlyNames(this);
            runOnUiThread(this::normalizePlaylistCacheFilesAsync);
        }, "cache-name-normalizer").start();
    }

    private void installCrashReporter() {
        Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
        if (previous instanceof CrashReportHandler) return;
        Thread.setDefaultUncaughtExceptionHandler(new CrashReportHandler(previous));
    }

    private final class CrashReportHandler implements Thread.UncaughtExceptionHandler {
        private final Thread.UncaughtExceptionHandler previous;

        CrashReportHandler(Thread.UncaughtExceptionHandler previous) {
            this.previous = previous;
        }

        @Override
        public void uncaughtException(Thread thread, Throwable throwable) {
            try {
                persistCrashReport(thread, throwable);
            } catch (Throwable ignored) {
            }
            if (previous != null) {
                previous.uncaughtException(thread, throwable);
                return;
            }
            android.os.Process.killProcess(android.os.Process.myPid());
            System.exit(10);
        }
    }

    private void persistCrashReport(Thread thread, Throwable throwable) {
        StringWriter stack = new StringWriter();
        if (throwable != null) throwable.printStackTrace(new PrintWriter(stack));
        StringBuilder report = new StringBuilder();
        report.append("Crash report\n");
        appendReportContext(report, thread == null ? "" : thread.getName());
        report.append("\nstack:\n").append(stack);
        storeProblemReport(report.toString());
    }

    private void persistNoResponseReport(long blockedMs) {
        try {
            Thread mainThread = Looper.getMainLooper().getThread();
            StringBuilder report = new StringBuilder();
            report.append("No response report\n");
            appendReportContext(report, mainThread == null ? "main" : mainThread.getName());
            report.append("blockedMs=").append(blockedMs).append('\n');
            report.append("\nmainThreadStack:\n");
            if (mainThread != null) {
                for (StackTraceElement element : mainThread.getStackTrace()) {
                    report.append("\tat ").append(element).append('\n');
                }
            }
            storeProblemReport(report.toString());
        } catch (Throwable ignored) {
        }
    }

    private void appendReportContext(StringBuilder report, String threadName) {
        report.append("time=").append(System.currentTimeMillis()).append('\n');
        report.append("package=").append(getPackageName()).append('\n');
        report.append("versionCode=").append(BuildConfig.VERSION_CODE).append('\n');
        report.append("versionName=").append(BuildConfig.VERSION_NAME).append('\n');
        report.append("device=").append(Build.MANUFACTURER).append(' ')
            .append(Build.MODEL).append(" / Android ").append(Build.VERSION.RELEASE)
            .append(" sdk=").append(Build.VERSION.SDK_INT).append('\n');
        report.append("thread=").append(threadName == null ? "" : threadName).append('\n');
        report.append("playContext=").append(playingSearchQueue ? "search" : "playlist").append('\n');
        report.append("playlistIndex=").append(currentPlaylistIndex).append('\n');
        report.append("songIndex=").append(currentSongIndex).append('\n');
        Playlist playlist = currentPlaylist();
        report.append("playlist=").append(playlist == null ? "" : playlist.name).append('\n');
        Song snapshotSong = currentSong;
        if (snapshotSong != null) {
            report.append("song=").append(snapshotSong.title).append(" / ")
                .append(snapshotSong.artist).append(" / ").append(snapshotSong.source).append('\n');
            report.append("networkCatalog=").append(snapshotSong.isNetworkCatalog()).append('\n');
            report.append("cachedUri=").append(trimForReport(snapshotSong.cachedUri, 260)).append('\n');
            report.append("uri=").append(trimForReport(snapshotSong.uri, 260)).append('\n');
            report.append("catalog=").append(trimForReport(snapshotSong.catalogJson, 1200)).append('\n');
        }
    }

    private void storeProblemReport(String reportText) {
        String text = trimForReport(reportText, 60000);
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit()
            .putString(KEY_CRASH_REPORT, text)
            .putLong(KEY_CRASH_REPORT_TIME, System.currentTimeMillis())
            .putBoolean(KEY_CRASH_REPORT_DISMISSED, false)
            .commit();
    }

    private void startResponsivenessWatchdog() {
        if (responsivenessWatchdogRunning) return;
        responsivenessWatchdogRunning = true;
        lastUiHeartbeatMs = System.currentTimeMillis();
        responsivenessHandler.post(responsivenessHeartbeat);
        Thread watchdog = new Thread(() -> {
            while (responsivenessWatchdogRunning) {
                try {
                    Thread.sleep(NO_RESPONSE_CHECK_INTERVAL_MS);
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                    return;
                }
                long gap = System.currentTimeMillis() - lastUiHeartbeatMs;
                if (gap >= NO_RESPONSE_THRESHOLD_MS && !noResponseReportWritten) {
                    noResponseReportWritten = true;
                    persistNoResponseReport(gap);
                }
            }
        }, "ui-responsiveness-watchdog");
        watchdog.setDaemon(true);
        watchdog.start();
    }

    private String trimForReport(String value, int maxLength) {
        if (value == null) return "";
        if (value.length() <= maxLength) return value;
        return value.substring(0, maxLength) + "\n...[truncated " + (value.length() - maxLength) + " chars]";
    }

    private void showPendingCrashReport() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String report = prefs.getString(KEY_CRASH_REPORT, "");
        if (report == null || report.trim().isEmpty()) return;
        if (prefs.getBoolean(KEY_CRASH_REPORT_DISMISSED, false)) return;
        new Handler(Looper.getMainLooper()).postDelayed(() -> showCrashReportDialog(report), 600);
    }

    private void showCrashReportDialog(String report) {
        if (isFinishing()) return;
        TextView text = new TextView(this);
        text.setText(report);
        text.setTextIsSelectable(true);
        text.setTextSize(12);
        text.setPadding(dp(14), dp(12), dp(14), dp(12));
        ScrollView scroll = new ScrollView(this);
        scroll.addView(text);
        new AlertDialog.Builder(this)
            .setTitle("\u4e0a\u6b21\u95ea\u9000/\u65e0\u54cd\u5e94\u62a5\u544a")
            .setView(scroll)
            .setPositiveButton("\u590d\u5236", (dialog, which) -> {
                ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                if (clipboard != null) {
                    clipboard.setPrimaryClip(ClipData.newPlainText("crash-or-no-response-report", report));
                    toast("\u95ea\u9000/\u65e0\u54cd\u5e94\u62a5\u544a\u5df2\u590d\u5236");
                }
                markCrashReportDismissed();
            })
            .setNegativeButton("\u6e05\u9664", (dialog, which) -> clearCrashReport())
            .setNeutralButton("\u5173\u95ed", (dialog, which) -> markCrashReportDismissed())
            .setOnCancelListener(dialog -> markCrashReportDismissed())
            .show();
    }

    private void clearCrashReport() {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit()
            .remove(KEY_CRASH_REPORT)
            .remove(KEY_CRASH_REPORT_TIME)
            .remove(KEY_CRASH_REPORT_DISMISSED)
            .apply();
    }

    private void markCrashReportDismissed() {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit()
            .putBoolean(KEY_CRASH_REPORT_DISMISSED, true)
            .apply();
    }

    private void openSavedCrashReport() {
        String report = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .getString(KEY_CRASH_REPORT, "");
        if (report == null || report.trim().isEmpty()) {
            toast("\u6682\u65e0\u95ea\u9000/\u65e0\u54cd\u5e94\u62a5\u544a");
            return;
        }
        showCrashReportDialog(report);
    }


    private void maybeRequireJiangLabPassphrase() {
        if (!BuildConfig.REQUIRE_FIRST_RUN_PASSPHRASE) return;
        SharedPreferences preferences = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        if (preferences.getBoolean(KEY_JIANGLAB_VERIFIED, false)) return;
        final EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setHint("请输入首次使用口令");
        input.setPadding(dp(18), 0, dp(18), 0);
        AlertDialog dialog = new AlertDialog.Builder(this)
            .setTitle("姜Lab首次验证")
            .setMessage("验证成功后，本机后续启动不再要求输入。")
            .setView(input)
            .setPositiveButton("验证", null)
            .create();
        dialog.setCancelable(false);
        dialog.setCanceledOnTouchOutside(false);
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE)
            .setOnClickListener(view -> {
                String expected = signingCertificateCommonName();
                String entered = input.getText().toString().trim();
                if (!expected.isEmpty() && expected.equals(entered)) {
                    preferences.edit().putBoolean(KEY_JIANGLAB_VERIFIED, true).apply();
                    dialog.dismiss();
                    toast("验证成功");
                } else {
                    input.setError("口令不正确");
                    input.selectAll();
                }
            }));
        dialog.show();
    }

    private String signingCertificateCommonName() {
        try {
            PackageInfo info;
            Signature[] signatures;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                info = getPackageManager().getPackageInfo(getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
                signatures = info.signingInfo == null ? null : info.signingInfo.getApkContentsSigners();
            } else {
                info = getPackageManager().getPackageInfo(getPackageName(), PackageManager.GET_SIGNATURES);
                signatures = info.signatures;
            }
            if (signatures == null || signatures.length == 0) return "";
            CertificateFactory factory = CertificateFactory.getInstance("X.509");
            X509Certificate certificate = (X509Certificate) factory.generateCertificate(
                new ByteArrayInputStream(signatures[0].toByteArray()));
            String distinguishedName = certificate.getSubjectX500Principal().getName();
            java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("(?:^|,)\\s*CN=([^,]+)")
                .matcher(distinguishedName);
            return matcher.find() ? matcher.group(1).trim() : "";
        } catch (Exception ignored) {
            return "";
        }
    }

    private void loadSavedUiSettings() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        playMode = clampPlayMode(prefs.getInt(KEY_PLAY_MODE, playMode));
        savedSearchSource = prefs.getString(KEY_SEARCH_SOURCE, "\u5feb\u901f\u641c\u7d22");
        if (savedSearchSource == null || savedSearchSource.trim().isEmpty()) {
            savedSearchSource = "\u5feb\u901f\u641c\u7d22";
        }
    }

    private int clampPlayMode(int value) {
        return value < 0 || value > 2 ? 0 : value;
    }

    private void savePlayMode() {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putInt(KEY_PLAY_MODE, clampPlayMode(playMode))
            .apply();
    }

    private void saveSearchSource(String source) {
        if (source == null || source.trim().isEmpty()) return;
        savedSearchSource = source;
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putString(KEY_SEARCH_SOURCE, source)
            .apply();
    }

    private int indexOf(String[] values, String wanted) {
        if (values == null || wanted == null) return -1;
        for (int i = 0; i < values.length; i++) {
            if (wanted.equals(values[i])) return i;
        }
        return -1;
    }

    private void registerPlaybackControlReceiver() {
        if (playbackReceiverRegistered) return;
        IntentFilter filter = new IntentFilter(PlaybackControlService.ACTION_COMMAND);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(playbackCommandReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(playbackCommandReceiver, filter);
        }
        playbackReceiverRegistered = true;
    }

    private MediaPlayer createWakefulMediaPlayer() {
        MediaPlayer player = new MediaPlayer();
        try {
            player.setWakeMode(getApplicationContext(), PowerManager.PARTIAL_WAKE_LOCK);
        } catch (Exception ignored) {
        }
        return player;
    }

    private void publishPlaybackControlState(boolean force) {
        String title = currentSong == null ? "尚未播放" : currentSong.title;
        String artist = currentSong == null ? "大宝贝儿老婆" : currentSong.artist;
        String songKey = currentSong == null ? "" : currentSong.key();
        boolean isPlaying = false;
        long duration = 0L;
        long position = 0L;
        if (mediaPlayer != null) {
            try {
                isPlaying = mediaPlayer.isPlaying();
                duration = Math.max(0L, mediaPlayer.getDuration());
                position = Math.max(0L, mediaPlayer.getCurrentPosition());
            } catch (Exception ignored) {
            }
        }
        long second = position / 1000L;
        if (!force
            && second == lastPublishedPlaybackSecond
            && isPlaying == lastPublishedPlaying
            && songKey.equals(lastPublishedSongKey)) {
            return;
        }
        lastPublishedPlaybackSecond = second;
        lastPublishedPlaying = isPlaying;
        lastPublishedSongKey = songKey;
        PlaybackControlService.publishState(
            this,
            title,
            artist,
            isPlaying,
            duration,
            position
        );
    }

    private View buildContentView() {
        shellView = new FrameLayout(this);

        backgroundView = new ImageView(this);
        backgroundView.setScaleType(ImageView.ScaleType.CENTER_CROP);
        applySavedBackground();
        shellView.addView(backgroundView, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(14), statusBarHeight() + dp(10), dp(14), dp(14));
        root.setBackgroundColor(Color.argb(72, 0, 0, 0));

        headerBar = new LinearLayout(this);
        headerBar.setOrientation(LinearLayout.HORIZONTAL);
        headerBar.setGravity(Gravity.CENTER_VERTICAL);

        Button settingsButton = makeRoundButton("\u2699", false);
        settingsButton.setTextSize(18);
        settingsButton.setOnClickListener(view -> toggleDrawer());
        headerBar.addView(settingsButton, new LinearLayout.LayoutParams(dp(48), dp(42)));

        BroomIconView clearCacheButton = new BroomIconView(this);
        clearCacheButton.setBackground(rounded(Color.argb(88, 255, 255, 255), dp(999)));
        clearCacheButton.setContentDescription("清除非歌单缓存");
        clearCacheButton.setOnClickListener(view -> confirmClearTransientCache());
        attachSubtlePressFeedback(clearCacheButton);
        LinearLayout.LayoutParams clearParams = new LinearLayout.LayoutParams(dp(42), dp(42));
        clearParams.setMargins(dp(6), 0, 0, 0);
        headerBar.addView(clearCacheButton, clearParams);

        searchStatusView = new TextView(this);
        searchStatusView.setText("\u70b9\u6b64\u641c\u7d22\u6b4c\u66f2");
        searchStatusView.setTextSize(14);
        searchStatusView.setGravity(Gravity.CENTER);
        searchStatusView.setTextColor(TEXT_MAIN);
        searchStatusView.setBackground(rounded(Color.argb(88, 255, 255, 255), dp(22)));
        searchStatusView.setOnClickListener(view -> showSearchPage());
        LinearLayout.LayoutParams searchStatusParams = new LinearLayout.LayoutParams(0, dp(42), 1);
        searchStatusParams.setMargins(dp(8), 0, dp(8), 0);
        headerBar.addView(searchStatusView, searchStatusParams);

        currentPlaylistButton = makeButton("\u5f53\u524d\u6b4c\u5355", true);
        currentPlaylistButton.setTextSize(12);
        currentPlaylistButton.setSingleLine(true);
        currentPlaylistButton.setGravity(Gravity.CENTER);
        currentPlaylistButton.setEllipsize(TextUtils.TruncateAt.END);
        currentPlaylistButton.setMarqueeRepeatLimit(-1);
        currentPlaylistButton.setOnClickListener(view -> showPlaylistPage());
        headerBar.addView(currentPlaylistButton, new LinearLayout.LayoutParams(dp(104), dp(42)));
        root.addView(headerBar);

        statusView = new TextView(this);
        statusView.setTextSize(12);
        statusView.setTextColor(TEXT_MUTED);
        statusView.setGravity(Gravity.CENTER);
        root.addView(statusView, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ));

        searchPanel = (LinearLayout) buildSearchPanel();
        searchPanel.setVisibility(View.GONE);
        root.addView(searchPanel, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1
        ));
        playerPanel = (LinearLayout) buildPlayerPanel();
        root.addView(playerPanel, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1
        ));
        playlistPanel = (LinearLayout) buildPlaylistPage();
        playlistPanel.setVisibility(View.GONE);
        root.addView(playlistPanel, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1
        ));

        shellView.addView(root, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));

        drawerDismissView = new View(this);
        drawerDismissView.setBackgroundColor(Color.argb(1, 0, 0, 0));
        drawerDismissView.setVisibility(View.GONE);
        drawerDismissView.setOnClickListener(view -> closeDrawer());
        shellView.addView(drawerDismissView, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        ));

        drawerPanel = buildDrawerPanel();
        drawerPanel.setVisibility(View.GONE);
        drawerPanel.setClickable(true);
        int drawerWidth = Math.round(getResources().getDisplayMetrics().widthPixels * 0.70f);
        FrameLayout.LayoutParams drawerParams = new FrameLayout.LayoutParams(
            drawerWidth,
            ViewGroup.LayoutParams.MATCH_PARENT
        );
        drawerParams.gravity = Gravity.START;
        shellView.addView(drawerPanel, drawerParams);
        return shellView;
    }

    private View buildSearchPanel() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(10), dp(10), dp(10), dp(10));
        panel.setBackground(rounded(Color.argb(98, 0, 0, 0), dp(22)));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);

        BackChevronView backButton = new BackChevronView(this);
        backButton.setOnClickListener(view -> showPlayerPage());
        row.addView(backButton, new LinearLayout.LayoutParams(dp(46), dp(46)));

        FrameLayout searchBox = new FrameLayout(this);
        searchInput = new EditText(this);
        searchInput.setSingleLine(true);
        searchInput.setHint("搜索歌曲 / 歌手");
        searchInput.setTextColor(TEXT_MAIN);
        searchInput.setHintTextColor(Color.argb(190, 255, 255, 255));
        searchInput.setPadding(dp(22), 0, dp(48), 0);
        searchInput.setBackground(rounded(Color.argb(72, 255, 255, 255), dp(22)));
        searchInput.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        searchInput.setOnEditorActionListener((view, actionId, event) -> {
            boolean keyboardSearch = actionId == EditorInfo.IME_ACTION_SEARCH
                || actionId == EditorInfo.IME_ACTION_DONE;
            boolean enterUp = event != null
                && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                && event.getAction() == KeyEvent.ACTION_UP;
            if (keyboardSearch || enterUp) {
                performSearch();
                return true;
            }
            return false;
        });
        searchBox.addView(searchInput, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        TextView clearSearchButton = new TextView(this);
        clearSearchButton.setText("×");
        clearSearchButton.setTextColor(Color.WHITE);
        clearSearchButton.setTextSize(17);
        clearSearchButton.setGravity(Gravity.CENTER);
        clearSearchButton.setIncludeFontPadding(false);
        clearSearchButton.setVisibility(View.GONE);
        clearSearchButton.setClickable(true);
        clearSearchButton.setFocusable(true);
        clearSearchButton.setContentDescription("清除搜索文字");
        clearSearchButton.setBackground(rounded(Color.argb(190, 112, 112, 118), dp(12)));
        clearSearchButton.setOnClickListener(view -> {
            searchInput.setText("");
            searchInput.requestFocus();
        });
        attachSubtlePressFeedback(clearSearchButton);
        FrameLayout.LayoutParams clearParams = new FrameLayout.LayoutParams(dp(24), dp(24));
        clearParams.gravity = Gravity.END | Gravity.CENTER_VERTICAL;
        clearParams.setMargins(0, 0, dp(10), 0);
        searchBox.addView(clearSearchButton, clearParams);
        searchInput.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence text, int start, int count, int after) {
            }

            @Override
            public void onTextChanged(CharSequence text, int start, int before, int count) {
                clearSearchButton.setVisibility(
                    text != null && text.length() > 0 ? View.VISIBLE : View.GONE);
            }

            @Override
            public void afterTextChanged(Editable editable) {
            }
        });

        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(0, dp(46), 1);
        inputParams.setMargins(dp(8), 0, dp(8), 0);
        row.addView(searchBox, inputParams);

        Button searchButton = makeButton("搜索", true);
        searchButton.setOnClickListener(view -> performSearch());
        row.addView(searchButton, new LinearLayout.LayoutParams(dp(76), dp(46)));
        panel.addView(row);

        sourceSpinner = new Spinner(this);
        String[] sources = {
            "快速搜索",
            "全部平台",
            "更多来源",
            "本地歌曲",
            "网易云",
            "QQ音乐",
            "酷狗",
            "酷我",
            "咪咕",
            "汽水",
            "哔哩哔哩",
            "5sing",
            "千千",
            "Jamendo",
            "Joox",
            "Apple Music"
        };
        sourceSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, sources));
        int savedSourceIndex = indexOf(sources, savedSearchSource);
        if (savedSourceIndex >= 0) sourceSpinner.setSelection(savedSourceIndex);
        sourceSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                Object selected = parent == null ? null : parent.getItemAtPosition(position);
                saveSearchSource(selected == null ? "" : String.valueOf(selected));
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
            }
        });
        panel.addView(sourceSpinner, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            dp(42)
        ));

        searchPageStatusView = new TextView(this);
        searchPageStatusView.setText("搜索只建立目录；滚动到底部继续加载，点击歌曲后缓存音频和歌词");
        searchPageStatusView.setTextColor(TEXT_MUTED);
        searchPageStatusView.setTextSize(12);
        searchPageStatusView.setPadding(dp(8), dp(5), dp(8), dp(5));
        panel.addView(searchPageStatusView);

        TextView header = new TextView(this);
        header.setText("歌名                 歌手             平台");
        header.setTextColor(TEXT_MUTED);
        header.setTextSize(13);
        header.setPadding(dp(8), dp(6), dp(8), dp(6));
        panel.addView(header);

        resultAdapter = new SongListAdapter(searchResults);
        searchResultsList = new ListView(this);
        searchResultsList.setBackground(rounded(Color.argb(72, 0, 0, 0), dp(20)));
        searchLoadMoreView = new TextView(this);
        searchLoadMoreView.setText("搜索后可在此加载下一批未搜索平台");
        searchLoadMoreView.setTextColor(TEXT_MAIN);
        searchLoadMoreView.setTextSize(14);
        searchLoadMoreView.setGravity(Gravity.CENTER);
        searchLoadMoreView.setPadding(dp(12), dp(16), dp(12), dp(16));
        searchLoadMoreView.setBackground(rounded(Color.argb(86, 255, 255, 255), dp(18)));
        searchLoadMoreView.setOnClickListener(view -> loadNextSearchBatch(false));
        attachSubtlePressFeedback(searchLoadMoreView);
        searchResultsList.addFooterView(searchLoadMoreView, null, true);
        searchResultsList.setAdapter(resultAdapter);
        searchResultsList.setOnItemClickListener((parent, view, position, id) -> {
            if (position < 0 || position >= searchResults.size()) return;
            playSongFromSearch(position);
            showPlayerPage();
        });
        searchResultsList.setOnItemLongClickListener((parent, view, position, id) -> {
            if (position >= 0 && position < searchResults.size()) {
                addSongToCurrentPlaylist(searchResults.get(position));
            }
            return true;
        });
        searchResultsList.setOnScrollListener(new AbsListView.OnScrollListener() {
            @Override
            public void onScrollStateChanged(AbsListView view, int scrollState) {
                if (scrollState == AbsListView.OnScrollListener.SCROLL_STATE_IDLE
                    && searchNearBottom && activeSearchSession != null && activeSearchSession.hasMore()) {
                    loadNextSearchBatch(false);
                }
            }

            @Override
            public void onScroll(AbsListView view, int firstVisibleItem, int visibleItemCount, int totalItemCount) {
                searchNearBottom = totalItemCount > 0 && visibleItemCount > 0
                    && firstVisibleItem + visibleItemCount >= totalItemCount - 1;
            }
        });
        panel.addView(searchResultsList, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1
        ));
        return panel;
    }

    private View buildPlayerPanel() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(14), dp(10), dp(14), dp(10));
        panel.setBackground(rounded(GLASS_DARK, dp(28)));

        titleView = new TextView(this);
        titleView.setTextSize(24);
        titleView.setTypeface(Typeface.DEFAULT_BOLD);
        titleView.setTextColor(TEXT_MAIN);
        titleView.setGravity(Gravity.CENTER);
        titleView.setSingleLine(true);
        titleView.setEllipsize(TextUtils.TruncateAt.END);
        panel.addView(titleView);

        artistView = new TextView(this);
        artistView.setTextSize(14);
        artistView.setTextColor(TEXT_MUTED);
        artistView.setGravity(Gravity.CENTER);
        artistView.setSingleLine(true);
        artistView.setEllipsize(TextUtils.TruncateAt.END);
        panel.addView(artistView);

        addCurrentButton = makeButton("加入当前歌单", false);
        addCurrentButton.setTextSize(12);
        addCurrentButton.setVisibility(View.GONE);
        addCurrentButton.setOnClickListener(view -> {
            if (currentSong == null) {
                toast("请先选择歌曲");
                return;
            }
            addSongToCurrentPlaylist(currentSong);
        });
        LinearLayout.LayoutParams addParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, dp(34));
        addParams.gravity = Gravity.CENTER_HORIZONTAL;
        addParams.setMargins(0, dp(4), 0, dp(3));
        panel.addView(addCurrentButton, addParams);

        FrameLayout lyricFrame = new FrameLayout(this);
        lyricFrame.setPadding(dp(5), dp(5), dp(5), dp(5));
        lyricFrame.setBackground(rounded(Color.argb(82, 0, 0, 0), dp(18)));

        lyricView = new TextView(this);
        lyricView.setTextSize(18);
        lyricView.setGravity(Gravity.CENTER);
        lyricView.setLineSpacing(8, 1.08f);
        lyricView.setPadding(dp(8), dp(6), dp(8), dp(8));
        lyricView.setTextColor(Color.argb(244, 255, 255, 255));
        lyricsScroll = new ScrollView(this);
        lyricsScroll.setFillViewport(true);
        lyricsScroll.setClipToPadding(false);
        lyricsScroll.setPadding(0, dp(44), 0, dp(46));
        lyricsScroll.setOnTouchListener((view, event) -> {
            if (event.getAction() == MotionEvent.ACTION_DOWN) {
                userLyricTouch = true;
            } else if (event.getAction() == MotionEvent.ACTION_UP) {
                seekByLyricTouch(event.getY());
                userLyricTouch = false;
            } else if (event.getAction() == MotionEvent.ACTION_CANCEL) {
                userLyricTouch = false;
            }
            return false;
        });
        lyricsScroll.addView(lyricView, new ScrollView.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT));
        lyricFrame.addView(lyricsScroll, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT));

        songVersionButton = makeButton("替换歌曲", false);
        songVersionButton.setTextSize(12);
        songVersionButton.setVisibility(View.GONE);
        songVersionButton.setOnClickListener(view -> showSongVersionPicker());
        FrameLayout.LayoutParams songAction = new FrameLayout.LayoutParams(
            dp(96), dp(36), Gravity.TOP | Gravity.START);
        songAction.setMargins(dp(6), dp(5), 0, 0);
        lyricFrame.addView(songVersionButton, songAction);

        lyricVersionButton = makeButton("替换歌词", false);
        lyricVersionButton.setTextSize(12);
        lyricVersionButton.setVisibility(View.GONE);
        lyricVersionButton.setOnClickListener(view -> showLyricVersionPicker());
        FrameLayout.LayoutParams lyricAction = new FrameLayout.LayoutParams(
            dp(96), dp(36), Gravity.TOP | Gravity.END);
        lyricAction.setMargins(0, dp(5), dp(6), 0);
        lyricFrame.addView(lyricVersionButton, lyricAction);

        confirmLyricButton = makeButton("确认替换", true);
        confirmLyricButton.setTextSize(12);
        confirmLyricButton.setVisibility(View.GONE);
        confirmLyricButton.setOnClickListener(view -> confirmPendingReplacement());
        FrameLayout.LayoutParams confirmAction = new FrameLayout.LayoutParams(
            dp(136), dp(38), Gravity.BOTTOM | Gravity.END);
        confirmAction.setMargins(0, 0, dp(6), dp(5));
        lyricFrame.addView(confirmLyricButton, confirmAction);

        LinearLayout.LayoutParams lyricFrameParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1);
        lyricFrameParams.setMargins(0, dp(4), 0, dp(2));
        panel.addView(lyricFrame, lyricFrameParams);

        progressSeekBar = new SeekBar(this);
        progressSeekBar.setMax(1);
        progressSeekBar.setProgress(0);
        progressSeekBar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser && progressTimeView != null) {
                    progressTimeView.setText(formatPlaybackTime(progress)
                        + " / " + formatPlaybackTime(seekBar.getMax()));
                }
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {
                userSeeking = true;
            }

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {
                try {
                    if (mediaPlayer != null) mediaPlayer.seekTo(seekBar.getProgress());
                } catch (Exception ignored) {
                }
                userSeeking = false;
                updatePlaybackProgress();
            }
        });
        LinearLayout.LayoutParams seekParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT);
        seekParams.setMargins(0, 0, 0, 0);
        panel.addView(progressSeekBar, seekParams);

        progressTimeView = new TextView(this);
        progressTimeView.setText("00:00 / 00:00");
        progressTimeView.setTextColor(TEXT_MUTED);
        progressTimeView.setTextSize(12);
        progressTimeView.setGravity(Gravity.CENTER);
        panel.addView(progressTimeView, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(18)));

        LinearLayout bottomBar = new LinearLayout(this);
        bottomBar.setOrientation(LinearLayout.HORIZONTAL);
        bottomBar.setGravity(Gravity.CENTER_VERTICAL);
        bottomBar.setMinimumHeight(dp(62));

        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.setGravity(Gravity.CENTER);
        controls.setPadding(0, dp(2), 0, dp(2));

        Button previous = makeRoundButton("⏮", false);
        previous.setTextSize(18);
        previous.setOnClickListener(view -> playPlaylistOffset(-1));
        attachSubtlePressFeedback(previous);
        controls.addView(previous, new LinearLayout.LayoutParams(dp(50), dp(50)));

        playButton = makeRoundButton("▶", true);
        playButton.setTextSize(22);
        playButton.setOnClickListener(view -> togglePlayback());
        LinearLayout.LayoutParams playParams = new LinearLayout.LayoutParams(dp(62), dp(62));
        playParams.setMargins(dp(28), 0, dp(28), 0);
        controls.addView(playButton, playParams);

        Button next = makeRoundButton("⏭", false);
        next.setTextSize(18);
        next.setOnClickListener(view -> playPlaylistOffset(1));
        attachSubtlePressFeedback(next);
        controls.addView(next, new LinearLayout.LayoutParams(dp(50), dp(50)));
        bottomBar.addView(controls, new LinearLayout.LayoutParams(
            0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        modeButton = makeRoundButton(playModeSymbol(), false);
        modeButton.setTextSize(12);
        modeButton.setOnClickListener(view -> cyclePlayMode());
        LinearLayout.LayoutParams modeParams = new LinearLayout.LayoutParams(dp(42), dp(42));
        modeParams.gravity = Gravity.CENTER_VERTICAL;
        bottomBar.addView(modeButton, modeParams);
        panel.addView(bottomBar, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT));
        return panel;
    }

    private void attachSubtlePressFeedback(View view) {
        if (view == null) return;
        view.setOnTouchListener((pressedView, event) -> {
            if (!pressedView.isEnabled()) return false;
            if (event == null) return false;
            int action = event.getActionMasked();
            if (action == MotionEvent.ACTION_DOWN) {
                pressedView.animate().cancel();
                pressedView.animate()
                    .scaleX(0.96f)
                    .scaleY(0.96f)
                    .setDuration(65L)
                    .start();
            } else if (action == MotionEvent.ACTION_UP
                || action == MotionEvent.ACTION_CANCEL) {
                pressedView.animate().cancel();
                pressedView.animate()
                    .scaleX(1f)
                    .scaleY(1f)
                    .setDuration(115L)
                    .start();
            }
            return false;
        });
    }

    private void attachPressFeedbackTree(View root) {
        if (root == null) return;
        boolean buttonLike = root instanceof Button
            || root instanceof BroomIconView
            || root instanceof BackChevronView
            || (root instanceof TextView && !(root instanceof EditText) && root.isClickable())
            || (root instanceof ImageView && root.isClickable())
            || (root instanceof LinearLayout && root.isClickable());
        if (buttonLike) attachSubtlePressFeedback(root);
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) root;
            for (int index = 0; index < group.getChildCount(); index++) {
                attachPressFeedbackTree(group.getChildAt(index));
            }
        }
    }

    private void hideKeyboardAndClearFocus(View target) {
        View focused = target != null ? target : getCurrentFocus();
        if (focused != null) {
            InputMethodManager manager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            if (manager != null) manager.hideSoftInputFromWindow(focused.getWindowToken(), 0);
            focused.clearFocus();
        }
    }

    private View buildPlaylistPage() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(10), dp(10), dp(10), dp(10));
        panel.setBackground(rounded(GLASS_DARK, dp(28)));

        LinearLayout topRow = new LinearLayout(this);
        topRow.setOrientation(LinearLayout.HORIZONTAL);
        topRow.setGravity(Gravity.CENTER_VERTICAL);
        BackChevronView backButton = new BackChevronView(this);
        backButton.setOnClickListener(view -> showPlayerPage());
        topRow.addView(backButton, new LinearLayout.LayoutParams(dp(46), dp(46)));
        TextView title = new TextView(this);
        title.setText("当前歌单");
        title.setTextColor(TEXT_MAIN);
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER);
        topRow.addView(title, new LinearLayout.LayoutParams(
            0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        Button playlistSortButton = makeButton("排序", false);
        playlistSortButton.setTextSize(12);
        playlistSortButton.setSingleLine(true);
        playlistSortButton.setContentDescription("排序当前歌单");
        playlistSortButton.setOnClickListener(view -> showCurrentPlaylistSortDialog());
        topRow.addView(playlistSortButton, new LinearLayout.LayoutParams(dp(58), dp(42)));
        panel.addView(topRow);

        FrameLayout playlistSearchBox = new FrameLayout(this);
        playlistSearchInput = new EditText(this);
        playlistSearchInput.setSingleLine(true);
        playlistSearchInput.setHint("搜索当前歌单中的歌曲 / 歌手");
        playlistSearchInput.setTextColor(TEXT_MAIN);
        playlistSearchInput.setHintTextColor(Color.argb(185, 255, 255, 255));
        playlistSearchInput.setBackground(rounded(Color.argb(72, 255, 255, 255), dp(20)));
        playlistSearchInput.setPadding(dp(14), 0, dp(48), 0);
        playlistSearchInput.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        playlistSearchInput.setOnEditorActionListener((view, actionId, event) -> {
            boolean keyboardSearch = actionId == EditorInfo.IME_ACTION_SEARCH
                || actionId == EditorInfo.IME_ACTION_DONE;
            boolean enterUp = event != null
                && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                && event.getAction() == KeyEvent.ACTION_UP;
            if (keyboardSearch || enterUp) {
                applyPlaylistFilter();
                hideKeyboardAndClearFocus(playlistSearchInput);
                return true;
            }
            return false;
        });
        playlistSearchBox.addView(playlistSearchInput, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        TextView clearPlaylistSearchButton = new TextView(this);
        clearPlaylistSearchButton.setText("×");
        clearPlaylistSearchButton.setTextColor(Color.WHITE);
        clearPlaylistSearchButton.setTextSize(17);
        clearPlaylistSearchButton.setGravity(Gravity.CENTER);
        clearPlaylistSearchButton.setIncludeFontPadding(false);
        clearPlaylistSearchButton.setVisibility(View.GONE);
        clearPlaylistSearchButton.setClickable(true);
        clearPlaylistSearchButton.setFocusable(true);
        clearPlaylistSearchButton.setContentDescription("清除歌单搜索文字");
        clearPlaylistSearchButton.setBackground(rounded(Color.argb(190, 112, 112, 118), dp(12)));
        clearPlaylistSearchButton.setOnClickListener(view -> {
            playlistSearchInput.setText("");
            playlistSearchInput.requestFocus();
        });
        attachSubtlePressFeedback(clearPlaylistSearchButton);
        FrameLayout.LayoutParams playlistClearParams = new FrameLayout.LayoutParams(dp(24), dp(24));
        playlistClearParams.gravity = Gravity.END | Gravity.CENTER_VERTICAL;
        playlistClearParams.setMargins(0, 0, dp(10), 0);
        playlistSearchBox.addView(clearPlaylistSearchButton, playlistClearParams);

        playlistSearchInput.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence text, int start, int count, int after) {
            }

            @Override
            public void afterTextChanged(Editable editable) {
            }

            @Override
            public void onTextChanged(CharSequence text, int start, int before, int count) {
                clearPlaylistSearchButton.setVisibility(
                    text != null && text.length() > 0 ? View.VISIBLE : View.GONE);
                applyPlaylistFilter();
            }
        });
        LinearLayout.LayoutParams searchParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(44));
        searchParams.setMargins(0, dp(6), 0, dp(6));
        panel.addView(playlistSearchBox, searchParams);

        TextView hint = new TextView(this);
        hint.setText("点击播放；长按歌曲后确认删除");
        hint.setTextColor(TEXT_MUTED);
        hint.setTextSize(12);
        hint.setGravity(Gravity.CENTER);
        panel.addView(hint);

        playlistAdapter = new SongListAdapter(playlistFilteredSongs);
        playlistSongsList = new ListView(this);
        playlistSongsList.setBackground(rounded(Color.argb(72, 0, 0, 0), dp(20)));
        playlistSongsList.setAdapter(playlistAdapter);
        playlistSongsList.setOnItemClickListener((parent, view, position, id) -> {
            if (position < 0 || position >= playlistFilteredSongs.size()) return;
            Song selected = playlistFilteredSongs.get(position);
            int actualIndex = currentPlaylist().songs.indexOf(selected);
            if (actualIndex < 0) return;
            playSongFromPlaylist(actualIndex);
            showPlayerPage();
        });
        playlistSongsList.setOnItemLongClickListener((parent, view, position, id) -> {
            if (position >= 0 && position < playlistFilteredSongs.size()) {
                confirmDeletePlaylistSong(playlistFilteredSongs.get(position));
            }
            return true;
        });
        panel.addView(playlistSongsList, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        playlistCacheButton = makeButton("一键缓存未缓存歌曲", true);
        playlistCacheButton.setTextSize(14);
        playlistCacheButton.setSingleLine(true);
        playlistCacheButton.setContentDescription("只缓存当前歌单中尚未缓存的歌曲");
        playlistCacheButton.setOnClickListener(view -> cacheCurrentPlaylistOneClick());
        LinearLayout.LayoutParams cacheButtonParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(44));
        cacheButtonParams.setMargins(0, dp(8), 0, 0);
        panel.addView(playlistCacheButton, cacheButtonParams);
        applyPlaylistFilter();
        updatePlaylistCacheButtonVisibility();
        return panel;
    }

    private void showCurrentPlaylistSortDialog() {
        final String[] options = {"歌名↑", "歌名↓", "歌手↑", "歌手↓"};
        new AlertDialog.Builder(this)
            .setTitle("排序当前歌单")
            .setItems(options, (dialog, which) -> sortCurrentPlaylist(which, options[which]))
            .setNegativeButton("取消", null)
            .show();
    }

    private void sortCurrentPlaylist(int mode, String label) {
        Playlist playlist = currentPlaylist();
        if (playlist.songs.size() < 2) {
            toast("当前歌单无需排序");
            return;
        }
        final boolean byArtist = mode >= 2;
        final boolean descending = mode == 1 || mode == 3;
        final java.text.Collator collator = java.text.Collator.getInstance(java.util.Locale.CHINA);
        collator.setStrength(java.text.Collator.PRIMARY);
        Collections.sort(playlist.songs, new Comparator<Song>() {
            @Override
            public int compare(Song left, Song right) {
                String leftPrimary = playlistSortText(byArtist ? left.artist : left.title);
                String rightPrimary = playlistSortText(byArtist ? right.artist : right.title);
                int result = collator.compare(leftPrimary, rightPrimary);
                if (descending) result = -result;
                if (result != 0) return result;

                String leftSecondary = playlistSortText(byArtist ? left.title : left.artist);
                String rightSecondary = playlistSortText(byArtist ? right.title : right.artist);
                result = collator.compare(leftSecondary, rightSecondary);
                if (result != 0) return result;
                return collator.compare(playlistSortText(left.source), playlistSortText(right.source));
            }
        });

        if (!playingSearchQueue) {
            currentSongIndex = currentSong == null ? -1 : playlist.songs.indexOf(currentSong);
        }
        savePlaylists();
        renderCurrentPlaylist();
        if (playlistSongsList != null) playlistSongsList.setSelection(0);
        toast("当前歌单已按" + label + "排序");
    }

    private String playlistSortText(String value) {
        if (value == null) return "";
        return java.text.Normalizer.normalize(value.trim(), java.text.Normalizer.Form.NFKC)
            .toLowerCase(java.util.Locale.ROOT);
    }

    private void applyPlaylistFilter() {
        playlistFilteredSongs.clear();
        String keyword = playlistSearchInput == null
            ? ""
            : playlistSearchInput.getText().toString().trim();
        for (Song song : currentPlaylist().songs) {
            if (keyword.isEmpty() || song.matches(keyword)) playlistFilteredSongs.add(song);
        }
        if (playlistAdapter != null) playlistAdapter.setSongs(playlistFilteredSongs);
    }

    private void confirmDeletePlaylistSong(Song song) {
        if (song == null) return;
        new AlertDialog.Builder(this)
            .setTitle("删除歌曲")
            .setMessage("确定从当前歌单中删除《" + song.title + "》吗？")
            .setNegativeButton("取消", null)
            .setPositiveButton("\u786e\u5b9a", (dialog, which) -> {
                int actualIndex = currentPlaylist().songs.indexOf(song);
                if (actualIndex < 0) return;
                currentPlaylist().songs.remove(actualIndex);
                if (!playingSearchQueue) {
                    if (currentSongIndex == actualIndex) currentSongIndex = -1;
                    else if (currentSongIndex > actualIndex) currentSongIndex--;
                }
                if (pendingLyricSong == song && !isSongInAnyPlaylist(song)) {
                    clearPendingLyricPreview();
                }
                savePlaylists();
                renderCurrentPlaylist();
                updateLyricActionVisibility(currentSong);
                toast("已从歌单删除：" + song.title + "；缓存已保留，可用扫把清理");
            })
            .show();
    }

    private View buildListsPanel() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.HORIZONTAL);
        panel.setPadding(0, dp(10), 0, 0);

        LinearLayout resultsColumn = buildColumn("\u641c\u7d22\u7ed3\u679c");
        resultAdapter = new SongListAdapter(searchResults);
        ListView resultsList = new ListView(this);
        resultsList.setBackground(rounded(Color.argb(72, 0, 0, 0), dp(20)));
        resultsList.setAdapter(resultAdapter);
        resultsList.setOnItemClickListener((parent, view, position, id) -> playSong(searchResults.get(position)));
        resultsList.setOnItemLongClickListener((parent, view, position, id) -> {
            addSongToCurrentPlaylist(searchResults.get(position));
            return true;
        });
        resultsColumn.addView(resultsList, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1
        ));

        LinearLayout playlistColumn = buildColumn("\u5f53\u524d\u6b4c\u5355");
        playlistAdapter = new SongListAdapter(currentPlaylist().songs);
        ListView playlistList = new ListView(this);
        playlistList.setBackground(rounded(Color.argb(72, 0, 0, 0), dp(20)));
        playlistList.setAdapter(playlistAdapter);
        playlistList.setOnItemClickListener((parent, view, position, id) -> playSongFromPlaylist(position));
        playlistList.setOnItemLongClickListener((parent, view, position, id) -> {
            Song removed = currentPlaylist().songs.remove(position);
            savePlaylists();
            renderCurrentPlaylist();
            toast("\u5df2\u5220\u9664\uff1a" + removed.title + "；缓存已保留，可用扫把清理");
            return true;
        });
        playlistColumn.addView(playlistList, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1
        ));

        panel.addView(resultsColumn, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1));
        panel.addView(playlistColumn, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1));
        return panel;
    }

    private LinearLayout buildColumn(String title) {
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setPadding(dp(4), 0, dp(4), 0);
        TextView label = new TextView(this);
        label.setText(title);
        label.setTextSize(16);
        label.setTypeface(Typeface.DEFAULT_BOLD);
        label.setTextColor(TEXT_MAIN);
        label.setGravity(Gravity.CENTER);
        column.addView(label);
        return column;
    }

    private final class SongListAdapter extends BaseAdapter {
        private List<Song> songs;

        SongListAdapter(List<Song> songs) {
            this.songs = songs;
        }

        void setSongs(List<Song> songs) {
            this.songs = songs;
            notifyDataSetChanged();
        }

        @Override
        public int getCount() {
            return songs == null ? 0 : songs.size();
        }

        @Override
        public Song getItem(int position) {
            return songs.get(position);
        }

        @Override
        public long getItemId(int position) {
            return position;
        }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            LinearLayout row = convertView instanceof LinearLayout ? (LinearLayout) convertView : null;
            if (row == null) {
                row = new LinearLayout(MainActivity.this);
                row.setOrientation(LinearLayout.HORIZONTAL);
                row.setGravity(Gravity.CENTER_VERTICAL);
                row.setPadding(dp(10), dp(9), dp(10), dp(9));
                row.addView(makeCell(0.42f, true));
                row.addView(makeCell(0.38f, false));
                row.addView(makeCell(0.20f, false));
            }
            Song song = getItem(position);
            ((TextView) row.getChildAt(0)).setText(song.title);
            ((TextView) row.getChildAt(1)).setText(song.artist);
            ((TextView) row.getChildAt(2)).setText(song.source);
            int color = song.unavailable ? Color.rgb(255, 96, 96) : TEXT_MAIN;
            for (int i = 0; i < row.getChildCount(); i++) {
                ((TextView) row.getChildAt(i)).setTextColor(color);
            }
            return row;
        }

        private TextView makeCell(float weight, boolean bold) {
            TextView cell = new TextView(MainActivity.this);
            cell.setSingleLine(true);
            cell.setEllipsize(TextUtils.TruncateAt.END);
            cell.setTextColor(TEXT_MAIN);
            cell.setTextSize(14);
            if (bold) cell.setTypeface(Typeface.DEFAULT_BOLD);
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, weight);
            params.setMargins(dp(4), 0, dp(4), 0);
            cell.setLayoutParams(params);
            return cell;
        }
    }

    private LinearLayout buildPlaylistManagerPanel() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(10), dp(10), dp(10), dp(10));
        panel.setBackground(rounded(Color.argb(54, 255, 255, 255), dp(18)));

        TextView label = new TextView(this);
        label.setText("歌单管理");
        label.setTextSize(17);
        label.setTypeface(Typeface.DEFAULT_BOLD);
        label.setTextColor(TEXT_MAIN);
        panel.addView(label);

        playlistSpinner = new Spinner(this);
        playlistSpinner.setVisibility(View.GONE);
        playlistSpinnerAdapter = new ArrayAdapter<>(this,
            android.R.layout.simple_spinner_dropdown_item, new ArrayList<>());
        playlistSpinner.setAdapter(playlistSpinnerAdapter);
        playlistSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                if (position >= 0 && position < playlists.size() && position != currentPlaylistIndex) {
                    currentPlaylistIndex = position;
                    savePlaylists();
                    renderCurrentPlaylist();
                }
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
            }
        });
        panel.addView(playlistSpinner, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 1));

        playlistManagerAdapter = new ArrayAdapter<String>(this,
            android.R.layout.simple_list_item_1, new ArrayList<>()) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                View view = super.getView(position, convertView, parent);
                TextView item = view.findViewById(android.R.id.text1);
                if (item != null) {
                    item.setTextColor(TEXT_MAIN);
                    item.setTextSize(14);
                    item.setSingleLine(true);
                    item.setEllipsize(TextUtils.TruncateAt.END);
                }
                view.setBackgroundColor(position == currentPlaylistIndex
                    ? Color.argb(74, 255, 78, 92) : Color.TRANSPARENT);
                return view;
            }
        };
        playlistManagerList = new ListView(this);
        playlistManagerList.setAdapter(playlistManagerAdapter);
        playlistManagerList.setBackground(rounded(Color.argb(58, 0, 0, 0), dp(14)));
        playlistManagerList.setOnItemClickListener((parent, view, position, id) -> {
            if (position >= 0 && position < playlists.size()) {
                currentPlaylistIndex = position;
                savePlaylists();
                renderCurrentPlaylist();
                showPlaylistPage();
            }
        });
        panel.addView(playlistManagerList, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(158)));

        LinearLayout firstRow = new LinearLayout(this);
        firstRow.setOrientation(LinearLayout.HORIZONTAL);
        firstRow.addView(makeSmallButton("新建", view -> promptNewPlaylist()),
            new LinearLayout.LayoutParams(0, dp(38), 1));
        firstRow.addView(makeSmallButton("改名", view -> promptRenamePlaylist()),
            new LinearLayout.LayoutParams(0, dp(38), 1));
        firstRow.addView(makeSmallButton("删除", view -> deleteCurrentPlaylist()),
            new LinearLayout.LayoutParams(0, dp(38), 1));
        panel.addView(firstRow);

        LinearLayout secondRow = new LinearLayout(this);
        secondRow.setOrientation(LinearLayout.HORIZONTAL);
        secondRow.addView(makeSmallButton("合并", view -> mergePlaylistsIntoCurrent()),
            new LinearLayout.LayoutParams(0, dp(38), 1));
        secondRow.addView(makeSmallButton("清空", view -> clearCurrentPlaylist()),
            new LinearLayout.LayoutParams(0, dp(38), 1));
        secondRow.addView(makeSmallButton("导出", view -> exportCurrentPlaylistCsv()),
            new LinearLayout.LayoutParams(0, dp(38), 1));
        panel.addView(secondRow);
        return panel;
    }

    private Button makeSmallButton(String text, View.OnClickListener listener) {
        Button button = makeButton(text, false);
        button.setTextSize(13);
        button.setOnClickListener(listener);
        return button;
    }

    private Button makeButton(String text, boolean primary) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        button.setTextColor(Color.WHITE);
        button.setBackground(rounded(primary ? ACCENT : Color.argb(78, 255, 255, 255), dp(22)));
        attachSubtlePressFeedback(button);
        return button;
    }

    private Button makeRoundButton(String text, boolean primary) {
        Button button = makeButton(text, primary);
        button.setTextColor(Color.WHITE);
        button.setBackground(rounded(primary ? ACCENT : Color.argb(88, 255, 255, 255), dp(999)));
        return button;
    }

    private GradientDrawable rounded(int color, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color);
        drawable.setCornerRadius(radius);
        return drawable;
    }

    private void toggleDrawer() {
        if (drawerPanel == null) return;
        boolean opening = drawerPanel.getVisibility() != View.VISIBLE;
        drawerPanel.setVisibility(opening ? View.VISIBLE : View.GONE);
        getWindow().setStatusBarColor(opening ? Color.rgb(22, 24, 34) : normalStatusBarColor);
        if (drawerDismissView != null) {
            drawerDismissView.setVisibility(opening ? View.VISIBLE : View.GONE);
        }
    }

    private void openPlaylistTools() {
        showPlaylistPage();
    }

    private void toggleSearchPanel() {
        showSearchPage();
    }

    private void showPlayerPage() {
        if (headerBar != null) headerBar.setVisibility(View.VISIBLE);
        if (statusView != null) statusView.setVisibility(View.VISIBLE);
        if (playerPanel != null) playerPanel.setVisibility(View.VISIBLE);
        if (searchPanel != null) searchPanel.setVisibility(View.GONE);
        if (playlistPanel != null) playlistPanel.setVisibility(View.GONE);
    }

    private void showSearchPage() {
        if (headerBar != null) headerBar.setVisibility(View.GONE);
        if (statusView != null) statusView.setVisibility(View.GONE);
        if (playerPanel != null) playerPanel.setVisibility(View.GONE);
        if (searchPanel != null) searchPanel.setVisibility(View.VISIBLE);
        if (playlistPanel != null) playlistPanel.setVisibility(View.GONE);
        if (searchInput != null) searchInput.requestFocus();
    }

    private void showPlaylistPage() {
        if (headerBar != null) headerBar.setVisibility(View.GONE);
        if (statusView != null) statusView.setVisibility(View.GONE);
        if (playerPanel != null) playerPanel.setVisibility(View.GONE);
        if (searchPanel != null) searchPanel.setVisibility(View.GONE);
        if (playlistPanel != null) playlistPanel.setVisibility(View.VISIBLE);
    }

    private void performSearch() {
        hideKeyboardAndClearFocus(searchInput);
        String keyword = searchInput.getText().toString().trim();
        if (keyword.isEmpty()) {
            toast("请输入歌曲名或歌手");
            return;
        }
        String mode = String.valueOf(sourceSpinner.getSelectedItem());
        activeSearchKeyword = keyword;
        activeSearchSession = null;
        searchPageLoading = false;
        searchNearBottom = false;
        searchResults.clear();
        if (searchLoadMoreView != null) {
            searchLoadMoreView.setVisibility(View.VISIBLE);
            searchLoadMoreView.setText("正在建立首批歌曲目录...");
        }

        if (mode.contains("本地")) {
            appendLocalSearch(keyword);
            sortByKeyword(searchResults, keyword);
            renderResults();
            searchPageStatusView.setText("本地搜索完成：" + searchResults.size() + " 首");
            if (searchLoadMoreView != null) searchLoadMoreView.setVisibility(View.GONE);
            return;
        }

        renderResults();
        activeSearchSession = CatalogSearch.newSession(keyword, mode);
        searchPageStatusView.setText(mode + "：正在加载首批歌曲目录...");
        loadNextSearchBatch(true);
    }

    private void loadNextSearchBatch(boolean firstBatch) {
        CatalogSearch.Session session = activeSearchSession;
        if (session == null || searchPageLoading || session.isLoading() || !session.hasMore()) {
            if (session != null && !session.hasMore() && searchLoadMoreView != null) {
                searchLoadMoreView.setText("当前搜索模式已加载完");
                searchLoadMoreView.setEnabled(false);
            }
            return;
        }
        searchPageLoading = true;
        if (searchLoadMoreView != null) {
            searchLoadMoreView.setEnabled(false);
            searchLoadMoreView.setText(firstBatch ? "正在搜索首批平台..." : "正在搜索下一批未搜索平台...");
        }
        if (!firstBatch) searchPageStatusView.setText("正在加载下一批未搜索平台或目录结果...");
        new Thread(() -> {
            CatalogSearch.Batch batch = session.loadNext();
            List<Song> rows = new ArrayList<>();
            for (CatalogSearch.Track track : batch.tracks) rows.add(Song.fromCatalog(track));
            runOnUiThread(() -> {
                if (session != activeSearchSession) return;
                appendUnique(searchResults, rows);
                renderResults();
                searchPageLoading = false;
                String platformText = batch.attemptedSources.isEmpty()
                    ? ""
                    : "，新搜索平台 " + batch.attemptedSources.size() + " 个";
                boolean hasMore = batch.hasMore;
                searchPageStatusView.setText(
                    "已建立目录 " + searchResults.size() + " 首" + platformText
                        + (hasMore ? "；继续向下滚动或点击底部加载" : "；当前模式已加载完")
                );
                if (searchLoadMoreView != null) {
                    searchLoadMoreView.setEnabled(hasMore);
                    searchLoadMoreView.setVisibility(View.VISIBLE);
                    searchLoadMoreView.setText(hasMore
                        ? "继续加载下一批未搜索平台"
                        : "当前搜索模式已加载完");
                }
            });
        }).start();
    }

    private void appendLocalSearch(String keyword) {
        for (Playlist playlist : playlists) {
            for (Song song : playlist.songs) {
                if (song.matches(keyword)) {
                    searchResults.add(song);
                }
            }
        }
    }

    private List<Song> searchOnline(String keyword, String source) {
        List<Song> rows = new ArrayList<>();
        if (source.contains("\u672c\u5730")) return rows;
        boolean quick = source.contains("\u5feb\u901f") || source.contains("\u5168\u90e8") || source.contains("\u66f4\u591a");
        if (source.contains("\u7f51\u6613") || quick) rows.addAll(searchNetease(keyword));
        if (source.contains("\u9177\u72d7") || quick) rows.addAll(searchKugou(keyword));
        if (source.contains("\u9177\u6211") || quick) rows.addAll(searchKuwo(keyword));
        if (source.contains("\u6c7d\u6c34")) {
            rows.add(new Song(keyword, "\u6c7d\u6c34\u76f4\u63a5\u63a5\u53e3\u5f85\u9a8c\u8bc1", "\u6c7d\u6c34", ""));
        }
        sortByKeyword(rows, keyword);
        return rows;
    }

    private List<Song> searchNetease(String keyword) {
        List<Song> rows = new ArrayList<>();
        try {
            String url = "https://music.163.com/api/search/get/web?s="
                + URLEncoder.encode(keyword, "UTF-8") + "&type=1&limit=20&offset=0";
            JSONObject payload = httpJson(url, "https://music.163.com/");
            JSONArray songs = payload.optJSONObject("result") == null
                ? null
                : payload.optJSONObject("result").optJSONArray("songs");
            if (songs == null) return rows;
            for (int i = 0; i < songs.length(); i++) {
                JSONObject item = songs.optJSONObject(i);
                if (item == null) continue;
                String title = item.optString("name", keyword);
                String artist = artistsFromNetease(item.optJSONArray("artists"));
                String id = item.optString("id", "");
                String playUrl = id.isEmpty() ? "" : "https://music.163.com/song/media/outer/url?id=" + id + ".mp3";
                rows.add(new Song(title, artist, "\u7f51\u6613\u4e91", "", playUrl));
            }
        } catch (Exception ignored) {
        }
        return rows;
    }

    private String artistsFromNetease(JSONArray artists) {
        if (artists == null) return "\u672a\u77e5\u6b4c\u624b";
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < artists.length(); i++) {
            JSONObject artist = artists.optJSONObject(i);
            if (artist == null) continue;
            if (builder.length() > 0) builder.append(" / ");
            builder.append(artist.optString("name"));
        }
        return builder.length() == 0 ? "\u672a\u77e5\u6b4c\u624b" : builder.toString();
    }

    private List<Song> searchKugou(String keyword) {
        List<Song> rows = new ArrayList<>();
        try {
            String url = "https://songsearch.kugou.com/song_search_v2?format=json&page=1&pagesize=20&keyword="
                + URLEncoder.encode(keyword, "UTF-8");
            JSONObject payload = httpJson(url, "https://www.kugou.com/");
            JSONObject data = payload.optJSONObject("data");
            JSONArray songs = data == null ? null : data.optJSONArray("lists");
            if (songs == null) return rows;
            for (int i = 0; i < songs.length(); i++) {
                JSONObject item = songs.optJSONObject(i);
                if (item == null) continue;
                rows.add(new Song(
                    item.optString("SongName", keyword),
                    item.optString("SingerName", "\u672a\u77e5\u6b4c\u624b"),
                    "\u9177\u72d7",
                    ""
                ));
            }
        } catch (Exception ignored) {
        }
        return rows;
    }

    private List<Song> searchKuwo(String keyword) {
        List<Song> rows = new ArrayList<>();
        try {
            String url = "http://search.kuwo.cn/r.s?all="
                + URLEncoder.encode(keyword, "UTF-8")
                + "&ft=music&itemset=web_2013&client=kt&pn=0&rn=20&rformat=json&encoding=utf8";
            JSONObject payload = httpJson(url, "http://www.kuwo.cn/");
            JSONArray songs = payload.optJSONArray("abslist");
            if (songs == null) return rows;
            for (int i = 0; i < songs.length(); i++) {
                JSONObject item = songs.optJSONObject(i);
                if (item == null) continue;
                rows.add(new Song(
                    cleanHtml(item.optString("SONGNAME", keyword)),
                    cleanHtml(item.optString("ARTIST", "\u672a\u77e5\u6b4c\u624b")),
                    "\u9177\u6211",
                    "",
                    kuwoPlayUrl(item)
                ));
            }
        } catch (Exception ignored) {
        }
        return rows;
    }

    private String kuwoPlayUrl(JSONObject item) {
        String rid = item.optString("MUSICRID", "");
        if (rid.isEmpty()) {
            String id = item.optString("DC_TARGETID", "");
            if (!id.isEmpty()) rid = "MUSIC_" + id;
        }
        if (rid.isEmpty()) return "";
        return "http://antiserver.kuwo.cn/anti.s?type=convert_url&format=mp3&response=url&rid=" + rid;
    }

    private String cleanHtml(String value) {
        if (value == null) return "";
        return value.replaceAll("<[^>]+>", "").replace("&nbsp;", " ").trim();
    }

    private JSONObject httpJson(String urlText, String referer) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(urlText).openConnection();
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(8000);
        connection.setRequestProperty("User-Agent", "Mozilla/5.0");
        connection.setRequestProperty("Referer", referer);
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream(), "UTF-8"))) {
            StringBuilder builder = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) builder.append(line);
            return new JSONObject(builder.toString());
        } finally {
            connection.disconnect();
        }
    }

    private void appendUnique(List<Song> target, List<Song> incoming) {
        Set<String> seen = new HashSet<>();
        for (Song song : target) seen.add(song.key());
        for (Song song : incoming) {
            if (seen.add(song.key())) target.add(song);
        }
    }

    private void sortByKeyword(List<Song> rows, String keyword) {
        final String normalized = normalize(keyword);
        Collections.sort(rows, new Comparator<Song>() {
            @Override
            public int compare(Song left, Song right) {
                return score(right, normalized) - score(left, normalized);
            }
        });
    }

    private int score(Song song, String keyword) {
        String title = normalize(song.title);
        String artist = normalize(song.artist);
        if (title.equals(keyword)) return 1000;
        if (title.contains(keyword)) return 800 - Math.abs(title.length() - keyword.length());
        if (keyword.contains(title) && title.length() > 1) return 620 + title.length();
        if (artist.contains(keyword)) return 320;
        return 0;
    }

    private String normalize(String value) {
        if (value == null) return "";
        return value.toLowerCase()
            .replace(" ", "")
            .replace("\uff08", "(")
            .replace("\uff09", ")")
            .replace("\u300a", "")
            .replace("\u300b", "")
            .trim();
    }

    private void addSongToCurrentPlaylist(Song song) {
        if (song == null) return;
        if (song == currentSong && song.isNetworkCatalog()) {
            new Thread(() -> {
                String existingUri = song.cachedUri == null ? "" : song.cachedUri;
                if (!NetworkMediaCache.cachedAudioExists(this, existingUri)) {
                    String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
                    existingUri = key.isEmpty() ? "" : CacheStorage.findAudioUri(this, key);
                }
                final String verifiedUri = NetworkMediaCache.cachedAudioExists(this, existingUri)
                    ? existingUri : "";
                runOnUiThread(() -> {
                    if (verifiedUri.isEmpty()) {
                        toast("歌曲还在缓存，完成后再加入歌单");
                        return;
                    }
                    song.cachedUri = verifiedUri;
                    song.uri = verifiedUri;
                    addSongToCurrentPlaylistReady(song);
                });
            }, "playlist-add-cache-check").start();
            return;
        }
        addSongToCurrentPlaylistReady(song);
    }

    private void addSongToCurrentPlaylistReady(Song song) {
        Playlist playlist = isLocalSong(song) ? localPlaylist() : onlineTargetPlaylist();
        int existingIndex = indexOfSong(playlist, song);
        if (existingIndex >= 0) {
            if (currentSong == song) switchPlaybackToPlaylist(playlist, existingIndex);
            toast((isLocalPlaylist(playlist) ? "\u672c\u5730\u6b4c\u5355\u5df2\u6709\uff1a" : "\u5f53\u524d\u5728\u7ebf\u6b4c\u5355\u5df2\u6709\uff1a") + song.title);
            return;
        }
        Song playlistSong = copySongForPlaylist(song);
        playlist.songs.add(playlistSong);
        int addedIndex = playlist.songs.size() - 1;
        playlistSong.unavailable = false;
        playlistSong.cacheFailed = false;
        savePlaylists();
        renderCurrentPlaylist();
        if (currentSong == song) {
            switchPlaybackToPlaylist(playlist, addedIndex);
            updateLyricActionVisibility(currentSong);
        }
        toast("\u5df2\u52a0\u5165" + playlist.name + "\uff1a" + song.title);
    }

    private Song copySongForPlaylist(Song song) {
        Song copy = new Song(song.title, song.artist, song.source, song.lyric,
            song.uri, song.catalogJson, song.cachedUri);
        copy.lyricLabel = song.lyricLabel;
        copy.unavailable = false;
        copy.autoUnavailable = false;
        copy.manualUnavailable = false;
        copy.manualAttempt = false;
        copy.cacheFailed = false;
        if (copy.isNetworkCatalog()) {
            if ((copy.cachedUri == null || copy.cachedUri.isEmpty())
                && copy.uri != null
                && (copy.uri.startsWith("file:") || copy.uri.startsWith("content:"))) {
                copy.cachedUri = copy.uri;
            }
            if (copy.cachedUri != null && !copy.cachedUri.isEmpty()) {
                copy.uri = copy.cachedUri;
            }
        }
        return copy;
    }

    private int indexOfSong(Playlist playlist, Song song) {
        if (playlist == null || song == null) return -1;
        String key = song.key();
        for (int i = 0; i < playlist.songs.size(); i++) {
            Song item = playlist.songs.get(i);
            if (item == song || item.key().equals(key)) return i;
        }
        return -1;
    }

    private void switchPlaybackToPlaylist(Playlist playlist, int songIndex) {
        if (playlist == null || songIndex < 0 || songIndex >= playlist.songs.size()) return;
        int playlistIndex = playlists.indexOf(playlist);
        if (playlistIndex < 0) return;
        currentPlaylistIndex = playlistIndex;
        currentSongIndex = songIndex;
        playingSearchQueue = false;
        searchSongIndex = -1;
        renderCurrentPlaylist();
        updateLyricActionVisibility(currentSong);
        saveLastSong(0);
    }

    private void renderResults() {
        if (resultAdapter != null) resultAdapter.setSongs(searchResults);
    }

    private void renderPlaylists() {
        if (playlistSpinnerAdapter == null) return;
        playlistSpinnerAdapter.clear();
        if (playlistManagerAdapter != null) playlistManagerAdapter.clear();
        for (Playlist playlist : playlists) {
            String label = (playlists.indexOf(playlist) == 0 ? "[本地] " : "[在线] ") + playlist.name + " \u00b7 " + playlist.songs.size() + "\u9996";
            playlistSpinnerAdapter.add(label);
            if (playlistManagerAdapter != null) playlistManagerAdapter.add(label);
        }
        playlistSpinnerAdapter.notifyDataSetChanged();
        if (playlistManagerAdapter != null) playlistManagerAdapter.notifyDataSetChanged();
        if (!playlists.isEmpty() && playlistSpinner != null) playlistSpinner.setSelection(currentPlaylistIndex);
        updateCurrentPlaylistButton();
    }

    private void updateCurrentPlaylistButton() {
        if (currentPlaylistButton == null) return;
        String rawName = currentPlaylist().name;
        final String name = rawName == null || rawName.trim().isEmpty()
            ? "\u5f53\u524d\u6b4c\u5355" : rawName.trim();

        currentPlaylistButton.setSelected(false);
        currentPlaylistButton.setHorizontallyScrolling(false);
        currentPlaylistButton.setGravity(Gravity.CENTER);
        currentPlaylistButton.setEllipsize(TextUtils.TruncateAt.END);
        currentPlaylistButton.setText(name);

        currentPlaylistButton.post(() -> {
            if (currentPlaylistButton == null) return;
            String currentRawName = currentPlaylist().name;
            String currentName = currentRawName == null || currentRawName.trim().isEmpty()
                ? "\u5f53\u524d\u6b4c\u5355" : currentRawName.trim();
            if (!name.equals(currentName)) return;

            int availableWidth = currentPlaylistButton.getWidth()
                - currentPlaylistButton.getCompoundPaddingLeft()
                - currentPlaylistButton.getCompoundPaddingRight();
            boolean overflow = availableWidth > 0
                && currentPlaylistButton.getPaint().measureText(name) > availableWidth;

            currentPlaylistButton.setSelected(false);
            currentPlaylistButton.setHorizontallyScrolling(overflow);
            currentPlaylistButton.setEllipsize(
                overflow ? TextUtils.TruncateAt.MARQUEE : TextUtils.TruncateAt.END);
            currentPlaylistButton.setMarqueeRepeatLimit(overflow ? -1 : 0);
            currentPlaylistButton.setGravity(
                overflow ? Gravity.CENTER_VERTICAL | Gravity.START : Gravity.CENTER);
            currentPlaylistButton.setText(overflow ? name + "\u3000\u3000" : name);
            currentPlaylistButton.setSelected(overflow);
        });
    }

    private void renderCurrentPlaylist() {
        applyPlaylistFilter();
        renderPlaylists();
        updatePlaylistCacheButtonVisibility();
        if (statusView != null) {
            statusView.setText("当前歌单：" + currentPlaylist().name
                + "，共 " + currentPlaylist().songs.size() + " 首");
        }
    }

    private void updatePlaylistCacheButtonVisibility() {
        if (playlistCacheButton == null) return;
        if (playlistCacheRunning) {
            playlistCacheButton.setVisibility(View.VISIBLE);
            playlistCacheButton.setEnabled(false);
            playlistCacheButton.setText("正在缓存当前歌单…");
            return;
        }

        final Playlist playlistSnapshot = currentPlaylist();
        final int playlistIndexSnapshot = currentPlaylistIndex;
        final List<Song> songSnapshot = playlistSnapshot == null
            ? new ArrayList<>() : new ArrayList<>(playlistSnapshot.songs);
        final int requestSerial = ++playlistCacheScanSerial;

        playlistCacheButton.setVisibility(View.VISIBLE);
        playlistCacheButton.setEnabled(false);
        playlistCacheButton.setText("正在检查缓存状态…");
        try {
            playlistCacheScanExecutor.execute(() -> {
                final int missing = uncachedNetworkSongs(songSnapshot).size();
                runOnUiThread(() -> {
                    if (playlistCacheButton == null || requestSerial != playlistCacheScanSerial) return;
                    if (playlistSnapshot != currentPlaylist()
                        || playlistIndexSnapshot != currentPlaylistIndex) {
                        updatePlaylistCacheButtonVisibility();
                        return;
                    }
                    playlistCacheButton.setEnabled(true);
                    playlistCacheButton.setVisibility(missing > 0 ? View.VISIBLE : View.GONE);
                    playlistCacheButton.setText("一键缓存未缓存歌曲（" + missing + "）");
                });
            });
        } catch (RuntimeException ignored) {
            playlistCacheButton.setEnabled(true);
        }
    }

    private List<Song> uncachedNetworkSongs(Playlist playlist) {
        if (playlist == null) return new ArrayList<>();
        return uncachedNetworkSongs(new ArrayList<>(playlist.songs));
    }

    private List<Song> uncachedNetworkSongs(List<Song> songs) {
        List<Song> result = new ArrayList<>();
        if (songs == null) return result;
        for (Song song : songs) {
            if (song == null || !song.isNetworkCatalog()) continue;
            if (songHasRecordedCache(song)) continue;
            result.add(song);
        }
        return result;
    }

    /**
     * Fast playlist-cache classification used by the cache button and batch worker.
     * It deliberately does not query the Storage Access Framework provider. Some
     * Android 16 document providers can block a directory query for many seconds;
     * playback already clears an unusable recorded URI through its normal failure
     * callback, while one-click cache only needs a non-blocking target list.
     */
    private boolean songHasRecordedCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return true;
        String cached = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (!cached.isEmpty()) return true;
        String direct = song.uri == null ? "" : song.uri.trim();
        return direct.startsWith("file:") || direct.startsWith("content:");
    }

    private boolean songHasPlayableCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return true;
        if (NetworkMediaCache.cachedAudioExists(this, song.cachedUri)) return true;
        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        String existingUri = key.isEmpty() ? "" : CacheStorage.findAudioUri(this, key);
        if (NetworkMediaCache.cachedAudioExists(this, existingUri)) {
            song.cachedUri = existingUri;
            song.uri = existingUri;
            song.cacheFailed = false;
            return true;
        }
        return false;
    }

    private void renderEmptyPlayer() {
        titleView.setText("还没有选择歌曲");
        artistView.setText("");
        lyricView.setText("");
        lyricLines.clear();
        highlightedLyricIndex = -1;
        clearPendingLyricPreview();
        if (addCurrentButton != null) addCurrentButton.setVisibility(View.GONE);
        if (songVersionButton != null) songVersionButton.setVisibility(View.GONE);
        if (lyricVersionButton != null) lyricVersionButton.setVisibility(View.GONE);
        if (playButton != null) playButton.setText("▶");
        resetPlaybackProgress();
    }

    private void showSongLyrics(Song song) {
        lyricLines.clear();
        highlightedLyricIndex = -1;
        updateLyricActionVisibility(song);
        if (song == null) {
            lyricView.setText("");
            return;
        }
        hydrateLyricFromCache(song);
        if (pendingLyricSong == song && pendingLyric != null && !pendingLyric.trim().isEmpty()) {
            applyLyricText(pendingLyric);
            if (confirmLyricButton != null) {
                confirmLyricButton.setVisibility(View.VISIBLE);
                confirmLyricButton.bringToFront();
            }
            return;
        }
        if (song.lyric != null && !song.lyric.trim().isEmpty()) {
            applyLyricText(song.lyric);
            return;
        }

        lyricView.setText("正在匹配歌词...");
        String matchKey = "current|" + song.key();
        if (!lyricMatchingSongs.add(matchKey)) return;
        final boolean bindToPlaylist = isSongInAnyPlaylist(song);
        android.util.Log.i("BabywifeLyrics", "match start key=" + song.key());
        PlaylistLyricMatcher.matchAsync(song.title, song.artist, song.catalogJson,
            new PlaylistLyricMatcher.Callback() {
                @Override
                public void onMatched(String lyric, String label) {
                    runOnUiThread(() -> {
                        lyricMatchingSongs.remove(matchKey);
                        if (currentSong != song) return;
                        String safeLyric = lyric == null ? "" : lyric.trim();
                        if (safeLyric.isEmpty()) {
                            lyricView.setText("暂未找到匹配歌词");
                            return;
                        }
                        String safeLabel = label == null ? "" : label;
                        if (bindToPlaylist) {
                            bindLyricToPlaylistCopies(song, safeLyric, safeLabel);
                            savePlaylists();
                        } else {
                            song.lyric = safeLyric;
                            song.lyricLabel = safeLabel;
                        }
                        applyLyricText(safeLyric);
                        if (statusView != null) statusView.setText("已匹配歌词：" + safeLabel);
                        android.util.Log.i("BabywifeLyrics", "match success key=" + song.key()
                            + " chars=" + safeLyric.length());
                    });
                }

                @Override
                public void onUnavailable() {
                    runOnUiThread(() -> {
                        lyricMatchingSongs.remove(matchKey);
                        if (currentSong == song && (song.lyric == null || song.lyric.trim().isEmpty())) {
                            lyricView.setText("暂未找到匹配歌词，可使用右上角替换歌词");
                        }
                        android.util.Log.w("BabywifeLyrics", "match unavailable key=" + song.key());
                    });
                }
            });
    }




    private LinearLayout.LayoutParams bottomSettingParams(int heightDp, int topMarginDp) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(heightDp));
        params.setMargins(0, dp(topMarginDp), 0, 0);
        return params;
    }

    private void showSongVersionPicker() {
        Song song = currentSong;
        if (song == null) {
            toast("请先选择歌曲");
            return;
        }
        if (!isSongInAnyPlaylist(song)) {
            toast("替换歌曲只对歌单内歌曲生效");
            return;
        }
        SongVersionPicker.show(this, song.title, song.artist, new SongVersionPicker.Callback() {
            @Override
            public void onStatus(String message) {
                runOnUiThread(() -> {
                    if (currentSong == song && statusView != null) statusView.setText(message);
                });
            }

            @Override
            public void onPreview(String title, String artist, String sourceLabel, String catalogJson) {
                runOnUiThread(() -> {
                    if (currentSong != song || catalogJson == null || catalogJson.trim().isEmpty()) return;
                    clearPendingLyricPreview();
                    pendingSongTarget = song;
                    pendingSongOriginalKey = song.key();
                    pendingSongTitle = title == null ? song.title : title;
                    pendingSongArtist = artist == null ? song.artist : artist;
                    pendingSongSource = sourceLabel == null ? song.source : sourceLabel;
                    pendingSongCatalogJson = catalogJson;
                    pendingReplacementType = REPLACEMENT_SONG;
                    titleView.setText(pendingSongTitle);
                    artistView.setText(pendingSongArtist + " · " + pendingSongSource);
                    if (confirmLyricButton != null) {
                        confirmLyricButton.setText("确认替换歌曲");
                        confirmLyricButton.setVisibility(View.VISIBLE);
                        confirmLyricButton.bringToFront();
                    }
                    statusView.setText("正在预览替换版本；点击右下角确认后才会写入歌单");
                });
            }

            @Override
            public void onUnavailable() {
                runOnUiThread(() -> {
                    if (currentSong != song) return;
                    song.manualUnavailable = true;
                    markSongUnavailable(song, song.autoUnavailable && song.manualUnavailable);
                    savePlaylists();
                    renderCurrentPlaylist();
                    statusView.setText("手动搜索全部来源后仍未找到相近版本");
                });
            }
        });
    }

    private void confirmPendingReplacement() {
        if (pendingReplacementType == REPLACEMENT_SONG) {
            confirmPendingSong();
        } else if (pendingReplacementType == REPLACEMENT_LYRIC) {
            confirmPendingLyric();
        }
    }

    private void confirmPendingSong() {
        Song target = pendingSongTarget;
        if (target == null || pendingSongCatalogJson == null || pendingSongCatalogJson.trim().isEmpty()) return;
        if (currentSong != target || !isSongInAnyPlaylist(target)) {
            clearPendingLyricPreview();
            toast("当前歌曲已不在歌单中");
            return;
        }
        String originalKey = pendingSongOriginalKey;
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == target || item.key().equals(originalKey)) {
                    item.title = pendingSongTitle;
                    item.artist = pendingSongArtist;
                    item.source = pendingSongSource;
                    item.catalogJson = pendingSongCatalogJson;
                    item.uri = "";
                    item.cachedUri = "";
                    item.lyric = "";
                    item.lyricLabel = "";
                    item.manualAttempt = true;
                    item.manualUnavailable = false;
                    item.unavailable = false;
                    item.cacheFailed = false;
                }
            }
        }
        target.title = pendingSongTitle;
        target.artist = pendingSongArtist;
        target.source = pendingSongSource;
        target.catalogJson = pendingSongCatalogJson;
        target.uri = "";
        target.cachedUri = "";
        target.lyric = "";
        target.lyricLabel = "";
        target.manualAttempt = true;
        target.manualUnavailable = false;
        target.unavailable = false;
        target.cacheFailed = false;
        clearPendingLyricPreview();
        savePlaylists();
        renderCurrentPlaylist();
        titleView.setText(target.title);
        artistView.setText(target.artist + " · " + target.source);
        statusView.setText("歌曲版本已替换，正在按新版本缓存播放");
        toast("已替换歌单中的歌曲版本");
        playSong(target);
    }

    private void persistResolvedCatalogToPlaylistCopies(Song song, String originalKey) {
        if (song == null || originalKey == null || originalKey.isEmpty()) return;
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == song || item.key().equals(originalKey)) {
                    item.source = song.source;
                    item.catalogJson = song.catalogJson;
                    item.cachedUri = song.cachedUri;
                    item.uri = song.uri;
                }
            }
        }
    }

    private void commitResolvedPlayback(Song song, PendingPlaybackCommit commit, int playToken) {
        if (song == null || commit == null || currentSong != song || playToken != playbackRequestSerial) return;
        if (commit.catalogJson != null && !commit.catalogJson.trim().isEmpty()) {
            song.catalogJson = commit.catalogJson;
        }
        if (commit.sourceLabel != null && !commit.sourceLabel.trim().isEmpty()) {
            song.source = commit.sourceLabel;
        }
        song.cachedUri = commit.audioUri;
        song.uri = commit.audioUri;
        if ((song.lyric == null || song.lyric.trim().isEmpty())
            && commit.lyric != null && !commit.lyric.trim().isEmpty()) {
            song.lyric = commit.lyric;
            song.lyricLabel = song.title + " · " + song.artist + " · " + song.source;
        }
        if (isSongInAnyPlaylist(song) && commit.lyric != null && !commit.lyric.trim().isEmpty()) {
            bindLyricToPlaylistCopies(song, commit.lyric, song.title + " · " + song.artist + " · " + song.source);
        }
        persistResolvedCatalogToPlaylistCopies(song, commit.originalKey);
        song.autoUnavailable = false;
        song.manualUnavailable = false;
        song.manualAttempt = false;
        song.cacheFailed = false;
        markSongUnavailable(song, false);
        artistView.setText(song.artist + " · " + song.source);
        if (commit.sourceChanged) {
            toast("原来源不可用，已确认并记住" + song.source + "版本");
            renderResults();
        }
        if (isSongInAnyPlaylist(song)) {
            savePlaylists();
            renderCurrentPlaylist();
        }
    }

    private void markPlaybackFailure(Song song, boolean afterCacheResolved) {
        if (song == null || !isSongInAnyPlaylist(song)) return;
        if (song.manualAttempt) {
            song.manualUnavailable = true;
            song.manualAttempt = false;
        } else {
            song.autoUnavailable = true;
        }
        markSongUnavailable(song, song.autoUnavailable && song.manualUnavailable);
        savePlaylists();
        renderCurrentPlaylist();
        if (afterCacheResolved) {
            toast("该来源缓存成功但无法播放，未写入替换来源");
        }
    }

    private void showLyricVersionPicker() {
        Song song = currentSong;
        if (song == null) {
            toast("请先选择歌曲");
            return;
        }
        if (!isSongInAnyPlaylist(song)) {
            toast("替换歌词只对歌单内歌曲生效");
            return;
        }
        LyricVersionPicker.show(this, song.title, song.artist, new LyricVersionPicker.Callback() {
            @Override
            public void onStatus(String message) {
                runOnUiThread(() -> {
                    if (currentSong == song && statusView != null) statusView.setText(message);
                });
            }

            @Override
            public void onPreview(String lyric, String lyricTitle, String lyricArtist, String sourceLabel) {
                runOnUiThread(() -> {
                    if (currentSong != song || lyric == null || lyric.trim().isEmpty()) return;
                    clearPendingLyricPreview();
                    pendingLyricSong = song;
                    pendingLyric = lyric;
                    pendingLyricLabel = lyricTitle + " · " + lyricArtist + " · " + sourceLabel;
                    pendingReplacementType = REPLACEMENT_LYRIC;
                    applyLyricText(lyric);
                    if (confirmLyricButton != null) {
                        confirmLyricButton.setText("确认替换歌词");
                        confirmLyricButton.setVisibility(View.VISIBLE);
                        confirmLyricButton.bringToFront();
                    }
                    statusView.setText("正在预览：" + pendingLyricLabel + "；点击右下角确认替换");
                });
            }
        });
    }

    private void confirmPendingLyric() {
        if (pendingLyricSong == null || pendingLyric == null || pendingLyric.trim().isEmpty()) return;
        if (currentSong != pendingLyricSong || !isSongInAnyPlaylist(pendingLyricSong)) {
            clearPendingLyricPreview();
            toast("当前歌曲已不在歌单中");
            return;
        }
        Song target = pendingLyricSong;
        String lyric = pendingLyric;
        String label = pendingLyricLabel;
        bindLyricToPlaylistCopies(target, lyric, label);
        clearPendingLyricPreview();
        savePlaylists();
        showSongLyrics(currentSong);
        statusView.setText("已绑定歌词：" + label);
        toast("歌词已与歌单歌曲绑定");
    }

    private void clearPendingLyricPreview() {
        pendingLyricSong = null;
        pendingLyric = "";
        pendingLyricLabel = "";
        pendingSongTarget = null;
        pendingSongOriginalKey = "";
        pendingSongTitle = "";
        pendingSongArtist = "";
        pendingSongSource = "";
        pendingSongCatalogJson = "";
        pendingReplacementType = REPLACEMENT_NONE;
        if (confirmLyricButton != null) {
            confirmLyricButton.setText("确认替换");
            confirmLyricButton.setVisibility(View.GONE);
        }
        if (currentSong != null && titleView != null && artistView != null) {
            titleView.setText(currentSong.title);
            artistView.setText(currentSong.artist + " · " + currentSong.source);
        }
    }

    private void updateLyricActionVisibility(Song song) {
        boolean existsInPlaylist = song != null && isSongInAnyPlaylist(song);
        boolean playlistContext = existsInPlaylist && !playingSearchQueue;
        boolean fromSearch = song != null && playingSearchQueue;
        if (addCurrentButton != null) {
            addCurrentButton.setText("加入当前歌单");
            addCurrentButton.setVisibility(fromSearch ? View.VISIBLE : View.GONE);
        }
        if (songVersionButton != null) {
            songVersionButton.setVisibility(playlistContext ? View.VISIBLE : View.GONE);
        }
        if (lyricVersionButton != null) {
            lyricVersionButton.setVisibility(playlistContext ? View.VISIBLE : View.GONE);
        }
        if (!playlistContext && (pendingLyricSong == song || pendingSongTarget == song)) {
            clearPendingLyricPreview();
        }
    }

    private boolean isSongInAnyPlaylist(Song song) {
        if (song == null) return false;
        String key = song.key();
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == song || item.key().equals(key)) return true;
            }
        }
        return false;
    }

    private void markSongUnavailable(Song song, boolean unavailable) {
        if (song == null) return;
        String key = song.key();
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == song || item.key().equals(key)) {
                    item.unavailable = unavailable;
                    item.autoUnavailable = song.autoUnavailable;
                    item.manualUnavailable = song.manualUnavailable;
                    item.manualAttempt = song.manualAttempt;
                    item.cacheFailed = song.cacheFailed;
                }
            }
        }
        song.unavailable = unavailable;
    }

    private void confirmClearTransientCache() {
        new AlertDialog.Builder(this)
            .setTitle("\u6e05\u7406\u7f13\u5b58")
            .setMessage("\u53ea\u5220\u9664\u672a\u52a0\u5165\u4efb\u4f55\u6b4c\u5355\u7684\u6b4c\u66f2\u548c\u6b4c\u8bcd\u7f13\u5b58\uff0c\u6b4c\u5355\u5185\u6b4c\u66f2\u4f1a\u4fdd\u7559\u3002")
            .setPositiveButton("\u6e05\u7406", (dialog, which) -> clearTransientCache())
            .setNegativeButton("\u53d6\u6d88", null)
            .show();
    }

    private void clearTransientCache() {
        Set<String> keepKeys = new HashSet<>();
        for (Playlist playlist : playlists) {
            for (Song song : playlist.songs) {
                if (song != null && song.isNetworkCatalog()) {
                    String cacheKey = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
                    if (!cacheKey.isEmpty()) keepKeys.add(cacheKey);
                }
            }
        }
        new Thread(() -> {
            int removed = NetworkMediaCache.clearExcept(this, keepKeys);
            getSharedPreferences("lyric_version_picker_cache", MODE_PRIVATE).edit().clear().apply();
            runOnUiThread(() -> toast("\u5df2\u6e05\u7406\u975e\u6b4c\u5355\u7f13\u5b58\uff1a" + removed + " \u4e2a\u6587\u4ef6"));
        }).start();
    }

    private void cacheCurrentPlaylistOneClick() {
        final Playlist playlist = currentPlaylist();
        if (playlist == null || playlist.songs.isEmpty()) {
            toast("\u5f53\u524d\u6b4c\u5355\u4e3a\u7a7a");
            return;
        }
        if (playlistCacheRunning) {
            toast("\u5f53\u524d\u6b4c\u5355\u6b63\u5728\u7f13\u5b58");
            return;
        }

        final List<Song> songSnapshot = new ArrayList<>(playlist.songs);
        final int cacheStartSerial = foregroundPlaybackSerial;
        playlistCacheRunning = true;
        ++playlistCacheScanSerial;
        if (playlistCacheButton != null) {
            playlistCacheButton.setVisibility(View.VISIBLE);
            playlistCacheButton.setEnabled(false);
            playlistCacheButton.setText("正在检查缓存状态…");
        }
        if (statusView != null) statusView.setText("正在检查当前歌单的缓存状态…");

        new Thread(() -> {
            List<Song> targets = uncachedNetworkSongs(songSnapshot);
            if (targets.isEmpty()) {
                runOnUiThread(() -> {
                    playlistCacheRunning = false;
                    updatePlaylistCacheButtonVisibility();
                    toast("当前歌单都已缓存");
                });
                return;
            }

            runOnUiThread(() -> {
                if (statusView != null) {
                    statusView.setText("开始缓存未缓存歌曲：" + playlist.name
                        + "，共 " + targets.size() + " 首");
                }
            });

            int done = 0;
            int skipped = 0;
            int failed = 0;
            boolean pausedForPlayback = false;
            for (int i = 0; i < targets.size(); i++) {
                if (foregroundPlaybackSerial != cacheStartSerial) {
                    pausedForPlayback = true;
                    break;
                }
                Song song = targets.get(i);
                if (song == null || !song.isNetworkCatalog()) {
                    skipped++;
                    continue;
                }
                if (songHasRecordedCache(song)) {
                    done++;
                    continue;
                }
                if (song.cacheFailed) {
                    skipped++;
                    continue;
                }
                final int index = i + 1;
                runOnUiThread(() -> {
                    if (statusView != null) {
                        statusView.setText("\u6b63\u5728\u7f13\u5b58 " + index + "/" + targets.size()
                            + "\uff1a" + song.title);
                    }
                });
                try {
                    NetworkMediaCache.CacheResult cached = cachePlaylistSongWithTimeout(song, cacheStartSerial);
                    if (foregroundPlaybackSerial != cacheStartSerial) {
                        pausedForPlayback = true;
                        break;
                    }
                    song.cachedUri = cached.audioUri;
                    song.uri = cached.audioUri;
                    if (cached.catalogJson != null && !cached.catalogJson.trim().isEmpty()) {
                        song.catalogJson = cached.catalogJson;
                    }
                    if (cached.sourceCode != null && !cached.sourceCode.trim().isEmpty()) {
                        song.source = CatalogSearch.labelForSource(cached.sourceCode);
                    }
                    if ((song.lyric == null || song.lyric.trim().isEmpty())
                        && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                        song.lyric = cached.lyric;
                    }
                    song.cacheFailed = false;
                    song.unavailable = false;
                    song.autoUnavailable = false;
                    song.manualUnavailable = false;
                    done++;
                } catch (Exception error) {
                    if (foregroundPlaybackSerial != cacheStartSerial) {
                        pausedForPlayback = true;
                        break;
                    }
                    song.cacheFailed = true;
                    song.unavailable = true;
                    failed++;
                }
            }
            int finalDone = done;
            int finalSkipped = skipped;
            int finalFailed = failed;
            boolean finalPausedForPlayback = pausedForPlayback;
            runOnUiThread(() -> {
                playlistCacheRunning = false;
                savePlaylists();
                renderCurrentPlaylist();
                if (statusView == null) return;
                if (finalPausedForPlayback) {
                    statusView.setText("\u5df2\u56e0\u524d\u53f0\u64ad\u653e\u5207\u6362\u800c\u6682\u505c\u4e00\u952e\u7f13\u5b58");
                } else {
                    statusView.setText("\u4e00\u952e\u7f13\u5b58\u5b8c\u6210\uff1a\u6210\u529f " + finalDone
                        + "\uff0c\u8df3\u8fc7 " + finalSkipped + "\uff0c\u65b0\u5931\u8d25 " + finalFailed);
                }
            });
        }, "playlist-one-click-cache").start();
    }

    private NetworkMediaCache.CacheResult cachePlaylistSongWithTimeout(Song song, int cacheStartSerial) throws Exception {
        ExecutorService executor = Executors.newSingleThreadExecutor();
        try {
            Callable<NetworkMediaCache.CacheResult> task = () -> NetworkMediaCache.cache(
                this,
                song.catalogJson,
                true,
                message -> {
                    if (foregroundPlaybackSerial != cacheStartSerial) {
                        throw new IllegalStateException("\u524d\u53f0\u64ad\u653e\u5df2\u5207\u6362\uff0c\u6682\u505c\u4e00\u952e\u7f13\u5b58");
                    }
                    runOnUiThread(() -> statusView.setText(message));
                }
            );
            Future<NetworkMediaCache.CacheResult> future = executor.submit(task);
            return future.get(PLAYLIST_CACHE_TRACK_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        } catch (java.util.concurrent.TimeoutException error) {
            throw new IllegalStateException("\u5355\u9996\u7f13\u5b58\u8d85\u8fc7 "
                + PLAYLIST_CACHE_TRACK_TIMEOUT_SECONDS + " \u79d2\uff0c\u5df2\u8df3\u8fc7");
        } finally {
            executor.shutdownNow();
        }
    }

    private void bindLyricToPlaylistCopies(Song song, String lyric, String label) {
        if (song == null || lyric == null || lyric.trim().isEmpty()) return;
        writeNetworkLyricCache(song, lyric);
        String key = song.key();
        for (Playlist playlist : playlists) {
            for (Song item : playlist.songs) {
                if (item == song || item.key().equals(key)) {
                    if (!item.isNetworkCatalog()) item.lyric = lyric;
                    item.lyricLabel = label == null ? "" : label;
                }
            }
        }
        song.lyric = lyric;
        song.lyricLabel = label == null ? "" : label;
    }

    private void hydrateLyricFromCache(Song song) {
        if (song == null || !song.isNetworkCatalog()) return;
        if (song.lyric != null && !song.lyric.trim().isEmpty()) return;
        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        if (key.isEmpty()) return;
        String cachedLyric = CacheStorage.readLyric(this, key);
        if (cachedLyric != null && !cachedLyric.trim().isEmpty()) {
            song.lyric = cachedLyric;
            if (song.lyricLabel == null || song.lyricLabel.trim().isEmpty()) {
                song.lyricLabel = song.title + " / " + song.artist + " / " + song.source;
            }
        }
    }

    private void writeNetworkLyricCache(Song song, String lyric) {
        if (song == null || !song.isNetworkCatalog() || lyric == null || lyric.trim().isEmpty()) return;
        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        if (key.isEmpty()) return;
        try {
            CacheStorage.writeLyric(this, key, lyric, song.title, song.artist, "", song.catalogJson);
        } catch (Exception error) {
            android.util.Log.w("BabywifePlaylist", "write lyric cache failed: " + error.getMessage());
        }
    }

    private void ensurePlaylistLyric(Song song) {
        if (song == null || !isSongInAnyPlaylist(song)) return;
        if (song.lyric != null && !song.lyric.trim().isEmpty()) return;
        String key = song.key();
        if (!lyricMatchingSongs.add(key)) return;
        if (currentSong == song && statusView != null) {
            statusView.setText("歌曲已加入歌单，正在匹配歌词...");
        }
        PlaylistLyricMatcher.matchAsync(song.title, song.artist, song.catalogJson,
            new PlaylistLyricMatcher.Callback() {
                @Override
                public void onMatched(String lyric, String label) {
                    runOnUiThread(() -> {
                        lyricMatchingSongs.remove(key);
                        if (!isSongInAnyPlaylist(song)) return;
                        if (song.lyric == null || song.lyric.trim().isEmpty()) {
                            bindLyricToPlaylistCopies(song, lyric, label);
                            savePlaylists();
                        }
                        if (currentSong == song && pendingLyricSong != song) {
                            showSongLyrics(song);
                            statusView.setText("已匹配歌词：" + label);
                        }
                    });
                }

                @Override
                public void onUnavailable() {
                    runOnUiThread(() -> {
                        lyricMatchingSongs.remove(key);
                        if (currentSong == song && pendingLyricSong != song
                            && (song.lyric == null || song.lyric.trim().isEmpty())) {
                            lyricView.setText("暂未找到匹配歌词，可点击右上角手动选择版本");
                            statusView.setText("自动匹配歌词未找到可用版本");
                        }
                    });
                }
            });
    }

    private String fetchBestLyricByKeyword(String keyword) {
        List<Song> candidates = searchNetease(keyword);
        for (Song candidate : candidates) {
            String id = neteaseIdFromSong(candidate);
            if (id.isEmpty()) continue;
            String lyric = fetchNeteaseLyric(id);
            if (!lyric.trim().isEmpty()) return lyric;
        }
        return "";
    }

    private String neteaseIdFromSong(Song song) {
        if (song == null || song.uri == null) return "";
        String uri = song.uri;
        int marker = uri.indexOf("id=");
        if (!song.source.contains("\u7f51\u6613") || marker < 0) return "";
        String tail = uri.substring(marker + 3);
        int dot = tail.indexOf('.');
        if (dot >= 0) tail = tail.substring(0, dot);
        int amp = tail.indexOf('&');
        if (amp >= 0) tail = tail.substring(0, amp);
        return tail.replaceAll("[^0-9]", "");
    }

    private String fetchNeteaseLyric(String id) {
        try {
            JSONObject payload = httpJson(
                "https://music.163.com/api/song/lyric?id=" + id + "&lv=1&kv=1&tv=-1",
                "https://music.163.com/"
            );
            JSONObject lrc = payload.optJSONObject("lrc");
            return lrc == null ? "" : lrc.optString("lyric", "");
        } catch (Exception ignored) {
            return "";
        }
    }

    private void applyLyricText(String raw) {
        lyricLines.clear();
        String safeRaw = raw == null ? "" : raw;
        String[] lines = safeRaw.split("\\r?\\n");
        for (String line : lines) {
            LyricLine parsed = parseLyricLine(line);
            if (parsed != null) lyricLines.add(parsed);
        }
        if (lyricLines.isEmpty()) {
            String visible = stripVisibleLyricTags(safeRaw);
            lyricView.setText(visible.trim().isEmpty() ? "暂无歌词" : visible);
            return;
        }
        renderLyricHighlight(0);
    }

    private LyricLine parseLyricLine(String line) {
        if (line == null || line.isEmpty()) return null;
        java.util.regex.Matcher matcher = java.util.regex.Pattern
            .compile("\\[(\\d{1,3}):(\\d{1,2}(?:\\.\\d{1,3})?)\\]")
            .matcher(line);
        if (!matcher.find()) return null;
        try {
            long minute = Long.parseLong(matcher.group(1));
            double second = Double.parseDouble(matcher.group(2));
            String text = stripVisibleLyricTags(line.substring(matcher.end())).trim();
            return new LyricLine(
                (long) (minute * 60000 + second * 1000),
                text.isEmpty() ? " " : text
            );
        } catch (Exception ignored) {
            return null;
        }
    }

    private void updateLyricProgress() {
        if (mediaPlayer == null || lyricLines.isEmpty()) return;
        int position;
        try {
            position = mediaPlayer.getCurrentPosition();
        } catch (Exception ignored) {
            return;
        }
        int index = lyricIndexFor(position);
        if (index != highlightedLyricIndex) renderLyricHighlight(index);
    }

    private void updatePlaybackProgress() {
        if (userSeeking || progressSeekBar == null || progressTimeView == null) return;
        if (mediaPlayer == null) {
            resetPlaybackProgress();
            return;
        }
        try {
            int duration = Math.max(1, mediaPlayer.getDuration());
            int position = Math.max(0, Math.min(duration, mediaPlayer.getCurrentPosition()));
            progressSeekBar.setMax(duration);
            progressSeekBar.setProgress(position);
            progressTimeView.setText(formatPlaybackTime(position)
                + " / " + formatPlaybackTime(duration));
            publishPlaybackControlState(false);
        } catch (Exception ignored) {
        }
    }

    private void resetPlaybackProgress() {
        if (progressSeekBar != null) {
            progressSeekBar.setMax(1);
            progressSeekBar.setProgress(0);
        }
        if (progressTimeView != null) progressTimeView.setText("00:00 / 00:00");
    }

    private String formatPlaybackTime(int milliseconds) {
        int totalSeconds = Math.max(0, milliseconds / 1000);
        return String.format(java.util.Locale.ROOT, "%02d:%02d",
            totalSeconds / 60, totalSeconds % 60);
    }

    private int lyricIndexFor(long positionMs) {
        int index = 0;
        for (int i = 0; i < lyricLines.size(); i++) {
            if (positionMs >= lyricLines.get(i).timeMs) index = i;
            else break;
        }
        return index;
    }

    private void renderLyricHighlight(int index) {
        if (lyricLines.isEmpty()) return;
        highlightedLyricIndex = Math.max(0, Math.min(index, lyricLines.size() - 1));
        int edgeBlankLines = Math.max(MIN_LYRIC_EDGE_BLANK_LINES, lyricEdgeBlankLineCount);
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < edgeBlankLines; i++) builder.append('\n');
        for (LyricLine line : lyricLines) builder.append(line.text).append('\n');
        for (int i = 0; i < edgeBlankLines; i++) builder.append('\n');

        SpannableString span = new SpannableString(builder.toString());
        int start = edgeBlankLines;
        for (int i = 0; i < lyricLines.size(); i++) {
            int end = start + lyricLines.get(i).text.length();
            if (i == highlightedLyricIndex) {
                span.setSpan(new ForegroundColorSpan(Color.WHITE), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                span.setSpan(new RelativeSizeSpan(ACTIVE_LYRIC_SCALE), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                span.setSpan(new StyleSpan(Typeface.BOLD), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            } else {
                span.setSpan(new ForegroundColorSpan(Color.argb(150, 255, 255, 255)), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            start = end + 1;
        }
        lyricView.setText(span);
        refreshLyricEdgeBlankLinesAndCenter();
    }

    private void refreshLyricEdgeBlankLinesAndCenter() {
        if (lyricsScroll == null || lyricView == null || lyricLines.isEmpty()) return;
        lyricsScroll.post(() -> {
            int visibleHeight = Math.max(1, lyricsScroll.getHeight()
                - lyricsScroll.getPaddingTop() - lyricsScroll.getPaddingBottom());
            int lineHeight = Math.max(lyricView.getLineHeight(), dp(30));
            int desiredBlankLines = Math.max(MIN_LYRIC_EDGE_BLANK_LINES,
                (int) Math.ceil(visibleHeight / (2.0 * lineHeight)) + 1);
            if (desiredBlankLines != lyricEdgeBlankLineCount) {
                lyricEdgeBlankLineCount = desiredBlankLines;
                renderLyricHighlight(highlightedLyricIndex);
                return;
            }
            if (!userLyricTouch) centerLyricLine(highlightedLyricIndex, true);
        });
    }

    private int lyricTextOffsetForIndex(int index) {
        if (lyricLines.isEmpty()) return 0;
        int safeIndex = Math.max(0, Math.min(index, lyricLines.size() - 1));
        int offset = Math.max(MIN_LYRIC_EDGE_BLANK_LINES, lyricEdgeBlankLineCount);
        for (int i = 0; i < safeIndex; i++) {
            String text = lyricLines.get(i).text;
            offset += (text == null ? 0 : text.length()) + 1;
        }
        return offset;
    }

    private int lyricTextEndOffsetForIndex(int index) {
        if (lyricLines.isEmpty()) return 0;
        int safeIndex = Math.max(0, Math.min(index, lyricLines.size() - 1));
        String text = lyricLines.get(safeIndex).text;
        return lyricTextOffsetForIndex(safeIndex) + (text == null ? 0 : text.length());
    }

    private int lyricIndexForTextOffset(int textOffset) {
        if (lyricLines.isEmpty()) return -1;
        int offset = Math.max(MIN_LYRIC_EDGE_BLANK_LINES, lyricEdgeBlankLineCount);
        if (textOffset <= offset) return 0;
        for (int i = 0; i < lyricLines.size(); i++) {
            String text = lyricLines.get(i).text;
            int end = offset + (text == null ? 0 : text.length());
            if (textOffset <= end) return i;
            offset = end + 1;
        }
        return lyricLines.size() - 1;
    }

    private void centerLyricLine(int index, boolean smooth) {
        if (userLyricTouch || lyricsScroll == null || lyricView == null || lyricLines.isEmpty()) return;
        int safeIndex = Math.max(0, Math.min(index, lyricLines.size() - 1));
        lyricsScroll.post(() -> {
            Layout layout = lyricView.getLayout();
            CharSequence displayedText = lyricView.getText();
            int textLength = displayedText == null ? 0 : displayedText.length();
            if (layout == null || layout.getLineCount() == 0 || textLength == 0) return;

            int startOffset = Math.max(0, Math.min(textLength - 1,
                lyricTextOffsetForIndex(safeIndex)));
            int endProbe = Math.max(startOffset, Math.min(textLength - 1,
                lyricTextEndOffsetForIndex(safeIndex) - 1));
            int startLine = layout.getLineForOffset(startOffset);
            int endLine = layout.getLineForOffset(endProbe);
            int blockCenter = lyricView.getTop() + lyricView.getTotalPaddingTop()
                + (layout.getLineTop(startLine) + layout.getLineBottom(endLine)) / 2;

            int visibleHeight = Math.max(1, lyricsScroll.getHeight()
                - lyricsScroll.getPaddingTop() - lyricsScroll.getPaddingBottom());
            int viewportCenter = lyricsScroll.getPaddingTop() + visibleHeight / 2;
            int targetY = Math.max(0, blockCenter - viewportCenter);
            scrollLyricsTo(targetY, smooth);
        });
    }

    private void scrollLyricsTo(int targetY, boolean smooth) {
        if (lyricsScroll == null) return;
        autoScrollingLyrics = true;
        if (smooth) lyricsScroll.smoothScrollTo(0, targetY);
        else lyricsScroll.scrollTo(0, targetY);
        lyricHandler.postDelayed(() -> autoScrollingLyrics = false, 260);
    }

    private int lyricIndexAtTouch(float y) {
        if (lyricsScroll == null || lyricView == null || lyricLines.isEmpty()) return -1;
        Layout layout = lyricView.getLayout();
        if (layout == null || layout.getLineCount() == 0) return -1;

        int contentY = lyricsScroll.getScrollY() + Math.max(0, (int) y)
            - lyricView.getTop() - lyricView.getTotalPaddingTop();
        int line = layout.getLineForVertical(Math.max(0, contentY));
        int textOffset = layout.getLineStart(line);
        return lyricIndexForTextOffset(textOffset);
    }

    private void seekByLyricTouch(float y) {
        if (autoScrollingLyrics || mediaPlayer == null || lyricLines.isEmpty()
            || lyricsScroll == null || lyricView == null) return;
        int index = lyricIndexAtTouch(y);
        if (index < 0) return;
        try {
            mediaPlayer.seekTo((int) Math.min(Integer.MAX_VALUE, lyricLines.get(index).timeMs));
            renderLyricHighlight(index);
            centerLyricLine(index, true);
            updatePlaybackProgress();
        } catch (Exception ignored) {
        }
    }

    private void restoreLastSong(boolean prepareAudio) {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String context = prefs.getString(KEY_LAST_CONTEXT, "playlist");
        int position = prefs.getInt(KEY_LAST_POSITION, 0);
        if ("search".equals(context)) {
            String raw = prefs.getString(KEY_LAST_SEARCH_SONG, "");
            try {
                if (raw != null && !raw.trim().isEmpty()) {
                    currentSong = Song.fromJson(new JSONObject(raw));
                    playingSearchQueue = true;
                    searchSongIndex = -1;
                    currentSongIndex = -1;
                    titleView.setText(currentSong.title);
                    artistView.setText(currentSong.artist + " · " + currentSong.source);
                    statusView.setText("已恢复上次搜索歌曲：" + currentSong.title);
                    if (prepareAudio) prepareLastSong(position);
                    else resetPlaybackProgress();
                    showPlayerPage();
                    return;
                }
            } catch (Exception ignored) {
            }
        }
        int playlistIndex = prefs.getInt(KEY_LAST_PLAYLIST, currentPlaylistIndex);
        int songIndex = prefs.getInt(KEY_LAST_SONG, -1);
        playingSearchQueue = false;
        if (playlistIndex >= 0 && playlistIndex < playlists.size()) {
            currentPlaylistIndex = playlistIndex;
            renderCurrentPlaylist();
            Playlist playlist = currentPlaylist();
            if (songIndex >= 0 && songIndex < playlist.songs.size()) {
                currentSongIndex = songIndex;
                currentSong = playlist.songs.get(songIndex);
                titleView.setText(currentSong.title);
                artistView.setText(currentSong.artist + " · " + currentSong.source);
                lyricView.setText(currentSong.lyric);
                statusView.setText("已恢复上次播放：" + currentSong.title);
                if (prepareAudio) prepareLastSong(position);
                else resetPlaybackProgress();
                showPlayerPage();
                return;
            }
        }
        renderEmptyPlayer();
        showPlayerPage();
    }

    private void prepareLastSong(int position) {
        if (currentSong == null) {
            if (playButton != null) playButton.setText("▶");
            resetPlaybackProgress();
            return;
        }
        updateLyricActionVisibility(currentSong);
        showSongLyrics(currentSong);
        if (currentSong.isNetworkCatalog()) {
            if (currentSong.cachedUri != null && !currentSong.cachedUri.trim().isEmpty()
                && NetworkMediaCache.cachedAudioExists(this, currentSong.cachedUri)) {
                currentSong.uri = currentSong.cachedUri;
            } else {
                currentSong.cachedUri = "";
                currentSong.uri = "";
                if (playButton != null) playButton.setText("▶");
                statusView.setText("网络歌曲目录已恢复，点击播放时再缓存");
                resetPlaybackProgress();
                return;
            }
        }
        if (currentSong.uri == null || currentSong.uri.isEmpty()) {
            if (playButton != null) playButton.setText("▶");
            resetPlaybackProgress();
            return;
        }
        try {
            stopPlayback();
            mediaPlayer = createWakefulMediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(currentSong.uri));
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());
            mediaPlayer.prepare();
            if (position > 0) mediaPlayer.seekTo(position);
            updatePlaybackProgress();
            playButton.setText("▶");
        } catch (Exception ignored) {
            stopPlayback();
            playButton.setText("▶");
        }
    }

    private void playSong(Song song) {
        if (song == null) return;
        int playToken = ++playbackRequestSerial;
        foregroundPlaybackSerial = playToken;
        if ((pendingLyricSong != null && pendingLyricSong != song)
            || (pendingSongTarget != null && pendingSongTarget != song)) {
            clearPendingLyricPreview();
        }
        currentSong = song;
        saveLastSong(0);
        titleView.setText(song.title);
        artistView.setText(song.artist + " · " + song.source);
        updateLyricActionVisibility(song);
        statusView.setText("当前选择：" + song.title);
        if (song.isNetworkCatalog()) {
            lyricLines.clear();
            highlightedLyricIndex = -1;
            if (song.lyric != null && !song.lyric.trim().isEmpty()) {
                applyLyricText(song.lyric);
            } else {
                lyricView.setText("正在准备音频，播放开始后再匹配歌词...");
            }
        } else {
            showSongLyrics(song);
        }
        publishPlaybackControlState(true);

        if (song.isNetworkCatalog()) {
            stopPlayback();
            playButton.setText("▶");
            if (!playingSearchQueue && isSongInAnyPlaylist(song)) {
                playPlaylistSongFromCacheFirst(song, playToken);
            } else if (song.cachedUri != null && !song.cachedUri.trim().isEmpty()) {
                song.uri = song.cachedUri;
                statusView.setText("已读取本次搜索缓存，正在启动播放...");
                startLocalPlayback(song, playToken, null, () -> {
                    song.cachedUri = "";
                    song.uri = "";
                    statusView.setText("本次搜索缓存无法播放，立即重新获取音频...");
                    cacheAndPlay(song, playToken);
                });
            } else {
                statusView.setText("未记录缓存，立即获取音频...");
                cacheAndPlay(song, playToken);
            }
            return;
        }

        if (song.uri == null || song.uri.isEmpty()) {
            stopPlayback();
            playButton.setText("▶");
            resolveAndPlay(song, playToken);
            return;
        }
        startLocalPlayback(song, playToken, null, null);
    }

    private void playPlaylistSongFromCacheFirst(Song song, int playToken) {
        String recorded = song.cachedUri == null ? "" : song.cachedUri.trim();
        if (recorded.isEmpty()) {
            statusView.setText("歌单没有记录缓存，立即获取音频...");
            cacheAndPlay(song, playToken);
            return;
        }
        song.uri = recorded;
        statusView.setText("已读取歌单记录缓存，正在启动播放...");
        startLocalPlayback(song, playToken, null, () -> {
            song.cachedUri = "";
            song.uri = "";
            statusView.setText("歌单记录缓存无法播放，立即重新获取音频...");
            cacheAndPlay(song, playToken);
        });
    }

    private void cacheAndPlay(Song song, int playToken) {
        String originalKey = song.key();
        statusView.setText("正在检查已有缓存...");
        new Thread(() -> {
            try {
                NetworkMediaCache.CacheResult cached = NetworkMediaCache.cache(
                    this,
                    song.catalogJson,
                    true,
                    message -> {
                        if (currentSong != song || playToken != playbackRequestSerial) {
                            throw new IllegalStateException("播放请求已切换，停止旧候选下载");
                        }
                        runOnUiThread(() -> {
                            if (currentSong == song && playToken == playbackRequestSerial) {
                                statusView.setText(message);
                            }
                        });
                    }
                );
                runOnUiThread(() -> {
                    if (currentSong != song || playToken != playbackRequestSerial) return;
                    String playbackUri = cached.audioUri;
                    String resolvedCatalogJson = cached.catalogJson;
                    String resolvedSourceCode = cached.sourceCode;
                    String resolvedSourceLabel = resolvedSourceCode == null || resolvedSourceCode.trim().isEmpty()
                        ? song.source : CatalogSearch.labelForSource(resolvedSourceCode);
                    String resolvedLyric = cached.lyric;
                    PendingPlaybackCommit commit = new PendingPlaybackCommit(
                        originalKey,
                        playbackUri,
                        resolvedCatalogJson,
                        resolvedSourceLabel,
                        cached.sourceChanged,
                        resolvedLyric
                    );
                    song.cachedUri = cached.audioUri;
                    song.uri = cached.audioUri;
                    if ((song.lyric == null || song.lyric.trim().isEmpty())
                        && cached.lyric != null && !cached.lyric.trim().isEmpty()) {
                        song.lyric = cached.lyric;
                        song.lyricLabel = song.title + " · " + song.artist + " · " + resolvedSourceLabel;
                    }
                    artistView.setText(song.artist + " · " + song.source);
                    showSongLyrics(song);
                    startLocalPlayback(song, playToken,
                        () -> commitResolvedPlayback(song, commit, playToken),
                        () -> {
                            if (cached.audioFromCache) {
                                NetworkMediaCache.deleteCatalogCache(this, cached.catalogJson);
                                song.cachedUri = "";
                                song.uri = "";
                                statusView.setText("记录缓存无法播放，立即重新获取音频...");
                                cacheAndPlay(song, playToken);
                            } else {
                                markPlaybackFailure(song, true);
                            }
                        });
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (currentSong != song || playToken != playbackRequestSerial) return;
                    stopPlayback();
                    playButton.setText("▶");
                    showSongLyrics(song);
                    markPlaybackFailure(song, false);
                    statusView.setText("缓存失败：" + error.getMessage());
                    toast("该歌曲当前无法缓存播放");
                });
            }
        }).start();
    }

    private String stripVisibleLyricTags(String lyric) {
        if (lyric == null) return "";
        StringBuilder out = new StringBuilder();
        for (String line : lyric.split("\\r?\\n")) {
            String clean = line
                .replaceAll("\\[[^\\]]*\\]", "")
                .replaceAll("<[^>]*>", "")
                .replaceAll("\\(\\s*\\d+\\s*,\\s*\\d+(?:\\s*,\\s*\\d+)?\\s*\\)", "")
                .replaceAll("\\{\\s*\\d+\\s*[,;:]\\s*\\d+[^}]*\\}", "")
                .trim();
            if (clean.isEmpty()) continue;
            if (out.length() > 0) out.append('\n');
            out.append(clean);
        }
        return out.toString();
    }

    private void resolveAndPlay(Song song, int playToken) {
        statusView.setText("\u6b63\u5728\u89e3\u6790\u53ef\u64ad\u653e\u97f3\u9891...");
        new Thread(() -> {
            Song resolved = resolvePlayableSong(song);
            runOnUiThread(() -> {
                if (currentSong != song || playToken != playbackRequestSerial) return;
                if (resolved == null || resolved.uri == null || resolved.uri.isEmpty()) {
                    toast("\u6682\u65f6\u6ca1\u6709\u89e3\u6790\u5230\u53ef\u64ad\u653e\u97f3\u9891");
                    return;
                }
                song.uri = resolved.uri;
                if ((song.lyric == null || song.lyric.trim().isEmpty()) && resolved.lyric != null) song.lyric = resolved.lyric;
                startLocalPlayback(song, playToken, null, null);
            });
        }).start();
    }

    private Song resolvePlayableSong(Song song) {
        String keyword = song.title + " " + song.artist;
        List<Song> candidates = new ArrayList<>();
        candidates.addAll(searchKuwo(keyword));
        candidates.addAll(searchNetease(keyword));
        sortByKeyword(candidates, song.title);
        for (Song candidate : candidates) {
            if (candidate.uri == null || candidate.uri.isEmpty()) continue;
            String playable = resolvePlaybackUri(candidate.uri);
            if (!playable.isEmpty()) {
                candidate.uri = playable;
                if (candidate.lyric == null || candidate.lyric.isEmpty()) {
                    String id = neteaseIdFromSong(candidate);
                    if (!id.isEmpty()) candidate.lyric = fetchNeteaseLyric(id);
                }
                return candidate;
            }
        }
        return null;
    }

    private String resolvePlaybackUri(String uri) {
        if (uri == null || uri.trim().isEmpty()) return "";
        String trimmed = uri.trim();
        if (!trimmed.contains("antiserver.kuwo.cn")) return trimmed;
        try {
            HttpURLConnection connection = (HttpURLConnection) new URL(trimmed).openConnection();
            connection.setConnectTimeout(8000);
            connection.setReadTimeout(8000);
            connection.setRequestProperty("User-Agent", "Mozilla/5.0");
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream(), "UTF-8"))) {
                String value = reader.readLine();
                return value == null ? "" : value.trim();
            } finally {
                connection.disconnect();
            }
        } catch (Exception ignored) {
            return trimmed;
        }
    }

    private void playSongFromPlaylist(int index) {
        if (index < 0 || index >= currentPlaylist().songs.size()) return;
        playingSearchQueue = false;
        searchSongIndex = -1;
        currentSongIndex = index;
        playSong(currentPlaylist().songs.get(index));
    }

    private void playSongFromSearch(int index) {
        if (index < 0 || index >= searchResults.size()) return;
        playingSearchQueue = true;
        searchSongIndex = index;
        currentSongIndex = -1;
        playSong(searchResults.get(index));
    }

    private void playPlaylistOffset(int offset) {
        if (playingSearchQueue) {
            if (searchResults.isEmpty()) {
                toast("\u641c\u7d22\u961f\u5217\u4e3a\u7a7a");
                return;
            }
            int nextIndex = searchSongIndex;
            if (nextIndex < 0 || nextIndex >= searchResults.size()) {
                nextIndex = 0;
            } else {
                nextIndex = (nextIndex + offset + searchResults.size()) % searchResults.size();
            }
            playSongFromSearch(nextIndex);
            return;
        }
        Playlist playlist = currentPlaylist();
        if (playlist.songs.isEmpty()) {
            toast("\u5f53\u524d\u6b4c\u5355\u4e3a\u7a7a");
            return;
        }
        int nextIndex = currentSongIndex;
        if (nextIndex < 0 || nextIndex >= playlist.songs.size()) {
            nextIndex = 0;
        } else if (playMode == 2 && offset != 0) {
            nextIndex = random.nextInt(playlist.songs.size());
        } else {
            nextIndex = (nextIndex + offset + playlist.songs.size()) % playlist.songs.size();
        }
        playSongFromPlaylist(nextIndex);
    }

    private void playAfterCompletion() {
        if (playingSearchQueue) {
            playPlaylistOffset(1);
            return;
        }
        if (playMode == 0) {
            playSong(currentSong);
        } else {
            playPlaylistOffset(1);
        }
    }

    private void cyclePlayMode() {
        playMode = (playMode + 1) % 3;
        savePlayMode();
        if (modeButton != null) modeButton.setText(playModeSymbol());
        toast(playModeText());
    }

    private String playModeText() {
        if (playMode == 0) return "\u5355\u66f2\u5faa\u73af";
        if (playMode == 1) return "\u987a\u5e8f\u64ad\u653e";
        return "\u968f\u673a\u64ad\u653e";
    }

    private String playModeSymbol() {
        if (playMode == 0) return "\u21bb";
        if (playMode == 1) return "\u2192";
        return "\u2928";
    }

    private void startLocalPlayback(Song song, int playToken, Runnable onStarted, Runnable onFailed) {
        try {
            stopPlayback();
            mediaPlayer = createWakefulMediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(song.uri));
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());
            mediaPlayer.setOnErrorListener((player, what, extra) -> {
                if (currentSong == song && playToken == playbackRequestSerial) {
                    stopPlayback();
                    playButton.setText("▶");
                    statusView.setText("播放失败：当前来源不可用");
                    if (onFailed != null) onFailed.run();
                    publishPlaybackControlState(true);
                }
                return true;
            });
            boolean online = song.uri.startsWith("http://") || song.uri.startsWith("https://");
            statusView.setText(online ? "正在打开在线音频..." : "缓存已就绪，正在启动播放...");
            mediaPlayer.setOnPreparedListener(player -> {
                try {
                    if (currentSong != song || playToken != playbackRequestSerial) return;
                    player.start();
                    onPlaybackStarted(song, onStarted);
                } catch (Exception error) {
                    stopPlayback();
                    playButton.setText("▶");
                    statusView.setText("播放失败：" + error.getMessage());
                    if (onFailed != null) onFailed.run();
                }
            });
            mediaPlayer.prepareAsync();
        } catch (Exception ex) {
            stopPlayback();
            playButton.setText("▶");
            if (onFailed != null) onFailed.run();
            toast("播放失败：" + ex.getMessage());
        }
    }

    private void onPlaybackStarted(Song song, Runnable onStarted) {
        playButton.setText("Ⅱ");
        saveLastSong(0);
        updatePlaybackProgress();
        lyricHandler.removeCallbacks(lyricTicker);
        lyricHandler.post(lyricTicker);
        statusView.setText("当前播放：" + song.title);
        if (song.isNetworkCatalog()) showSongLyrics(song);
        if (onStarted != null) onStarted.run();
        publishPlaybackControlState(true);
    }

    private void togglePlayback() {
        if (mediaPlayer == null) {
            if (currentSong != null) {
                playSong(currentSong);
            } else if (!currentPlaylist().songs.isEmpty()) {
                playSongFromPlaylist(0);
            } else {
                toast("请先导入或选择歌曲");
            }
            publishPlaybackControlState(true);
            return;
        }
        if (mediaPlayer.isPlaying()) {
            mediaPlayer.pause();
            playButton.setText("▶");
            saveLastSong(mediaPlayer.getCurrentPosition());
            lyricHandler.removeCallbacks(lyricTicker);
        } else {
            mediaPlayer.start();
            playButton.setText("Ⅱ");
            lyricHandler.post(lyricTicker);
        }
        publishPlaybackControlState(true);
    }

    private void saveLastSong(int position) {
        if (currentSong == null) return;
        SharedPreferences.Editor editor = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit()
            .putInt(KEY_LAST_POSITION, Math.max(0, position));
        if (playingSearchQueue && !isSongInAnyPlaylist(currentSong)) {
            editor.putString(KEY_LAST_CONTEXT, "search")
                .putString(KEY_LAST_SEARCH_SONG, currentSong.toJson().toString())
                .remove(KEY_LAST_SONG)
                .apply();
            return;
        }
        int playlistIndex = currentPlaylistIndex;
        int songIndex = currentSongIndex;
        if (songIndex < 0) songIndex = currentPlaylist().songs.indexOf(currentSong);
        if (songIndex < 0) return;
        editor.putString(KEY_LAST_CONTEXT, "playlist")
            .remove(KEY_LAST_SEARCH_SONG)
            .putInt(KEY_LAST_PLAYLIST, playlistIndex)
            .putInt(KEY_LAST_SONG, songIndex)
            .apply();
    }

    private void stopPlayback() {
        if (mediaPlayer != null) {
            try {
                mediaPlayer.stop();
            } catch (Exception ignored) {
            }
            mediaPlayer.release();
            mediaPlayer = null;
        }
        lyricHandler.removeCallbacks(lyricTicker);
        resetPlaybackProgress();
        publishPlaybackControlState(true);
    }

    private LinearLayout buildDrawerPanel() {
        LinearLayout drawer = new LinearLayout(this);
        drawer.setOrientation(LinearLayout.VERTICAL);
        drawer.setPadding(dp(14), statusBarHeight() + dp(20), dp(14), dp(16));
        drawer.setBackground(rounded(Color.argb(226, 22, 24, 34), dp(22)));

        LinearLayout.LayoutParams managerParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT);
        managerParams.setMargins(0, dp(4), 0, 0);
        drawer.addView(buildPlaylistManagerPanel(), managerParams);

        View managerSettingsGap = new View(this);
        managerSettingsGap.setMinimumHeight(dp(20));
        drawer.addView(managerSettingsGap, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));

        LinearLayout bottomActions = new LinearLayout(this);
        bottomActions.setOrientation(LinearLayout.VERTICAL);

        uninstallCleanupButton = makeButton(uninstallCleanupSettingText(), false);
        uninstallCleanupButton.setOnClickListener(view -> toggleUninstallCleanupSetting());
        bottomActions.addView(uninstallCleanupButton, bottomSettingParams(38, 0));

        cacheLocationButton = makeButton(CacheStorage.description(this), false);
        cacheLocationButton.setSingleLine(true);
        cacheLocationButton.setEllipsize(TextUtils.TruncateAt.MIDDLE);
        cacheLocationButton.setOnClickListener(view -> showCacheLocationDialog());
        bottomActions.addView(cacheLocationButton, bottomSettingParams(38, 2));

        Button crashReportButton = makeButton("\u95ea\u9000/\u65e0\u54cd\u5e94\u62a5\u544a", false);
        crashReportButton.setOnClickListener(view -> openSavedCrashReport());
        bottomActions.addView(crashReportButton, bottomSettingParams(38, 2));

        Button importAudio = makeButton("导入本地歌曲", false);
        importAudio.setOnClickListener(view -> showLocalAudioImportOptions());
        bottomActions.addView(importAudio, bottomSettingParams(38, 2));

        Button importPlaylist = makeButton("导入歌单", false);
        importPlaylist.setOnClickListener(view -> showPlaylistImportOptions());
        bottomActions.addView(importPlaylist, bottomSettingParams(38, 2));

        Button chooseBackground = makeButton("选择本地图片作为背景", false);
        chooseBackground.setOnClickListener(view -> chooseBackgroundImage());
        bottomActions.addView(chooseBackground, bottomSettingParams(38, 2));

        if (getResources().getBoolean(R.bool.icon_selector_enabled)) {
            Button changeIcon = makeButton("更换桌面图标", false);
            changeIcon.setOnClickListener(view -> showLauncherIconPicker());
            bottomActions.addView(changeIcon, bottomSettingParams(38, 2));
        }

        Button resetBackground = makeButton("恢复默认背景", true);
        resetBackground.setOnClickListener(view -> showBuiltInBackgroundPicker());
        bottomActions.addView(resetBackground, bottomSettingParams(42, 5));

        drawer.addView(bottomActions, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT));
        return drawer;
    }

    private void closeDrawer() {
        if (drawerPanel != null) drawerPanel.setVisibility(View.GONE);
        if (drawerDismissView != null) drawerDismissView.setVisibility(View.GONE);
        getWindow().setStatusBarColor(normalStatusBarColor);
    }

    private void showCacheLocationDialog() {
        new AlertDialog.Builder(this)
            .setTitle("歌单缓存位置")
            .setMessage(CacheStorage.details(this)
                + "\n\n更换位置时会迁移旧缓存文件夹内的全部普通文件。每个文件复制并校验成功后才切换位置，最后删除旧文件。"
                + "\n需要授予文件管理权限，并在系统文件选择器中确认新的缓存文件夹。")
            .setPositiveButton("选择缓存文件夹", (dialog, which) -> requestFileManagementThenChooseCacheFolder())
            .setNeutralButton("使用卸载时清理的位置", (dialog, which) -> migrateCacheToInternal())
            .setNegativeButton("取消", null)
            .show();
    }

    private void requestFileManagementThenChooseCacheFolder() {
        if (hasFileManagementPermission()) {
            chooseCacheFolder();
            return;
        }
        pendingCacheFolderSelection = true;
        new AlertDialog.Builder(this)
            .setTitle("授予文件管理权限")
            .setMessage("为了把旧缓存文件夹中的全部文件移动到新文件夹，并删除旧位置中的原文件，"
                + "需要在系统设置中允许本应用管理所有文件。授权后仍会让你选择新的缓存文件夹。")
            .setPositiveButton("前往授权", (dialog, which) -> openFileManagementSettings())
            .setNegativeButton("取消", (dialog, which) -> pendingCacheFolderSelection = false)
            .show();
    }

    private boolean hasFileManagementPermission() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.R
            || Environment.isExternalStorageManager();
    }

    private void openFileManagementSettings() {
        fileManagementSettingsOpened = true;
        try {
            Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        } catch (Exception appPageUnavailable) {
            try {
                startActivity(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION));
            } catch (Exception settingsUnavailable) {
                fileManagementSettingsOpened = false;
                pendingCacheFolderSelection = false;
                toast("无法打开文件管理权限设置，请在系统设置中手动授权");
            }
        }
    }

    private void chooseCacheFolder() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
            | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_CACHE_FOLDER);
    }

    private void migrateCacheToDocumentTree(Uri treeUri) {
        if (treeUri == null) return;
        statusView.setText("正在迁移歌曲与歌词缓存，请勿关闭软件...");
        new Thread(() -> {
            try {
                CacheStorage.MigrationResult result = CacheStorage.useDocumentTree(this, treeUri);
                runOnUiThread(() -> {
                    refreshCachedUrisAfterMigrationAsync();
                    updateCacheLocationButton();
                    updateUninstallCleanupButton();
                    statusView.setText("缓存位置已更新");
                    String cleanup = result.retainedInOldLocation > 0
                        ? "；旧文件夹仍有 " + result.retainedInOldLocation + " 个文件未能删除，请检查文件管理权限"
                        : "；旧文件夹中的原文件已删除";
                    toast(result.changed
                        ? "缓存位置已更换，已迁移并校验 " + result.copied + " 个文件" + cleanup + "；卸载后会保留"
                        : "当前已经是所选缓存文件夹");
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    statusView.setText("缓存位置更换失败");
                    toast("缓存文件夹设置失败，旧文件未删除：" + error.getMessage());
                });
            }
        }).start();
    }

    private void migrateCacheToInternal() {
        statusView.setText("正在把缓存迁回应用内部，请勿关闭软件...");
        new Thread(() -> {
            try {
                CacheStorage.MigrationResult result = CacheStorage.useInternalStorage(this);
                runOnUiThread(() -> {
                    refreshCachedUrisAfterMigrationAsync();
                    updateCacheLocationButton();
                    updateUninstallCleanupButton();
                    statusView.setText("缓存位置已更新");
                    String cleanup = result.retainedInOldLocation > 0
                        ? "；外部旧文件夹仍有 " + result.retainedInOldLocation + " 个文件未能删除"
                        : "；外部旧文件已删除";
                    toast(result.changed
                        ? "已迁回应用内部，共迁移并校验 " + result.copied + " 个文件" + cleanup + "；卸载时会清理"
                        : "当前已经使用卸载时清理的位置");
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    statusView.setText("缓存迁回失败");
                    toast("迁回应用内部失败，原文件未删除：" + error.getMessage());
                });
            }
        }).start();
    }

    private void updateCacheLocationButton() {
        if (cacheLocationButton != null) cacheLocationButton.setText(CacheStorage.description(this));
    }

    private void normalizePlaylistCacheFilesAsync() {
        List<Song> snapshot = new ArrayList<>();
        for (Playlist playlist : new ArrayList<>(playlists)) {
            if (playlist == null) continue;
            snapshot.addAll(new ArrayList<>(playlist.songs));
        }
        new Thread(() -> {
            Set<String> seen = new HashSet<>();
            for (Song song : snapshot) {
                if (song == null || !song.isNetworkCatalog()) continue;
                String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
                if (key.isEmpty() || !seen.add(key)) continue;
                NetworkMediaCache.normalizeCacheFiles(this, song.catalogJson);
            }
            runOnUiThread(this::refreshCachedUrisAfterMigrationAsync);
        }).start();
    }

    /**
     * Never queries the Storage Access Framework provider on the main thread.
     * Xiaomi/Android 16 may block a document-tree query for more than ten seconds.
     */
    private void refreshCachedUrisAfterMigrationAsync() {
        List<Song> snapshot = new ArrayList<>();
        for (Playlist playlist : new ArrayList<>(playlists)) {
            if (playlist == null) continue;
            snapshot.addAll(new ArrayList<>(playlist.songs));
        }
        snapshot.addAll(new ArrayList<>(searchResults));
        Song currentSongSnapshot = currentSong;
        if (currentSongSnapshot != null) snapshot.add(currentSongSnapshot);

        new Thread(() -> {
            Set<Song> visited = Collections.newSetFromMap(
                new java.util.IdentityHashMap<Song, Boolean>());
            for (Song song : snapshot) refreshCachedUri(song, visited);
            runOnUiThread(() -> {
                savePlaylists();
                renderCurrentPlaylist();
                renderResults();
            });
        }, "cache-uri-refresh").start();
    }

    private void refreshCachedUri(Song song, Set<Song> visited) {
        if (song == null || !song.isNetworkCatalog() || !visited.add(song)) return;
        String key = NetworkMediaCache.cacheKeyForCatalog(song.catalogJson);
        String uri = key.isEmpty() ? "" : CacheStorage.findAudioUri(this, key);
        song.cachedUri = uri;
        if (!uri.isEmpty()) song.uri = uri;
    }

    private String uninstallCleanupSettingText() {
        return "卸载软件时清理缓存："
            + (CacheStorage.uninstallCleanupEnabled(this) ? "开启" : "关闭");
    }

    private void updateUninstallCleanupButton() {
        if (uninstallCleanupButton != null) {
            uninstallCleanupButton.setText(uninstallCleanupSettingText());
        }
    }

    private void toggleUninstallCleanupSetting() {
        if (CacheStorage.uninstallCleanupEnabled(this)) {
            new AlertDialog.Builder(this)
                .setTitle("卸载软件时清理缓存")
                .setMessage("当前为开启状态，缓存位于应用内部。关闭后需要选择一个外部总文件夹，"
                    + "歌曲、歌词和歌曲信息会迁移过去，卸载软件后仍然保留。")
                .setPositiveButton("选择保留文件夹", (dialog, which) -> requestFileManagementThenChooseCacheFolder())
                .setNegativeButton("取消", null)
                .show();
        } else {
            new AlertDialog.Builder(this)
                .setTitle("卸载软件时清理缓存")
                .setMessage("开启后会先把全部缓存迁回应用内部，并删除所选外部文件夹中的对应缓存文件。"
                    + "以后卸载软件时，Android 会一并清理这些缓存。")
                .setPositiveButton("迁回并开启", (dialog, which) -> migrateCacheToInternal())
                .setNegativeButton("取消", null)
                .show();
        }
    }

    private void showLocalAudioImportOptions() {
        new AlertDialog.Builder(this)
            .setTitle("导入本地歌曲")
            .setItems(new CharSequence[] {"选择歌曲", "选择文件夹"}, (dialog, which) -> {
                if (which == 0) chooseAudioFiles();
                else chooseAudioFolder();
            })
            .setNegativeButton("取消", null)
            .show();
    }

    private void showPlaylistImportOptions() {
        new AlertDialog.Builder(this)
            .setTitle("导入歌单")
            .setItems(new CharSequence[] {"CSV 文件", "歌单链接"}, (dialog, which) -> {
                if (which == 0) openPlaylistCsvImport();
                else promptImportPlaylistLink();
            })
            .setNegativeButton("取消", null)
            .show();
    }

    private void chooseBackgroundImage() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("image/*");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_BACKGROUND_IMAGE);
    }

    private void chooseAudioFiles() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("audio/*");
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_AUDIO_FILES);
    }

    private void chooseAudioFolder() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_AUDIO_FOLDER);
    }

    private void promptImportPlaylistLink() {
        promptText("\u5bfc\u5165\u6b4c\u5355\u94fe\u63a5", "\u7c98\u8d34\u7f51\u6613 / \u9177\u72d7 / \u6c7d\u6c34\u6b4c\u5355\u94fe\u63a5", "", value -> {
            String source = sourceFromPlaylistUrl(value);
            toast("\u6b63\u5728\u5bfc\u5165\uff1a" + source);
            new Thread(() -> {
                Playlist imported = importPlaylistFromUrl(value, source);
                runOnUiThread(() -> {
                    if (imported.songs.isEmpty()) {
                        toast("\u6b4c\u5355\u5bfc\u5165\u5931\u8d25\u6216\u6ca1\u6709\u8bfb\u5230\u6b4c\u66f2");
                        return;
                    }
                    dedupePlaylist(imported);
                    playlists.add(imported);
                    currentPlaylistIndex = playlists.size() - 1;
                    savePlaylists();
                    renderCurrentPlaylist();
                    showPlaylistPage();
                    toast("\u5df2\u5bfc\u5165 " + imported.songs.size() + " \u9996\uff1a" + imported.name);
                });
            }).start();
        });
    }

    private Playlist importPlaylistFromUrl(String url, String source) {
        String sourceCode = sourceCodeFromPlaylistUrl(url);
        if ("netease".equals(sourceCode)) return importNeteasePlaylist(url);
        if ("qq".equals(sourceCode)) return importQQPlaylist(url);
        if ("kuwo".equals(sourceCode)) return importKuwoPlaylist(url);
        if ("kugou".equals(sourceCode)) return importKugouPlaylist(url);
        if ("migu".equals(sourceCode)) return importMiguPlaylist(url);
        return new Playlist(source + "歌单");
    }

    private Playlist importNeteasePlaylist(String urlText) {
        String playlistId = firstMatch(urlText, "(?:id=|playlist/)(\\d+)");
        Playlist imported = new Playlist("网易云歌单 " + playlistId);
        if (playlistId.isEmpty()) return imported;
        try {
            JSONObject payload = httpJson(
                "https://music.163.com/api/v6/playlist/detail?id=" + playlistId,
                "https://music.163.com/"
            );
            JSONObject playlist = payload.optJSONObject("playlist");
            if (playlist == null) playlist = payload.optJSONObject("result");
            if (playlist == null) return imported;
            String name = playlist.optString("name", "");
            if (!name.isEmpty()) imported.name = name;
            JSONArray tracks = playlist.optJSONArray("tracks");
            if (tracks != null) appendNeteasePlaylistTracks(imported, tracks);
            JSONArray trackIds = playlist.optJSONArray("trackIds");
            if (trackIds != null && imported.songs.size() < trackIds.length()) {
                List<String> ids = new ArrayList<>();
                for (int i = 0; i < trackIds.length() && ids.size() < MAX_IMPORT_COUNT; i++) {
                    JSONObject item = trackIds.optJSONObject(i);
                    if (item != null && item.optLong("id", 0) > 0) ids.add(String.valueOf(item.optLong("id")));
                }
                fetchNeteaseSongDetails(imported, ids);
            }
        } catch (Exception ignored) {
        }
        return imported;
    }

    private Playlist importQQPlaylist(String urlText) {
        String playlistId = firstMatch(urlText, "(?:disstid=|playlist/)(\\d+)");
        Playlist imported = new Playlist("QQ音乐歌单 " + playlistId);
        if (playlistId.isEmpty()) return imported;
        try {
            JSONObject payload = httpJson(
                "https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg"
                    + "?type=1&json=1&utf8=1&onlysong=0&format=json&disstid=" + playlistId,
                "https://y.qq.com/"
            );
            JSONArray cdlist = payload.optJSONArray("cdlist");
            JSONObject playlist = cdlist == null || cdlist.length() == 0 ? null : cdlist.optJSONObject(0);
            if (playlist == null) return imported;
            String name = playlist.optString("dissname", "");
            if (!name.isEmpty()) imported.name = name;
            JSONArray songs = playlist.optJSONArray("songlist");
            if (songs == null) return imported;
            for (int i = 0; i < songs.length() && imported.songs.size() < MAX_IMPORT_COUNT; i++) {
                JSONObject item = songs.optJSONObject(i);
                if (item == null) continue;
                String id = firstNonEmpty(item.optString("songmid"), item.optString("mid"), item.optString("songid"));
                String title = firstNonEmpty(item.optString("songname"), item.optString("name"));
                String artist = namesFromArray(item.optJSONArray("singer"), "name");
                String album = firstNonEmpty(item.optString("albumname"), item.optString("album"));
                int duration = item.optInt("interval", 0);
                Song song = createNetworkCatalogSong(id, title, artist, album, duration, "qq");
                if (!containsSong(imported, song)) imported.songs.add(song);
            }
        } catch (Exception ignored) {
        }
        return imported;
    }

    private Playlist importKuwoPlaylist(String urlText) {
        String playlistId = firstMatch(urlText, "(?:pid=|playlist/|play_detail/)(\\d+)");
        Playlist imported = new Playlist("酷我歌单 " + playlistId);
        if (playlistId.isEmpty()) return imported;
        try {
            JSONObject payload = httpJson(
                "http://nplserver.kuwo.cn/pl.svc?op=getlistinfo&pn=0&rn=1000&encode=utf-8"
                    + "&keyset=pl2012&identity=kuwo&pid=" + playlistId,
                "http://www.kuwo.cn/"
            );
            String name = payload.optString("title", payload.optString("name", ""));
            if (!name.isEmpty()) imported.name = name;
            JSONArray songs = payload.optJSONArray("musiclist");
            if (songs == null) songs = payload.optJSONArray("abslist");
            if (songs == null) return imported;
            for (int i = 0; i < songs.length() && imported.songs.size() < MAX_IMPORT_COUNT; i++) {
                JSONObject item = songs.optJSONObject(i);
                if (item == null) continue;
                String id = firstNonEmpty(item.optString("id"), item.optString("rid"), item.optString("MUSICRID"), item.optString("DC_TARGETID"));
                if (!id.isEmpty() && !id.startsWith("MUSIC_")) id = "MUSIC_" + id;
                String title = cleanHtml(firstNonEmpty(item.optString("name"), item.optString("SONGNAME")));
                String artist = cleanHtml(firstNonEmpty(item.optString("artist"), item.optString("ARTIST")));
                String album = cleanHtml(firstNonEmpty(item.optString("album"), item.optString("ALBUM")));
                Song song = createNetworkCatalogSong(id, title, artist, album, 0, "kuwo");
                if (!containsSong(imported, song)) imported.songs.add(song);
            }
        } catch (Exception ignored) {
        }
        return imported;
    }

    private Playlist importKugouPlaylist(String urlText) {
        String playlistId = firstMatch(urlText, "(?:special/single/|specialid=|id=)(\\d+)");
        Playlist imported = new Playlist("酷狗歌单 " + playlistId);
        if (playlistId.isEmpty()) return imported;
        try {
            JSONObject payload = httpJson("https://m.kugou.com/plist/list/" + playlistId + "?json=true", "https://m.kugou.com/");
            JSONObject info = payload.optJSONObject("info");
            if (info != null && !info.optString("specialname", "").isEmpty()) imported.name = info.optString("specialname");
            JSONArray songs = null;
            if (info != null) songs = info.optJSONArray("list");
            JSONObject list = payload.optJSONObject("list");
            if (songs == null && list != null) songs = list.optJSONArray("list");
            if (songs != null) appendKugouJsonSongs(imported, songs);
        } catch (Exception ignored) {
        }
        if (!imported.songs.isEmpty()) return imported;
        try {
            String html = httpText("https://www.kugou.com/yy/special/single/" + playlistId + ".html", "https://www.kugou.com/");
            java.util.regex.Matcher matcher = java.util.regex.Pattern
                .compile("\\\"(?:hash|FileHash)\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"[^{}]{0,800}?\\\"(?:songname|SongName)\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"[^{}]{0,800}?\\\"(?:singername|SingerName)\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"")
                .matcher(html);
            while (matcher.find() && imported.songs.size() < MAX_IMPORT_COUNT) {
                Song song = createNetworkCatalogSong(matcher.group(1), matcher.group(2), matcher.group(3), "", 0, "kugou");
                if (!containsSong(imported, song)) imported.songs.add(song);
            }
        } catch (Exception ignored) {
        }
        return imported;
    }

    private void appendKugouJsonSongs(Playlist imported, JSONArray songs) {
        for (int i = 0; i < songs.length() && imported.songs.size() < MAX_IMPORT_COUNT; i++) {
            JSONObject item = songs.optJSONObject(i);
            if (item == null) continue;
            String id = firstNonEmpty(item.optString("hash"), item.optString("FileHash"), item.optString("audio_id"));
            String title = firstNonEmpty(item.optString("songname"), item.optString("SongName"), item.optString("filename"));
            String artist = firstNonEmpty(item.optString("singername"), item.optString("SingerName"), item.optString("singer"));
            if (title.contains(" - ") && (artist.isEmpty() || "未知歌手".equals(artist))) {
                String[] parts = title.split(" - ", 2);
                artist = parts[0];
                title = parts[1];
            }
            Song song = createNetworkCatalogSong(id, title, artist, "", item.optInt("duration", 0), "kugou");
            if (!containsSong(imported, song)) imported.songs.add(song);
        }
    }

    private Playlist importMiguPlaylist(String urlText) {
        String playlistId = firstMatch(urlText, "(?:playlistId=|id=|playlist/)([A-Za-z0-9]+)");
        Playlist imported = new Playlist("咪咕歌单 " + playlistId);
        if (playlistId.isEmpty()) return imported;
        try {
            JSONObject payload = httpJson(
                "https://app.c.nf.migu.cn/MIGUM3.0/v1.0/content/queryplaylistinfo.do?playListId=" + playlistId,
                "https://music.migu.cn/"
            );
            JSONObject data = payload.optJSONObject("data");
            if (data == null) data = payload;
            String name = data.optString("playlistName", data.optString("name", ""));
            if (!name.isEmpty()) imported.name = name;
            JSONArray songs = data.optJSONArray("contentList");
            if (songs == null) songs = data.optJSONArray("songList");
            if (songs == null) return imported;
            for (int i = 0; i < songs.length() && imported.songs.size() < MAX_IMPORT_COUNT; i++) {
                JSONObject item = songs.optJSONObject(i);
                if (item == null) continue;
                String id = firstNonEmpty(item.optString("copyrightId"), item.optString("contentId"), item.optString("songId"));
                String title = firstNonEmpty(item.optString("songName"), item.optString("name"));
                String artist = firstNonEmpty(item.optString("singerName"), item.optString("singer"));
                String album = firstNonEmpty(item.optString("albumName"), item.optString("album"));
                Song song = createNetworkCatalogSong(id, title, artist, album, item.optInt("duration", 0), "migu");
                if (!containsSong(imported, song)) imported.songs.add(song);
            }
        } catch (Exception ignored) {
        }
        return imported;
    }

    private void appendNeteasePlaylistTracks(Playlist imported, JSONArray tracks) {
        for (int i = 0; i < tracks.length() && imported.songs.size() < MAX_IMPORT_COUNT; i++) {
            JSONObject item = tracks.optJSONObject(i);
            if (item == null) continue;
            Song song = neteaseSongFromJson(item);
            if (!containsSong(imported, song)) imported.songs.add(song);
        }
    }

    private void fetchNeteaseSongDetails(Playlist imported, List<String> ids) {
        for (int start = 0; start < ids.size() && imported.songs.size() < MAX_IMPORT_COUNT; start += 200) {
            int end = Math.min(ids.size(), start + 200);
            try {
                String joined = TextUtils.join(",", ids.subList(start, end));
                JSONObject payload = httpJson(
                    "https://music.163.com/api/song/detail?ids=[" + joined + "]",
                    "https://music.163.com/"
                );
                JSONArray songs = payload.optJSONArray("songs");
                if (songs != null) appendNeteasePlaylistTracks(imported, songs);
            } catch (Exception ignored) {
            }
        }
    }

    private Song neteaseSongFromJson(JSONObject item) {
        String title = item.optString("name", "未知歌曲");
        JSONArray artists = item.optJSONArray("artists");
        if (artists == null) artists = item.optJSONArray("ar");
        String artist = artistsFromNetease(artists);
        String id = item.optString("id", "");
        JSONObject albumObject = item.optJSONObject("album");
        if (albumObject == null) albumObject = item.optJSONObject("al");
        String album = albumObject == null ? "" : albumObject.optString("name", "");
        int duration = item.optInt("duration", item.optInt("dt", 0));
        if (duration > 1000) duration /= 1000;
        return createNetworkCatalogSong(id, title, artist, album, duration, "netease");
    }

    private Song createNetworkCatalogSong(String id, String title, String artist, String album, int duration, String sourceCode) {
        return new Song(
            firstNonEmpty(title, "未知歌曲"),
            firstNonEmpty(artist, "未知歌手"),
            sourceLabelFromCode(sourceCode),
            "",
            "",
            buildCatalogJson(sourceCode, id, title, artist, album, duration),
            ""
        );
    }

    private String buildCatalogJson(String sourceCode, String id, String title, String artist, String album, int duration) {
        if (id == null || id.trim().isEmpty()) return "";
        try {
            JSONObject catalog = new JSONObject();
            catalog.put("id", id.trim());
            catalog.put("name", title == null ? "" : title);
            catalog.put("artist", artist == null ? "" : artist);
            catalog.put("album", album == null ? "" : album);
            catalog.put("duration", Math.max(0, duration));
            catalog.put("source", sourceCode == null ? "" : sourceCode);
            catalog.put("url", "");
            JSONObject extra = new JSONObject();
            extra.put("song_id", id.trim());
            extra.put("catalog_source", sourceCode == null ? "" : sourceCode);
            catalog.put("extra", extra);
            return catalog.toString();
        } catch (JSONException ignored) {
            return "";
        }
    }

    private String sourceCodeFromPlaylistUrl(String url) {
        String lower = url == null ? "" : url.toLowerCase();
        if (lower.contains("163.com") || lower.contains("netease")) return "netease";
        if (lower.contains("y.qq.com") || lower.contains("qq.com")) return "qq";
        if (lower.contains("kugou")) return "kugou";
        if (lower.contains("kuwo")) return "kuwo";
        if (lower.contains("migu")) return "migu";
        if (lower.contains("qishui") || lower.contains("douyin") || lower.contains("music.douyin")) return "soda";
        return "";
    }

    private String sourceLabelFromCode(String sourceCode) {
        if ("netease".equals(sourceCode)) return "网易云";
        if ("qq".equals(sourceCode)) return "QQ音乐";
        if ("kugou".equals(sourceCode)) return "酷狗";
        if ("kuwo".equals(sourceCode)) return "酷我";
        if ("migu".equals(sourceCode)) return "咪咕";
        if ("soda".equals(sourceCode)) return "汽水";
        return "外部来源";
    }

    private String firstMatch(String value, String regex) {
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile(regex).matcher(value == null ? "" : value);
        return matcher.find() ? matcher.group(1) : "";
    }

    private String firstNonEmpty(String... values) {
        if (values == null) return "";
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) return value.trim();
        }
        return "";
    }

    private String namesFromArray(JSONArray array, String key) {
        if (array == null) return "未知歌手";
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < array.length(); i++) {
            JSONObject item = array.optJSONObject(i);
            if (item == null) continue;
            String name = item.optString(key, "");
            if (name.isEmpty()) continue;
            if (builder.length() > 0) builder.append(" / ");
            builder.append(name);
        }
        return builder.length() == 0 ? "未知歌手" : builder.toString();
    }

    private String httpText(String urlText, String referer) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) new URL(urlText).openConnection();
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(10000);
        connection.setRequestProperty("User-Agent", "Mozilla/5.0");
        connection.setRequestProperty("Referer", referer);
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(connection.getInputStream(), "UTF-8"))) {
            StringBuilder builder = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) builder.append(line).append('\n');
            return builder.toString();
        } finally {
            connection.disconnect();
        }
    }

    private String playlistIdFromUrl(String urlText) {
        return firstMatch(urlText, "(?:id=|playlist/)(\\d+)");
    }

    private String sourceFromPlaylistUrl(String url) {
        return sourceLabelFromCode(sourceCodeFromPlaylistUrl(url));
    }


    private void showBuiltInBackgroundPicker() {
        boolean dual = getResources().getBoolean(R.bool.dual_background_selector);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(12), dp(8), dp(12), dp(8));
        final AlertDialog[] holder = new AlertDialog[1];
        addBackgroundPreview(root, "新版默认背景", R.drawable.default_background,
            BACKGROUND_MODE_DEFAULT, holder);
        if (dual) {
            addBackgroundPreview(root, "旧版默认背景", R.drawable.default_background_legacy,
                BACKGROUND_MODE_LEGACY, holder);
        }
        holder[0] = new AlertDialog.Builder(this)
            .setTitle("选择默认背景")
            .setView(root)
            .setNegativeButton("取消", null)
            .create();
        holder[0].show();
    }

    private void addBackgroundPreview(LinearLayout root, String label, int drawableId,
                                      String mode, AlertDialog[] holder) {
        TextView title = new TextView(this);
        title.setText(label);
        title.setTextSize(15);
        title.setTextColor(Color.DKGRAY);
        title.setGravity(Gravity.CENTER);
        root.addView(title);
        ImageView preview = new ImageView(this);
        preview.setScaleType(ImageView.ScaleType.CENTER_CROP);
        preview.setImageResource(drawableId);
        preview.setOnClickListener(view -> {
            selectBuiltInBackground(mode);
            if (holder[0] != null) holder[0].dismiss();
        });
        attachSubtlePressFeedback(preview);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(178));
        params.setMargins(0, dp(4), 0, dp(10));
        root.addView(preview, params);
    }

    private void showLauncherIconPicker() {
        if (!getResources().getBoolean(R.bool.icon_selector_enabled)) return;
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.HORIZONTAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(dp(12), dp(12), dp(12), dp(12));
        final AlertDialog[] holder = new AlertDialog[1];
        root.addView(buildIconPreview("经典图标", R.mipmap.ic_launcher_classic,
            "classic", holder), new LinearLayout.LayoutParams(0, dp(170), 1));
        root.addView(buildIconPreview("新图标", R.mipmap.ic_launcher_new,
            "new", holder), new LinearLayout.LayoutParams(0, dp(170), 1));
        holder[0] = new AlertDialog.Builder(this)
            .setTitle("选择桌面图标")
            .setView(root)
            .setNegativeButton("取消", null)
            .create();
        holder[0].show();
    }

    private View buildIconPreview(String label, int iconId, String mode, AlertDialog[] holder) {
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setGravity(Gravity.CENTER);
        ImageView image = new ImageView(this);
        image.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        image.setImageResource(iconId);
        column.addView(image, new LinearLayout.LayoutParams(dp(112), dp(112)));
        TextView text = new TextView(this);
        text.setText(label);
        text.setTextColor(Color.DKGRAY);
        text.setTextSize(15);
        text.setGravity(Gravity.CENTER);
        column.addView(text);
        column.setOnClickListener(view -> {
            switchLauncherIcon(mode);
            if (holder[0] != null) holder[0].dismiss();
        });
        attachSubtlePressFeedback(column);
        return column;
    }

    private void switchLauncherIcon(String mode) {
        if (!getResources().getBoolean(R.bool.icon_selector_enabled)) return;
        boolean useNew = "new".equals(mode);
        PackageManager manager = getPackageManager();
        ComponentName classic = new ComponentName(this, getPackageName() + ".LauncherClassic");
        ComponentName newer = new ComponentName(this, getPackageName() + ".LauncherNew");
        ComponentName enabled = useNew ? newer : classic;
        ComponentName disabled = useNew ? classic : newer;
        manager.setComponentEnabledSetting(enabled,
            PackageManager.COMPONENT_ENABLED_STATE_ENABLED,
            PackageManager.DONT_KILL_APP);
        manager.setComponentEnabledSetting(disabled,
            PackageManager.COMPONENT_ENABLED_STATE_DISABLED,
            PackageManager.DONT_KILL_APP);
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit().putString(KEY_LAUNCHER_ICON, useNew ? "new" : "classic").apply();
        toast("桌面图标已切换，部分桌面可能需要几秒刷新");
    }

    private void resetBackgroundImage() {
        selectBuiltInBackground(BACKGROUND_MODE_DEFAULT);
    }

    private void selectBuiltInBackground(String mode) {
        boolean dual = getResources().getBoolean(R.bool.dual_background_selector);
        String normalized = dual && BACKGROUND_MODE_LEGACY.equals(mode)
            ? BACKGROUND_MODE_LEGACY
            : BACKGROUND_MODE_DEFAULT;
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .remove(KEY_BACKGROUND_URI)
            .putString(KEY_BACKGROUND_MODE, normalized)
            .apply();
        applySavedBackground();
        toast(dual && BACKGROUND_MODE_LEGACY.equals(normalized)
            ? "\u5df2\u5207\u6362\u4e3a\u65e7\u7248\u9ed8\u8ba4\u80cc\u666f"
            : "\u5df2\u6062\u590d\u9ed8\u8ba4\u80cc\u666f");
    }

    private void applySavedBackground() {
        if (backgroundView == null) return;
        SharedPreferences preferences = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String rawUri = preferences.getString(KEY_BACKGROUND_URI, "");
        if (rawUri != null && !rawUri.isEmpty()) {
            try {
                backgroundView.setImageURI(Uri.parse(rawUri));
                return;
            } catch (Exception ignored) {
            }
        }
        boolean dual = getResources().getBoolean(R.bool.dual_background_selector);
        String mode = preferences.getString(KEY_BACKGROUND_MODE, BACKGROUND_MODE_DEFAULT);
        backgroundView.setImageResource(dual && BACKGROUND_MODE_LEGACY.equals(mode)
            ? R.drawable.default_background_legacy
            : R.drawable.default_background);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_CACHE_FOLDER && resultCode == RESULT_OK && data != null && data.getData() != null) {
            migrateCacheToDocumentTree(data.getData());
        } else if (requestCode == REQUEST_EXPORT_PLAYLIST && resultCode == RESULT_OK && data != null && data.getData() != null) {
            int index = pendingExportPlaylistIndex;
            pendingExportPlaylistIndex = -1;
            if (index >= 0 && index < playlists.size()) {
                writePlaylistCsv(data.getData(), playlists.get(index));
            }
        } else if (requestCode == REQUEST_IMPORT_PLAYLIST_CSV && resultCode == RESULT_OK && data != null && data.getData() != null) {
            importPlaylistCsv(data.getData());
        } else if (requestCode == REQUEST_BACKGROUND_IMAGE && resultCode == RESULT_OK && data != null && data.getData() != null) {
            Uri uri = data.getData();
            try {
                getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            } catch (Exception ignored) {
            }
            getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .putString(KEY_BACKGROUND_URI, uri.toString())
                .putString(KEY_BACKGROUND_MODE, BACKGROUND_MODE_CUSTOM)
                .apply();
            applySavedBackground();
            toast("\u80cc\u666f\u5df2\u66f4\u65b0");
        } else if (requestCode == REQUEST_AUDIO_FILES && resultCode == RESULT_OK && data != null) {
            int added = importAudioResult(data);
            if (added > 0) {
                currentPlaylistIndex = 0;
                dedupePlaylist(localPlaylist());
                savePlaylists();
                renderCurrentPlaylist();
            }
            toast("\u5df2\u5bfc\u5165 " + added + " \u9996\u672c\u5730\u6b4c\u66f2");
        } else if (requestCode == REQUEST_AUDIO_FOLDER && resultCode == RESULT_OK && data != null && data.getData() != null) {
            Uri treeUri = data.getData();
            try {
                getContentResolver().takePersistableUriPermission(treeUri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            } catch (Exception ignored) {
            }
            int added = importAudioFolder(treeUri);
            if (added > 0) {
                currentPlaylistIndex = 0;
                dedupePlaylist(localPlaylist());
                savePlaylists();
                renderCurrentPlaylist();
            }
            toast("\u5df2\u4ece\u6587\u4ef6\u5939\u5bfc\u5165 " + added + " \u9996");
        }
    }


    private void openPlaylistCsvImport() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[] {
            "text/csv",
            "text/comma-separated-values",
            "text/plain",
            "application/csv",
            "application/vnd.ms-excel"
        });
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_IMPORT_PLAYLIST_CSV);
    }

    private void importPlaylistCsv(Uri uri) {
        try {
            getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } catch (Exception ignored) {
        }
        String defaultName = stripExtension(displayNameForUri(uri));
        new Thread(() -> {
            String csvText = readTextUri(uri);
            Playlist imported = parsePlaylistCsv(csvText, defaultName);
            runOnUiThread(() -> {
                if (imported.songs.isEmpty()) {
                    toast("CSV\u6b4c\u5355\u6ca1\u6709\u8bfb\u5230\u53ef\u5bfc\u5165\u7684\u6b4c\u66f2");
                    return;
                }
                dedupePlaylist(imported);
                playlists.add(imported);
                currentPlaylistIndex = playlists.size() - 1;
                savePlaylists();
                renderCurrentPlaylist();
                toast("\u5df2\u5bfc\u5165CSV\u6b4c\u5355\uff1a" + imported.name + "  " + imported.songs.size() + " \u9996");
            });
        }).start();
    }

    private Playlist parsePlaylistCsv(String csvText, String defaultName) {
        Playlist imported = new Playlist(firstNonEmpty(defaultName, "CSV\u6b4c\u5355"));
        List<List<String>> rows = parseCsvRows(csvText);
        if (rows.isEmpty()) return imported;
        Map<String, Integer> columns = playlistCsvColumns(rows.get(0));
        int start = hasPlaylistCsvHeader(columns) ? 1 : 0;
        for (int i = start; i < rows.size() && imported.songs.size() < MAX_IMPORT_COUNT; i++) {
            List<String> row = rows.get(i);
            String title = csvValue(row, columns, "title", 0);
            String artist = csvValue(row, columns, "artist", 1);
            String album = csvValue(row, columns, "album", 2);
            int duration = csvInt(csvValue(row, columns, "duration", 3));
            String sourceLabel = csvValue(row, columns, "sourceLabel", 4);
            String sourceCode = csvSourceCode(csvValue(row, columns, "sourceCode", 5), sourceLabel);
            String songId = csvValue(row, columns, "songId", 6);
            String lyricLabel = csvValue(row, columns, "lyricLabel", 7);
            if (title.trim().isEmpty()) continue;
            if (artist.trim().isEmpty()) artist = "\u672a\u77e5\u6b4c\u624b";
            if (sourceLabel.trim().isEmpty()) sourceLabel = sourceLabelFromCode(sourceCode);
            String catalogJson = buildCatalogJson(sourceCode, songId, title, artist, album, duration);
            Song song = new Song(title, artist, sourceLabel, "", "", catalogJson, "");
            song.lyricLabel = lyricLabel;
            if (!containsSong(imported, song)) imported.songs.add(song);
        }
        return imported;
    }

    private List<List<String>> parseCsvRows(String csvText) {
        List<List<String>> rows = new ArrayList<>();
        if (csvText == null || csvText.trim().isEmpty()) return rows;
        List<String> row = new ArrayList<>();
        StringBuilder cell = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < csvText.length(); i++) {
            char ch = csvText.charAt(i);
            if (quoted) {
                if (ch == '"') {
                    if (i + 1 < csvText.length() && csvText.charAt(i + 1) == '"') {
                        cell.append('"');
                        i++;
                    } else {
                        quoted = false;
                    }
                } else {
                    cell.append(ch);
                }
            } else if (ch == '"') {
                quoted = true;
            } else if (ch == ',') {
                row.add(cell.toString());
                cell.setLength(0);
            } else if (ch == '\n') {
                row.add(cell.toString());
                rows.add(row);
                row = new ArrayList<>();
                cell.setLength(0);
            } else if (ch != '\r') {
                cell.append(ch);
            }
        }
        if (cell.length() > 0 || !row.isEmpty()) {
            row.add(cell.toString());
            rows.add(row);
        }
        return rows;
    }

    private Map<String, Integer> playlistCsvColumns(List<String> header) {
        Map<String, Integer> columns = new HashMap<>();
        for (int i = 0; header != null && i < header.size(); i++) {
            String key = normalizeCsvHeader(header.get(i));
            if (key.contains("歌曲id") || key.equals("id") || key.equals("songid")) {
                columns.put("songId", i);
            } else if (key.equals("歌名") || key.equals("歌曲名") || key.equals("歌曲标题")
                || key.equals("title") || key.equals("name")) {
                columns.put("title", i);
            } else if (key.contains("歌手") || key.contains("演唱") || key.equals("artist") || key.equals("singer")) {
                columns.put("artist", i);
            } else if (key.contains("专辑") || key.equals("album")) {
                columns.put("album", i);
            } else if (key.contains("时长") || key.equals("duration") || key.equals("time")) {
                columns.put("duration", i);
            } else if (key.contains("平台代码") || key.equals("sourcecode")) {
                columns.put("sourceCode", i);
            } else if (key.contains("平台") || key.equals("source") || key.equals("platform")) {
                columns.put("sourceLabel", i);
            } else if (key.contains("歌词") || key.equals("lyric") || key.equals("lyriclabel") || key.equals("lyricversion")) {
                columns.put("lyricLabel", i);
            }
        }
        return columns;
    }

    private boolean hasPlaylistCsvHeader(Map<String, Integer> columns) {
        return columns.containsKey("title") || columns.containsKey("artist") || columns.containsKey("songId");
    }

    private String normalizeCsvHeader(String value) {
        if (value == null) return "";
        return value.replace("\ufeff", "").trim().toLowerCase(Locale.ROOT)
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
            .replace("\uff08", "(")
            .replace("\uff09", ")");
    }

    private String csvValue(List<String> row, Map<String, Integer> columns, String key, int fallback) {
        int index = columns.containsKey(key) ? columns.get(key) : fallback;
        if (row == null || index < 0 || index >= row.size()) return "";
        String value = row.get(index);
        return value == null ? "" : value.replace("\ufeff", "").trim();
    }

    private int csvInt(String value) {
        try {
            return (int) Math.max(0, Math.round(Double.parseDouble(value.trim())));
        } catch (Exception ignored) {
            return 0;
        }
    }

    private String csvSourceCode(String sourceCode, String sourceLabel) {
        String raw = sourceCode == null ? "" : sourceCode.trim().toLowerCase();
        if (!raw.isEmpty()) return raw;
        String label = sourceLabel == null ? "" : sourceLabel.trim();
        String lower = label.toLowerCase();
        if (label.contains("\u7f51\u6613") || lower.contains("netease")) return "netease";
        if (label.contains("QQ") || lower.contains("qq")) return "qq";
        if (label.contains("\u9177\u72d7") || lower.contains("kugou")) return "kugou";
        if (label.contains("\u9177\u6211") || lower.contains("kuwo")) return "kuwo";
        if (label.contains("\u54aa\u5495") || lower.contains("migu")) return "migu";
        if (label.contains("\u6c7d\u6c34") || lower.contains("soda") || lower.contains("qishui")) return "soda";
        if (label.contains("5sing") || lower.contains("fivesing")) return "fivesing";
        if (label.contains("\u5343\u5343") || lower.contains("qianqian")) return "qianqian";
        if (lower.contains("jamendo")) return "jamendo";
        if (lower.contains("joox")) return "joox";
        if (lower.contains("apple")) return "apple";
        return "";
    }

    private void exportCurrentPlaylistCsv() {
        Playlist playlist = currentPlaylist();
        pendingExportPlaylistIndex = currentPlaylistIndex;
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("text/csv");
        String safeName = playlist.name.replaceAll("[\\\\/:*?\"<>|]", "_").trim();
        if (safeName.isEmpty()) safeName = "歌单";
        intent.putExtra(Intent.EXTRA_TITLE, safeName + ".csv");
        startActivityForResult(intent, REQUEST_EXPORT_PLAYLIST);
    }

    private void writePlaylistCsv(Uri uri, Playlist playlist) {
        if (uri == null || playlist == null) return;
        try (OutputStream output = getContentResolver().openOutputStream(uri);
             OutputStreamWriter writer = new OutputStreamWriter(output, "UTF-8")) {
            writer.write('\ufeff');
            writer.write("歌名,歌手,专辑,时长秒,平台,平台代码,歌曲ID,歌词版本\r\n");
            for (Song song : playlist.songs) {
                String album = "";
                String sourceCode = "";
                String songId = "";
                long duration = 0;
                if (song.catalogJson != null && !song.catalogJson.trim().isEmpty()) {
                    try {
                        JSONObject catalog = new JSONObject(song.catalogJson);
                        album = catalog.optString("album", "");
                        sourceCode = catalog.optString("source", "");
                        songId = catalog.optString("id", "");
                        duration = catalog.optLong("duration", 0);
                        if (duration > 10000) duration /= 1000;
                    } catch (Exception ignored) {
                    }
                }
                writer.write(csvCell(song.title) + ","
                    + csvCell(song.artist) + ","
                    + csvCell(album) + ","
                    + duration + ","
                    + csvCell(song.source) + ","
                    + csvCell(sourceCode) + ","
                    + csvCell(songId) + ","
                    + csvCell(song.lyricLabel) + "\r\n");
            }
            writer.flush();
            toast("已导出歌单：" + playlist.name);
        } catch (Exception error) {
            toast("导出失败：" + error.getMessage());
        }
    }

    private String csvCell(String value) {
        String safe = value == null ? "" : value.replace("\"", "\"\"");
        return "\"" + safe + "\"";
    }

    private int importAudioResult(Intent data) {
        int added = 0;
        ClipData clipData = data.getClipData();
        if (clipData != null) {
            for (int i = 0; i < clipData.getItemCount() && added < MAX_IMPORT_COUNT; i++) {
                if (importAudioUri(clipData.getItemAt(i).getUri())) added++;
            }
        } else if (data.getData() != null && importAudioUri(data.getData())) {
            added++;
        }
        return added;
    }

    private int importAudioFolder(Uri treeUri) {
        String treeId = DocumentsContract.getTreeDocumentId(treeUri);
        Uri childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, treeId);
        List<FolderEntry> audioEntries = new ArrayList<>();
        Map<String, String> lyricsByBase = new HashMap<>();
        try (Cursor cursor = getContentResolver().query(
            childrenUri,
            new String[] {
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE
            },
            null,
            null,
            null
        )) {
            if (cursor == null) return 0;
            while (cursor.moveToNext()) {
                String docId = cursor.getString(0);
                String name = cursor.getString(1);
                String mime = cursor.getString(2);
                if (docId == null || name == null) continue;
                Uri docUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, docId);
                if (isAudioFileName(name) || (mime != null && mime.startsWith("audio/"))) {
                    audioEntries.add(new FolderEntry(name, docUri));
                } else if (isLyricFileName(name)) {
                    lyricsByBase.put(baseName(name), readTextUri(docUri));
                }
                if (audioEntries.size() >= MAX_IMPORT_COUNT) break;
            }
        } catch (Exception ex) {
            toast("\u6587\u4ef6\u5939\u8bfb\u53d6\u5931\u8d25\uff1a" + ex.getMessage());
            return 0;
        }
        int added = 0;
        for (FolderEntry entry : audioEntries) {
            String title = stripExtension(entry.name);
            String lyric = lyricsByBase.get(baseName(entry.name));
            Song song = new Song(title, "\u672c\u5730\u6587\u4ef6", "\u672c\u5730", lyric == null ? "" : lyric, entry.uri.toString());
            if (!containsSong(localPlaylist(), song)) {
                localPlaylist().songs.add(song);
                added++;
            }
        }
        return added;
    }

    private boolean importAudioUri(Uri uri) {
        try {
            getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
        } catch (Exception ignored) {
        }
        String name = displayNameForUri(uri);
        Song song = new Song(stripExtension(name), "\u672c\u5730\u6587\u4ef6", "\u672c\u5730", "", uri.toString());
        if (containsSong(localPlaylist(), song)) return false;
        localPlaylist().songs.add(song);
        return true;
    }

    private boolean isAudioFileName(String name) {
        String lower = name == null ? "" : name.toLowerCase();
        return lower.endsWith(".mp3") || lower.endsWith(".flac") || lower.endsWith(".m4a")
            || lower.endsWith(".wav") || lower.endsWith(".ogg") || lower.endsWith(".aac");
    }

    private boolean isLyricFileName(String name) {
        return name != null && name.toLowerCase().endsWith(".lrc");
    }

    private String baseName(String name) {
        return stripExtension(name).trim().toLowerCase();
    }

    private String readTextUri(Uri uri) {
        try (InputStream input = getContentResolver().openInputStream(uri)) {
            if (input == null) return "";
            BufferedReader reader = new BufferedReader(new InputStreamReader(input, "UTF-8"));
            StringBuilder builder = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) builder.append(line).append('\n');
            return builder.toString();
        } catch (Exception ignored) {
            return "";
        }
    }

    private String displayNameForUri(Uri uri) {
        try (Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) {
                    String name = cursor.getString(index);
                    if (name != null && !name.trim().isEmpty()) return name.trim();
                }
            }
        } catch (Exception ignored) {
        }
        String fallback = uri.getLastPathSegment();
        return fallback == null || fallback.isEmpty() ? "\u672c\u5730\u6b4c\u66f2" : fallback;
    }

    private String stripExtension(String name) {
        int dot = name.lastIndexOf('.');
        return dot > 0 ? name.substring(0, dot) : name;
    }

    private void promptNewPlaylist() {
        promptText("新建在线歌单", "请输入在线歌单名称", "", value -> {
            Playlist playlist = new Playlist(value);
            playlists.add(playlist);
            currentPlaylistIndex = playlists.indexOf(playlist);
            savePlaylists();
            renderCurrentPlaylist();
        });
    }

    private void promptRenamePlaylist() {
        promptText("\u91cd\u547d\u540d\u6b4c\u5355", "\u8bf7\u8f93\u5165\u65b0\u540d\u79f0", currentPlaylist().name, value -> {
            currentPlaylist().name = value;
            savePlaylists();
            renderCurrentPlaylist();
        });
    }

    private void promptText(String title, String hint, String initial, TextCallback callback) {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setHint(hint);
        input.setText(initial);
        new AlertDialog.Builder(this)
            .setTitle(title)
            .setView(input)
            .setNegativeButton("\u53d6\u6d88", null)
            .setPositiveButton("\u786e\u5b9a", (dialog, which) -> {
                String value = input.getText().toString().trim();
                if (value.isEmpty()) {
                    toast("\u540d\u79f0\u4e0d\u80fd\u4e3a\u7a7a");
                    return;
                }
                callback.onText(value);
            })
            .show();
    }

    private void deleteCurrentPlaylist() {
        Playlist selected = currentPlaylist();
        if (isLocalPlaylist(selected)) {
            toast("本地歌单固定保留，不能删除；可以清空、导出CSV或改名");
            return;
        }
        new AlertDialog.Builder(this)
            .setTitle("删除在线歌单")
            .setMessage("确定删除在线歌单《" + selected.name + "》及其中的 " + selected.songs.size() + " 首歌曲吗？")
            .setNegativeButton("取消", null)
            .setPositiveButton("\u786e\u5b9a", (dialog, which) -> {
                List<Song> removedSongs = new ArrayList<>(selected.songs);
                int removedIndex = currentPlaylistIndex;
                playlists.remove(removedIndex);
                currentPlaylistIndex = Math.max(0, Math.min(removedIndex, playlists.size() - 1));
                if (!playingSearchQueue) {
                    currentSongIndex = -1;
                    currentSong = null;
                    stopPlayback();
                    renderEmptyPlayer();
                }
                savePlaylists();
                renderCurrentPlaylist();
                toast("已删除在线歌单：" + selected.name + "；缓存已保留，可用扫把清理");
            })
            .show();
    }

    private void clearCurrentPlaylist() {
        List<Song> removedSongs = new ArrayList<>(currentPlaylist().songs);
        currentPlaylist().songs.clear();
        savePlaylists();
        renderCurrentPlaylist();
        toast("\u5df2\u6e05\u7a7a\u5f53\u524d\u6b4c\u5355；缓存已保留，可用扫把清理");
    }

    private void mergePlaylistsIntoCurrent() {
        Playlist target = currentPlaylist();
        if (isLocalPlaylist(target)) {
            toast("本地歌单不参与合并，请先选择一个在线歌单");
            return;
        }
        List<Playlist> sources = new ArrayList<>();
        for (int i = 1; i < playlists.size(); i++) {
            Playlist playlist = playlists.get(i);
            if (playlist != target) sources.add(playlist);
        }
        if (sources.isEmpty()) {
            toast("没有其他在线歌单可合并");
            return;
        }
        int sourceCount = sources.size();
        new AlertDialog.Builder(this)
            .setTitle("合并在线歌单")
            .setMessage("将其他 " + sourceCount + " 个在线歌单合并到《" + target.name
                + "》。同歌名且同歌手只保留一首；本地歌单不会参与或被删除。")
            .setNegativeButton("取消", null)
            .setPositiveButton("\u5408\u5e76", (dialog, which) -> {
                Map<String, Song> kept = new HashMap<>();
                for (Song song : target.songs) kept.put(dedupeKey(song), song);
                int added = 0;
                int merged = 0;
                for (Playlist source : sources) {
                    for (Song song : source.songs) {
                        String key = dedupeKey(song);
                        Song existing = kept.get(key);
                        if (existing == null) {
                            target.songs.add(song);
                            kept.put(key, song);
                            added++;
                        } else {
                            mergeSongMetadata(existing, song);
                            merged++;
                        }
                    }
                }
                playlists.removeAll(sources);
                dedupePlaylist(target);
                currentPlaylistIndex = playlists.indexOf(target);
                savePlaylists();
                renderCurrentPlaylist();
                toast("在线歌单合并完成：新增 " + added + " 首，合并重复 " + merged + " 首；本地歌单保持不变");
            })
            .show();
    }

    private boolean containsSong(Playlist playlist, Song song) {
        String key = dedupeKey(song);
        for (Song item : playlist.songs) {
            if (dedupeKey(item).equals(key)) return true;
        }
        return false;
    }

    private int dedupePlaylist(Playlist playlist) {
        Map<String, Song> kept = new HashMap<>();
        List<Song> unique = new ArrayList<>();
        for (Song song : playlist.songs) {
            String key = dedupeKey(song);
            Song existing = kept.get(key);
            if (existing == null) {
                kept.put(key, song);
                unique.add(song);
            } else {
                mergeSongMetadata(existing, song);
            }
        }
        int removed = playlist.songs.size() - unique.size();
        if (removed > 0) {
            playlist.songs.clear();
            playlist.songs.addAll(unique);
        }
        return removed;
    }

    private String dedupeKey(Song song) {
        String title = normalizeDedupe(song == null ? "" : song.title);
        String artist = normalizeDedupe(song == null ? "" : song.artist);
        if (isLocalSong(song)) {
            String uri = song == null || song.uri == null ? "" : song.uri.trim().toLowerCase(java.util.Locale.ROOT);
            return uri.isEmpty() ? "local-meta|" + title + "|" + artist : "local-uri|" + uri;
        }
        return "online|" + title + "|" + artist;
    }

    private String normalizeDedupe(String value) {
        if (value == null) return "";
        return java.text.Normalizer.normalize(value, java.text.Normalizer.Form.NFKC)
            .toLowerCase(java.util.Locale.ROOT)
            .replaceAll("[\\s·•・_/\\\\,，、;；]+", "")
            .trim();
    }

    private boolean isLocalSong(Song song) {
        if (song == null) return false;
        String source = song.source == null ? "" : song.source;
        String uri = song.uri == null ? "" : song.uri;
        return source.contains("本地") || (uri.startsWith("content://") && !song.isNetworkCatalog());
    }

    private boolean isLocalPlaylist(Playlist playlist) {
        return playlist != null && !playlists.isEmpty() && playlists.get(0) == playlist;
    }

    private Playlist localPlaylist() {
        if (playlists.isEmpty()) playlists.add(new Playlist("本地歌曲"));
        return playlists.get(0);
    }

    private Playlist onlineTargetPlaylist() {
        Playlist selected = currentPlaylist();
        if (!isLocalPlaylist(selected)) return selected;
        if (playlists.size() > 1) {
            currentPlaylistIndex = 1;
            return playlists.get(1);
        }
        Playlist created = new Playlist("在线歌曲");
        playlists.add(created);
        currentPlaylistIndex = 1;
        return created;
    }

    private boolean empty(String value) {
        return value == null || value.trim().isEmpty();
    }

    private void mergeSongMetadata(Song keeper, Song candidate) {
        if (keeper == null || candidate == null) return;
        if (empty(keeper.artist) || "未知歌手".equals(keeper.artist)) keeper.artist = candidate.artist;
        if (empty(keeper.source) || "在线".equals(keeper.source)) keeper.source = candidate.source;
        if (empty(keeper.lyric) && !empty(candidate.lyric)) keeper.lyric = candidate.lyric;
        if (empty(keeper.lyricLabel) && !empty(candidate.lyricLabel)) keeper.lyricLabel = candidate.lyricLabel;
        if (empty(keeper.catalogJson) && !empty(candidate.catalogJson)) keeper.catalogJson = candidate.catalogJson;
        if (empty(keeper.cachedUri) && !empty(candidate.cachedUri)) keeper.cachedUri = candidate.cachedUri;
        if (empty(keeper.uri) && !empty(candidate.uri)) keeper.uri = candidate.uri;
    }

    private boolean normalizePlaylistKinds() {
        if (playlists.isEmpty()) {
            playlists.add(new Playlist("本地歌曲"));
            currentPlaylistIndex = 0;
            return true;
        }
        Playlist selected = currentPlaylistIndex >= 0 && currentPlaylistIndex < playlists.size()
            ? playlists.get(currentPlaylistIndex) : null;
        Playlist local = playlists.get(0);
        List<Song> localSongs = new ArrayList<>();
        List<Song> recoveredOnlineSongs = new ArrayList<>();
        boolean changed = false;
        for (int i = 0; i < playlists.size(); i++) {
            Playlist playlist = playlists.get(i);
            List<Song> onlineSongs = new ArrayList<>();
            for (Song song : playlist.songs) {
                if (isLocalSong(song)) localSongs.add(song);
                else onlineSongs.add(song);
            }
            if (i == 0) {
                recoveredOnlineSongs.addAll(onlineSongs);
                if (!onlineSongs.isEmpty()) changed = true;
            } else {
                if (playlist.songs.size() != onlineSongs.size()) changed = true;
                playlist.songs.clear();
                playlist.songs.addAll(onlineSongs);
            }
        }
        local.songs.clear();
        local.songs.addAll(localSongs);
        if (dedupePlaylist(local) > 0) changed = true;
        if (!recoveredOnlineSongs.isEmpty()) {
            Playlist recovered = new Playlist("在线歌曲");
            recovered.songs.addAll(recoveredOnlineSongs);
            dedupePlaylist(recovered);
            playlists.add(1, recovered);
            changed = true;
        }
        for (int i = 1; i < playlists.size(); i++) {
            if (dedupePlaylist(playlists.get(i)) > 0) changed = true;
        }
        if (selected == local || selected == null) currentPlaylistIndex = 0;
        else {
            int restored = playlists.indexOf(selected);
            currentPlaylistIndex = restored >= 0 ? restored : 0;
        }
        return changed;
    }

    private Playlist currentPlaylist() {
        if (playlists.isEmpty()) {
            playlists.add(new Playlist("\u672c\u5730\u6b4c\u66f2"));
            currentPlaylistIndex = 0;
        }
        if (currentPlaylistIndex < 0 || currentPlaylistIndex >= playlists.size()) currentPlaylistIndex = 0;
        return playlists.get(currentPlaylistIndex);
    }

    private boolean migrateLegacyNeteasePlaylistSongs(Playlist playlist) {
        boolean changed = false;
        for (Song song : playlist.songs) {
            if (song == null || song.isNetworkCatalog() || !song.source.contains("网易")) continue;
            String id = firstMatch(song.uri, "id=(\\d+)");
            if (id.isEmpty()) continue;
            song.catalogJson = buildCatalogJson("netease", id, song.title, song.artist, "", 0);
            song.uri = "";
            song.cachedUri = "";
            changed = true;
        }
        return changed;
    }

    private void loadPlaylists() {
        playlists.clear();
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        currentPlaylistIndex = prefs.getInt(KEY_CURRENT_PLAYLIST, 0);
        String raw = prefs.getString(KEY_PLAYLISTS, "[]");
        boolean playlistsMigrated = false;
        try {
            JSONArray array = new JSONArray(raw);
            for (int i = 0; i < array.length(); i++) {
                Playlist playlist = Playlist.fromJson(array.getJSONObject(i));
                if ("默认歌单".equals(playlist.name)) playlist.name = "本地歌曲";
                if (migrateLegacyNeteasePlaylistSongs(playlist)) playlistsMigrated = true;
                dedupePlaylist(playlist);
                playlists.add(playlist);
            }
        } catch (JSONException ignored) {
            playlists.clear();
        }
        if (playlists.isEmpty()) playlists.add(new Playlist("本地歌曲"));
        if (normalizePlaylistKinds()) playlistsMigrated = true;
        if (currentPlaylistIndex < 0 || currentPlaylistIndex >= playlists.size()) currentPlaylistIndex = 0;
        if (playlistsMigrated) savePlaylists();
    }

    private void savePlaylists() {
        JSONArray array = new JSONArray();
        for (Playlist playlist : playlists) array.put(playlist.toJson());
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putString(KEY_PLAYLISTS, array.toString())
            .putInt(KEY_CURRENT_PLAYLIST, currentPlaylistIndex)
            .apply();
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private int statusBarHeight() {
        int resourceId = getResources().getIdentifier("status_bar_height", "dimen", "android");
        if (resourceId > 0) return getResources().getDimensionPixelSize(resourceId);
        return dp(24);
    }

    private void toast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    @Override
    public void onBackPressed() {
        if (drawerPanel != null && drawerPanel.getVisibility() == View.VISIBLE) {
            closeDrawer();
            return;
        }
        if (searchPanel != null && searchPanel.getVisibility() == View.VISIBLE) {
            showPlayerPage();
            return;
        }
        if (playlistPanel != null && playlistPanel.getVisibility() == View.VISIBLE) {
            showPlayerPage();
            return;
        }
        moveTaskToBack(true);
    }

    @Override
    protected void onDestroy() {
        if (mediaPlayer != null && currentSong != null) {
            try {
                saveLastSong(mediaPlayer.getCurrentPosition());
            } catch (Exception ignored) {
            }
        }
        stopPlayback();
        lyricHandler.removeCallbacks(lyricTicker);
        responsivenessWatchdogRunning = false;
        responsivenessHandler.removeCallbacks(responsivenessHeartbeat);
        ++playlistCacheScanSerial;
        playlistCacheScanExecutor.shutdownNow();
        if (playbackReceiverRegistered) {
            try {
                unregisterReceiver(playbackCommandReceiver);
            } catch (Exception ignored) {
            }
            playbackReceiverRegistered = false;
        }
        stopService(new Intent(this, PlaybackControlService.class));
        super.onDestroy();
    }

    private interface TextCallback {
        void onText(String value);
    }

    private static final class LyricLine {
        final long timeMs;
        final String text;

        LyricLine(long timeMs, String text) {
            this.timeMs = timeMs;
            this.text = text == null ? "" : text;
        }
    }

    private static final class FolderEntry {
        final String name;
        final Uri uri;

        FolderEntry(String name, Uri uri) {
            this.name = name;
            this.uri = uri;
        }
    }

    private static final class Playlist {
        String name;
        final List<Song> songs = new ArrayList<>();

        Playlist(String name) {
            this.name = name == null || name.isEmpty() ? "\u672c\u5730\u6b4c\u66f2" : name;
        }

        JSONObject toJson() {
            JSONObject object = new JSONObject();
            JSONArray array = new JSONArray();
            try {
                object.put("name", name);
                for (Song song : songs) array.put(song.toJson());
                object.put("songs", array);
            } catch (JSONException ignored) {
            }
            return object;
        }

        static Playlist fromJson(JSONObject object) {
            Playlist playlist = new Playlist(object.optString("name", "\u672c\u5730\u6b4c\u66f2"));
            JSONArray array = object.optJSONArray("songs");
            if (array != null) {
                for (int i = 0; i < array.length(); i++) {
                    JSONObject item = array.optJSONObject(i);
                    if (item != null) playlist.songs.add(Song.fromJson(item));
                }
            }
            return playlist;
        }
    }

    private static final class Song {
        String title;
        String artist;
        String source;
        String lyric;
        String lyricLabel;
        String uri;
        String catalogJson;
        String cachedUri;
        boolean unavailable;
        boolean autoUnavailable;
        boolean manualUnavailable;
        boolean manualAttempt;
        boolean cacheFailed;

        Song(String title, String artist, String source, String lyric) {
            this(title, artist, source, lyric, "", "", "");
        }

        Song(String title, String artist, String source, String lyric, String uri) {
            this(title, artist, source, lyric, uri, "", "");
        }

        Song(String title, String artist, String source, String lyric, String uri, String catalogJson, String cachedUri) {
            this.title = title == null || title.isEmpty() ? "未知歌曲" : title;
            this.artist = artist == null || artist.isEmpty() ? "未知歌手" : artist;
            this.source = source == null || source.isEmpty() ? "本地" : source;
            this.lyric = lyric == null ? "" : lyric;
            this.lyricLabel = "";
            this.uri = uri == null ? "" : uri;
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.cachedUri = cachedUri == null ? "" : cachedUri;
            this.unavailable = false;
            this.autoUnavailable = false;
            this.manualUnavailable = false;
            this.manualAttempt = false;
            this.cacheFailed = false;
        }

        static Song fromCatalog(CatalogSearch.Track track) {
            return new Song(
                track.title,
                track.artist,
                track.sourceLabel,
                "",
                "",
                track.rawJson,
                ""
            );
        }

        boolean isNetworkCatalog() {
            return catalogJson != null && !catalogJson.trim().isEmpty();
        }

        String display() {
            String cached = isNetworkCatalog() && cachedUri != null && !cachedUri.isEmpty() ? "  \u00b7 \u5df2\u7f13\u5b58" : "";
            String bad = unavailable ? "  \u00b7 \u8d44\u6e90\u4e0d\u53ef\u7528" : "";
            return "\u6b4c\u540d\uff1a" + title + "\n\u6b4c\u624b\uff1a" + artist + "    \u5e73\u53f0\uff1a" + source + cached + bad;
        }

        String key() {
            if (isNetworkCatalog()) {
                try {
                    JSONObject object = new JSONObject(catalogJson);
                    String sourceCode = object.optString("source", "");
                    String id = object.optString("id", "");
                    if (!sourceCode.isEmpty() && !id.isEmpty()) return (sourceCode + "|" + id).toLowerCase();
                } catch (Exception ignored) {
                }
            }
            if (!uri.isEmpty()) return uri.toLowerCase();
            return (title + "|" + artist + "|" + source).toLowerCase();
        }

        boolean matches(String keyword) {
            String key = (title + " " + artist + " " + source).toLowerCase();
            return key.contains(keyword.toLowerCase());
        }

        JSONObject toJson() {
            JSONObject object = new JSONObject();
            try {
                object.put("title", title);
                object.put("artist", artist);
                object.put("source", source);
                object.put("lyric", persistentLyric());
                object.put("lyricLabel", lyricLabel);
                object.put("uri", uri);
                object.put("catalogJson", catalogJson);
                object.put("cachedUri", cachedUri);
                object.put("unavailable", unavailable);
                object.put("autoUnavailable", autoUnavailable);
                object.put("manualUnavailable", manualUnavailable);
                object.put("cacheFailed", cacheFailed);
            } catch (JSONException ignored) {
            }
            return object;
        }

        String persistentLyric() {
            return isNetworkCatalog() ? "" : lyric;
        }

        static Song fromJson(JSONObject object) {
            Song song = new Song(
                object.optString("title"),
                object.optString("artist"),
                object.optString("source"),
                object.optString("lyric"),
                object.optString("uri"),
                object.optString("catalogJson"),
                object.optString("cachedUri")
            );
            song.lyricLabel = object.optString("lyricLabel", "");
            song.unavailable = object.optBoolean("unavailable", false);
            song.autoUnavailable = object.optBoolean("autoUnavailable", song.unavailable);
            song.manualUnavailable = object.optBoolean("manualUnavailable", song.unavailable);
            song.manualAttempt = false;
            song.cacheFailed = object.optBoolean("cacheFailed", false);
            return song;
        }
    }

    private static final class PendingPlaybackCommit {
        final String originalKey;
        final String audioUri;
        final String catalogJson;
        final String sourceLabel;
        final boolean sourceChanged;
        final String lyric;

        PendingPlaybackCommit(String originalKey, String audioUri, String catalogJson,
                              String sourceLabel, boolean sourceChanged, String lyric) {
            this.originalKey = originalKey == null ? "" : originalKey;
            this.audioUri = audioUri == null ? "" : audioUri;
            this.catalogJson = catalogJson == null ? "" : catalogJson;
            this.sourceLabel = sourceLabel == null ? "" : sourceLabel;
            this.sourceChanged = sourceChanged;
            this.lyric = lyric == null ? "" : lyric;
        }
    }
}
