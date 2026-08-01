package com.jianglab.babywife;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Build;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AbsListView;
import android.widget.BaseAdapter;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Manual replacement picker based on the private-library identity rules.
 * Only exact normalized title+artist matches that can resolve an audio URL are shown.
 */
final class SongVersionPicker {
    interface Callback {
        void onStatus(String message);
        void onPreview(String title, String artist, String sourceLabel, String catalogJson);
        void onUnavailable();
    }

    private static final String CACHE_PREFS = "song_version_directory_v4_exact_playable";
    private static final int MAX_CACHED_ROWS = 64;

    private final Activity activity;
    private final String title;
    private final String artist;
    private final Callback callback;
    private final CatalogSearch.Session session;
    private final List<CatalogSearch.Track> rows = new ArrayList<>();
    private final Set<String> emitted = new HashSet<>();
    private final SharedPreferences cachePreferences;
    private final String cacheKey;
    private boolean loading;
    private CandidateAdapter adapter;
    private TextView status;
    private TextView footer;
    private AlertDialog dialog;
    private float touchDownY;

    private SongVersionPicker(Activity activity, String identity, String title,
                              String artist, Callback callback) {
        this.activity = activity;
        this.title = title == null ? "" : title.trim();
        this.artist = artist == null ? "" : artist.trim();
        this.callback = callback;
        this.cachePreferences = activity.getSharedPreferences(CACHE_PREFS, Activity.MODE_PRIVATE);
        this.cacheKey = "song_" + Integer.toHexString(
            CatalogSearch.identityKey(this.title, this.artist).hashCode());
        this.session = CatalogSearch.newSession(
            activity,
            (this.title + " " + this.artist).trim(),
            "全部平台",
            true
        );
        loadCachedDirectory();
    }

    static void show(Activity activity, String identity, String title,
                     String artist, Callback callback) {
        new SongVersionPicker(activity, identity, title, artist, callback).showDialog();
    }

