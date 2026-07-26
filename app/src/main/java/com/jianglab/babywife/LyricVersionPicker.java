package com.jianglab.babywife;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AbsListView;
import android.widget.BaseAdapter;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import bridge.Bridge;

/** Lazy lyric catalog. Nothing is searched until show() is called. */
final class LyricVersionPicker {
    interface Callback {
        void onStatus(String message);
        void onPreview(String lyric, String lyricTitle, String lyricArtist, String sourceLabel);
    }

    private static final String CACHE_PREFS = "lyric_version_directory_v1";
    private static final List<String> SOURCES = Arrays.asList(
        "netease", "qq", "kugou", "kuwo", "migu", "soda",
        "bilibili", "fivesing", "qianqian", "jamendo", "joox", "apple"
    );
    private static final int SOURCE_BATCH = 3;
    private static final int MAX_PER_SOURCE = 8;
    private static final int MAX_CACHED_ROWS = 96;

    private final Activity activity;
    private final String title;
    private final String artist;
    private final Callback callback;
    private final List<Candidate> rows = new ArrayList<>();
    private final Set<String> emitted = new HashSet<>();
    private final SharedPreferences cachePreferences;
    private final String cacheKey;
    private int nextSource = 0;
    private boolean loading = false;
    private CandidateAdapter adapter;
    private TextView status;
    private TextView footer;
    private AlertDialog dialog;

    private LyricVersionPicker(Activity activity, String title, String artist, Callback callback) {
        this.activity = activity;
        this.title = title == null ? "" : title.trim();
        this.artist = artist == null ? "" : artist.trim();
        this.callback = callback;
        this.cachePreferences = activity.getSharedPreferences(CACHE_PREFS, Activity.MODE_PRIVATE);
        this.cacheKey = "song_" + Integer.toHexString(
            (normalizeTitle(this.title) + "|" + normalizeArtist(this.artist)).hashCode()
        );
        loadCachedDirectory();
    }

    static void show(Activity activity, String title, String artist, Callback callback) {
        new LyricVersionPicker(activity, title, artist, callback).showDialog();
    }

