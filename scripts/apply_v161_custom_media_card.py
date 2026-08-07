from pathlib import Path

root = Path(__file__).resolve().parents[1]
service_path = root / "app/src/main/java/com/jianglab/babywife/PlaybackControlService.java"
gradle_path = root / "app/build.gradle"
log_path = root / "PROJECT_LOG.md"
res_layout = root / "app/src/main/res/layout"
res_layout.mkdir(parents=True, exist_ok=True)
compact_path = res_layout / "notification_media_compact.xml"
expanded_path = res_layout / "notification_media_expanded.xml"

service = service_path.read_text(encoding="utf-8")
gradle = gradle_path.read_text(encoding="utf-8")

if "versionCode 2026080761" in gradle:
    print("v161 already applied")
    raise SystemExit(0)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)

service = replace_once(
    service,
    "import android.os.IBinder;\n",
    "import android.os.IBinder;\nimport android.view.View;\nimport android.widget.RemoteViews;\n",
    "RemoteViews imports",
)

old_build = '''    private Notification buildNotification() {
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
        int mediaColor = artwork == null
            ? FALLBACK_MEDIA_COLOR : darkMediaColor(PlaybackArtworkLoader.averageColor(artwork));
        builder.setColor(mediaColor);
        if (artwork != null) {
            // High-resolution square art is supplied to both MediaSession and
            // the notification. Android/OEM lock screens can then crop/enlarge
            // it as the media-card backdrop instead of falling back to white.
            builder.setLargeIcon(artwork);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder.setColorized(true);
        }
        return builder.build();
    }

    private int darkMediaColor(int color) {
        if (color == 0) return FALLBACK_MEDIA_COLOR;
        int red = Math.max(18, Color.red(color) * 58 / 100);
        int green = Math.max(18, Color.green(color) * 58 / 100);
        int blue = Math.max(22, Color.blue(color) * 58 / 100);
        return Color.rgb(red, green, blue);
    }
'''

new_build = '''    private Notification buildNotification() {
        Intent openIntent = new Intent(this, MainActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent contentIntent = PendingIntent.getActivity(
            this,
            10,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        // v161 intentionally does NOT use Notification.MediaStyle. On the user's
        // ROM the system completely re-skinned MediaStyle into the same pale card,
        // ignoring the app's dark color. A custom RemoteViews notification makes
        // the visible card itself app-controlled instead of palette-controlled by
        // SystemUI. MediaSession remains active for headset/Bluetooth transport.
        RemoteViews compact = buildCompactRemoteViews();
        RemoteViews expanded = buildExpandedRemoteViews();

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
            .setColor(FALLBACK_MEDIA_COLOR);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            builder.setCustomContentView(compact)
                .setCustomBigContentView(expanded)
                .setCustomHeadsUpContentView(compact)
                .setStyle(new Notification.DecoratedCustomViewStyle());
        } else {
            builder.setContent(compact);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            // Do not let SystemUI recolor the custom dark surface from wallpaper.
            builder.setColorized(false);
        }
        return builder.build();
    }

    private RemoteViews buildCompactRemoteViews() {
        RemoteViews views = new RemoteViews(getPackageName(), R.layout.notification_media_compact);
        bindCommonRemoteViews(views, false);
        return views;
    }

    private RemoteViews buildExpandedRemoteViews() {
        RemoteViews views = new RemoteViews(getPackageName(), R.layout.notification_media_expanded);
        bindCommonRemoteViews(views, true);
        return views;
    }

    private void bindCommonRemoteViews(RemoteViews views, boolean expanded) {
        views.setTextViewText(R.id.media_title, title);
        views.setTextViewText(R.id.media_artist, artist);
        views.setTextViewText(R.id.media_previous, "⏮");
        views.setTextViewText(R.id.media_toggle, playing ? "Ⅱ" : "▶");
        views.setTextViewText(R.id.media_next, "⏭");
        views.setOnClickPendingIntent(R.id.media_previous,
            servicePendingIntent(ACTION_PREVIOUS, expanded ? 21 : 11));
        views.setOnClickPendingIntent(R.id.media_toggle,
            servicePendingIntent(ACTION_TOGGLE, expanded ? 22 : 12));
        views.setOnClickPendingIntent(R.id.media_next,
            servicePendingIntent(ACTION_NEXT, expanded ? 23 : 13));

        if (artwork != null) {
            views.setImageViewBitmap(R.id.media_artwork, artwork);
            views.setViewVisibility(R.id.media_artwork, View.VISIBLE);
            if (expanded) {
                views.setImageViewBitmap(R.id.media_background, artwork);
                views.setViewVisibility(R.id.media_background, View.VISIBLE);
            }
        } else {
            views.setViewVisibility(R.id.media_artwork, View.INVISIBLE);
            if (expanded) views.setViewVisibility(R.id.media_background, View.GONE);
        }

        if (expanded) {
            int max = duration > 0L ? (int) Math.min(Integer.MAX_VALUE, duration) : 1;
            int progress = duration > 0L
                ? (int) Math.min(max, Math.max(0L, position)) : 0;
            views.setProgressBar(R.id.media_progress, max, progress, false);
            views.setTextViewText(R.id.media_position, formatMediaTime(position));
            views.setTextViewText(R.id.media_duration, formatMediaTime(duration));
        }
    }

    private String formatMediaTime(long millis) {
        long totalSeconds = Math.max(0L, millis) / 1000L;
        long minutes = totalSeconds / 60L;
        long seconds = totalSeconds % 60L;
        return String.format(java.util.Locale.ROOT, "%d:%02d", minutes, seconds);
    }
'''