    static void show(Activity activity, String title, String artist, Callback callback) {
        show(activity, "", title, artist, callback);
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
            CatalogSearch.Track selected = rows.get(position);
            if (callback != null) {
                callback.onPreview(selected.title, selected.artist,
                    selected.sourceLabel, selected.rawJson);
            }
            if (dialog != null && dialog.isShowing()) dialog.dismiss();
        });
        list.setOnScrollListener(new AbsListView.OnScrollListener() {
            private boolean nearBottom;

            @Override
            public void onScrollStateChanged(AbsListView view, int scrollState) {
                if (scrollState == SCROLL_STATE_IDLE && nearBottom && session.hasMore()) loadNext();
            }

            @Override
            public void onScroll(AbsListView view, int firstVisibleItem,
                                 int visibleItemCount, int totalItemCount) {
                nearBottom = totalItemCount > 0 && visibleItemCount > 0
                    && firstVisibleItem + visibleItemCount >= totalItemCount - 1;
            }
        });
        list.setOnTouchListener((view, event) -> {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                touchDownY = event.getY();
            } else if (event.getActionMasked() == MotionEvent.ACTION_UP) {
                float distance = event.getY() - touchDownY;
                if (distance >= dp(72) && list.getFirstVisiblePosition() == 0
                    && session.hasMore() && !loading) {
                    loadNext();
                }
            }
            return false;
        });
        root.addView(list, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(430)));

        dialog = new AlertDialog.Builder(activity)
            .setTitle("选择可播放的同歌名同歌手版本")
            .setView(root)
            .setNegativeButton("关闭", null)
            .create();
        dialog.show();

        if (!rows.isEmpty()) {
            adapter.notifyDataSetChanged();
            status.setText("已保留上次验证可播放的 " + rows.size() + " 个版本"
                + (session.hasMore() ? "；下拉或滚到底部加载更多" : "；全部来源已搜索"));
            updateFooter();
        } else {
            status.setText("正在按同歌名同歌手规则搜索并验证可播放来源…");
            loadNext();
        }
    }

    private void loadNext() {
        if (loading || !session.hasMore()) {
            updateFooter();
            return;
        }
        loading = true;
        footer.setEnabled(false);
        footer.setText("正在搜索并验证更多版本…");
        if (callback != null) {
            callback.onStatus("手动搜索优先：正在查找同歌名同歌手且可播放的版本…");
        }

        new Thread(() -> {
            CatalogSearch.Batch batch = null;
            Throwable failure = null;
            List<CatalogSearch.Track> accepted = new ArrayList<>();
            try {
                batch = session.loadNext();
                for (CatalogSearch.Track track : batch.tracks) {
                    if (track == null || track.id.isEmpty()) continue;
                    if (!CatalogSearch.sameIdentity(title, artist, track)) continue;
                    String playableCatalog = NetworkMediaCache.prepareManualCatalog(
                        activity, track.rawJson);
                    if (playableCatalog.isEmpty()) continue;
                    CatalogSearch.Track verified = new CatalogSearch.Track(
                        new JSONObject(playableCatalog), track.sourceCode);
                    if (emitted.add(verified.key())) accepted.add(verified);
                }
            } catch (Throwable error) {
                failure = error;
            }
            CatalogSearch.Batch result = batch;
            Throwable error = failure;
            if (!activityUsable()) return;
            activity.runOnUiThread(() -> {
                if (!activityUsable()) return;
                loading = false;
                if (error != null) {
                    status.setText("本次验证异常，已保留现有可播放结果；可下拉重试");
                    if (callback != null) callback.onStatus("歌曲版本验证异常，可继续重试");
                    updateFooter();
                    return;
                }
                rows.addAll(accepted);
                saveCachedDirectory();
                adapter.notifyDataSetChanged();
                status.setText("已找到并验证可播放的 " + rows.size() + " 个同歌名同歌手版本"
                    + (session.hasMore() ? "；下拉或滚到底部继续加载" : "；全部来源已搜索"));
                if (result != null && !result.hasMore && rows.isEmpty() && callback != null) {
                    callback.onUnavailable();
                }
                updateFooter();
            });
        }, "manual-exact-playable-version-search").start();
    }

    private boolean activityUsable() {
        if (activity == null || activity.isFinishing()) return false;
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.JELLY_BEAN_MR1 || !activity.isDestroyed();
    }

    private void loadCachedDirectory() {
        String raw = cachePreferences.getString(cacheKey, "");
        if (raw == null || raw.trim().isEmpty()) return;
        try {
            JSONObject root = new JSONObject(raw);
            session.restoreNextSourceIndex(root.optInt("nextSourceIndex", 0));
            JSONArray array = root.optJSONArray("rows");
            if (array == null) return;
            for (int i = 0; i < array.length() && rows.size() < MAX_CACHED_ROWS; i++) {
                JSONObject item = array.optJSONObject(i);
                if (item == null) continue;
                String rawJson = item.optString("rawJson", "");
                String source = item.optString("source", "");
                if (rawJson.isEmpty() || source.isEmpty()) continue;
                CatalogSearch.Track track = new CatalogSearch.Track(new JSONObject(rawJson), source);
                if (track.id.isEmpty() || !CatalogSearch.sameIdentity(title, artist, track)) continue;
                if (!emitted.add(track.key())) continue;
                rows.add(track);
            }
        } catch (Exception ignored) {
            rows.clear();
            emitted.clear();
            session.restoreNextSourceIndex(0);
        }
    }

    private void saveCachedDirectory() {
        try {
            JSONObject root = new JSONObject();
            root.put("nextSourceIndex", session.nextSourceIndex());
            JSONArray array = new JSONArray();
            int start = Math.max(0, rows.size() - MAX_CACHED_ROWS);
            for (int i = start; i < rows.size(); i++) {
                CatalogSearch.Track track = rows.get(i);
                JSONObject item = new JSONObject();
                item.put("source", track.sourceCode);
                item.put("rawJson", track.rawJson);
                array.put(item);
            }
            root.put("rows", array);
            cachePreferences.edit().putString(cacheKey, root.toString()).apply();
        } catch (Exception ignored) {
        }
    }

    private void updateFooter() {
        if (footer == null) return;
        boolean more = session.hasMore();
        footer.setEnabled(more && !loading);
        footer.setText(more
            ? "下拉或点击此处继续验证其他来源"
            : "全部歌曲来源已搜索完成");
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
        public CatalogSearch.Track getItem(int position) {
            return rows.get(position);
        }

        @Override
        public long getItemId(int position) {
            return position;
        }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            TextView text = convertView instanceof TextView
                ? (TextView) convertView : new TextView(activity);
            CatalogSearch.Track item = getItem(position);
            String album = item.album == null || item.album.trim().isEmpty()
                ? "未标注专辑" : item.album;
            text.setText("歌名：" + item.title + "\n歌手：" + item.artist
                + "\n专辑：" + album + "    来源：" + item.sourceLabel
                + "    状态：已验证可播放");
            text.setTextSize(15);
            text.setTextColor(Color.rgb(28, 28, 32));
            text.setPadding(dp(12), dp(10), dp(12), dp(10));
            return text;
        }
    }
}
