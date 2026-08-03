from pathlib import Path

root = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'Cannot find {label} in {path}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


def append_once(path: Path, marker: str, text: str) -> None:
    current = path.read_text(encoding='utf-8')
    if marker in current:
        return
    path.write_text(current.rstrip() + '\n\n' + text.rstrip() + '\n', encoding='utf-8')

main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
cache_path = root / 'app/src/main/java/com/jianglab/babywife/CacheStorage.java'
manifest_path = root / 'app/src/main/AndroidManifest.xml'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'
project_log_path = root / 'PROJECT_LOG.md'
changelog_path = root / 'docs/CHANGELOG.md'

# Version.
replace_once(
    gradle_path,
    'versionCode 2026080132\n        versionName "2026.08.03.search-keyboard-button-feedback"',
    'versionCode 2026080133\n        versionName "2026.08.03.full-cache-folder-migration"',
    'v133 version',
)

# Manifest: explicit all-files access for external-folder-to-external-folder migration.
replace_once(
    manifest_path,
    '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />\n',
    '    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK" />\n'
    '    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />\n',
    'all files access permission',
)

# MainActivity imports and state.
replace_once(main_path, 'import android.app.Activity;\n', 'import android.Manifest;\nimport android.app.Activity;\n', 'Manifest import')
replace_once(main_path, 'import android.os.Build;\n', 'import android.os.Build;\nimport android.os.Environment;\n', 'Environment import')
replace_once(main_path, 'import android.provider.OpenableColumns;\n', 'import android.provider.OpenableColumns;\nimport android.provider.Settings;\n', 'Settings import')
replace_once(
    main_path,
    '    private int pendingExportPlaylistIndex = -1;\n',
    '    private int pendingExportPlaylistIndex = -1;\n'
    '    private boolean pendingCacheFolderSelection = false;\n'
    '    private boolean fileManagementSettingsOpened = false;\n',
    'cache permission state',
)

replace_once(
    main_path,
    '        renderCurrentPlaylist();\n        scheduleStartupWork();\n    }\n\n    private void scheduleStartupWork() {',
    '        renderCurrentPlaylist();\n        scheduleStartupWork();\n    }\n\n'
    '    @Override\n'
    '    protected void onResume() {\n'
    '        super.onResume();\n'
    '        if (!pendingCacheFolderSelection || !fileManagementSettingsOpened) return;\n'
    '        fileManagementSettingsOpened = false;\n'
    '        if (hasFileManagementPermission()) {\n'
    '            pendingCacheFolderSelection = false;\n'
    '            chooseCacheFolder();\n'
    '        } else {\n'
    '            pendingCacheFolderSelection = false;\n'
    '            toast("未授予文件管理权限，未更换缓存文件夹");\n'
    '        }\n'
    '    }\n\n'
    '    private void scheduleStartupWork() {',
    'onResume permission continuation',
)

replace_once(
    main_path,
    '            .setMessage(CacheStorage.details(this)\n'
    '                + "\\n\\n更换位置时会先复制全部受管理文件，全部成功后才切换并删除旧位置文件。")\n'
    '            .setPositiveButton("选择缓存文件夹", (dialog, which) -> chooseCacheFolder())',
    '            .setMessage(CacheStorage.details(this)\n'
    '                + "\\n\\n更换位置时会迁移旧缓存文件夹内的全部普通文件。每个文件复制并校验成功后才切换位置，最后删除旧文件。"\n'
    '                + "\\n需要授予文件管理权限，并在系统文件选择器中确认新的缓存文件夹。")\n'
    '            .setPositiveButton("选择缓存文件夹", (dialog, which) -> requestFileManagementThenChooseCacheFolder())',
    'cache location dialog',
)

old_choose = '''    private void chooseCacheFolder() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
            | Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
            | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        startActivityForResult(intent, REQUEST_CACHE_FOLDER);
    }
'''
new_choose = '''    private void requestFileManagementThenChooseCacheFolder() {
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
'''
replace_once(main_path, old_choose, new_choose, 'file management permission flow')

replace_once(
    main_path,
    '.setPositiveButton("选择保留文件夹", (dialog, which) -> chooseCacheFolder())',
    '.setPositiveButton("选择保留文件夹", (dialog, which) -> requestFileManagementThenChooseCacheFolder())',
    'uninstall cleanup external-folder action',
)

