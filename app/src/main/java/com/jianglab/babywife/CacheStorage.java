package com.jianglab.babywife;

import android.content.ContentResolver;
import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** Storage abstraction for internal files and user-selected Storage Access Framework trees. */
final class CacheStorage {
    static final String TRANSIENT_FOLDER = "缓存";

    private static final String PREFS = "cache_storage";
    private static final String KEY_ROOT_TREE_URI = "root_tree_uri";
    private static final String INTERNAL_ROOT = "playlist_cache";
    private static final String DIRECTORY_MIME = DocumentsContract.Document.MIME_TYPE_DIR;

    interface ProgressCallback {
        void onProgress(long written, long total);
    }

    static final class Entry {
        final Uri uri;
        final String name;
        final long size;

        Entry(Uri uri, String name, long size) {
            this.uri = uri;
            this.name = name == null ? "" : name;
            this.size = Math.max(0L, size);
        }
    }

    private static final class Bucket {
        final File directory;
        final Uri treeUri;
        final Uri documentUri;

        Bucket(File directory, Uri treeUri, Uri documentUri) {
            this.directory = directory;
            this.treeUri = treeUri;
            this.documentUri = documentUri;
        }

        boolean isSaf() {
            return treeUri != null && documentUri != null;
        }
    }

    private CacheStorage() {
    }

    static String rootTreeUri(Context context) {
        return preferences(context).getString(KEY_ROOT_TREE_URI, "");
    }

    static void setRootTreeUri(Context context, Uri treeUri) {
        if (context == null || treeUri == null) return;
        preferences(context).edit().putString(KEY_ROOT_TREE_URI, treeUri.toString()).apply();
    }

    static void resetToInternal(Context context) {
        if (context == null) return;
        preferences(context).edit().remove(KEY_ROOT_TREE_URI).apply();
    }

    static String locationLabel(Context context) {
        String raw = rootTreeUri(context);
        if (raw == null || raw.trim().isEmpty()) {
            return "应用默认位置";
        }
        try {
            Uri tree = Uri.parse(raw);
            Uri root = rootDocument(tree);
            String name = displayName(context, root);
            return name.isEmpty() ? "已选择文件夹" : name;
        } catch (Exception ignored) {
            return "已选择文件夹";
        }
    }

    static void ensureLayout(Context context, List<String> playlistNames) throws Exception {
        bucket(context, TRANSIENT_FOLDER, true);
        if (playlistNames == null) return;
        for (String name : playlistNames) {
            bucket(context, sanitizeFolderName(name), true);
        }
    }

    static boolean renameFolder(Context context, String oldName, String newName) {
        String oldSafe = sanitizeFolderName(oldName);
        String newSafe = sanitizeFolderName(newName);
        if (oldSafe.equals(newSafe)) return true;
        try {
            String raw = rootTreeUri(context);
            if (raw == null || raw.trim().isEmpty()) {
                File root = internalRoot(context);
                File oldDir = new File(root, oldSafe);
                File newDir = new File(root, newSafe);
                if (!oldDir.exists()) return newDir.exists() || newDir.mkdirs();
                if (newDir.exists()) return false;
                return oldDir.renameTo(newDir);
            }
            Uri tree = Uri.parse(raw);
            Uri root = rootDocument(tree);
            Entry oldEntry = findChild(context, tree, root, oldSafe, true);
            if (oldEntry == null) {
                return findOrCreateDirectory(context, tree, root, newSafe) != null;
            }
            Entry conflict = findChild(context, tree, root, newSafe, true);
            if (conflict != null) return false;
            Uri renamed = DocumentsContract.renameDocument(
                context.getContentResolver(), oldEntry.uri, newSafe);
            return renamed != null;
        } catch (Exception ignored) {
            return false;
        }
    }