service = replace_once(service, old_build, new_build, "replace MediaStyle with custom card")

gradle = replace_once(
    gradle,
    "        versionCode 2026080760\n        versionName \"2026.08.07.v160-fast-cache-dark-media\"",
    "        versionCode 2026080761\n        versionName \"2026.08.07.v161-custom-dark-media-card\"",
    "v161 version",
)

compact_xml = '''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="72dp"
    android:orientation="horizontal"
    android:gravity="center_vertical"
    android:paddingStart="10dp"
    android:paddingEnd="10dp"
    android:background="#FF1B191F">

    <ImageView
        android:id="@+id/media_artwork"
        android:layout_width="52dp"
        android:layout_height="52dp"
        android:layout_marginEnd="10dp"
        android:scaleType="centerCrop"
        android:contentDescription="封面" />

    <LinearLayout
        android:layout_width="0dp"
        android:layout_height="match_parent"
        android:layout_weight="1"
        android:orientation="vertical"
        android:gravity="center_vertical">

        <TextView
            android:id="@+id/media_title"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:maxLines="1"
            android:ellipsize="end"
            android:textColor="#FFFFFFFF"
            android:textStyle="bold"
            android:textSize="16sp" />

        <TextView
            android:id="@+id/media_artist"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:layout_marginTop="2dp"
            android:maxLines="1"
            android:ellipsize="end"
            android:textColor="#FFC8C3CC"
            android:textSize="13sp" />
    </LinearLayout>

    <TextView
        android:id="@+id/media_previous"
        android:layout_width="42dp"
        android:layout_height="match_parent"
        android:gravity="center"
        android:textColor="#FFFFFFFF"
        android:textSize="23sp" />

    <TextView
        android:id="@+id/media_toggle"
        android:layout_width="44dp"
        android:layout_height="match_parent"
        android:gravity="center"
        android:textColor="#FFFFFFFF"
        android:textSize="26sp" />

    <TextView
        android:id="@+id/media_next"
        android:layout_width="42dp"
        android:layout_height="match_parent"
        android:gravity="center"
        android:textColor="#FFFFFFFF"
        android:textSize="23sp" />
</LinearLayout>
'''