replace_once(
    main_path,
    '                    toast(result.changed\n'
    '                        ? "缓存位置已更换，已迁移 " + result.copied + " 个文件；卸载后会保留"\n'
    '                        : "当前已经是所选缓存文件夹");',
    '                    String cleanup = result.retainedInOldLocation > 0\n'
    '                        ? "；旧文件夹仍有 " + result.retainedInOldLocation + " 个文件未能删除，请检查文件管理权限"\n'
    '                        : "；旧文件夹中的原文件已删除";\n'
    '                    toast(result.changed\n'
    '                        ? "缓存位置已更换，已迁移并校验 " + result.copied + " 个文件" + cleanup + "；卸载后会保留"\n'
    '                        : "当前已经是所选缓存文件夹");',
    'external migration result text',
)
replace_once(
    main_path,
    '                    toast(result.changed\n'
    '                        ? "已迁回应用内部，共迁移 " + result.copied + " 个文件；卸载时会清理"\n'
    '                        : "当前已经使用卸载时清理的位置");',
    '                    String cleanup = result.retainedInOldLocation > 0\n'
    '                        ? "；外部旧文件夹仍有 " + result.retainedInOldLocation + " 个文件未能删除"\n'
    '                        : "；外部旧文件已删除";\n'
    '                    toast(result.changed\n'
    '                        ? "已迁回应用内部，共迁移并校验 " + result.copied + " 个文件" + cleanup + "；卸载时会清理"\n'
    '                        : "当前已经使用卸载时清理的位置");',
    'internal migration result text',
)

# CacheStorage: permission requirement, full-folder file enumeration, hash verification, retained-file reporting.
replace_once(cache_path, 'import android.net.Uri;\n', 'import android.net.Uri;\nimport android.os.Build;\nimport android.os.Environment;\n', 'cache Environment imports')
replace_once(cache_path, 'import java.nio.charset.StandardCharsets;\n', 'import java.nio.charset.StandardCharsets;\nimport java.security.MessageDigest;\n', 'MessageDigest import')

replace_once(
    cache_path,
    '        final int removedFromOldLocation;\n        final boolean changed;\n\n'
    '        MigrationResult(int copied, int removedFromOldLocation, boolean changed) {\n'
    '            this.copied = copied;\n'
    '            this.removedFromOldLocation = removedFromOldLocation;\n'
    '            this.changed = changed;\n'
    '        }',
    '        final int removedFromOldLocation;\n'
    '        final int retainedInOldLocation;\n'
    '        final boolean changed;\n\n'
    '        MigrationResult(int copied, int removedFromOldLocation, boolean changed) {\n'
    '            this.copied = copied;\n'
    '            this.removedFromOldLocation = removedFromOldLocation;\n'
    '            this.retainedInOldLocation = Math.max(0, copied - removedFromOldLocation);\n'
    '            this.changed = changed;\n'
    '        }',
    'migration result retained count',
)

replace_once(
    cache_path,
    '    static MigrationResult useDocumentTree(Context context, Uri treeUri) throws Exception {\n'
    '        if (context == null || treeUri == null) throw new IllegalArgumentException("缓存文件夹无效");',
    '    static MigrationResult useDocumentTree(Context context, Uri treeUri) throws Exception {\n'
    '        if (context == null || treeUri == null) throw new IllegalArgumentException("缓存文件夹无效");\n'
    '        requireFileManagementPermission();',
    'external migration permission guard',
)
replace_once(
    cache_path,
    '    static MigrationResult useInternalStorage(Context context) throws Exception {\n'
    '        if (context == null) return new MigrationResult(0, 0, false);',
    '    static MigrationResult useInternalStorage(Context context) throws Exception {\n'
    '        if (context == null) return new MigrationResult(0, 0, false);\n'
    '        requireFileManagementPermission();',
    'internal migration permission guard',
)
replace_once(cache_path, 'List<DocumentEntry> source = listDocumentsStrict(context, oldTree, true);', 'List<DocumentEntry> source = listDocumentsStrict(context, oldTree, false);', 'all old external files in useDocumentTree')
replace_once(cache_path, 'List<File> source = listManagedInternalFiles(context);', 'List<File> source = listAllInternalFiles(context);', 'all old internal files')
replace_once(cache_path, 'List<DocumentEntry> source = listDocumentsStrict(context, oldTree, true);', 'List<DocumentEntry> source = listDocumentsStrict(context, oldTree, false);', 'all old external files in useInternalStorage')