    private void showDialog() {
        LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(12);
        root.setPadding(pad, pad, pad, pad);

        status = new TextView(activity);
        status.setTextSize(13);
        status.setTextColor(Color.DKGRAY);
        status.setPadding(0, 0, 0, dp(8));
        root.addView(status);

        ListView list = new ListView(activity);
        adapter = new CandidateAdapter();
        footer = new TextView(activity);
        footer.setTextSize(14);
        footer.setGravity(Gravity.CENTER);
        footer.setPadding(dp(10), dp(16), dp(10), dp(16));
        footer.setOnClickListener(view -> loadNext());
        list.addFooterView(footer, null, true);
        list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) -> {
            if (position < 0 || position >= rows.size()) return;
            fetchSelected(rows.get(position));
        });
        list.setOnScrollListener(new AbsListView.OnScrollListener() {
            private boolean nearBottom;

            @Override
            public void onScrollStateChanged(AbsListView view, int scrollState) {
                if (scrollState == SCROLL_STATE_IDLE && nearBottom && hasMore()) loadNext();
            }

            @Override
            public void onScroll(AbsListView view, int firstVisibleItem, int visibleItemCount, int totalItemCount) {
                nearBottom = totalItemCount > 0 && visibleItemCount > 0
                    && firstVisibleItem + visibleItemCount >= totalItemCount - 1;
            }
        });
        root.addView(list, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(430)
        ));

        dialog = new AlertDialog.Builder(activity)
            .setTitle("选择歌词版本")
            .setView(root)
            .setNegativeButton("关闭", null)
            .create();
        dialog.show();

        if (!rows.isEmpty()) {
            adapter.notifyDataSetChanged();
            status.setText("已载入上次保留的 " + rows.size() + " 个歌词版本"
                + (hasMore() ? "；向下滑动继续搜索更多" : "；全部来源已搜索"));
            updateFooter();
        } else {
            if (!hasMore()) nextSource = 0;
            status.setText("正在建立首批歌词版本目录...");
            footer.setText("正在搜索首批歌词版本...");
            loadNext();
        }
    }

    private boolean hasMore() {
        return nextSource < SOURCES.size();
    }

    private void updateFooter() {
        if (footer == null) return;
        footer.setEnabled(hasMore() && !loading);
        footer.setText(hasMore() ? "继续加载更多歌词版本" : "全部歌词来源已搜索完成");
    }

    private void loadNext() {
        if (loading || !hasMore()) return;
        loading = true;
        int start = nextSource;
        int end = Math.min(SOURCES.size(), start + SOURCE_BATCH);
        nextSource = end;
        footer.setEnabled(false);
        footer.setText("正在搜索下一批歌词版本...");
        status.setText("正在搜索第 " + (start + 1) + "–" + end + " 个来源...");

        new Thread(() -> {
            List<Candidate> incoming = new ArrayList<>();
            String keyword = (title + " " + artist).trim();
            for (int i = start; i < end; i++) {
                incoming.addAll(searchSource(SOURCES.get(i), keyword));
            }
            activity.runOnUiThread(() -> {
                for (Candidate item : incoming) {
                    if (rows.size() >= MAX_CACHED_ROWS) break;
                    if (emitted.add(item.key())) rows.add(item);
                }
                saveCachedDirectory();
                adapter.notifyDataSetChanged();
                loading = false;
                status.setText("已找到 " + rows.size() + " 个歌词版本"
                    + (hasMore() ? "；向下滑动继续加载" : "；全部来源已搜索"));
                updateFooter();
            });
        }).start();
    }

    private List<Candidate> searchSource(String source, String keyword) {
        List<Candidate> out = new ArrayList<>();
        try {
            JSONObject response = new JSONObject(Bridge.search(source, keyword));
            if (!response.optBoolean("ok", false)) return out;
            JSONArray data = response.optJSONArray("data");
            if (data == null) return out;
            int accepted = 0;
            for (int i = 0; i < data.length() && accepted < MAX_PER_SOURCE; i++) {
                JSONObject object = data.optJSONObject(i);
                if (object == null) continue;
                object.put("source", source);
                String id = object.optString("id", "").trim();
                String name = object.optString("name", "").trim();
                if (id.isEmpty() || name.isEmpty() || !titleRelated(title, name)) continue;
                out.add(new Candidate(
                    id,
                    name,
                    object.optString("artist", "未知歌手").trim(),
                    source,
                    object.toString()
                ));
                accepted++;
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    private void fetchSelected(Candidate candidate) {
        if (candidate == null || loading) return;
        loading = true;
        status.setText("正在读取《" + candidate.title + "》的歌词...");
        if (callback != null) callback.onStatus("正在读取选中的歌词版本...");
        android.util.Log.i("BabywifeLyrics", "picker fetch source=" + candidate.source
            + " id=" + candidate.id);
        new Thread(() -> {
            String result = PlaylistLyricMatcher.fetchExactLyric(candidate.rawJson);
            activity.runOnUiThread(() -> {
                loading = false;
                if (result.isEmpty()) {
                    status.setText("该版本暂未取得歌词，可继续选择其他版本");
                    android.util.Log.w("BabywifeLyrics", "picker lyric unavailable source="
                        + candidate.source + " id=" + candidate.id);
                    Toast.makeText(activity, "该歌词版本暂不可用", Toast.LENGTH_SHORT).show();
                    updateFooter();
                    return;
                }
                if (callback != null) {
                    callback.onPreview(
                        result,
                        candidate.title,
                        candidate.artist,
                        label(candidate.source)
                    );
                }
                android.util.Log.i("BabywifeLyrics", "picker lyric success source="
                    + candidate.source + " id=" + candidate.id + " chars=" + result.length());
                if (dialog != null && dialog.isShowing()) dialog.dismiss();
            });
        }, "lyric-version-fetch").start();
    }

    private void loadCachedDirectory() {
        String raw = cachePreferences.getString(cacheKey, "");
        if (raw == null || raw.trim().isEmpty()) return;
        try {
            JSONObject root = new JSONObject(raw);
            nextSource = Math.max(0, Math.min(SOURCES.size(), root.optInt("nextSource", 0)));
            JSONArray array = root.optJSONArray("rows");
            if (array == null) return;
            for (int i = 0; i < array.length() && rows.size() < MAX_CACHED_ROWS; i++) {
                JSONObject item = array.optJSONObject(i);
                if (item == null) continue;
                Candidate candidate = new Candidate(
                    item.optString("id", ""),
                    item.optString("title", ""),
                    item.optString("artist", "未知歌手"),
                    item.optString("source", ""),
                    item.optString("rawJson", "")
                );
                if (candidate.id.isEmpty() || candidate.title.isEmpty()
                    || candidate.source.isEmpty() || candidate.rawJson.isEmpty()) continue;
                if (emitted.add(candidate.key())) rows.add(candidate);
            }
        } catch (Exception ignored) {
            rows.clear();
            emitted.clear();
            nextSource = 0;
        }
    }

    private void saveCachedDirectory() {
        try {
            JSONObject root = new JSONObject();
            root.put("nextSource", nextSource);
            JSONArray array = new JSONArray();
            for (Candidate candidate : rows) {
                JSONObject item = new JSONObject();
                item.put("id", candidate.id);
                item.put("title", candidate.title);
                item.put("artist", candidate.artist);
                item.put("source", candidate.source);
                item.put("rawJson", candidate.rawJson);
                array.put(item);
            }
            root.put("rows", array);
            cachePreferences.edit().putString(cacheKey, root.toString()).apply();
        } catch (Exception ignored) {
        }
    }

    private static boolean titleRelated(String wanted, String candidate) {
        String left = normalizeTitle(wanted);
        String right = normalizeTitle(candidate);
        if (left.isEmpty() || right.isEmpty()) return false;
        return left.equals(right) || left.contains(right) || right.contains(left);
    }

    private static String normalizeTitle(String value) {
        if (value == null) return "";
        return value.toLowerCase(Locale.ROOT)
            .replaceAll("[（(【\\[].*?[）)】\\]]", "")
            .replaceAll("[\\s\\p{Punct}《》·•]", "")
            .trim();
    }

    private static String normalizeArtist(String value) {
        if (value == null) return "";
        return value.toLowerCase(Locale.ROOT)
            .replaceAll("[\\s\\p{Punct}/、&·•]", "")
            .trim();
    }

    private static String label(String source) {
        return CatalogSearch.labelForSource(source);
    }

    private int dp(int value) {
        return (int) (value * activity.getResources().getDisplayMetrics().density + 0.5f);
    }

    private final class CandidateAdapter extends BaseAdapter {
        @Override
        public int getCount() {
            return rows.size();
        }

        @Override
        public Candidate getItem(int position) {
            return rows.get(position);
        }

        @Override
        public long getItemId(int position) {
            return position;
        }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            TextView text = convertView instanceof TextView ? (TextView) convertView : new TextView(activity);
            Candidate item = getItem(position);
            text.setText("歌词名：" + item.title + "\n歌手：" + item.artist + "\n来源：" + label(item.source));
            text.setTextSize(15);
            text.setTextColor(Color.rgb(28, 28, 32));
            text.setPadding(dp(12), dp(10), dp(12), dp(10));
            return text;
        }
    }

    private static final class Candidate {
        final String id;
        final String title;
        final String artist;
        final String source;
        final String rawJson;

        Candidate(String id, String title, String artist, String source, String rawJson) {
            this.id = id == null ? "" : id;
            this.title = title == null ? "" : title;
            this.artist = artist == null || artist.isEmpty() ? "未知歌手" : artist;
            this.source = source == null ? "" : source;
            this.rawJson = rawJson == null ? "" : rawJson;
        }

        String key() {
            return source + "|" + id;
        }
    }
}