expanded_xml = '''<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="184dp"
    android:background="#FF17151A">

    <ImageView
        android:id="@+id/media_background"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:scaleType="centerCrop"
        android:contentDescription="封面背景" />

    <View
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:background="#B8000000" />

    <LinearLayout
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:orientation="vertical"
        android:paddingStart="14dp"
        android:paddingEnd="14dp"
        android:paddingTop="12dp"
        android:paddingBottom="10dp">

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="66dp"
            android:orientation="horizontal"
            android:gravity="center_vertical">

            <ImageView
                android:id="@+id/media_artwork"
                android:layout_width="58dp"
                android:layout_height="58dp"
                android:layout_marginEnd="12dp"
                android:scaleType="centerCrop"
                android:contentDescription="封面" />

            <LinearLayout
                android:layout_width="0dp"
                android:layout_height="match_parent"
                android:layout_weight="1"
                android:orientation="vertical"
                android:gravity="center_vertical">

                <TextView
                    android:id="@+id/media_title"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:maxLines="1"
                    android:ellipsize="end"
                    android:textColor="#FFFFFFFF"
                    android:textStyle="bold"
                    android:textSize="19sp" />

                <TextView
                    android:id="@+id/media_artist"
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_marginTop="3dp"
                    android:maxLines="1"
                    android:ellipsize="end"
                    android:textColor="#FFE0DCE4"
                    android:textSize="14sp" />
            </LinearLayout>
        </LinearLayout>

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="48dp"
            android:orientation="horizontal"
            android:gravity="center">

            <TextView
                android:id="@+id/media_previous"
                android:layout_width="72dp"
                android:layout_height="match_parent"
                android:gravity="center"
                android:textColor="#FFFFFFFF"
                android:textSize="28sp" />

            <TextView
                android:id="@+id/media_toggle"
                android:layout_width="86dp"
                android:layout_height="match_parent"
                android:gravity="center"
                android:textColor="#FFFFFFFF"
                android:textSize="32sp" />

            <TextView
                android:id="@+id/media_next"
                android:layout_width="72dp"
                android:layout_height="match_parent"
                android:gravity="center"
                android:textColor="#FFFFFFFF"
                android:textSize="28sp" />
        </LinearLayout>

        <LinearLayout
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="horizontal"
            android:gravity="center_vertical">

            <TextView
                android:id="@+id/media_position"
                android:layout_width="44dp"
                android:layout_height="wrap_content"
                android:gravity="start"
                android:textColor="#FFD4CFD8"
                android:textSize="11sp" />

            <ProgressBar
                android:id="@+id/media_progress"
                style="?android:attr/progressBarStyleHorizontal"
                android:layout_width="0dp"
                android:layout_height="4dp"
                android:layout_weight="1"
                android:layout_marginStart="6dp"
                android:layout_marginEnd="6dp" />

            <TextView
                android:id="@+id/media_duration"
                android:layout_width="44dp"
                android:layout_height="wrap_content"
                android:gravity="end"
                android:textColor="#FFD4CFD8"
                android:textSize="11sp" />
        </LinearLayout>
    </LinearLayout>
</FrameLayout>
'''

compact_path.write_text(compact_xml, encoding="utf-8")
expanded_path.write_text(expanded_xml, encoding="utf-8")
service_path.write_text(service, encoding="utf-8")
gradle_path.write_text(gradle, encoding="utf-8")

log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
entry = '''\n## 2026-08-07 · v161\n- 基线：v160，继续保留 v159/v160 的缓存修复。\n- 锁屏/通知栏不再使用会被手机 SystemUI 强制改成浅色的 `Notification.MediaStyle`；改为应用自定义深色 RemoteViews 媒体卡。\n- 展开卡片以歌曲封面作为全卡背景并叠加深色遮罩，同时保留封面缩略图、标题、歌手、进度和上一首/播放暂停/下一首。\n- MediaSession 继续保留用于耳机/蓝牙媒体键，但不再把 token 交给系统去重绘浅色媒体卡。\n'''
if "## 2026-08-07 · v161" not in log:
    log_path.write_text(log.rstrip() + "\n" + entry, encoding="utf-8")

required = [
    "versionCode 2026080761",
    "R.layout.notification_media_compact",
    "R.layout.notification_media_expanded",
    "new Notification.DecoratedCustomViewStyle()",
    "views.setImageViewBitmap(R.id.media_background, artwork)",
]
combined = service + "\n" + gradle + compact_xml + expanded_xml
for token in required:
    if token not in combined:
        raise SystemExit("missing v161 token: " + token)
if "new Notification.MediaStyle()" in service:
    raise SystemExit("MediaStyle still present in v161 service")
if "favorite" in service.lower() or "heart" in service.lower():
    raise SystemExit("unexpected favorite/heart action")

print("v161 custom media card patch applied")
