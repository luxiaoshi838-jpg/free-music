package com.jianglab.babywife;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.TextUtils;
import android.text.style.ForegroundColorSpan;
import android.text.style.RelativeSizeSpan;
import android.text.style.StyleSpan;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.InputStream;
import java.io.BufferedReader;
import java.io.InputStreamReader;
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

public class MainActivity extends Activity {
    private static final String PREFS_NAME = "babywife_state";
    private static final String KEY_PLAYLISTS = "playlists_v2";
    private static final String KEY_CURRENT_PLAYLIST = "current_playlist";
    private static final String KEY_BACKGROUND_URI = "background_uri";
    private static final String KEY_LAST_PLAYLIST = "last_playlist";
    private static final String KEY_LAST_SONG = "last_song";
    private static final String KEY_LAST_POSITION = "last_position";
    private static final int REQUEST_BACKGROUND_IMAGE = 7301;
    private static final int REQUEST_AUDIO_FILES = 7302;
    private static final int REQUEST_AUDIO_FOLDER = 7303;
    private static final int MAX_IMPORT_COUNT = 1000;

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
    private ScrollView lyricsScroll;
    private TextView statusView;
    private TextView searchStatusView;
    private Button currentPlaylistButton;
    private Button playButton;
    private Button modeButton;
    private Button addCurrentButton;
    private EditText searchInput;
    private Spinner sourceSpinner;
    private Spinner playlistSpinner;
    private ListView playlistManagerList;
    private FrameLayout shellView;
    private LinearLayout drawerPanel;
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
    private final Random random = new Random();
    private final Handler lyricHandler = new Handler(Looper.getMainLooper());
    private final List<LyricLine> lyricLines = new ArrayList<>();
    private boolean userLyricTouch = false;
    private boolean autoScrollingLyrics = false;
    private int highlightedLyricIndex = -1;
    private final Runnable lyricTicker = new Runnable() {
        @Override
        public void run() {
            updateLyricProgress();
            lyricHandler.postDelayed(this, 600);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        loadPlaylists();
        setContentView(buildContentView());
        renderPlaylists();
        renderCurrentPlaylist();
        restoreLastSong();
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
        currentPlaylistButton.setOnClickListener(view -> showPlaylistPage());
        headerBar.addView(currentPlaylistButton, new LinearLayout.LayoutParams(dp(112), dp(42)));
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

        drawerPanel = buildDrawerPanel();
        drawerPanel.setVisibility(View.GONE);
        FrameLayout.LayoutParams drawerParams = new FrameLayout.LayoutParams(
            dp(310),
            ViewGroup.LayoutParams.MATCH_PARENT
        );
        drawerParams.gravity = Gravity.START;
        drawerParams.topMargin = statusBarHeight() + dp(18);
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

        Button backButton = makeRoundButton("\u2039", false);
        backButton.setTextSize(22);
        backButton.setOnClickListener(view -> showPlayerPage());
        row.addView(backButton, new LinearLayout.LayoutParams(dp(46), dp(46)));

        searchInput = new EditText(this);
        searchInput.setSingleLine(true);
        searchInput.setHint("\u641c\u7d22\u6b4c\u66f2 / \u6b4c\u624b");
        searchInput.setTextColor(TEXT_MAIN);
        searchInput.setHintTextColor(Color.argb(190, 255, 255, 255));
        searchInput.setBackground(rounded(Color.argb(72, 255, 255, 255), dp(22)));
        LinearLayout.LayoutParams inputParams = new LinearLayout.LayoutParams(0, dp(46), 1);
        inputParams.setMargins(dp(8), 0, dp(8), 0);
        row.addView(searchInput, inputParams);

        Button searchButton = makeButton("\u641c\u7d22", true);
        searchButton.setOnClickListener(view -> performSearch());
        LinearLayout.LayoutParams buttonParams = new LinearLayout.LayoutParams(dp(76), dp(46));
        row.addView(searchButton, buttonParams);
        panel.addView(row);

        sourceSpinner = new Spinner(this);
        String[] sources = {
            "\u5feb\u901f\u641c\u7d22",
            "\u5168\u90e8\u5e38\u7528\u6765\u6e90",
            "\u66f4\u591a\u6765\u6e90",
            "\u672c\u5730\u6b4c\u66f2",
            "\u7f51\u6613\u4e91",
            "\u9177\u72d7",
            "\u9177\u6211",
            "\u54aa\u5495",
            "QQ\u97f3\u4e50",
            "\u6c7d\u6c34"
        };
        sourceSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, sources));
        panel.addView(sourceSpinner, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            dp(42)
        ));

        TextView header = new TextView(this);
        header.setText("\u6b4c\u540d                 \u6b4c\u624b             \u5e73\u53f0");
        header.setTextColor(TEXT_MUTED);
        header.setTextSize(13);
        header.setPadding(dp(8), dp(12), dp(8), dp(6));
        panel.addView(header);

        resultAdapter = new SongListAdapter(searchResults);
        ListView resultsList = new ListView(this);
        resultsList.setBackground(rounded(Color.argb(72, 0, 0, 0), dp(20)));
        resultsList.setAdapter(resultAdapter);
        resultsList.setOnItemClickListener((parent, view, position, id) -> {
            playSongFromSearch(position);
            showPlayerPage();
        });
        resultsList.setOnItemLongClickListener((parent, view, position, id) -> {
            addSongToCurrentPlaylist(searchResults.get(position));
            return true;
        });
        panel.addView(resultsList, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1
        ));
        return panel;
    }

    private View buildPlayerPanel() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(18), dp(34), dp(18), dp(18));
        panel.setBackground(rounded(GLASS_DARK, dp(28)));

        titleView = new TextView(this);
        titleView.setTextSize(28);
        titleView.setTypeface(Typeface.DEFAULT_BOLD);
        titleView.setTextColor(TEXT_MAIN);
        titleView.setGravity(Gravity.CENTER);
        panel.addView(titleView);

        artistView = new TextView(this);
        artistView.setTextSize(15);
        artistView.setTextColor(TEXT_MUTED);
        artistView.setGravity(Gravity.CENTER);
        panel.addView(artistView);

        addCurrentButton = makeButton("\u52a0\u5165\u5f53\u524d\u6b4c\u5355", false);
        addCurrentButton.setTextSize(13);
        addCurrentButton.setOnClickListener(view -> {
            if (currentSong == null) {
                toast("\u8bf7\u5148\u9009\u62e9\u6b4c\u66f2");
                return;
            }
            addSongToCurrentPlaylist(currentSong);
        });
        LinearLayout.LayoutParams addParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            dp(40)
        );
        addParams.gravity = Gravity.CENTER_HORIZONTAL;
        addParams.setMargins(0, dp(12), 0, 0);
        panel.addView(addCurrentButton, addParams);

        lyricView = new TextView(this);
        lyricView.setTextSize(18);
        lyricView.setGravity(Gravity.CENTER);
        lyricView.setLineSpacing(8, 1.08f);
        lyricView.setTextColor(Color.argb(232, 255, 255, 255));
        lyricsScroll = new ScrollView(this);
        lyricsScroll.setFillViewport(true);
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
            ViewGroup.LayoutParams.MATCH_PARENT
        ));
        LinearLayout.LayoutParams lyricParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1
        );
        lyricParams.setMargins(0, dp(18), 0, dp(12));
        panel.addView(lyricsScroll, lyricParams);

        LinearLayout bottomBar = new LinearLayout(this);
        bottomBar.setOrientation(LinearLayout.HORIZONTAL);
        bottomBar.setGravity(Gravity.CENTER_VERTICAL);

        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.HORIZONTAL);
        controls.setGravity(Gravity.CENTER);
        controls.setPadding(0, dp(8), 0, dp(8));

        Button previous = makeRoundButton("\u23ee", false);
        previous.setTextSize(18);
        previous.setOnClickListener(view -> playPlaylistOffset(-1));
        controls.addView(previous, new LinearLayout.LayoutParams(dp(52), dp(52)));

        playButton = makeRoundButton("\u25b6", true);
        playButton.setTextSize(22);
        playButton.setOnClickListener(view -> togglePlayback());
        LinearLayout.LayoutParams playParams = new LinearLayout.LayoutParams(dp(66), dp(66));
        playParams.setMargins(dp(34), 0, dp(34), 0);
        controls.addView(playButton, playParams);

        Button next = makeRoundButton("\u23ed", false);
        next.setTextSize(18);
        next.setOnClickListener(view -> playPlaylistOffset(1));
        controls.addView(next, new LinearLayout.LayoutParams(dp(52), dp(52)));
        bottomBar.addView(controls, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        modeButton = makeRoundButton(playModeSymbol(), false);
        modeButton.setTextSize(12);
        modeButton.setOnClickListener(view -> cyclePlayMode());
        LinearLayout.LayoutParams modeParams = new LinearLayout.LayoutParams(
            dp(42),
            dp(42)
        );
        modeParams.gravity = Gravity.BOTTOM;
        bottomBar.addView(modeButton, modeParams);
        panel.addView(bottomBar, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        ));
        return panel;
    }

    private View buildPlaylistPage() {
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(10), dp(10), dp(10), dp(10));
        panel.setBackground(rounded(GLASS_DARK, dp(28)));

        LinearLayout topRow = new LinearLayout(this);
        topRow.setOrientation(LinearLayout.HORIZONTAL);
        topRow.setGravity(Gravity.CENTER_VERTICAL);

        Button backButton = makeRoundButton("\u2039", false);
        backButton.setTextSize(22);
        backButton.setOnClickListener(view -> showPlayerPage());
        topRow.addView(backButton, new LinearLayout.LayoutParams(dp(46), dp(46)));

        TextView title = new TextView(this);
        title.setText("\u5f53\u524d\u6b4c\u5355");
        title.setTextColor(TEXT_MAIN);
        title.setTextSize(20);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setGravity(Gravity.CENTER);
        topRow.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        TextView spacer = new TextView(this);
        topRow.addView(spacer, new LinearLayout.LayoutParams(dp(46), dp(46)));
        panel.addView(topRow);

        TextView hint = new TextView(this);
        hint.setText("\u70b9\u51fb\u64ad\u653e\uff0c\u957f\u6309\u5220\u9664");
        hint.setTextColor(TEXT_MUTED);
        hint.setTextSize(12);
        hint.setGravity(Gravity.CENTER);
        panel.addView(hint);

        playlistAdapter = new SongListAdapter(currentPlaylist().songs);
        ListView playlistList = new ListView(this);
        playlistList.setBackground(rounded(Color.argb(72, 0, 0, 0), dp(20)));
        playlistList.setAdapter(playlistAdapter);
        playlistList.setOnItemClickListener((parent, view, position, id) -> {
            playSongFromPlaylist(position);
            showPlayerPage();
        });
        playlistList.setOnItemLongClickListener((parent, view, position, id) -> {
            Song removed = currentPlaylist().songs.remove(position);
            savePlaylists();
            renderCurrentPlaylist();
            toast("\u5df2\u5220\u9664\uff1a" + removed.title);
            return true;
        });
        panel.addView(playlistList, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            0,
            1
        ));
        return panel;
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
            toast("\u5df2\u5220\u9664\uff1a" + removed.title);
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
        label.setText("\u6b4c\u5355\u7ba1\u7406");
        label.setTextSize(17);
        label.setTypeface(Typeface.DEFAULT_BOLD);
        label.setTextColor(TEXT_MAIN);
        panel.addView(label);

        playlistSpinner = new Spinner(this);
        playlistSpinner.setVisibility(View.GONE);
        playlistSpinnerAdapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new ArrayList<>());
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
            ViewGroup.LayoutParams.MATCH_PARENT,
            1
        ));

        playlistManagerAdapter = new ArrayAdapter<String>(this, android.R.layout.simple_list_item_1, new ArrayList<>()) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                View view = super.getView(position, convertView, parent);
                TextView text = view.findViewById(android.R.id.text1);
                if (text != null) {
                    text.setTextColor(TEXT_MAIN);
                    text.setTextSize(14);
                    text.setSingleLine(true);
                    text.setEllipsize(TextUtils.TruncateAt.END);
                }
                view.setBackgroundColor(position == currentPlaylistIndex ? Color.argb(74, 255, 78, 92) : Color.TRANSPARENT);
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
            ViewGroup.LayoutParams.MATCH_PARENT,
            dp(190)
        ));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.addView(makeSmallButton("\u65b0\u5efa", view -> promptNewPlaylist()), new LinearLayout.LayoutParams(0, dp(40), 1));
        actions.addView(makeSmallButton("\u6539\u540d", view -> promptRenamePlaylist()), new LinearLayout.LayoutParams(0, dp(40), 1));
        actions.addView(makeSmallButton("\u5408\u5e76", view -> mergePlaylistsIntoCurrent()), new LinearLayout.LayoutParams(0, dp(40), 1));
        actions.addView(makeSmallButton("\u6e05\u7a7a", view -> clearCurrentPlaylist()), new LinearLayout.LayoutParams(0, dp(40), 1));
        panel.addView(actions);
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
        drawerPanel.setVisibility(drawerPanel.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE);
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
        String keyword = searchInput.getText().toString().trim();
        if (keyword.isEmpty()) {
            toast("\u8bf7\u8f93\u5165\u6b4c\u66f2\u540d");
            return;
        }
        searchResults.clear();
        appendLocalSearch(keyword);
        sortByKeyword(searchResults, keyword);
        renderResults();
        searchStatusView.setText("\u641c\u7d22\uff1a" + keyword);
        statusView.setText("\u6b63\u5728\u641c\u7d22\u5728\u7ebf\u6765\u6e90...");
        new Thread(() -> {
            List<Song> online = searchOnline(keyword, String.valueOf(sourceSpinner.getSelectedItem()));
            runOnUiThread(() -> {
                appendUnique(searchResults, online);
                sortByKeyword(searchResults, keyword);
                renderResults();
                statusView.setText("\u641c\u7d22\u5b8c\u6210\uff1a" + searchResults.size() + " \u9996");
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
        Playlist playlist = currentPlaylist();
        if (containsSong(playlist, song)) {
            toast("\u5f53\u524d\u6b4c\u5355\u5df2\u6709\uff1a" + song.title);
            return;
        }
        playlist.songs.add(song);
        savePlaylists();
        renderCurrentPlaylist();
        toast("\u5df2\u52a0\u5165 " + playlist.name + "\uff1a" + song.title);
    }

    private void renderResults() {
        if (resultAdapter != null) resultAdapter.setSongs(searchResults);
    }

    private void renderPlaylists() {
        if (playlistSpinnerAdapter == null) return;
        playlistSpinnerAdapter.clear();
        if (playlistManagerAdapter != null) playlistManagerAdapter.clear();
        for (Playlist playlist : playlists) {
            String label = playlist.name + " \u00b7 " + playlist.songs.size() + "\u9996";
            playlistSpinnerAdapter.add(label);
            if (playlistManagerAdapter != null) playlistManagerAdapter.add(label);
        }
        playlistSpinnerAdapter.notifyDataSetChanged();
        if (playlistManagerAdapter != null) playlistManagerAdapter.notifyDataSetChanged();
        if (!playlists.isEmpty() && playlistSpinner != null) playlistSpinner.setSelection(currentPlaylistIndex);
        if (currentPlaylistButton != null) currentPlaylistButton.setText(currentPlaylist().name);
    }

    private void renderCurrentPlaylist() {
        if (playlistAdapter == null) return;
        playlistAdapter.setSongs(currentPlaylist().songs);
        renderPlaylists();
        statusView.setText("\u5f53\u524d\u6b4c\u5355\uff1a" + currentPlaylist().name + "\uff0c\u5171 " + currentPlaylist().songs.size() + " \u9996");
    }

    private void renderEmptyPlayer() {
        titleView.setText("\u8fd8\u6ca1\u6709\u9009\u62e9\u6b4c\u66f2");
        artistView.setText("");
        lyricView.setText("");
        lyricLines.clear();
        highlightedLyricIndex = -1;
        if (playButton != null) playButton.setText("\u25b6");
    }

    private void showSongLyrics(Song song) {
        lyricLines.clear();
        highlightedLyricIndex = -1;
        if (song.lyric != null && !song.lyric.trim().isEmpty()) {
            applyLyricText(song.lyric);
            return;
        }
        lyricView.setText("\u6b63\u5728\u5339\u914d\u6b4c\u8bcd...");
        String neteaseId = neteaseIdFromSong(song);
        if (!neteaseId.isEmpty()) {
            new Thread(() -> {
                String lyric = fetchNeteaseLyric(neteaseId);
                runOnUiThread(() -> {
                    if (currentSong == song) {
                        if (lyric.trim().isEmpty()) {
                            lyricView.setText("\u6682\u672a\u627e\u5230\u6b4c\u8bcd");
                        } else {
                            song.lyric = lyric;
                            applyLyricText(lyric);
                            savePlaylists();
                        }
                    }
                });
            }).start();
        } else {
            new Thread(() -> {
                String lyric = fetchBestLyricByKeyword(song.title + " " + song.artist);
                runOnUiThread(() -> {
                    if (currentSong == song) {
                        if (lyric.trim().isEmpty()) {
                            lyricView.setText("\u6682\u672a\u627e\u5230\u6b4c\u8bcd");
                        } else {
                            song.lyric = lyric;
                            applyLyricText(lyric);
                            savePlaylists();
                        }
                    }
                });
            }).start();
        }
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
        String[] lines = raw.split("\\r?\\n");
        for (String line : lines) {
            LyricLine parsed = parseLyricLine(line);
            if (parsed != null) lyricLines.add(parsed);
        }
        if (lyricLines.isEmpty()) {
            lyricView.setText(raw.trim().isEmpty() ? "\u6682\u65e0\u6b4c\u8bcd" : raw);
            return;
        }
        renderLyricHighlight(0);
    }

    private LyricLine parseLyricLine(String line) {
        int close = line.indexOf(']');
        if (!line.startsWith("[") || close <= 1) return null;
        String time = line.substring(1, close);
        String text = line.substring(close + 1).trim();
        String[] parts = time.split(":");
        if (parts.length < 2) return null;
        try {
            long minute = Long.parseLong(parts[0]);
            double second = Double.parseDouble(parts[1]);
            return new LyricLine((long) (minute * 60000 + second * 1000), text.isEmpty() ? " " : text);
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

    private int lyricIndexFor(long positionMs) {
        int index = 0;
        for (int i = 0; i < lyricLines.size(); i++) {
            if (positionMs >= lyricLines.get(i).timeMs) index = i;
            else break;
        }
        return index;
    }

    private void renderLyricHighlight(int index) {
        highlightedLyricIndex = Math.max(0, Math.min(index, lyricLines.size() - 1));
        StringBuilder builder = new StringBuilder();
        for (LyricLine line : lyricLines) builder.append(line.text).append('\n');
        SpannableString span = new SpannableString(builder.toString());
        int start = 0;
        for (int i = 0; i < lyricLines.size(); i++) {
            int end = start + lyricLines.get(i).text.length();
            if (i == highlightedLyricIndex) {
                span.setSpan(new ForegroundColorSpan(Color.WHITE), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                span.setSpan(new RelativeSizeSpan(1.22f), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                span.setSpan(new StyleSpan(Typeface.BOLD), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            } else {
                span.setSpan(new ForegroundColorSpan(Color.argb(150, 255, 255, 255)), start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            start = end + 1;
        }
        lyricView.setText(span);
        if (!userLyricTouch && lyricsScroll != null) {
            lyricsScroll.post(() -> {
                int lineHeight = Math.max(lyricView.getLineHeight(), dp(28));
                int targetY = Math.max(0, highlightedLyricIndex * lineHeight - lyricsScroll.getHeight() / 2);
                autoScrollingLyrics = true;
                lyricsScroll.smoothScrollTo(0, targetY);
                autoScrollingLyrics = false;
            });
        }
    }

    private void seekByLyricTouch(float y) {
        if (autoScrollingLyrics || mediaPlayer == null || lyricLines.isEmpty() || lyricsScroll == null) return;
        int lineHeight = Math.max(lyricView.getLineHeight(), dp(28));
        int index = Math.max(0, Math.min(lyricLines.size() - 1, (int) ((lyricsScroll.getScrollY() + y) / lineHeight)));
        try {
            mediaPlayer.seekTo((int) lyricLines.get(index).timeMs);
            renderLyricHighlight(index);
        } catch (Exception ignored) {
        }
    }

    private void restoreLastSong() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        int playlistIndex = prefs.getInt(KEY_LAST_PLAYLIST, currentPlaylistIndex);
        int songIndex = prefs.getInt(KEY_LAST_SONG, -1);
        int position = prefs.getInt(KEY_LAST_POSITION, 0);
        if (playlistIndex >= 0 && playlistIndex < playlists.size()) {
            currentPlaylistIndex = playlistIndex;
            renderCurrentPlaylist();
            Playlist playlist = currentPlaylist();
            if (songIndex >= 0 && songIndex < playlist.songs.size()) {
                currentSongIndex = songIndex;
                currentSong = playlist.songs.get(songIndex);
                titleView.setText(currentSong.title);
                artistView.setText(currentSong.artist + " \u00b7 " + currentSong.source);
                lyricView.setText(currentSong.lyric);
                statusView.setText("\u5df2\u6062\u590d\u4e0a\u6b21\u64ad\u653e\uff1a" + currentSong.title);
                prepareLastSong(position);
                showPlayerPage();
                return;
            }
        }
        renderEmptyPlayer();
        showPlayerPage();
    }

    private void prepareLastSong(int position) {
        if (currentSong == null || currentSong.uri == null || currentSong.uri.isEmpty()) {
            if (playButton != null) playButton.setText("\u25b6");
            return;
        }
        try {
            stopPlayback();
            mediaPlayer = new MediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(currentSong.uri));
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());
            mediaPlayer.prepare();
            if (position > 0) {
                mediaPlayer.seekTo(position);
            }
            playButton.setText("\u25b6");
        } catch (Exception ignored) {
            stopPlayback();
            playButton.setText("\u25b6");
        }
    }

    private void playSong(Song song) {
        currentSong = song;
        saveLastSong(0);
        titleView.setText(song.title);
        artistView.setText(song.artist + " \u00b7 " + song.source);
        if (addCurrentButton != null) addCurrentButton.setVisibility(playingSearchQueue ? View.VISIBLE : View.GONE);
        showSongLyrics(song);
        statusView.setText("\u5f53\u524d\u64ad\u653e\uff1a" + song.title);
        if (song.uri == null || song.uri.isEmpty()) {
            stopPlayback();
            playButton.setText("\u25b6");
            resolveAndPlay(song);
            return;
        }
        startLocalPlayback(song);
    }

    private void resolveAndPlay(Song song) {
        statusView.setText("\u6b63\u5728\u89e3\u6790\u53ef\u64ad\u653e\u97f3\u9891...");
        new Thread(() -> {
            Song resolved = resolvePlayableSong(song);
            runOnUiThread(() -> {
                if (currentSong != song) return;
                if (resolved == null || resolved.uri == null || resolved.uri.isEmpty()) {
                    toast("\u6682\u65f6\u6ca1\u6709\u89e3\u6790\u5230\u53ef\u64ad\u653e\u97f3\u9891");
                    return;
                }
                song.uri = resolved.uri;
                if ((song.lyric == null || song.lyric.trim().isEmpty()) && resolved.lyric != null) song.lyric = resolved.lyric;
                startLocalPlayback(song);
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
            startLocalPlayback(currentSong);
        } else {
            playPlaylistOffset(1);
        }
    }

    private void cyclePlayMode() {
        playMode = (playMode + 1) % 3;
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

    private void startLocalPlayback(Song song) {
        try {
            stopPlayback();
            mediaPlayer = new MediaPlayer();
            mediaPlayer.setDataSource(this, Uri.parse(song.uri));
            mediaPlayer.setOnCompletionListener(player -> playAfterCompletion());
            if (song.uri.startsWith("http://") || song.uri.startsWith("https://")) {
                statusView.setText("\u6b63\u5728\u6253\u5f00\u5728\u7ebf\u97f3\u9891...");
                mediaPlayer.setOnPreparedListener(player -> {
                    player.start();
                    playButton.setText("\u2161");
                    statusView.setText("\u5f53\u524d\u64ad\u653e\uff1a" + song.title);
                    lyricHandler.removeCallbacks(lyricTicker);
                    lyricHandler.post(lyricTicker);
                });
                mediaPlayer.prepareAsync();
            } else {
                mediaPlayer.prepare();
                mediaPlayer.start();
                playButton.setText("\u2161");
                saveLastSong(0);
                lyricHandler.removeCallbacks(lyricTicker);
                lyricHandler.post(lyricTicker);
            }
        } catch (Exception ex) {
            stopPlayback();
            playButton.setText("\u25b6");
            toast("\u64ad\u653e\u5931\u8d25\uff1a" + ex.getMessage());
        }
    }

    private void togglePlayback() {
        if (mediaPlayer == null) {
            if (currentSong != null) {
                playSong(currentSong);
            } else if (!currentPlaylist().songs.isEmpty()) {
                playSongFromPlaylist(0);
            } else {
                toast("\u8bf7\u5148\u5bfc\u5165\u6216\u9009\u62e9\u6b4c\u66f2");
            }
            return;
        }
        if (mediaPlayer.isPlaying()) {
            mediaPlayer.pause();
            playButton.setText("\u25b6");
            saveLastSong(mediaPlayer.getCurrentPosition());
            lyricHandler.removeCallbacks(lyricTicker);
        } else {
            mediaPlayer.start();
            playButton.setText("\u2161");
            lyricHandler.post(lyricTicker);
        }
    }

    private void saveLastSong(int position) {
        if (currentSong == null) return;
        int playlistIndex = currentPlaylistIndex;
        int songIndex = currentSongIndex;
        if (songIndex < 0) {
            songIndex = currentPlaylist().songs.indexOf(currentSong);
        }
        if (songIndex < 0) return;
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putInt(KEY_LAST_PLAYLIST, playlistIndex)
            .putInt(KEY_LAST_SONG, songIndex)
            .putInt(KEY_LAST_POSITION, Math.max(0, position))
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
    }

    private LinearLayout buildDrawerPanel() {
        LinearLayout drawer = new LinearLayout(this);
        drawer.setOrientation(LinearLayout.VERTICAL);
        drawer.setPadding(dp(14), dp(18), dp(14), dp(14));
        drawer.setBackground(rounded(Color.argb(226, 22, 24, 34), dp(22)));

        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);

        TextView title = new TextView(this);
        title.setText("\u8bbe\u7f6e");
        title.setTextSize(22);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(TEXT_MAIN);
        header.addView(title, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        Button close = makeButton("\u00d7", false);
        close.setTextSize(20);
        close.setOnClickListener(view -> closeDrawer());
        header.addView(close, new LinearLayout.LayoutParams(dp(48), dp(42)));
        drawer.addView(header);

        drawer.addView(buildPlaylistManagerPanel());

        TextView skinTitle = new TextView(this);
        skinTitle.setText("\u80cc\u666f\u76ae\u80a4");
        skinTitle.setTextSize(17);
        skinTitle.setTypeface(Typeface.DEFAULT_BOLD);
        skinTitle.setTextColor(TEXT_MAIN);
        skinTitle.setPadding(0, dp(16), 0, dp(6));
        drawer.addView(skinTitle);

        Button chooseBackground = makeButton("\u9009\u62e9\u672c\u5730\u56fe\u7247\u4f5c\u4e3a\u80cc\u666f", false);
        chooseBackground.setOnClickListener(view -> chooseBackgroundImage());
        drawer.addView(chooseBackground, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)));

        Button importAudio = makeButton("\u5bfc\u5165\u672c\u5730\u6b4c\u66f2\u5230\u5f53\u524d\u6b4c\u5355", true);
        importAudio.setOnClickListener(view -> chooseAudioFiles());
        drawer.addView(importAudio, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)));

        Button importFolder = makeButton("\u9009\u62e9\u6587\u4ef6\u5939\u5bfc\u5165\u5168\u90e8\u6b4c\u66f2", false);
        importFolder.setOnClickListener(view -> chooseAudioFolder());
        drawer.addView(importFolder, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)));

        Button importPlaylist = makeButton("\u5bfc\u5165\u7f51\u6613/\u9177\u72d7/\u6c7d\u6c34\u6b4c\u5355\u94fe\u63a5", false);
        importPlaylist.setOnClickListener(view -> promptImportPlaylistLink());
        drawer.addView(importPlaylist, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)));

        Button resetBackground = makeButton("\u6062\u590d\u9ed8\u8ba4\u80cc\u666f", false);
        resetBackground.setOnClickListener(view -> resetBackgroundImage());
        drawer.addView(resetBackground, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(44)));
        return drawer;
    }

    private void closeDrawer() {
        if (drawerPanel != null) drawerPanel.setVisibility(View.GONE);
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
        if (source.contains("\u7f51\u6613")) return importNeteasePlaylist(url);
        Playlist imported = new Playlist(source + "\u6b4c\u5355");
        imported.songs.add(new Song("\u6682\u672a\u63a5\u5165\u89e3\u6790\uff1a" + source, "\u8bf7\u5148\u7528\u7f51\u6613\u4e91/\u672c\u5730\u5bfc\u5165", source, ""));
        return imported;
    }

    private Playlist importNeteasePlaylist(String urlText) {
        String playlistId = playlistIdFromUrl(urlText);
        Playlist imported = new Playlist("\u7f51\u6613\u4e91\u6b4c\u5355 " + playlistId);
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
        String title = item.optString("name", "\u672a\u77e5\u6b4c\u66f2");
        JSONArray artists = item.optJSONArray("artists");
        if (artists == null) artists = item.optJSONArray("ar");
        String artist = artistsFromNetease(artists);
        String id = item.optString("id", "");
        String playUrl = id.isEmpty() ? "" : "https://music.163.com/song/media/outer/url?id=" + id + ".mp3";
        return new Song(title, artist, "\u7f51\u6613\u4e91", "", playUrl);
    }

    private String playlistIdFromUrl(String urlText) {
        String text = urlText == null ? "" : urlText;
        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("(?:id=|playlist/)(\\d+)").matcher(text);
        return matcher.find() ? matcher.group(1) : "";
    }

    private String sourceFromPlaylistUrl(String url) {
        String lower = url.toLowerCase();
        if (lower.contains("163.com") || lower.contains("netease")) return "\u7f51\u6613\u4e91";
        if (lower.contains("kugou")) return "\u9177\u72d7";
        if (lower.contains("qishui") || lower.contains("douyin") || lower.contains("music.douyin")) return "\u6c7d\u6c34";
        if (lower.contains("kuwo")) return "\u9177\u6211";
        if (lower.contains("qq.com")) return "QQ\u97f3\u4e50";
        return "\u5916\u90e8\u6765\u6e90";
    }

    private void resetBackgroundImage() {
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit().remove(KEY_BACKGROUND_URI).apply();
        applySavedBackground();
        toast("\u5df2\u6062\u590d\u9ed8\u8ba4\u80cc\u666f");
    }

    private void applySavedBackground() {
        if (backgroundView == null) return;
        String rawUri = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(KEY_BACKGROUND_URI, "");
        if (rawUri != null && !rawUri.isEmpty()) {
            try {
                backgroundView.setImageURI(Uri.parse(rawUri));
                return;
            } catch (Exception ignored) {
            }
        }
        backgroundView.setImageResource(R.drawable.default_background);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_BACKGROUND_IMAGE && resultCode == RESULT_OK && data != null && data.getData() != null) {
            Uri uri = data.getData();
            try {
                getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            } catch (Exception ignored) {
            }
            getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit().putString(KEY_BACKGROUND_URI, uri.toString()).apply();
            applySavedBackground();
            toast("\u80cc\u666f\u5df2\u66f4\u65b0");
        } else if (requestCode == REQUEST_AUDIO_FILES && resultCode == RESULT_OK && data != null) {
            int added = importAudioResult(data);
            if (added > 0) {
                dedupePlaylist(currentPlaylist());
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
                dedupePlaylist(currentPlaylist());
                savePlaylists();
                renderCurrentPlaylist();
            }
            toast("\u5df2\u4ece\u6587\u4ef6\u5939\u5bfc\u5165 " + added + " \u9996");
        }
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
            if (!containsSong(currentPlaylist(), song)) {
                currentPlaylist().songs.add(song);
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
        if (containsSong(currentPlaylist(), song)) return false;
        currentPlaylist().songs.add(song);
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
        promptText("\u65b0\u5efa\u6b4c\u5355", "\u8bf7\u8f93\u5165\u6b4c\u5355\u540d\u79f0", "", value -> {
            playlists.add(new Playlist(value));
            currentPlaylistIndex = playlists.size() - 1;
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
        if (playlists.size() <= 1) {
            toast("\u81f3\u5c11\u4fdd\u7559\u4e00\u4e2a\u6b4c\u5355");
            return;
        }
        String name = currentPlaylist().name;
        playlists.remove(currentPlaylistIndex);
        currentPlaylistIndex = Math.max(0, currentPlaylistIndex - 1);
        savePlaylists();
        renderCurrentPlaylist();
        toast("\u5df2\u5220\u9664\u6b4c\u5355\uff1a" + name);
    }

    private void clearCurrentPlaylist() {
        currentPlaylist().songs.clear();
        savePlaylists();
        renderCurrentPlaylist();
        toast("\u5df2\u6e05\u7a7a\u5f53\u524d\u6b4c\u5355");
    }

    private void mergePlaylistsIntoCurrent() {
        Playlist target = currentPlaylist();
        Set<String> seen = new HashSet<>();
        for (Song song : target.songs) seen.add(dedupeKey(song));
        int added = 0;
        for (int i = 0; i < playlists.size(); i++) {
            if (i == currentPlaylistIndex) continue;
            for (Song song : playlists.get(i).songs) {
                if (seen.add(dedupeKey(song))) {
                    target.songs.add(song);
                    added++;
                }
            }
        }
        dedupePlaylist(target);
        savePlaylists();
        renderCurrentPlaylist();
        toast("\u5408\u5e76\u5b8c\u6210\uff0c\u65b0\u589e " + added + " \u9996");
    }

    private boolean containsSong(Playlist playlist, Song song) {
        String key = dedupeKey(song);
        for (Song item : playlist.songs) {
            if (dedupeKey(item).equals(key)) return true;
        }
        return false;
    }

    private int dedupePlaylist(Playlist playlist) {
        Set<String> seen = new HashSet<>();
        List<Song> unique = new ArrayList<>();
        for (Song song : playlist.songs) {
            if (seen.add(dedupeKey(song))) unique.add(song);
        }
        int removed = playlist.songs.size() - unique.size();
        if (removed > 0) {
            playlist.songs.clear();
            playlist.songs.addAll(unique);
        }
        return removed;
    }

    private String dedupeKey(Song song) {
        String source = normalizeDedupe(song.source);
        String title = normalizeDedupe(song.title);
        String artist = normalizeDedupe(song.artist);
        if (source.contains("\u672c\u5730")) {
            return "local|" + title;
        }
        if (!song.uri.isEmpty() && !song.uri.startsWith("content://")) {
            return "uri|" + song.uri.toLowerCase();
        }
        return source + "|" + title + "|" + artist;
    }

    private String normalizeDedupe(String value) {
        if (value == null) return "";
        return value.toLowerCase()
            .replace("\uff08", "(")
            .replace("\uff09", ")")
            .replaceAll("\\s+", "")
            .trim();
    }

    private Playlist currentPlaylist() {
        if (playlists.isEmpty()) {
            playlists.add(new Playlist("\u672c\u5730\u6b4c\u66f2"));
            currentPlaylistIndex = 0;
        }
        if (currentPlaylistIndex < 0 || currentPlaylistIndex >= playlists.size()) currentPlaylistIndex = 0;
        return playlists.get(currentPlaylistIndex);
    }

    private void loadPlaylists() {
        playlists.clear();
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        currentPlaylistIndex = prefs.getInt(KEY_CURRENT_PLAYLIST, 0);
        String raw = prefs.getString(KEY_PLAYLISTS, "[]");
        try {
            JSONArray array = new JSONArray(raw);
            for (int i = 0; i < array.length(); i++) {
                Playlist playlist = Playlist.fromJson(array.getJSONObject(i));
                if ("\u9ed8\u8ba4\u6b4c\u5355".equals(playlist.name)) playlist.name = "\u672c\u5730\u6b4c\u66f2";
                dedupePlaylist(playlist);
                playlists.add(playlist);
            }
        } catch (JSONException ignored) {
            playlists.clear();
        }
        if (playlists.isEmpty()) playlists.add(new Playlist("\u672c\u5730\u6b4c\u66f2"));
        if (currentPlaylistIndex < 0 || currentPlaylistIndex >= playlists.size()) currentPlaylistIndex = 0;
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
        final String title;
        final String artist;
        final String source;
        String lyric;
        String uri;

        Song(String title, String artist, String source, String lyric) {
            this(title, artist, source, lyric, "");
        }

        Song(String title, String artist, String source, String lyric, String uri) {
            this.title = title == null || title.isEmpty() ? "\u672a\u77e5\u6b4c\u66f2" : title;
            this.artist = artist == null || artist.isEmpty() ? "\u672a\u77e5\u6b4c\u624b" : artist;
            this.source = source == null || source.isEmpty() ? "\u672c\u5730" : source;
            this.lyric = lyric == null ? "" : lyric;
            this.uri = uri == null ? "" : uri;
        }

        String display() {
            return "\u6b4c\u540d\uff1a" + title + "\n\u6b4c\u624b\uff1a" + artist + "    \u5e73\u53f0\uff1a" + source;
        }

        String key() {
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
                object.put("lyric", lyric);
                object.put("uri", uri);
            } catch (JSONException ignored) {
            }
            return object;
        }

        static Song fromJson(JSONObject object) {
            return new Song(
                object.optString("title"),
                object.optString("artist"),
                object.optString("source"),
                object.optString("lyric"),
                object.optString("uri")
            );
        }
    }
}
