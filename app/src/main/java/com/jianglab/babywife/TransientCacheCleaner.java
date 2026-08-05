package com.jianglab.babywife;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/** Deletes user-visible friendly cache files that are not referenced by any playlist. */
final class TransientCacheCleaner {
    private static final String PREFS = "cache_storage";
    private static final String KEY_TREE_URI = "tree_uri";
    private static final String META_PREFIX = ".babywife_";
    private static final String META_SUFFIX = ".json";
    private static final int KEY_LENGTH = 64;

    private TransientCacheCleaner() {
    }

    static int clearDocumentTreeExcept(Context context, Set<String> keepKeys) {
        if (context == null) return 0;
        Uri tree = selectedTree(context);
        if (tree == null) return 0;

        Set<String> keep = new HashSet<>();
        if (keepKeys != null) {
            for (String key : keepKeys) {
                if (key != null) keep.add(key.toLowerCase(Locale.ROOT));
            }
        }

        try {
            List<DocumentEntry> entries = listAllDocuments(context, tree);
            Set<String> deleteNames = new HashSet<>();

            for (DocumentEntry entry : entries) {
                String key = metadataKey(entry.name);
                if (!validKey(key) || keep.contains(key)) continue;
                deleteNames.add(entry.name);
                JSONObject metadata = readJson(context, entry.uri);
                if (metadata == null) continue;
                String audioFile = metadata.optString("audioFile", "").trim();
                String lyricFile = metadata.optString("lyricFile", "").trim();
                if (!audioFile.isEmpty()) deleteNames.add(audioFile);
                if (!lyricFile.isEmpty()) deleteNames.add(lyricFile);
            }

            for (DocumentEntry entry : entries) {
                String key = legacyKey(entry.name);
                if (validKey(key) && !keep.contains(key)) deleteNames.add(entry.name);
            }

            int removed = 0;
            for (DocumentEntry entry : entries) {
                if (!deleteNames.contains(entry.name)) continue;
                try {
                    if (DocumentsContract.deleteDocument(
                        context.getContentResolver(), entry.uri)) {
                        removed++;
                    }
                } catch (Exception ignored) {
                }
            }
            return removed;
        } catch (Exception ignored) {
            return 0;
        }
    }

    private static Uri selectedTree(Context context) {
        String raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_TREE_URI, "");
        if (raw == null || raw.trim().isEmpty()) return null;
        try {
            return Uri.parse(raw);
        } catch (Exception ignored) {
            return null;
        }
    }

    private static List<DocumentEntry> listAllDocuments(Context context, Uri tree) throws Exception {
        List<DocumentEntry> entries = new ArrayList<>();
        String[] projection = {
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE
        };
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(
            tree, DocumentsContract.getTreeDocumentId(tree));
        Cursor cursor = context.getContentResolver().query(
            children, projection, null, null, null);
        if (cursor == null) throw new IllegalStateException("无法读取缓存文件夹");
        try (Cursor closeable = cursor) {
            int idColumn = closeable.getColumnIndex(
                DocumentsContract.Document.COLUMN_DOCUMENT_ID);
            int nameColumn = closeable.getColumnIndex(
                DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            int typeColumn = closeable.getColumnIndex(
                DocumentsContract.Document.COLUMN_MIME_TYPE);
            while (closeable.moveToNext()) {
                String id = idColumn < 0 ? "" : closeable.getString(idColumn);
                String name = nameColumn < 0 ? "" : closeable.getString(nameColumn);
                String type = typeColumn < 0 ? "" : closeable.getString(typeColumn);
                if (id == null || id.isEmpty()
                    || DocumentsContract.Document.MIME_TYPE_DIR.equals(type)) {
                    continue;
                }
                entries.add(new DocumentEntry(
                    name == null ? "" : name,
                    DocumentsContract.buildDocumentUriUsingTree(tree, id)));
            }
        }
        return entries;
    }

    private static JSONObject readJson(Context context, Uri uri) {
        try (InputStream raw = context.getContentResolver().openInputStream(uri);
             InputStream input = raw == null ? null : new BufferedInputStream(raw);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            if (input == null) return null;
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                if (count > 0) output.write(buffer, 0, count);
            }
            return new JSONObject(new String(output.toByteArray(), StandardCharsets.UTF_8));
        } catch (Exception ignored) {
            return null;
        }
    }

    private static String metadataKey(String name) {
        if (name == null || !name.startsWith(META_PREFIX)
            || !name.endsWith(META_SUFFIX)) {
            return "";
        }
        int start = META_PREFIX.length();
        int end = name.length() - META_SUFFIX.length();
        return end > start
            ? name.substring(start, end).toLowerCase(Locale.ROOT) : "";
    }

    private static String legacyKey(String name) {
        if (name == null || name.length() <= KEY_LENGTH
            || name.charAt(KEY_LENGTH) != '.') {
            return "";
        }
        String key = name.substring(0, KEY_LENGTH).toLowerCase(Locale.ROOT);
        return validKey(key) ? key : "";
    }

    private static boolean validKey(String key) {
        if (key == null || key.length() != KEY_LENGTH) return false;
        for (int index = 0; index < key.length(); index++) {
            char value = Character.toLowerCase(key.charAt(index));
            if (!((value >= '0' && value <= '9')
                || (value >= 'a' && value <= 'f'))) {
                return false;
            }
        }
        return true;
    }

    private static final class DocumentEntry {
        final String name;
        final Uri uri;

        DocumentEntry(String name, Uri uri) {
            this.name = name;
            this.uri = uri;
        }
    }
}
