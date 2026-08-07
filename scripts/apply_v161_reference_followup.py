from pathlib import Path

root = Path(__file__).resolve().parents[1]
service_path = root / "app/src/main/java/com/jianglab/babywife/PlaybackControlService.java"
service = service_path.read_text(encoding="utf-8")

marker = "private PendingIntent audioOutputPendingIntent()"
if marker in service:
    print("v161 reference followup already applied")
    raise SystemExit(0)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)

service = replace_once(
    service,
    "import android.widget.RemoteViews;\n",
    "import android.widget.RemoteViews;\n\nimport org.json.JSONObject;\n",
    "json import",
)

service = replace_once(
    service,
    '''        views.setTextViewText(R.id.media_title, title);\n        views.setTextViewText(R.id.media_artist, artist);\n        views.setTextViewText(R.id.media_previous, "⏮");''',
    '''        views.setTextViewText(R.id.media_title, title);\n        views.setTextViewText(R.id.media_artist, artist);\n        views.setTextViewText(R.id.media_previous, "⏮");''',
    "binding anchor",
)

old_expanded = '''        if (expanded) {\n            int max = duration > 0L ? (int) Math.min(Integer.MAX_VALUE, duration) : 1;\n            int progress = duration > 0L\n                ? (int) Math.min(max, Math.max(0L, position)) : 0;\n            views.setProgressBar(R.id.media_progress, max, progress, false);\n            views.setTextViewText(R.id.media_position, formatMediaTime(position));\n            views.setTextViewText(R.id.media_duration, formatMediaTime(duration));\n        }\n    }\n\n    private String formatMediaTime(long millis) {'''
new_expanded = '''        if (expanded) {\n            views.setTextViewText(R.id.media_source, mediaSourceLabel());\n            views.setOnClickPendingIntent(R.id.media_headset, audioOutputPendingIntent());\n            views.setOnClickPendingIntent(R.id.media_queue, openPlayerPendingIntent());\n            int max = duration > 0L ? (int) Math.min(Integer.MAX_VALUE, duration) : 1;\n            int progress = duration > 0L\n                ? (int) Math.min(max, Math.max(0L, position)) : 0;\n            views.setProgressBar(R.id.media_progress, max, progress, false);\n            views.setTextViewText(R.id.media_position, formatMediaTime(position));\n            views.setTextViewText(R.id.media_duration, formatMediaTime(duration));\n        }\n    }\n\n    private String mediaSourceLabel() {\n        try {\n            JSONObject object = new JSONObject(catalogJson == null ? "{}" : catalogJson);\n            String source = object.optString("source", "").trim();\n            if (!source.isEmpty()) return source.toUpperCase(java.util.Locale.ROOT);\n        } catch (Exception ignored) {\n        }\n        String uri = mediaUri == null ? "" : mediaUri.trim();\n        if (uri.startsWith("content:") || uri.startsWith("file:")) return "LOCAL";\n        return "";\n    }\n\n    private PendingIntent audioOutputPendingIntent() {\n        Intent intent = new Intent(android.provider.Settings.ACTION_BLUETOOTH_SETTINGS)\n            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);\n        return PendingIntent.getActivity(\n            this, 31, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);\n    }\n\n    private PendingIntent openPlayerPendingIntent() {\n        Intent intent = new Intent(this, MainActivity.class)\n            .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);\n        return PendingIntent.getActivity(\n            this, 32, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);\n    }\n\n    private String formatMediaTime(long millis) {'''
service = replace_once(service, old_expanded, new_expanded, "expanded reference controls")

service_path.write_text(service, encoding="utf-8")
print("v161 standalone-reference followup applied")