    static Entry findAudio(Context context, String folderName, String key) {
        try {
            Bucket bucket = bucket(context, folderName, false);
            if (bucket == null) return null;
            String prefix = key + ".";
            for (Entry entry : list(context, bucket)) {
                String name = entry.name;
                if (!name.startsWith(prefix) || name.endsWith(".part") || name.endsWith(".lrc")) continue;
                if (entry.size > 0) return entry;
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    static String readText(Context context, String folderName, String fileName) {
        try {
            Bucket bucket = bucket(context, folderName, false);
            if (bucket == null) return "";
            Entry entry = find(context, bucket, fileName);
            if (entry == null) return "";
            try (InputStream input = context.getContentResolver().openInputStream(entry.uri)) {
                if (input == null) return "";
                byte[] data = readLimited(input, 4L * 1024L * 1024L);
                return new String(data, StandardCharsets.UTF_8);
            }
        } catch (Exception ignored) {
            return "";
        }
    }

    static Uri writeText(Context context, String folderName, String fileName, String text) throws Exception {
        byte[] data = (text == null ? "" : text).getBytes(StandardCharsets.UTF_8);
        try (InputStream input = new java.io.ByteArrayInputStream(data)) {
            return write(context, folderName, fileName, "text/plain", input, data.length, data.length + 1L, null);
        }
    }

    static Uri writeAudio(Context context, String folderName, String key, String extension,
                          InputStream source, long total, long maxBytes,
                          ProgressCallback callback) throws Exception {
        String safeExtension = extension == null || extension.trim().isEmpty() ? "mp3" : extension.trim();
        return write(context, folderName, key + "." + safeExtension,
            mimeForExtension(safeExtension), source, total, maxBytes, callback);
    }

    static String promoteFromTransient(Context context, String key, String playlistName) {
        String targetFolder = sanitizeFolderName(playlistName);
        try {
            Bucket source = bucket(context, TRANSIENT_FOLDER, false);
            if (source == null) return "";
            Bucket target = bucket(context, targetFolder, true);
            Entry promotedAudio = null;
            for (Entry entry : list(context, source)) {
                if (!entry.name.startsWith(key + ".") || entry.name.endsWith(".part")) continue;
                Entry copied = copyEntry(context, entry, target);
                if (copied != null) {
                    if (!entry.name.endsWith(".lrc")) promotedAudio = copied;
                    delete(context, entry.uri);
                }
            }
            return promotedAudio == null ? "" : promotedAudio.uri.toString();
        } catch (Exception ignored) {
            return "";
        }
    }

    static int clearFolder(Context context, String folderName) {
        int removed = 0;
        try {
            Bucket bucket = bucket(context, folderName, false);
            if (bucket == null) return 0;
            for (Entry entry : list(context, bucket)) {
                if (delete(context, entry.uri)) removed++;
            }
        } catch (Exception ignored) {
        }
        return removed;
    }

    static boolean uriExists(Context context, String rawUri) {
        if (context == null || rawUri == null || rawUri.trim().isEmpty()) return false;
        try {
            Uri uri = Uri.parse(rawUri);
            if ("file".equalsIgnoreCase(uri.getScheme())) {
                File file = new File(uri.getPath());
                return file.exists() && file.length() > 0;
            }
            try (android.content.res.AssetFileDescriptor descriptor =
                     context.getContentResolver().openAssetFileDescriptor(uri, "r")) {
                return descriptor != null && descriptor.getLength() != 0;
            }
        } catch (Exception ignored) {
            return false;
        }
    }

    private static Uri write(Context context, String folderName, String fileName, String mime,
                             InputStream source, long total, long maxBytes,
                             ProgressCallback callback) throws Exception {
        Bucket bucket = bucket(context, folderName, true);
        if (bucket == null) throw new IllegalStateException("无法创建缓存文件夹");
        String tempName = fileName + ".part";
        deleteNamed(context, bucket, tempName);
        Entry temp = createFile(context, bucket, tempName, mime);
        if (temp == null) throw new IllegalStateException("无法创建缓存文件");
        long written = 0;
        boolean success = false;
        try (InputStream input = new BufferedInputStream(source);
             OutputStream output = new BufferedOutputStream(
                 context.getContentResolver().openOutputStream(temp.uri, "wt"))) {
            if (output == null) throw new IllegalStateException("无法写入缓存文件");
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                if (count == 0) continue;
                written += count;
                if (written > maxBytes) throw new IllegalStateException("歌曲文件超过缓存上限");
                output.write(buffer, 0, count);
                if (callback != null) callback.onProgress(written, total);
            }
            output.flush();
            if (written <= 0 && total != 0) throw new IllegalStateException("没有写入缓存内容");
            success = true;
        } finally {
            if (!success) delete(context, temp.uri);
        }
        deleteNamed(context, bucket, fileName);
        Uri finalUri = rename(context, temp.uri, fileName);
        if (finalUri != null) return finalUri;
        Entry finalEntry = createFile(context, bucket, fileName, mime);
        if (finalEntry == null) throw new IllegalStateException("无法完成缓存文件");
        try (InputStream input = context.getContentResolver().openInputStream(temp.uri);
             OutputStream output = context.getContentResolver().openOutputStream(finalEntry.uri, "wt")) {
            copy(input, output);
        }
        delete(context, temp.uri);
        return finalEntry.uri;
    }

    private static Entry copyEntry(Context context, Entry source, Bucket target) throws Exception {
        deleteNamed(context, target, source.name);
        Entry output = createFile(context, target, source.name, mimeForName(source.name));
        if (output == null) return null;
        try (InputStream input = context.getContentResolver().openInputStream(source.uri);
             OutputStream stream = context.getContentResolver().openOutputStream(output.uri, "wt")) {
            copy(input, stream);
        }
        return new Entry(output.uri, output.name, source.size);
    }

    private static Bucket bucket(Context context, String rawFolder, boolean create) throws Exception {
        String folderName = sanitizeFolderName(rawFolder);
        String rawTree = rootTreeUri(context);
        if (rawTree == null || rawTree.trim().isEmpty()) {
            File directory = new File(internalRoot(context), folderName);
            if (create && !directory.exists() && !directory.mkdirs()) {
                throw new IllegalStateException("无法创建缓存目录：" + folderName);
            }
            return directory.exists() ? new Bucket(directory, null, null) : null;
        }
        Uri tree = Uri.parse(rawTree);
        Uri root = rootDocument(tree);
        Entry entry = findChild(context, tree, root, folderName, true);
        Uri folder = entry == null && create
            ? findOrCreateDirectory(context, tree, root, folderName)
            : entry == null ? null : entry.uri;
        return folder == null ? null : new Bucket(null, tree, folder);
    }

    private static File internalRoot(Context context) {
        File root = new File(context.getFilesDir(), INTERNAL_ROOT);
        if (!root.exists()) root.mkdirs();
        return root;
    }

    private static List<Entry> list(Context context, Bucket bucket) throws Exception {
        List<Entry> out = new ArrayList<>();
        if (!bucket.isSaf()) {
            File[] files = bucket.directory.listFiles();
            if (files != null) {
                for (File file : files) {
                    out.add(new Entry(Uri.fromFile(file), file.getName(), file.length()));
                }
            }
            return out;
        }
        ContentResolver resolver = context.getContentResolver();
        String parentId = DocumentsContract.getDocumentId(bucket.documentUri);
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(bucket.treeUri, parentId);
        String[] projection = {
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_SIZE
        };
        try (Cursor cursor = resolver.query(children, projection, null, null, null)) {
            if (cursor == null) return out;
            while (cursor.moveToNext()) {
                String id = cursor.getString(0);
                String name = cursor.getString(1);
                long size = cursor.isNull(2) ? 0L : cursor.getLong(2);
                Uri uri = DocumentsContract.buildDocumentUriUsingTree(bucket.treeUri, id);
                out.add(new Entry(uri, name, size));
            }
        }
        return out;
    }

    private static Entry find(Context context, Bucket bucket, String fileName) throws Exception {
        if (!bucket.isSaf()) {
            File file = new File(bucket.directory, fileName);
            return file.exists() ? new Entry(Uri.fromFile(file), file.getName(), file.length()) : null;
        }
        return findChild(context, bucket.treeUri, bucket.documentUri, fileName, false);
    }

    private static Entry createFile(Context context, Bucket bucket, String fileName, String mime) throws Exception {
        if (!bucket.isSaf()) {
            File file = new File(bucket.directory, fileName);
            if (!file.exists() && !file.createNewFile()) return null;
            return new Entry(Uri.fromFile(file), file.getName(), file.length());
        }
        Uri uri = DocumentsContract.createDocument(
            context.getContentResolver(), bucket.documentUri, mime, fileName);
        return uri == null ? null : new Entry(uri, fileName, 0L);
    }

    private static void deleteNamed(Context context, Bucket bucket, String name) throws Exception {
        Entry existing = find(context, bucket, name);
        if (existing != null) delete(context, existing.uri);
    }

    private static boolean delete(Context context, Uri uri) {
        if (uri == null) return false;
        try {
            if ("file".equalsIgnoreCase(uri.getScheme())) {
                return new File(uri.getPath()).delete();
            }
            return DocumentsContract.deleteDocument(context.getContentResolver(), uri);
        } catch (Exception ignored) {
            return false;
        }
    }

    private static Uri rename(Context context, Uri uri, String name) {
        try {
            if ("file".equalsIgnoreCase(uri.getScheme())) {
                File source = new File(uri.getPath());
                File target = new File(source.getParentFile(), name);
                return source.renameTo(target) ? Uri.fromFile(target) : null;
            }
            return DocumentsContract.renameDocument(context.getContentResolver(), uri, name);
        } catch (Exception ignored) {
            return null;
        }
    }

    private static Entry findChild(Context context, Uri tree, Uri parent, String wanted, boolean directory) throws Exception {
        ContentResolver resolver = context.getContentResolver();
        String parentId = DocumentsContract.getDocumentId(parent);
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId);
        String[] projection = {
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE,
            DocumentsContract.Document.COLUMN_SIZE
        };
        try (Cursor cursor = resolver.query(children, projection, null, null, null)) {
            if (cursor == null) return null;
            while (cursor.moveToNext()) {
                String id = cursor.getString(0);
                String name = cursor.getString(1);
                String mime = cursor.getString(2);
                long size = cursor.isNull(3) ? 0L : cursor.getLong(3);
                if (!wanted.equals(name)) continue;
                boolean isDirectory = DIRECTORY_MIME.equals(mime);
                if (directory != isDirectory) continue;
                Uri uri = DocumentsContract.buildDocumentUriUsingTree(tree, id);
                return new Entry(uri, name, size);
            }
        }
        return null;
    }

    private static Uri findOrCreateDirectory(Context context, Uri tree, Uri parent, String name) throws Exception {
        Entry existing = findChild(context, tree, parent, name, true);
        if (existing != null) return existing.uri;
        return DocumentsContract.createDocument(
            context.getContentResolver(), parent, DIRECTORY_MIME, name);
    }

    private static Uri rootDocument(Uri treeUri) {
        return DocumentsContract.buildDocumentUriUsingTree(
            treeUri, DocumentsContract.getTreeDocumentId(treeUri));
    }

    private static String displayName(Context context, Uri uri) {
        try (Cursor cursor = context.getContentResolver().query(
            uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                String name = cursor.getString(0);
                return name == null ? "" : name.trim();
            }
        } catch (Exception ignored) {
        }
        return "";
    }

    private static byte[] readLimited(InputStream input, long limit) throws Exception {
        java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
        byte[] buffer = new byte[16 * 1024];
        long total = 0;
        int count;
        while ((count = input.read(buffer)) >= 0) {
            if (count == 0) continue;
            total += count;
            if (total > limit) throw new IllegalStateException("文本缓存超过上限");
            output.write(buffer, 0, count);
        }
        return output.toByteArray();
    }

    private static void copy(InputStream input, OutputStream output) throws Exception {
        if (input == null || output == null) throw new IllegalStateException("无法复制缓存文件");
        byte[] buffer = new byte[64 * 1024];
        int count;
        while ((count = input.read(buffer)) >= 0) {
            if (count > 0) output.write(buffer, 0, count);
        }
        output.flush();
    }

    static String sanitizeFolderName(String value) {
        String safe = value == null ? "" : value.trim();
        safe = safe.replaceAll("[\\\\/:*?\"<>|]", "_").replaceAll("[\\r\\n\\t]", " ").trim();
        if (safe.isEmpty()) safe = "未命名歌单";
        return safe.length() > 80 ? safe.substring(0, 80) : safe;
    }

    private static String mimeForName(String name) {
        int dot = name == null ? -1 : name.lastIndexOf('.');
        return mimeForExtension(dot < 0 ? "" : name.substring(dot + 1));
    }

    private static String mimeForExtension(String extension) {
        String ext = extension == null ? "" : extension.toLowerCase();
        if ("lrc".equals(ext) || "txt".equals(ext)) return "text/plain";
        if ("flac".equals(ext)) return "audio/flac";
        if ("ogg".equals(ext) || "opus".equals(ext)) return "audio/ogg";
        if ("wav".equals(ext)) return "audio/wav";
        if ("m4a".equals(ext) || "aac".equals(ext)) return "audio/mp4";
        return "audio/mpeg";
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