# Release old SAF permission only when the old location was fully emptied.
replace_once(
    cache_path,
    '            removed = deleteDocuments(context, source);\n        } else {',
    '            removed = deleteDocuments(context, source);\n'
    '            if (removed == source.size()) releaseTreePermission(context, oldTree);\n'
    '        } else {',
    'release old tree permission after external migration',
)
replace_once(
    cache_path,
    '        int removed = deleteDocuments(context, source);\n        return new MigrationResult(copied, removed, true);',
    '        int removed = deleteDocuments(context, source);\n'
    '        if (removed == source.size()) releaseTreePermission(context, oldTree);\n'
    '        return new MigrationResult(copied, removed, true);',
    'release old tree permission after internal migration',
)

old_copy_files = '''    private static int copyFilesToTree(Context context, List<File> source, Uri targetTree) throws Exception {
        int copied = 0;
        for (File file : source) {
            Uri target = createOrReplaceDocument(context, targetTree, file.getName(), mimeForName(file.getName()));
            try (InputStream input = new BufferedInputStream(new FileInputStream(file));
                 OutputStream raw = context.getContentResolver().openOutputStream(target, "w");
                 OutputStream output = raw == null ? null : new BufferedOutputStream(raw)) {
                if (output == null) throw new IllegalStateException("无法写入新缓存文件夹：" + file.getName());
                copy(input, output);
            }
            copied++;
        }
        return copied;
    }
'''
new_copy_files = '''    private static int copyFilesToTree(Context context, List<File> source, Uri targetTree) throws Exception {
        int copied = 0;
        for (File file : source) {
            Uri target = createOrReplaceDocument(context, targetTree, file.getName(), mimeForName(file.getName()));
            String sourceDigest;
            try (InputStream input = new BufferedInputStream(new FileInputStream(file));
                 OutputStream raw = context.getContentResolver().openOutputStream(target, "w");
                 OutputStream output = raw == null ? null : new BufferedOutputStream(raw)) {
                if (output == null) throw new IllegalStateException("无法写入新缓存文件夹：" + file.getName());
                sourceDigest = copyAndDigest(input, output);
            }
            verifyDocumentDigest(context, target, sourceDigest, file.getName());
            copied++;
        }
        return copied;
    }
'''
replace_once(cache_path, old_copy_files, new_copy_files, 'verified internal-to-tree copy')

old_copy_docs = '''    private static int copyDocumentsToTree(Context context, List<DocumentEntry> source, Uri targetTree) throws Exception {
        int copied = 0;
        for (DocumentEntry entry : source) {
            Uri target = createOrReplaceDocument(context, targetTree, entry.name, mimeForName(entry.name));
            try (InputStream rawInput = context.getContentResolver().openInputStream(entry.uri);
                 InputStream input = rawInput == null ? null : new BufferedInputStream(rawInput);
                 OutputStream rawOutput = context.getContentResolver().openOutputStream(target, "w");
                 OutputStream output = rawOutput == null ? null : new BufferedOutputStream(rawOutput)) {
                if (input == null || output == null) throw new IllegalStateException("无法迁移缓存文件：" + entry.name);
                copy(input, output);
            }
            copied++;
        }
        return copied;
    }
'''
new_copy_docs = '''    private static int copyDocumentsToTree(Context context, List<DocumentEntry> source, Uri targetTree) throws Exception {
        int copied = 0;
        for (DocumentEntry entry : source) {
            Uri target = createOrReplaceDocument(context, targetTree, entry.name, mimeForName(entry.name));
            String sourceDigest;
            try (InputStream rawInput = context.getContentResolver().openInputStream(entry.uri);
                 InputStream input = rawInput == null ? null : new BufferedInputStream(rawInput);
                 OutputStream rawOutput = context.getContentResolver().openOutputStream(target, "w");
                 OutputStream output = rawOutput == null ? null : new BufferedOutputStream(rawOutput)) {
                if (input == null || output == null) throw new IllegalStateException("无法迁移缓存文件：" + entry.name);
                sourceDigest = copyAndDigest(input, output);
            }
            verifyDocumentDigest(context, target, sourceDigest, entry.name);
            copied++;
        }
        return copied;
    }
'''
replace_once(cache_path, old_copy_docs, new_copy_docs, 'verified tree-to-tree copy')

