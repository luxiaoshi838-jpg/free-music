package com.jianglab.babywife;

import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;

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
import java.util.Locale;
import java.util.Set;

/**
 * One-folder cache storage.
 *
 * By default files are stored in the app-private files/network_music directory and are removed
 * when the app is uninstalled. The user may select a persistent document-tree directory; audio
 * and lyric files then live together directly in that single directory.
 */
final class CacheStorage {
    private static final String PREFS = "cache_storage";
    private static final String KEY_TREE_URI = "tree_uri";
    private static final String INTERNAL_FOLDER = "network_music";

    private CacheStorage() {
    }

    static void useDocumentTree(Context context, Uri treeUri) throws Exception {
        if (context == null || treeUri == null) throw new IllegalArgumentException("缓存文件夹无效");
        int flags = Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION;
        context.getContentResolver().takePersistableUriPermission(treeUri, flags);
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_TREE_URI, treeUri.toString()).apply();
        // Confirm the directory is actually writable before accepting it.
        String probeName = ".babywife_cache_probe";
        Uri probe = createOrReplaceDocument(context, treeUri, probeName, "application/octet-stream");
        try (OutputStream output = context.getContentResolver().openOutputStream(probe, "w")) {
            if (output == null) throw new IllegalStateException("无法写入所选缓存文件夹");
            output.write(1);
        }
        DocumentsContract.deleteDocument(context.getContentResolver(), probe);
    }

    static void useInternalStorage(Context context) {
        if (context == null) return;
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().remove(KEY_TREE_URI).apply();
    }

    static boolean usesDocumentTree(Context context) {
        return selectedTree(context) != null;
    }

    static String description(Context context) {
        Uri tree = selectedTree(context);
        if (tree == null) return "歌单缓存位置：应用内部（卸载时清空）";
        String label = tree.getLastPathSegment();
        if (label == null || label.trim().isEmpty()) label = tree.toString();
        label = Uri.decode(label);
        return "歌单缓存位置：" + label;
    }

    static String findAudioUri(Context context, String key) {
        if (context == null || key == null || key.isEmpty()) return "";
        Uri selected = selectedTree(context);
        if (selected != null) {
            try {
                for (DocumentEntry entry : listDocuments(context, selected)) {
                    if (isAudioForKey(entry.name, key) && entry.size > 0) return entry.uri.toString();
                }
            } catch (Exception ignored) {
            }
        }
        File audio = findInternalAudio(internalRoot(context), key);
        return audio == null ? "" : Uri.fromFile(audio).toString();
    }

    static String readLyric(Context context, String key) {
        if (context == null || key == null || key.isEmpty()) return "";
        Uri selected = selectedTree(context);
        if (selected != null) {
            try {
                Uri lyric = findDocument(context, selected, key + ".lrc");
                if (lyric != null) return readText(context.getContentResolver().openInputStream(lyric));
            } catch (Exception ignored) {
            }
        }
        File file = new File(internalRoot(context), key + ".lrc");
        try {
            return readText(new FileInputStream(file));
        } catch (Exception ignored) {
            return "";
        }
    }

    static void writeLyric(Context context, String key, String text) throws Exception {
        if (context == null || key == null || key.isEmpty() || text == null || text.trim().isEmpty()) return;
        Uri selected = selectedTree(context);
        if (selected != null) {
            Uri outputUri = createOrReplaceDocument(context, selected, key + ".lrc", "text/plain");
            try (OutputStream output = context.getContentResolver().openOutputStream(outputUri, "w")) {
                if (output == null) throw new IllegalStateException("无法写入歌词缓存");
                output.write(text.getBytes(StandardCharsets.UTF_8));
            }
            return;
        }
        File root = internalRoot(context);
        if (!root.exists() && !root.mkdirs()) throw new IllegalStateException("无法创建缓存目录");
        File output = new File(root, key + ".lrc");
        File partial = new File(root, key + ".lrc.part");
        try (FileOutputStream stream = new FileOutputStream(partial)) {
            stream.write(text.getBytes(StandardCharsets.UTF_8));
        }
        replaceFile(partial, output);
    }

    static String storeAudio(Context context, String key, String extension, File source) throws Exception {
        if (context == null || key == null || key.isEmpty() || source == null || !source.isFile() || source.length() <= 0) {
            throw new IllegalArgumentException("歌曲缓存文件无效");
        }
        String safeExtension = extension == null ? "mp3" : extension.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
        if (safeExtension.isEmpty()) safeExtension = "mp3";
        String fileName = key + "." + safeExtension;
        Uri selected = selectedTree(context);
        if (selected != null) {
            removeAudioForKey(context, selected, key);
            Uri target = createOrReplaceDocument(context, selected, fileName, audioMime(safeExtension));
            try (InputStream input = new BufferedInputStream(new FileInputStream(source));
                 OutputStream output = new BufferedOutputStream(context.getContentResolver().openOutputStream(target, "w"))) {
                if (output == null) throw new IllegalStateException("无法写入歌曲缓存");
                copy(input, output);
            }
            return target.toString();
        }
        File root = internalRoot(context);
        if (!root.exists() && !root.mkdirs()) throw new IllegalStateException("无法创建缓存目录");
        removeInternalAudio(root, key);
        File target = new File(root, fileName);
        try (InputStream input = new BufferedInputStream(new FileInputStream(source));
             OutputStream output = new BufferedOutputStream(new FileOutputStream(target))) {
            copy(input, output);
        }
        return Uri.fromFile(target).toString();
    }

    static int clearExcept(Context context, Set<String> keepKeys) {
        if (context == null) return 0;
        int removed = clearInternalExcept(internalRoot(context), keepKeys);
        Uri selected = selectedTree(context);
        if (selected != null) {
            try {
                ContentResolver resolver = context.getContentResolver();
                for (DocumentEntry entry : listDocuments(context, selected)) {
                    String key = cacheKeyFromName(entry.name);
                    if (key.isEmpty() || (keepKeys != null && keepKeys.contains(key))) continue;
                    if (DocumentsContract.deleteDocument(resolver, entry.uri)) removed++;
                }
            } catch (Exception ignored) {
            }
        }
        return removed;
    }

    static boolean exists(Context context, String uriText) {
        if (context == null || uriText == null || uriText.trim().isEmpty()) return false;
        try {
            Uri uri = Uri.parse(uriText);
            if ("file".equalsIgnoreCase(uri.getScheme())) {
                File file = new File(uri.getPath());
                return file.isFile() && file.length() > 0;
            }
            if ("content".equalsIgnoreCase(uri.getScheme())) {
                try (android.content.res.AssetFileDescriptor descriptor =
                         context.getContentResolver().openAssetFileDescriptor(uri, "r")) {
                    return descriptor != null && descriptor.getLength() != 0;
                }
            }
        } catch (Exception ignored) {
        }
        return false;
    }

    private static Uri selectedTree(Context context) {
        if (context == null) return null;
        SharedPreferences preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String raw = preferences.getString(KEY_TREE_URI, "");
        if (raw == null || raw.trim().isEmpty()) return null;
        try {
            return Uri.parse(raw);
        } catch (Exception ignored) {
            return null;
        }
    }

    private static File internalRoot(Context context) {
        return new File(context.getFilesDir(), INTERNAL_FOLDER);
    }

    private static Uri treeDocumentUri(Uri treeUri) {
        return DocumentsContract.buildDocumentUriUsingTree(treeUri, DocumentsContract.getTreeDocumentId(treeUri));
    }

    private static Uri childrenUri(Uri treeUri) {
        return DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, DocumentsContract.getTreeDocumentId(treeUri));
    }

    private static List<DocumentEntry> listDocuments(Context context, Uri treeUri) {
        List<DocumentEntry> entries = new ArrayList<>();
        String[] projection = {
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_SIZE,
            DocumentsContract.Document.COLUMN_MIME_TYPE
        };
        try (Cursor cursor = context.getContentResolver().query(childrenUri(treeUri), projection, null, null, null)) {
            if (cursor == null) return entries;
            int idColumn = cursor.getColumnIndex(DocumentsContract.Document.COLUMN_DOCUMENT_ID);
            int nameColumn = cursor.getColumnIndex(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            int sizeColumn = cursor.getColumnIndex(DocumentsContract.Document.COLUMN_SIZE);
            int typeColumn = cursor.getColumnIndex(DocumentsContract.Document.COLUMN_MIME_TYPE);
            while (cursor.moveToNext()) {
                String id = idColumn < 0 ? "" : cursor.getString(idColumn);
                String name = nameColumn < 0 ? "" : cursor.getString(nameColumn);
                long size = sizeColumn < 0 || cursor.isNull(sizeColumn) ? -1 : cursor.getLong(sizeColumn);
                String type = typeColumn < 0 ? "" : cursor.getString(typeColumn);
                if (id == null || id.isEmpty() || DocumentsContract.Document.MIME_TYPE_DIR.equals(type)) continue;
                entries.add(new DocumentEntry(name == null ? "" : name,
                    DocumentsContract.buildDocumentUriUsingTree(treeUri, id), size));
            }
        } catch (Exception ignored) {
        }
        return entries;
    }

    private static Uri findDocument(Context context, Uri treeUri, String name) {
        for (DocumentEntry entry : listDocuments(context, treeUri)) {
            if (name.equals(entry.name)) return entry.uri;
        }
        return null;
    }

    private static Uri createOrReplaceDocument(Context context, Uri treeUri, String name, String mime) throws Exception {
        Uri existing = findDocument(context, treeUri, name);
        if (existing != null) DocumentsContract.deleteDocument(context.getContentResolver(), existing);
        Uri created = DocumentsContract.createDocument(context.getContentResolver(), treeDocumentUri(treeUri), mime, name);
        if (created == null) throw new IllegalStateException("无法在所选文件夹创建缓存文件");
        return created;
    }

    private static void removeAudioForKey(Context context, Uri treeUri, String key) {
        for (DocumentEntry entry : listDocuments(context, treeUri)) {
            if (!isAudioForKey(entry.name, key)) continue;
            try {
                DocumentsContract.deleteDocument(context.getContentResolver(), entry.uri);
            } catch (Exception ignored) {
            }
        }
    }

    private static boolean isAudioForKey(String name, String key) {
        return name != null && name.startsWith(key + ".") && !name.endsWith(".lrc") && !name.endsWith(".part");
    }

    private static File findInternalAudio(File root, String key) {
        File[] files = root.listFiles();
        if (files == null) return null;
        for (File file : files) {
            if (file.isFile() && isAudioForKey(file.getName(), key) && file.length() > 0) return file;
        }
        return null;
    }

    private static void removeInternalAudio(File root, String key) {
        File[] files = root.listFiles();
        if (files == null) return;
        for (File file : files) {
            if (file.isFile() && isAudioForKey(file.getName(), key)) file.delete();
        }
    }

    private static int clearInternalExcept(File root, Set<String> keepKeys) {
        File[] files = root.listFiles();
        if (files == null) return 0;
        int removed = 0;
        for (File file : files) {
            if (file == null || !file.isFile()) continue;
            String key = cacheKeyFromName(file.getName());
            if (!key.isEmpty() && keepKeys != null && keepKeys.contains(key)) continue;
            if (file.delete()) removed++;
        }
        return removed;
    }

    private static String cacheKeyFromName(String name) {
        if (name == null) return "";
        int dot = name.indexOf('.');
        return dot > 0 ? name.substring(0, dot) : "";
    }

    private static String readText(InputStream raw) {
        if (raw == null) return "";
        try (InputStream input = raw) {
            byte[] buffer = new byte[16 * 1024];
            java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream();
            int count;
            while ((count = input.read(buffer)) >= 0 && output.size() < 4 * 1024 * 1024) {
                if (count > 0) output.write(buffer, 0, count);
            }
            return new String(output.toByteArray(), StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            return "";
        }
    }

    private static void replaceFile(File source, File target) throws Exception {
        if (target.exists() && !target.delete()) throw new IllegalStateException("无法替换旧缓存");
        if (source.renameTo(target)) return;
        try (InputStream input = new FileInputStream(source); OutputStream output = new FileOutputStream(target)) {
            copy(input, output);
        }
        source.delete();
    }

    private static void copy(InputStream input, OutputStream output) throws Exception {
        byte[] buffer = new byte[64 * 1024];
        int count;
        while ((count = input.read(buffer)) >= 0) {
            if (count > 0) output.write(buffer, 0, count);
        }
    }

    private static String audioMime(String extension) {
        if ("flac".equals(extension)) return "audio/flac";
        if ("m4a".equals(extension) || "aac".equals(extension)) return "audio/mp4";
        if ("ogg".equals(extension) || "opus".equals(extension)) return "audio/ogg";
        if ("wav".equals(extension)) return "audio/wav";
        return "audio/mpeg";
    }

    private static final class DocumentEntry {
        final String name;
        final Uri uri;
        final long size;

        DocumentEntry(String name, Uri uri, long size) {
            this.name = name;
            this.uri = uri;
            this.size = size;
        }
    }
}
