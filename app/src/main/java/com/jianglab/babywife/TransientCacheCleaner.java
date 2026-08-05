package com.jianglab.babywife;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/** Deletes cache files that are not referenced by any saved playlist. */
final class TransientCacheCleaner {
    private static final String CACHE_PREFS = "cache_storage";
    private static final String KEY_TREE_URI = "tree_uri";
    private static final String STATE_PREFS = "babywife_state";
    private static final String KEY_PLAYLISTS = "playlists_v2";
    private static final String META_PREFIX = ".babywife_";
    private static final String META_SUFFIX = ".json";
    private static final int KEY_LENGTH = 64;

    private TransientCacheCleaner() {
    }

    static int clearDocumentTreeExcept(Context context, Set<String> keepKeys) {
        if (context == null) return 0;
        Uri tree = selectedTree(context);
        if (tree == null) return 0;

        Set<String> keep = normalizedKeys(keepKeys);
        Set<String> playlistUris = savedPlaylistUris(context);
        Set<String> keepNames = savedPlaylistFileNames(context, playlistUris);

        try {
            List<DocumentEntry> entries = listAllDocuments(context, tree);
            Set<String> deleteNames = new HashSet<>();

            for (DocumentEntry entry : entries) {
                String key = metadataKey(entry.name);
                if (!validKey(key)) continue;
                JSONObject metadata = readJson(context, entry.uri);
                String audioFile = metadata == null ? ""
                    : metadata.optString("audioFile", "").trim();
                String lyricFile = metadata == null ? ""
                    : metadata.optString("lyricFile", "").trim();
                if (keep.contains(key)) {
                    keepNames.add(entry.name);
                    if (!audioFile.isEmpty()) keepNames.add(audioFile);
                    if (!lyricFile.isEmpty()) keepNames.add(lyricFile);
                } else {
                    deleteNames.add(entry.name);
                    if (!audioFile.isEmpty()) deleteNames.add(audioFile);
                    if (!lyricFile.isEmpty()) deleteNames.add(lyricFile);
                }
            }

            for (DocumentEntry entry : entries) {
                if (playlistUris.contains(entry.uri.toString()) || keepNames.contains(entry.name)) {
                    continue;
                }
                String key = legacyKey(entry.name);
                if (validKey(key)) {
                    if (!keep.contains(key)) deleteNames.add(entry.name);
                    continue;
                }
                if (entry.name.endsWith(".part") || entry.name.endsWith(".move_part")) {
                    deleteNames.add(entry.name);
                    continue;
                }
                if (isFriendlyCacheFile(entry.name)) {
                    // Also removes old orphan files whose metadata was already deleted
                    // after a false-negative completion check.
                    deleteNames.add(entry.name);
                }
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

    private static Set<String> normalizedKeys(Set<String> values) {
        Set<String> result = new HashSet<>();
        if (values == null) return result;
        for (String value : values) {
            if (value != null && validKey(value.toLowerCase(Locale.ROOT))) {
                result.add(value.toLowerCase(Locale.ROOT));
            }
        }
        return result;
    }

    private static Set<String> savedPlaylistUris(Context context) {
        Set<String> uris = new HashSet<>();
        String raw = context.getSharedPreferences(STATE_PREFS, Context.MODE_PRIVATE)
            .getString(KEY_PLAYLISTS, "[]");
        try {
            JSONArray playlists = new JSONArray(raw == null ? "[]" : raw);
            for (int playlistIndex = 0; playlistIndex < playlists.length(); playlistIndex++) {
                JSONObject playlist = playlists.optJSONObject(playlistIndex);
                JSONArray songs = playlist == null ? null : playlist.optJSONArray("songs");
                if (songs == null) continue;
                for (int songIndex = 0; songIndex < songs.length(); songIndex++) {
                    JSONObject song = songs.optJSONObject(songIndex);
                    if (song == null) continue;
                    addManagedUri(uris, song.optString("cachedUri", ""));
                    addManagedUri(uris, song.optString("uri", ""));
                }
            }
        } catch (Exception ignored) {
        }
        return uris;
    }

    private static void addManagedUri(Set<String> uris, String raw) {
        if (raw == null) return;
        String value = raw.trim();
        if (value.startsWith("content://") || value.startsWith("file://")) {
            uris.add(value);
        }
    }

    private static Set<String> savedPlaylistFileNames(Context context, Set<String> uris) {
        Set<String> names = new HashSet<>();
        for (String raw : uris) {
            try {
                Uri uri = Uri.parse(raw);
                if ("file".equalsIgnoreCase(uri.getScheme())) {
                    String path = uri.getPath();
                    if (path != null && !path.isEmpty()) names.add(new File(path).getName());
                    continue;
                }
                if (!"content".equalsIgnoreCase(uri.getScheme())) continue;
                try (Cursor cursor = context.getContentResolver().query(
                    uri, new String[] {OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst()) {
                        int column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                        String name = column < 0 ? "" : cursor.getString(column);
                        if (name != null && !name.trim().isEmpty()) names.add(name.trim());
                    }
                }
            } catch (Exception ignored) {
            }
        }
        return names;
    }

    private static Uri selectedTree(Context context) {
        String raw = context.getSharedPreferences(CACHE_PREFS, Context.MODE_PRIVATE)
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

    private static boolean isFriendlyCacheFile(String name) {
        if (name == null || name.trim().isEmpty()) return false;
        String lower = name.toLowerCase(Locale.ROOT);
        int dot = lower.lastIndexOf('.');
        if (dot <= 0 || dot >= lower.length() - 1) return false;
        String base = lower.substring(0, dot);
        String extension = lower.substring(dot + 1);
        if (!base.contains(" - ")) return false;
        return extension.equals("mp3") || extension.equals("flac")
            || extension.equals("m4a") || extension.equals("aac")
            || extension.equals("ogg") || extension.equals("opus")
            || extension.equals("wav") || extension.equals("wma")
            || extension.equals("webm") || extension.equals("amr")
            || extension.equals("mid") || extension.equals("midi")
            || extension.equals("aiff") || extension.equals("ac3")
            || extension.equals("eac3") || extension.equals("audio")
            || extension.equals("lrc");
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
