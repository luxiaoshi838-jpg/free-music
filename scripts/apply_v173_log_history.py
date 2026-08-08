from pathlib import Path


def replace_method(text: str, signature: str, replacement: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise SystemExit("method not found: " + signature)
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit("method brace not found: " + signature)
    depth = 0
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement + text[i + 1:]
    raise SystemExit("unterminated method: " + signature)


gradle = Path("app/build.gradle")
g = gradle.read_text(encoding="utf-8")
if "versionCode 2026080872" in g:
    g = g.replace("versionCode 2026080872", "versionCode 2026080873", 1)
if 'versionName "2026.08.08.v172-compact-search-mode"' in g:
    g = g.replace(
        'versionName "2026.08.08.v172-compact-search-mode"',
        'versionName "2026.08.08.v173-log-history"',
        1,
    )
if "versionCode 2026080873" not in g or 'versionName "2026.08.08.v173-log-history"' not in g:
    raise SystemExit("v173 version patch failed")
gradle.write_text(g, encoding="utf-8")

path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = path.read_text(encoding="utf-8")

key_anchor = '    private static final String KEY_CRASH_REPORT_DISMISSED = "last_crash_report_dismissed";\n'
key_insert = key_anchor + '    private static final String KEY_PROBLEM_REPORT_HISTORY = "problem_report_history_v1";\n    private static final int MAX_PROBLEM_REPORT_HISTORY = 10;\n'
if "KEY_PROBLEM_REPORT_HISTORY" not in text:
    if key_anchor not in text:
        raise SystemExit("history key anchor missing")
    text = text.replace(key_anchor, key_insert, 1)

create_old = """        loadPlaylists();
        suppressCrashReportAfterAppUpdate();
        captureLastProcessExitReport();"""
create_new = """        loadPlaylists();
        migrateLegacyProblemReportIfNeeded();
        suppressCrashReportAfterAppUpdate();
        captureLastProcessExitReport();"""
if create_new not in text:
    if create_old not in text:
        raise SystemExit("onCreate report sequence anchor missing")
    text = text.replace(create_old, create_new, 1)

suppress_method = '''    private void suppressCrashReportAfterAppUpdate() {
        try {
            SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
            PackageInfo packageInfo = getPackageManager().getPackageInfo(getPackageName(), 0);
            long currentVersion = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P
                ? packageInfo.getLongVersionCode() : packageInfo.versionCode;
            boolean hasVersionMarker = prefs.contains(KEY_LAST_APP_VERSION_CODE);
            long previousVersion = prefs.getLong(KEY_LAST_APP_VERSION_CODE, currentVersion);
            boolean packageHasBeenUpdated = packageInfo.lastUpdateTime > packageInfo.firstInstallTime + 1000L;
            boolean firstLaunchWithMarkerSupportAfterUpdate = !hasVersionMarker && packageHasBeenUpdated;
            boolean versionChanged = hasVersionMarker && previousVersion != currentVersion;

            SharedPreferences.Editor editor = prefs.edit()
                .putLong(KEY_LAST_APP_VERSION_CODE, currentVersion);
            if (firstLaunchWithMarkerSupportAfterUpdate || versionChanged) {
                // APK update is a normal process restart, not a diagnostic failure.
                // Mark all pre-launch exit history as handled while preserving older real logs.
                editor.putLong(KEY_LAST_HANDLED_EXIT_TIME, System.currentTimeMillis())
                    .putBoolean(KEY_CRASH_REPORT_DISMISSED, true)
                    .putBoolean(KEY_PLAYBACK_TRANSITION_PENDING, false)
                    .remove(KEY_PLAYBACK_TRANSITION_DETAIL)
                    .remove(KEY_PLAYBACK_TRANSITION_TIME);
            }
            editor.apply();
        } catch (Throwable ignored) {
        }
    }'''
text = replace_method(text, "    private void suppressCrashReportAfterAppUpdate()", suppress_method)

store_method = '''    private void storeProblemReport(String reportText) {
        String text = trimForReport(reportText, 60000);
        long now = System.currentTimeMillis();
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        appendProblemReportHistory(prefs, text, now);
        prefs.edit()
            .putString(KEY_CRASH_REPORT, text)
            .putLong(KEY_CRASH_REPORT_TIME, now)
            .putBoolean(KEY_CRASH_REPORT_DISMISSED, false)
            .apply();
    }'''
text = replace_method(text, "    private void storeProblemReport(String reportText)", store_method)

open_method = '''    private void openSavedCrashReport() {
        migrateLegacyProblemReportIfNeeded();
        JSONArray history = readProblemReportHistory();
        if (history.length() == 0) {
            toast("暂无播放/闪退问题报告");
            return;
        }
        showProblemReportHistoryDialog(history);
    }'''
text = replace_method(text, "    private void openSavedCrashReport()", open_method)

insert_marker = "    private void maybeRequireJiangLabPassphrase() {"
history_methods = '''    private void migrateLegacyProblemReportIfNeeded() {
        try {
            SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
            JSONArray existingHistory = readProblemReportHistory();
            if (existingHistory.length() > 0) return;
            String legacy = prefs.getString(KEY_CRASH_REPORT, "");
            if (legacy == null || legacy.trim().isEmpty()) return;
            long time = prefs.getLong(KEY_CRASH_REPORT_TIME, System.currentTimeMillis());
            appendProblemReportHistory(prefs, legacy, time);
        } catch (Throwable ignored) {
        }
    }

    private JSONArray readProblemReportHistory() {
        try {
            String raw = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .getString(KEY_PROBLEM_REPORT_HISTORY, "[]");
            return new JSONArray(raw == null || raw.trim().isEmpty() ? "[]" : raw);
        } catch (Throwable ignored) {
            return new JSONArray();
        }
    }

    private String problemReportName(long timestamp) {
        try {
            return new java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.ROOT)
                .format(new java.util.Date(timestamp));
        } catch (Throwable ignored) {
            return String.valueOf(timestamp);
        }
    }

    private void appendProblemReportHistory(SharedPreferences prefs, String report, long timestamp) {
        try {
            JSONArray old = readProblemReportHistory();
            JSONArray next = new JSONArray();
            JSONObject newest = new JSONObject();
            newest.put("name", problemReportName(timestamp));
            newest.put("time", timestamp);
            newest.put("text", trimForReport(report, 60000));
            next.put(newest);
            for (int i = 0; i < old.length() && next.length() < MAX_PROBLEM_REPORT_HISTORY; i++) {
                JSONObject item = old.optJSONObject(i);
                if (item == null) continue;
                long oldTime = item.optLong("time", 0L);
                String oldText = item.optString("text", "");
                if (oldTime == timestamp && oldText.equals(report)) continue;
                next.put(item);
            }
            prefs.edit().putString(KEY_PROBLEM_REPORT_HISTORY, next.toString()).apply();
        } catch (Throwable ignored) {
        }
    }

    private void showProblemReportHistoryDialog(JSONArray history) {
        if (isFinishing()) return;
        int count = Math.min(history.length(), MAX_PROBLEM_REPORT_HISTORY);
        CharSequence[] names = new CharSequence[count];
        for (int i = 0; i < count; i++) {
            JSONObject item = history.optJSONObject(i);
            names[i] = item == null ? "未知日志" : item.optString("name", "未知日志");
        }
        new AlertDialog.Builder(this)
            .setTitle("播放/闪退日志（最多10条）")
            .setItems(names, (dialog, which) -> {
                JSONObject item = history.optJSONObject(which);
                if (item != null) showProblemReportActions(item);
            })
            .setNegativeButton("关闭", null)
            .show();
    }

    private void showProblemReportActions(JSONObject item) {
        String name = item.optString("name", "未知日志");
        String report = item.optString("text", "");
        new AlertDialog.Builder(this)
            .setTitle(name)
            .setItems(new CharSequence[] {"查看", "复制", "删除"}, (dialog, which) -> {
                if (which == 0) {
                    showCrashReportDialog(report);
                } else if (which == 1) {
                    ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                    if (clipboard != null) {
                        clipboard.setPrimaryClip(ClipData.newPlainText(name, report));
                        toast("已复制日志：" + name);
                    }
                } else if (which == 2) {
                    confirmDeleteProblemReport(item);
                }
            })
            .setNegativeButton("取消", null)
            .show();
    }

    private void confirmDeleteProblemReport(JSONObject target) {
        String name = target.optString("name", "未知日志");
        new AlertDialog.Builder(this)
            .setTitle("删除日志")
            .setMessage("确定删除 " + name + "？")
            .setPositiveButton("删除", (dialog, which) -> deleteProblemReport(target))
            .setNegativeButton("取消", null)
            .show();
    }

    private void deleteProblemReport(JSONObject target) {
        try {
            JSONArray old = readProblemReportHistory();
            JSONArray next = new JSONArray();
            long targetTime = target.optLong("time", Long.MIN_VALUE);
            String targetText = target.optString("text", "");
            for (int i = 0; i < old.length(); i++) {
                JSONObject item = old.optJSONObject(i);
                if (item == null) continue;
                if (item.optLong("time", Long.MAX_VALUE) == targetTime
                    && item.optString("text", "").equals(targetText)) {
                    continue;
                }
                next.put(item);
            }
            SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
            SharedPreferences.Editor editor = prefs.edit()
                .putString(KEY_PROBLEM_REPORT_HISTORY, next.toString());
            if (next.length() == 0) {
                editor.remove(KEY_CRASH_REPORT)
                    .remove(KEY_CRASH_REPORT_TIME)
                    .putBoolean(KEY_CRASH_REPORT_DISMISSED, true);
            } else {
                JSONObject latest = next.optJSONObject(0);
                if (latest != null) {
                    editor.putString(KEY_CRASH_REPORT, latest.optString("text", ""))
                        .putLong(KEY_CRASH_REPORT_TIME, latest.optLong("time", 0L))
                        .putBoolean(KEY_CRASH_REPORT_DISMISSED, true);
                }
            }
            editor.apply();
            toast("已删除日志：" + target.optString("name", ""));
            JSONArray refreshed = readProblemReportHistory();
            if (refreshed.length() > 0) showProblemReportHistoryDialog(refreshed);
        } catch (Throwable ignored) {
            toast("删除日志失败");
        }
    }

'''
if "private void showProblemReportHistoryDialog" not in text:
    if insert_marker not in text:
        raise SystemExit("history method insertion marker missing")
    text = text.replace(insert_marker, history_methods + insert_marker, 1)

path.write_text(text, encoding="utf-8")