old_copy_internal = '''    private static int copyDocumentsToInternal(Context context, List<DocumentEntry> source, File root) throws Exception {
        int copied = 0;
        for (DocumentEntry entry : source) {
            File partial = new File(root, entry.name + ".move_part");
            File target = new File(root, entry.name);
            try (InputStream rawInput = context.getContentResolver().openInputStream(entry.uri);
                 InputStream input = rawInput == null ? null : new BufferedInputStream(rawInput);
                 OutputStream output = new BufferedOutputStream(new FileOutputStream(partial))) {
                if (input == null) throw new IllegalStateException("无法读取旧缓存文件：" + entry.name);
                copy(input, output);
            }
            replaceFile(partial, target);
            copied++;
        }
        return copied;
    }
'''
new_copy_internal = '''    private static int copyDocumentsToInternal(Context context, List<DocumentEntry> source, File root) throws Exception {
        int copied = 0;
        for (DocumentEntry entry : source) {
            File partial = new File(root, entry.name + ".move_part");
            File target = new File(root, entry.name);
            String sourceDigest;
            try (InputStream rawInput = context.getContentResolver().openInputStream(entry.uri);
                 InputStream input = rawInput == null ? null : new BufferedInputStream(rawInput);
                 OutputStream output = new BufferedOutputStream(new FileOutputStream(partial))) {
                if (input == null) throw new IllegalStateException("无法读取旧缓存文件：" + entry.name);
                sourceDigest = copyAndDigest(input, output);
            }
            String targetDigest = digest(new FileInputStream(partial));
            if (!sourceDigest.equals(targetDigest)) {
                partial.delete();
                throw new IllegalStateException("迁移后校验失败：" + entry.name);
            }
            replaceFile(partial, target);
            copied++;
        }
        return copied;
    }
'''
replace_once(cache_path, old_copy_internal, new_copy_internal, 'verified tree-to-internal copy')

replace_once(
    cache_path,
    '    private static List<File> listManagedInternalFiles(Context context) {\n'
    '        List<File> files = new ArrayList<>();\n'
    '        File[] entries = internalRoot(context).listFiles();\n'
    '        if (entries == null) return files;\n'
    '        for (File file : entries) {\n'
    '            if (file != null && file.isFile() && isManagedCacheName(file.getName())) files.add(file);\n'
    '        }\n'
    '        return files;\n'
    '    }',
    '    private static List<File> listAllInternalFiles(Context context) {\n'
    '        List<File> files = new ArrayList<>();\n'
    '        File[] entries = internalRoot(context).listFiles();\n'
    '        if (entries == null) return files;\n'
    '        for (File file : entries) {\n'
    '            if (file == null || !file.isFile()) continue;\n'
    '            String name = file.getName();\n'
    '            if (name.endsWith(".part") || name.endsWith(".move_part")) continue;\n'
    '            files.add(file);\n'
    '        }\n'
    '        return files;\n'
    '    }',
    'all internal cache files enumerator',
)

