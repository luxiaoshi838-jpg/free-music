package com.jianglab.babywife;

import android.app.Activity;
import android.app.AlertDialog;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AbsListView;
import android.widget.BaseAdapter;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Metadata-only song version picker. Search never resolves or downloads audio;
 * the selected catalog is only committed after the shared confirmation button is pressed.
 */
final class SongVersionPicker {
    interface Callback {
        void onStatus(String message);
        void onPreview(String title, String artist, String sourceLabel, String catalogJson);
    }

    private final Activity activity;
    private final String title;
    private final String artist;
    private final Callback callback;
    private final CatalogSearch.Session session;
    private final List<CatalogSearch.Track> rows = new ArrayList<>();
    private final Set<String> emitted = new HashSet<>();
    private boolean loading;
    private CandidateAdapter adapter;
    private TextView status;
    private TextView footer;
    private AlertDialog dialog;

    private SongVersionPicker(Activity activity, String title, String artist, Callback callback) {
        this.activity = activity;
        this.title = title == null ? "" : title.trim();
        this.artist = artist == null ? "" : artist.trim();
        this.callback = callback;
        this.session = CatalogSearch.newSession((this.title + " " + this.artist).trim(), "全部平台");
    }

    static void show(Activity activity, String title, String artist, Callback callback) {
        new SongVersionPicker(activity, title, artist, callback).showDialog();
    }

    private void showDialog() {
        LinearLayout root = new LinearLayout(activity);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(12);
        root.setPadding(pad, pad, pad, pad);

        status = new TextView(activity);
        status.setTextSize(13);
        status.setTextColor(Color.DKGRAY);
        status.setText("正在建立首批歌曲版本目录…");
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
                callback.onPreview(selected.title, selected.artist, selected.sourceLabel, selected.rawJson);
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
            public void onScroll(AbsListView view, int firstVisibleItem, int visibleItemCount, int totalItemCount) {
                nearBottom = totalItemCount > 0 && visibleItemCount > 0
                    && firstVisibleItem + visibleItemCount >= totalItemCount - 1;
            }
        });
        root.addView(list, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(430)));

        dialog = new AlertDialog.Builder(activity)
            .setTitle("选择歌曲版本")
            .setView(root)
            .setNegativeButton("关闭", null)
            .create();
        dialog.show();
        loadNext();
    }

    private void loadNext() {
        if (loading || !session.hasMore()) {
            updateFooter();
            return;
        }
        loading = true;
        footer.setEnabled(false);
        footer.setText("正在搜索更多歌曲版本…");
        if (callback != null) callback.onStatus("正在搜索可替换的歌曲版本…");

        new Thread(() -> {
            CatalogSearch.Batch batch = session.loadNext();
            List<CatalogSearch.Track> accepted = new ArrayList<>();
            for (CatalogSearch.Track track : batch.tracks) {
                if (track == null || track.id.isEmpty() || !CatalogSearch.sameIdentity(title, artist, track)) continue;
                if (emitted.add(track.key())) accepted.add(track);
            }
            activity.runOnUiThread(() -> {
                rows.addAll(accepted);
                adapter.notifyDataSetChanged();
                loading = false;
                status.setText("已找到 " + rows.size() + " 个歌曲版本"
                    + (session.hasMore() ? "；向下滑动继续加载" : "；全部来源已搜索"));
                updateFooter();
            });
        }).start();
    }

    private void updateFooter() {
        if (footer == null) return;
        boolean more = session.hasMore();
        footer.setEnabled(more && !loading);
        footer.setText(more ? "继续加载更多歌曲版本" : "全部歌曲来源已搜索完成");
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
            TextView text = convertView instanceof TextView ? (TextView) convertView : new TextView(activity);
            CatalogSearch.Track item = getItem(position);
            String album = item.album == null || item.album.trim().isEmpty() ? "未标注专辑" : item.album;
            text.setText("歌名：" + item.title + "\n歌手：" + item.artist
                + "\n专辑：" + album + "    来源：" + item.sourceLabel);
            text.setTextSize(15);
            text.setTextColor(Color.rgb(28, 28, 32));
            text.setPadding(dp(12), dp(10), dp(12), dp(10));
            return text;
        }
    }
}