# Helpers inserted before saveSelectedTree.
replace_once(
    cache_path,
    '    private static void saveSelectedTree(Context context, Uri treeUri) {',
    '    private static void requireFileManagementPermission() {\n'
    '        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R\n'
    '            && !Environment.isExternalStorageManager()) {\n'
    '            throw new SecurityException("请先授予文件管理权限");\n'
    '        }\n'
    '    }\n\n'
    '    private static void releaseTreePermission(Context context, Uri treeUri) {\n'
    '        if (context == null || treeUri == null) return;\n'
    '        try {\n'
    '            context.getContentResolver().releasePersistableUriPermission(treeUri,\n'
    '                Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);\n'
    '        } catch (Exception ignored) {\n'
    '        }\n'
    '    }\n\n'
    '    private static void verifyDocumentDigest(Context context, Uri target,\n'
    '                                             String expected, String name) throws Exception {\n'
    '        String actual = digest(context.getContentResolver().openInputStream(target));\n'
    '        if (expected.equals(actual)) return;\n'
    '        try {\n'
    '            DocumentsContract.deleteDocument(context.getContentResolver(), target);\n'
    '        } catch (Exception ignored) {\n'
    '        }\n'
    '        throw new IllegalStateException("迁移后校验失败：" + name);\n'
    '    }\n\n'
    '    private static String copyAndDigest(InputStream input, OutputStream output) throws Exception {\n'
    '        MessageDigest digest = MessageDigest.getInstance("SHA-256");\n'
    '        byte[] buffer = new byte[64 * 1024];\n'
    '        int count;\n'
    '        while ((count = input.read(buffer)) >= 0) {\n'
    '            if (count <= 0) continue;\n'
    '            output.write(buffer, 0, count);\n'
    '            digest.update(buffer, 0, count);\n'
    '        }\n'
    '        output.flush();\n'
    '        return hex(digest.digest());\n'
    '    }\n\n'
    '    private static String digest(InputStream raw) throws Exception {\n'
    '        if (raw == null) throw new IllegalStateException("无法读取迁移后的文件");\n'
    '        try (InputStream input = new BufferedInputStream(raw)) {\n'
    '            MessageDigest digest = MessageDigest.getInstance("SHA-256");\n'
    '            byte[] buffer = new byte[64 * 1024];\n'
    '            int count;\n'
    '            while ((count = input.read(buffer)) >= 0) {\n'
    '                if (count > 0) digest.update(buffer, 0, count);\n'
    '            }\n'
    '            return hex(digest.digest());\n'
    '        }\n'
    '    }\n\n'
    '    private static String hex(byte[] bytes) {\n'
    '        StringBuilder text = new StringBuilder(bytes.length * 2);\n'
    '        for (byte value : bytes) text.append(String.format(Locale.ROOT, "%02x", value & 0xff));\n'
    '        return text.toString();\n'
    '    }\n\n'
    '    private static void saveSelectedTree(Context context, Uri treeUri) {',
    'migration verification helpers',
)

# Check script.
replace_once(
    check_path,
    "gradle = (root / 'app/build.gradle').read_text(encoding='utf-8')\n",
    "gradle = (root / 'app/build.gradle').read_text(encoding='utf-8')\nmanifest = (root / 'app/src/main/AndroidManifest.xml').read_text(encoding='utf-8')\n",
    'manifest verification input',
)
replace_once(
    check_path,
    "    'version bumped': 'versionCode 2026080132' in gradle,",
    "    'full cache folder migration and file management permission': (\n"
    "        'android.permission.MANAGE_EXTERNAL_STORAGE' in manifest\n"
    "        and 'Environment.isExternalStorageManager()' in main\n"
    "        and 'Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION' in main\n"
    "        and 'requestFileManagementThenChooseCacheFolder()' in main\n"
    "        and 'listDocumentsStrict(context, oldTree, false)' in cache\n"
    "        and 'listAllInternalFiles(context)' in cache\n"
    "        and 'copyAndDigest' in cache\n"
    "        and 'verifyDocumentDigest' in cache\n"
    "        and 'retainedInOldLocation' in cache\n"
    "        and 'listDocumentsStrict(context, oldTree, true)' not in cache\n"
    "    ),\n"
    "    'version bumped': 'versionCode 2026080133' in gradle,",
    'v133 feature checks',
)

append_once(
    project_log_path,
    'Full cache folder migration with all-files permission',
    '''## 2026-08-03 - Full cache folder migration with all-files permission

- Fixed cache-folder changes skipping friendly files named `歌曲名 - 歌手.扩展名`.
- External-to-external and external-to-internal moves now enumerate every regular file in the old cache folder.
- Each copied file is SHA-256 verified before the selected cache location changes or old files are removed.
- Android 11+ now requests the system all-files management permission before opening the destination folder picker.
- Migration reports any old files that could not be deleted instead of silently claiming a complete move.''',
)
append_once(
    changelog_path,
    'full-cache-folder-migration',
    '''## 2026.08.03.full-cache-folder-migration

- Changing the cache folder now moves all regular files from the previous cache folder, including friendly audio and lyric filenames.
- Added Android all-files management permission flow for reliable old-folder cleanup.
- Added SHA-256 copy verification and explicit reporting for old files that remain after migration.''',
)

print('v133 full cache folder migration patch applied')
