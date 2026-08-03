package com.jianglab.babywife;

import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.DocumentsContract;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * One-folder cache storage with two explicit uninstall behaviours.
 *
 * App-private storage is removed by Android when the app is uninstalled.
 * A user-selected document-tree folder remains after uninstall. Android does
 * not deliver a reliable callback to an app that is itself being uninstalled,
 * so switching the setting migrates the files between those two storage types.
 */
final class CacheStorage {
    private static final String PREFS = "cache_storage";
    private static final String KEY_TREE_URI = "tree_uri";
    private static final String INTERNAL_FOLDER = "network_music";
    private static final String META_PREFIX = ".babywife_";
    private static final String META_SUFFIX = ".json";
    private static final int KEY_LENGTH = 64;

    private CacheStorage() {
    }

    static final class MigrationResult {
        final int copied;
        final int removedFromOldLocation;
        final int retainedInOldLocation;
        final boolean changed;

        MigrationResult(int copied, int removedFromOldLocation, boolean changed) {
            this.copied = copied;
            this.removedFromOldLocation = removedFromOldLocation;
            this.retainedInOldLocation = Math.max(0, copied - removedFromOldLocation);
            this.changed = changed;
        }
    }

    static MigrationResult useDocumentTree(Context context, Uri treeUri) throws Exception {
        if (context == null || treeUri == null) throw new IllegalArgumentException("缓存文件夹无效");
        requireFileManagementPermission();
        int flags = Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION;
        context.getContentResolver().takePersistableUriPermission(treeUri, flags);
        verifyWritableTree(context, treeUri);

        Uri oldTree = selectedTree(context);
        if (oldTree != null && oldTree.toString().equals(treeUri.toString())) {
            saveSelectedTree(context, treeUri);
            return new MigrationResult(0, 0, false);
        }

        int copied;
        int removed;
        if (oldTree != null) {
            List<DocumentEntry> source = listDocumentsStrict(context, oldTree, false);
            copied = copyDocumentsToTree(context, source, treeUri);
            saveSelectedTree(context, treeUri);
            removed = deleteDocuments(context, source);
            if (removed == source.size()) releaseTreePermission(context, oldTree);
        } else {
            List<File> source = listAllInternalFiles(context);
            copied = copyFilesToTree(context, source, treeUri);
            saveSelectedTree(context, treeUri);
            removed = deleteFiles(source);
        }
        return new MigrationResult(copied, removed, true);
    }

    static MigrationResult useInternalStorage(Context context) throws Exception {
        if (context == null) return new MigrationResult(0, 0, false);
        requireFileManagementPermission();
        Uri oldTree = selectedTree(context);
        if (oldTree == null) return new MigrationResult(0, 0, false);

        List<DocumentEntry> source = listDocumentsStrict(context, oldTree, false);
        File root = internalRoot(context);
        if (!root.exists() && !root.mkdirs()) throw new IllegalStateException("无法创建应用内部缓存目录");
        int copied = copyDocumentsToInternal(context, source, root);
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(KEY_TREE_URI).apply();
        int removed = deleteDocuments(context, source);
        if (removed == source.size()) releaseTreePermission(context, oldTree);
        return new MigrationResult(copied, removed, true);
    }

    static boolean usesDocumentTree(Context context) {
        return selectedTree(context) != null;
    }

    static boolean uninstallCleanupEnabled(Context context) {
        return selectedTree(context) == null;
    }

    static String defaultLocation(Context context) {
        return internalRoot(context).getAbsolutePath();
    }

    static String description(Context context) {
        Uri tree = selectedTree(context);
        if (tree == null) return "缓存文件夹：应用内部";
        return "缓存文件夹：" + treeLabel(tree);
    }

    static String details(Context context) {
        Uri tree = selectedTree(context);
        StringBuilder text = new StringBuilder();
        text.append("原版默认缓存位置：\n")
            .append(defaultLocation(context))
            .append("\n该应用内部目录会随卸载清除，普通文件管理器通常无法直接访问。\n\n当前缓存位置：\n");
        if (tree == null) {
            text.append(defaultLocation(context))
                .append("\n（应用内部；卸载软件时由 Android 清理）");
        } else {
            text.append(treeLabel(tree)).append("\n").append(tree.toString())
                .append("\n（自选总文件夹；卸载软件后仍保留，可转移和手动管理）");
        }
        text.append("\n\n删除歌单或歌曲只移除歌单记录，不删除歌曲和歌词文件；")
            .append("顶部扫把只清理不再属于任何歌单的缓存。");
        return text.toString();
    }

    static void ensureFriendlyNames(Context context, String key, String title, String artist,
                                    String album, String catalogJson) throws Exception {
        if (!validKey(key) || context == null) return;
        MetadataRecord record = metadata(key, title, artist, album, catalogJson);
        Uri tree = selectedTree(context);
        if (tree != null) {
            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            DocumentEntry audio = findDocumentAudioForKey(context, tree, key, existing);
            DocumentEntry lyric = findDocumentLyricForKey(context, tree, key, existing);
            String friendly = friendlyBaseForTree(context, tree, record, existing);
            if (audio != null) {
                String ext = extensionOf(audio.name);
                String desired = friendly + "." + ext;
                if (!desired.equals(audio.name)) moveDocument(context, tree, audio, desired, audioMime(ext));
                record.audioFile = desired;
            } else if (existing != null) {
                record.audioFile = existing.audioFile;
            }
            if (lyric != null) {
                String desired = friendly + ".lrc";
                if (!desired.equals(lyric.name)) moveDocument(context, tree, lyric, desired, "text/plain");
                record.lyricFile = desired;
            } else if (existing != null) {
                record.lyricFile = existing.lyricFile;
            }
            if (existing == null && audio == null && lyric == null) return;
            writeMetadataToTree(context, tree, record);
            return;
        }

        File root = internalRoot(context);
        if (!root.exists() && !root.mkdirs()) throw new IllegalStateException("无法创建缓存目录");
        MetadataRecord existing = readMetadataFromInternal(root, key);
        File audio = findInternalAudioForKey(root, key, existing);
        File lyric = findInternalLyricForKey(root, key, existing);
        String friendly = friendlyBaseForInternal(root, record, existing);
        if (audio != null) {
            String ext = extensionOf(audio.getName());
            String desired = friendly + "." + ext;
            File target = new File(root, desired);
            if (!desired.equals(audio.getName())) moveFile(audio, target);
            record.audioFile = desired;
        } else if (existing != null) {
            record.audioFile = existing.audioFile;
        }
        if (lyric != null) {
            String desired = friendly + ".lrc";
            File target = new File(root, desired);
            if (!desired.equals(lyric.getName())) moveFile(lyric, target);
            record.lyricFile = desired;
        } else if (existing != null) {
            record.lyricFile = existing.lyricFile;
        }
        if (existing == null && audio == null && lyric == null) return;
        writeMetadataToInternal(root, record);
    }


    static int normalizeAllFriendlyNames(Context context) {
        if (context == null) return 0;
        Set<String> keys = new HashSet<>();
        Uri tree = selectedTree(context);
        if (tree != null) {
            try {
                for (DocumentEntry entry : listDocumentsStrict(context, tree, true)) {
                    String key = metadataKey(entry.name);
                    if (validKey(key)) keys.add(key);
                }
                int normalized = 0;
                for (String key : keys) {
                    try {
                        MetadataRecord record = readMetadataFromTree(context, tree, key);
                        if (record == null) continue;
                        ensureFriendlyNames(context, key, record.title, record.artist,
                            record.album, record.catalogJson);
                        normalized++;
                    } catch (Exception ignored) {
                    }
                }
                return normalized;
            } catch (Exception ignored) {
                return 0;
            }
        }

        File root = internalRoot(context);
        File[] files = root.listFiles();
        if (files == null) return 0;
        for (File file : files) {
            if (!file.isFile()) continue;
            String key = metadataKey(file.getName());
            if (validKey(key)) keys.add(key);
        }
        int normalized = 0;
        for (String key : keys) {
            try {
                MetadataRecord record = readMetadataFromInternal(root, key);
                if (record == null) continue;
                ensureFriendlyNames(context, key, record.title, record.artist,
                    record.album, record.catalogJson);
                normalized++;
            } catch (Exception ignored) {
            }
        }
        return normalized;
    }

    static String findAudioUri(Context context, String key) {
        if (context == null || !validKey(key)) return "";
        Uri tree = selectedTree(context);
        if (tree != null) {
            try {
                MetadataRecord record = readMetadataFromTree(context, tree, key);
                if (record != null && !record.audioFile.isEmpty()) {
                    Uri uri = findDocument(context, tree, record.audioFile);
                    if (uri != null) return uri.toString();
                }
                DocumentEntry fallback = findDocumentAudioForKey(context, tree, key, record);
                if (fallback != null && fallback.size != 0) return fallback.uri.toString();
            } catch (Exception ignored) {
            }
        }
        File root = internalRoot(context);
        MetadataRecord record = readMetadataFromInternal(root, key);
        if (record != null && !record.audioFile.isEmpty()) {
            File file = new File(root, record.audioFile);
            if (file.isFile() && file.length() > 0) return Uri.fromFile(file).toString();
        }
        File fallback = findInternalAudioForKey(root, key, record);
        return fallback == null ? "" : Uri.fromFile(fallback).toString();
    }

    static String readLyric(Context context, String key) {
        if (context == null || !validKey(key)) return "";
        Uri tree = selectedTree(context);
        if (tree != null) {
            try {
                MetadataRecord record = readMetadataFromTree(context, tree, key);
                if (record != null && !record.lyricFile.isEmpty()) {
                    Uri uri = findDocument(context, tree, record.lyricFile);
                    if (uri != null) return readText(context.getContentResolver().openInputStream(uri));
                }
                DocumentEntry fallback = findDocumentLyricForKey(context, tree, key, record);
                if (fallback != null) return readText(context.getContentResolver().openInputStream(fallback.uri));
            } catch (Exception ignored) {
            }
        }
        File root = internalRoot(context);
        MetadataRecord record = readMetadataFromInternal(root, key);
        if (record != null && !record.lyricFile.isEmpty()) {
            File file = new File(root, record.lyricFile);
            if (file.isFile()) {
                try {
                    return readText(new FileInputStream(file));
                } catch (Exception ignored) {
                }
            }
        }
        File fallback = findInternalLyricForKey(root, key, record);
        try {
            return fallback == null ? "" : readText(new FileInputStream(fallback));
        } catch (Exception ignored) {
            return "";
        }
    }

    static void writeLyric(Context context, String key, String text, String title, String artist,
                           String album, String catalogJson) throws Exception {
        if (context == null || !validKey(key) || text == null || text.trim().isEmpty()) return;
        MetadataRecord record = metadata(key, title, artist, album, catalogJson);
        Uri tree = selectedTree(context);
        if (tree != null) {
            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            if (existing != null) record.audioFile = existing.audioFile;
            String friendly = friendlyBaseForTree(context, tree, record, existing);
            removeDocumentsForKey(context, tree, key, true, false, false);
            String name = friendly + ".lrc";
            Uri outputUri = createOrReplaceDocument(context, tree, name, "text/plain");
            try (OutputStream output = context.getContentResolver().openOutputStream(outputUri, "w")) {
                if (output == null) throw new IllegalStateException("无法写入歌词缓存");
                output.write(text.getBytes(StandardCharsets.UTF_8));
            }
            record.lyricFile = name;
            writeMetadataToTree(context, tree, record);
            return;
        }

        File root = internalRoot(context);
        if (!root.exists() && !root.mkdirs()) throw new IllegalStateException("无法创建缓存目录");
        MetadataRecord existing = readMetadataFromInternal(root, key);
        if (existing != null) record.audioFile = existing.audioFile;
        String friendly = friendlyBaseForInternal(root, record, existing);
        removeInternalForKey(root, key, true, false, false);
        String name = friendly + ".lrc";
        File output = new File(root, name);
        File partial = new File(root, name + ".part");
        try (FileOutputStream stream = new FileOutputStream(partial)) {
            stream.write(text.getBytes(StandardCharsets.UTF_8));
        }
        replaceFile(partial, output);
        record.lyricFile = name;
        writeMetadataToInternal(root, record);
    }

    static String storeAudio(Context context, String key, String extension, File source, String title,
                             String artist, String album, String catalogJson) throws Exception {
        if (context == null || !validKey(key) || source == null || !source.isFile() || source.length() <= 0) {
            throw new IllegalArgumentException("歌曲缓存文件无效");
        }
        String safeExtension = sanitizeExtension(extension);
        MetadataRecord record = metadata(key, title, artist, album, catalogJson);
        Uri tree = selectedTree(context);
        if (tree != null) {
            MetadataRecord existing = readMetadataFromTree(context, tree, key);
            if (existing != null) record.lyricFile = existing.lyricFile;
            String baseName = friendlyBase(record);
            removeDocumentsForKey(context, tree, key, false, true, false);
            removeTreeAudioWithBase(context, tree, baseName);
            String fileName = baseName + "." + safeExtension;
            Uri target = createOrReplaceDocument(context, tree, fileName, audioMime(safeExtension));
            try (InputStream input = new BufferedInputStream(new FileInputStream(source));
                 OutputStream raw = context.getContentResolver().openOutputStream(target, "w");
                 OutputStream output = raw == null ? null : new BufferedOutputStream(raw)) {
                if (output == null) throw new IllegalStateException("无法写入歌曲缓存");
                copy(input, output);
            }
            record.audioFile = fileName;
            writeMetadataToTree(context, tree, record);
            return target.toString();
        }

        File root = internalRoot(context);
        if (!root.exists() && !root.mkdirs()) throw new IllegalStateException("无法创建缓存目录");
        MetadataRecord existing = readMetadataFromInternal(root, key);
        if (existing != null) record.lyricFile = existing.lyricFile;
        String baseName = friendlyBase(record);
        removeInternalForKey(root, key, false, true, false);
        removeInternalAudioWithBase(root, baseName);
        String fileName = baseName + "." + safeExtension;
        File target = new File(root, fileName);
        try (InputStream input = new BufferedInputStream(new FileInputStream(source));
             OutputStream output = new BufferedOutputStream(new FileOutputStream(target))) {
            copy(input, output);
        }
        record.audioFile = fileName;
        writeMetadataToInternal(root, record);
        return Uri.fromFile(target).toString();
    }

    static int deleteKey(Context context, String key) {
        if (context == null || !validKey(key)) return 0;
        int removed = removeInternalForKey(internalRoot(context), key, true, true, true);
        Uri tree = selectedTree(context);
        if (tree != null) {
            try {
                removed += removeDocumentsForKey(context, tree, key, true, true, true);
            } catch (Exception ignored) {
            }
        }
        return removed;
    }

    static int clearExcept(Context context, Set<String> keepKeys) {
        if (context == null) return 0;
        Set<String> keep = keepKeys == null ? new HashSet<>() : keepKeys;
        int removed = clearInternalExcept(internalRoot(context), keep);
        Uri tree = selectedTree(context);
        if (tree != null) {
            try {
                removed += clearTreeExcept(context, tree, keep);
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

    private static MetadataRecord metadata(String key, String title, String artist,
                                           String album, String catalogJson) {
        MetadataRecord record = new MetadataRecord();
        record.key = key == null ? "" : key.toLowerCase(Locale.ROOT);
        record.title = safeNamePart(title, "未知歌曲", 76);
        record.artist = safeNamePart(artist, "未知歌手", 60);
        record.album = album == null ? "" : album.trim();
        record.catalogJson = catalogJson == null ? "" : catalogJson;
        return record;
    }

    private static String friendlyBase(MetadataRecord record) {
        String base = record.title + " - " + record.artist;
        if (base.length() > 140) base = base.substring(0, 140).trim();
        return base;
    }

    private static void removeInternalAudioWithBase(File root, String baseName) {
        File[] files = root == null ? null : root.listFiles();
        if (files == null) return;
        for (File file : files) {
            if (!file.isFile()) continue;
            String name = file.getName();
            if (isMetadataName(name) || isLyricName(name)
                || name.endsWith(".part") || name.endsWith(".move_part")) continue;
            if (fileBase(name).equalsIgnoreCase(baseName)) deleteFile(file);
        }
    }

    private static void removeTreeAudioWithBase(Context context, Uri tree,
                                                String baseName) throws Exception {
        for (DocumentEntry entry : listDocumentsStrict(context, tree, false)) {
            String name = entry.name;
            if (isMetadataName(name) || isLyricName(name)
                || name.endsWith(".part") || name.endsWith(".move_part")) continue;
            if (!fileBase(name).equalsIgnoreCase(baseName)) continue;
            try {
                DocumentsContract.deleteDocument(context.getContentResolver(), entry.uri);
            } catch (Exception ignored) {
            }
        }
    }

    private static String friendlyBaseForInternal(File root, MetadataRecord record,
                                                  MetadataRecord existing) {
        Set<String> occupied = new HashSet<>();
        File[] files = root == null ? null : root.listFiles();
        if (files != null) {
            for (File file : files) {
                if (!file.isFile()) continue;
                String name = file.getName();
                if (isMetadataName(name) || name.endsWith(".part") || name.endsWith(".move_part")) continue;
                if (existing != null && (name.equals(existing.audioFile) || name.equals(existing.lyricFile))) continue;
                occupied.add(fileBase(name).toLowerCase(Locale.ROOT));
            }
        }
        return chooseFriendlyBase(record, existing, occupied);
    }

    private static String friendlyBaseForTree(Context context, Uri tree, MetadataRecord record,
                                              MetadataRecord existing) throws Exception {
        Set<String> occupied = new HashSet<>();
        for (DocumentEntry entry : listDocumentsStrict(context, tree, true)) {
            String name = entry.name;
            if (isMetadataName(name) || name.endsWith(".part") || name.endsWith(".move_part")) continue;
            if (existing != null && (name.equals(existing.audioFile) || name.equals(existing.lyricFile))) continue;
            occupied.add(fileBase(name).toLowerCase(Locale.ROOT));
        }
        return chooseFriendlyBase(record, existing, occupied);
    }

    private static String chooseFriendlyBase(MetadataRecord record, MetadataRecord existing,
                                             Set<String> occupied) {
        String plain = friendlyBase(record);
        String current = existingFriendlyBase(plain, existing);
        if (!current.isEmpty() && !occupied.contains(current.toLowerCase(Locale.ROOT))) return current;
        for (int index = 1; index <= 9999; index++) {
            String candidate = index == 1 ? plain : plain + " (" + index + ")";
            if (!occupied.contains(candidate.toLowerCase(Locale.ROOT))) return candidate;
        }
        throw new IllegalStateException("歌曲缓存文件名冲突过多");
    }

    private static String existingFriendlyBase(String plain, MetadataRecord existing) {
        if (existing == null) return "";
        String audioBase = fileBase(existing.audioFile);
        if (isFriendlyVariant(plain, audioBase)) return audioBase;
        String lyricBase = fileBase(existing.lyricFile);
        return isFriendlyVariant(plain, lyricBase) ? lyricBase : "";
    }

    private static boolean isFriendlyVariant(String plain, String candidate) {
        if (candidate == null || candidate.isEmpty()) return false;
        if (candidate.equals(plain)) return true;
        if (!candidate.startsWith(plain + " (") || !candidate.endsWith(")")) return false;
        String number = candidate.substring(plain.length() + 2, candidate.length() - 1);
        if (number.isEmpty()) return false;
        for (int i = 0; i < number.length(); i++) {
            if (!Character.isDigit(number.charAt(i))) return false;
        }
        return true;
    }

    private static String fileBase(String name) {
        if (name == null || name.isEmpty()) return "";
        int dot = name.lastIndexOf('.');
        return dot > 0 ? name.substring(0, dot) : name;
    }

    private static String metadataName(String key) {
        return META_PREFIX + key.toLowerCase(Locale.ROOT) + META_SUFFIX;
    }

    private static String metadataKey(String name) {
        if (name == null || !name.startsWith(META_PREFIX) || !name.endsWith(META_SUFFIX)) return "";
        int start = META_PREFIX.length();
        int end = name.length() - META_SUFFIX.length();
        return end > start ? name.substring(start, end).toLowerCase(Locale.ROOT) : "";
    }

    private static MetadataRecord readMetadataFromInternal(File root, String key) {
        File file = new File(root, metadataName(key));
        if (!file.isFile()) return null;
        try {
            return MetadataRecord.fromJson(readText(new FileInputStream(file)));
        } catch (Exception ignored) {
            return null;
        }
    }

    private static MetadataRecord readMetadataFromTree(Context context, Uri tree, String key) {
        try {
            Uri uri = findDocument(context, tree, metadataName(key));
            if (uri == null) return null;
            return MetadataRecord.fromJson(readText(context.getContentResolver().openInputStream(uri)));
        } catch (Exception ignored) {
            return null;
        }
    }

    private static void writeMetadataToInternal(File root, MetadataRecord record) throws Exception {
        File output = new File(root, metadataName(record.key));
        File partial = new File(root, output.getName() + ".part");
        try (FileOutputStream stream = new FileOutputStream(partial)) {
            stream.write(record.toJson().toString().getBytes(StandardCharsets.UTF_8));
        }
        replaceFile(partial, output);
    }

    private static void writeMetadataToTree(Context context, Uri tree, MetadataRecord record) throws Exception {
        Uri output = createOrReplaceDocument(context, tree, metadataName(record.key), "application/json");
        try (OutputStream stream = context.getContentResolver().openOutputStream(output, "w")) {
            if (stream == null) throw new IllegalStateException("无法写入歌曲信息");
            stream.write(record.toJson().toString().getBytes(StandardCharsets.UTF_8));
        }
    }

    private static File findInternalAudioForKey(File root, String key, MetadataRecord record) {
        if (record != null && !record.audioFile.isEmpty()) {
            File named = new File(root, record.audioFile);
            if (named.isFile() && named.length() > 0) return named;
        }
        File[] files = root.listFiles();
        if (files == null) return null;
        for (File file : files) {
            if (!file.isFile() || isLyricName(file.getName()) || isMetadataName(file.getName())
                || file.getName().endsWith(".part") || file.getName().endsWith(".move_part")) continue;
            if (legacyKeyFromName(file.getName()).equals(key) && file.length() > 0) return file;
        }
        return null;
    }

    private static File findInternalLyricForKey(File root, String key, MetadataRecord record) {
        if (record != null && !record.lyricFile.isEmpty()) {
            File named = new File(root, record.lyricFile);
            if (named.isFile()) return named;
        }
        File[] files = root.listFiles();
        if (files == null) return null;
        for (File file : files) {
            if (file.isFile() && isLyricName(file.getName()) && legacyKeyFromName(file.getName()).equals(key)) {
                return file;
            }
        }
        return null;
    }

    private static DocumentEntry findDocumentAudioForKey(Context context, Uri tree, String key,
                                                          MetadataRecord record) throws Exception {
        List<DocumentEntry> entries = listDocumentsStrict(context, tree, true);
        if (record != null && !record.audioFile.isEmpty()) {
            for (DocumentEntry entry : entries) {
                if (record.audioFile.equals(entry.name) && entry.size != 0) return entry;
            }
        }
        for (DocumentEntry entry : entries) {
            if (isLyricName(entry.name) || isMetadataName(entry.name)) continue;
            if (legacyKeyFromName(entry.name).equals(key) && entry.size != 0) return entry;
        }
        return null;
    }

    private static DocumentEntry findDocumentLyricForKey(Context context, Uri tree, String key,
                                                          MetadataRecord record) throws Exception {
        List<DocumentEntry> entries = listDocumentsStrict(context, tree, true);
        if (record != null && !record.lyricFile.isEmpty()) {
            for (DocumentEntry entry : entries) {
                if (record.lyricFile.equals(entry.name)) return entry;
            }
        }
        for (DocumentEntry entry : entries) {
            if (isLyricName(entry.name) && legacyKeyFromName(entry.name).equals(key)) return entry;
        }
        return null;
    }

    private static int removeInternalForKey(File root, String key, boolean lyric,
                                            boolean audio, boolean metadata) {
        int removed = 0;
        MetadataRecord record = readMetadataFromInternal(root, key);
        if (record != null) {
            if (lyric && !record.lyricFile.isEmpty() && deleteFile(new File(root, record.lyricFile))) removed++;
            if (audio && !record.audioFile.isEmpty() && deleteFile(new File(root, record.audioFile))) removed++;
        }
        File[] files = root.listFiles();
        if (files != null) {
            for (File file : files) {
                if (!file.isFile()) continue;
                String name = file.getName();
                if (metadata && name.equals(metadataName(key))) {
                    if (deleteFile(file)) removed++;
                } else if (legacyKeyFromName(name).equals(key)) {
                    if ((lyric && isLyricName(name)) || (audio && !isLyricName(name) && !isMetadataName(name))) {
                        if (deleteFile(file)) removed++;
                    }
                }
            }
        }
        return removed;
    }

    private static int removeDocumentsForKey(Context context, Uri tree, String key, boolean lyric,
                                             boolean audio, boolean metadata) throws Exception {
        int removed = 0;
        MetadataRecord record = readMetadataFromTree(context, tree, key);
        Set<String> names = new HashSet<>();
        if (record != null) {
            if (lyric && !record.lyricFile.isEmpty()) names.add(record.lyricFile);
            if (audio && !record.audioFile.isEmpty()) names.add(record.audioFile);
        }
        ContentResolver resolver = context.getContentResolver();
        for (DocumentEntry entry : listDocumentsStrict(context, tree, true)) {
            String name = entry.name;
            boolean match = names.contains(name)
                || (metadata && name.equals(metadataName(key)))
                || (legacyKeyFromName(name).equals(key)
                    && ((lyric && isLyricName(name))
                    || (audio && !isLyricName(name) && !isMetadataName(name))));
            if (match) {
                try {
                    if (DocumentsContract.deleteDocument(resolver, entry.uri)) removed++;
                } catch (Exception ignored) {
                }
            }
        }
        return removed;
    }

    private static int clearInternalExcept(File root, Set<String> keep) {
        File[] files = root.listFiles();
        if (files == null) return 0;
        int removed = 0;
        Set<String> handledNames = new HashSet<>();
        for (File file : files) {
            if (!file.isFile() || !isMetadataName(file.getName())) continue;
            String key = keyFromMetadataName(file.getName());
            if (!validKey(key) || keep.contains(key)) continue;
            MetadataRecord record = readMetadataFromInternal(root, key);
            if (record != null) {
                if (!record.audioFile.isEmpty()) handledNames.add(record.audioFile);
                if (!record.lyricFile.isEmpty()) handledNames.add(record.lyricFile);
                if (!record.audioFile.isEmpty() && deleteFile(new File(root, record.audioFile))) removed++;
                if (!record.lyricFile.isEmpty() && deleteFile(new File(root, record.lyricFile))) removed++;
            }
            handledNames.add(file.getName());
            if (deleteFile(file)) removed++;
        }
        files = root.listFiles();
        if (files == null) return removed;
        for (File file : files) {
            if (!file.isFile() || handledNames.contains(file.getName())) continue;
            String key = legacyKeyFromName(file.getName());
            if (validKey(key) && !keep.contains(key) && deleteFile(file)) removed++;
        }
        return removed;
    }

    private static int clearTreeExcept(Context context, Uri tree, Set<String> keep) throws Exception {
        List<DocumentEntry> entries = listDocumentsStrict(context, tree, true);
        Set<String> deleteNames = new HashSet<>();
        for (DocumentEntry entry : entries) {
            if (!isMetadataName(entry.name)) continue;
            String key = keyFromMetadataName(entry.name);
            if (!validKey(key) || keep.contains(key)) continue;
            MetadataRecord record = MetadataRecord.fromJson(
                readText(context.getContentResolver().openInputStream(entry.uri)));
            if (record != null) {
                if (!record.audioFile.isEmpty()) deleteNames.add(record.audioFile);
                if (!record.lyricFile.isEmpty()) deleteNames.add(record.lyricFile);
            }
            deleteNames.add(entry.name);
        }
        for (DocumentEntry entry : entries) {
            String key = legacyKeyFromName(entry.name);
            if (validKey(key) && !keep.contains(key)) deleteNames.add(entry.name);
        }
        int removed = 0;
        for (DocumentEntry entry : entries) {
            if (!deleteNames.contains(entry.name)) continue;
            try {
                if (DocumentsContract.deleteDocument(context.getContentResolver(), entry.uri)) removed++;
            } catch (Exception ignored) {
            }
        }
        return removed;
    }

    private static void requireFileManagementPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R
            && !Environment.isExternalStorageManager()) {
            throw new SecurityException("请先授予文件管理权限");
        }
    }

    private static void releaseTreePermission(Context context, Uri treeUri) {
        if (context == null || treeUri == null) return;
        try {
            context.getContentResolver().releasePersistableUriPermission(treeUri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
        } catch (Exception ignored) {
        }
    }

    private static void verifyDocumentDigest(Context context, Uri target,
                                             String expected, String name) throws Exception {
        String actual = digest(context.getContentResolver().openInputStream(target));
        if (expected.equals(actual)) return;
        try {
            DocumentsContract.deleteDocument(context.getContentResolver(), target);
        } catch (Exception ignored) {
        }
        throw new IllegalStateException("迁移后校验失败：" + name);
    }

    private static String copyAndDigest(InputStream input, OutputStream output) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] buffer = new byte[64 * 1024];
        int count;
        while ((count = input.read(buffer)) >= 0) {
            if (count <= 0) continue;
            output.write(buffer, 0, count);
            digest.update(buffer, 0, count);
        }
        output.flush();
        return hex(digest.digest());
    }

    private static String digest(InputStream raw) throws Exception {
        if (raw == null) throw new IllegalStateException("无法读取迁移后的文件");
        try (InputStream input = new BufferedInputStream(raw)) {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                if (count > 0) digest.update(buffer, 0, count);
            }
            return hex(digest.digest());
        }
    }

    private static String hex(byte[] bytes) {
        StringBuilder text = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) text.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        return text.toString();
    }

    private static void saveSelectedTree(Context context, Uri treeUri) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY_TREE_URI, treeUri.toString()).apply();
    }

    private static void verifyWritableTree(Context context, Uri treeUri) throws Exception {
        String probeName = ".babywife_cache_probe_" + System.currentTimeMillis();
        Uri probe = createOrReplaceDocument(context, treeUri, probeName, "application/octet-stream");
        try (OutputStream output = context.getContentResolver().openOutputStream(probe, "w")) {
            if (output == null) throw new IllegalStateException("无法写入所选缓存文件夹");
            output.write(1);
        } finally {
            try {
                DocumentsContract.deleteDocument(context.getContentResolver(), probe);
            } catch (Exception ignored) {
            }
        }
    }

    private static int copyFilesToTree(Context context, List<File> source, Uri targetTree) throws Exception {
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

    private static int copyDocumentsToTree(Context context, List<DocumentEntry> source, Uri targetTree) throws Exception {
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

    private static int copyDocumentsToInternal(Context context, List<DocumentEntry> source, File root) throws Exception {
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

    private static int deleteDocuments(Context context, List<DocumentEntry> entries) {
        int removed = 0;
        for (DocumentEntry entry : entries) {
            try {
                if (DocumentsContract.deleteDocument(context.getContentResolver(), entry.uri)) removed++;
            } catch (Exception ignored) {
            }
        }
        return removed;
    }

    private static int deleteFiles(List<File> files) {
        int removed = 0;
        for (File file : files) {
            if (file != null && deleteFile(file)) removed++;
        }
        return removed;
    }

    private static List<File> listAllInternalFiles(Context context) {
        List<File> files = new ArrayList<>();
        File[] entries = internalRoot(context).listFiles();
        if (entries == null) return files;
        for (File file : entries) {
            if (file == null || !file.isFile()) continue;
            String name = file.getName();
            if (name.endsWith(".part") || name.endsWith(".move_part")) continue;
            files.add(file);
        }
        return files;
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

    private static String treeLabel(Uri tree) {
        String label = tree == null ? "" : tree.getLastPathSegment();
        if (label == null || label.trim().isEmpty()) label = tree == null ? "" : tree.toString();
        return Uri.decode(label);
    }

    private static Uri treeDocumentUri(Uri treeUri) {
        return DocumentsContract.buildDocumentUriUsingTree(treeUri, DocumentsContract.getTreeDocumentId(treeUri));
    }

    private static Uri childrenUri(Uri treeUri) {
        return DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, DocumentsContract.getTreeDocumentId(treeUri));
    }

    private static List<DocumentEntry> listDocumentsStrict(Context context, Uri treeUri, boolean managedOnly) throws Exception {
        List<DocumentEntry> entries = new ArrayList<>();
        String[] projection = {
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_SIZE,
            DocumentsContract.Document.COLUMN_MIME_TYPE
        };
        Cursor cursor = context.getContentResolver().query(childrenUri(treeUri), projection, null, null, null);
        if (cursor == null) throw new IllegalStateException("无法读取缓存文件夹");
        try (Cursor closeable = cursor) {
            int idColumn = closeable.getColumnIndex(DocumentsContract.Document.COLUMN_DOCUMENT_ID);
            int nameColumn = closeable.getColumnIndex(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            int sizeColumn = closeable.getColumnIndex(DocumentsContract.Document.COLUMN_SIZE);
            int typeColumn = closeable.getColumnIndex(DocumentsContract.Document.COLUMN_MIME_TYPE);
            while (closeable.moveToNext()) {
                String id = idColumn < 0 ? "" : closeable.getString(idColumn);
                String name = nameColumn < 0 ? "" : closeable.getString(nameColumn);
                long size = sizeColumn < 0 || closeable.isNull(sizeColumn) ? -1 : closeable.getLong(sizeColumn);
                String type = typeColumn < 0 ? "" : closeable.getString(typeColumn);
                if (id == null || id.isEmpty() || DocumentsContract.Document.MIME_TYPE_DIR.equals(type)) continue;
                String safeName = name == null ? "" : name;
                if (managedOnly && !isManagedCacheName(safeName)) continue;
                entries.add(new DocumentEntry(safeName,
                    DocumentsContract.buildDocumentUriUsingTree(treeUri, id), size));
            }
        }
        return entries;
    }

    private static Uri findDocument(Context context, Uri treeUri, String name) {
        try {
            for (DocumentEntry entry : listDocumentsStrict(context, treeUri, false)) {
                if (name.equals(entry.name)) return entry.uri;
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private static Uri createOrReplaceDocument(Context context, Uri treeUri, String name, String mime) throws Exception {
        Uri existing = findDocument(context, treeUri, name);
        if (existing != null && !DocumentsContract.deleteDocument(context.getContentResolver(), existing)) {
            throw new IllegalStateException("无法替换目标缓存文件：" + name);
        }
        Uri created = DocumentsContract.createDocument(context.getContentResolver(),
            treeDocumentUri(treeUri), mime, name);
        if (created == null) throw new IllegalStateException("无法在所选文件夹创建缓存文件");
        return created;
    }

    private static void moveDocument(Context context, Uri tree, DocumentEntry source,
                                     String targetName, String mime) throws Exception {
        Uri existing = findDocument(context, tree, targetName);
        if (existing != null && !existing.equals(source.uri)) {
            DocumentsContract.deleteDocument(context.getContentResolver(), existing);
        }
        try {
            Uri renamed = DocumentsContract.renameDocument(context.getContentResolver(), source.uri, targetName);
            if (renamed != null) return;
        } catch (Exception ignored) {
        }
        Uri target = createOrReplaceDocument(context, tree, targetName, mime);
        try (InputStream rawInput = context.getContentResolver().openInputStream(source.uri);
             InputStream input = rawInput == null ? null : new BufferedInputStream(rawInput);
             OutputStream rawOutput = context.getContentResolver().openOutputStream(target, "w");
             OutputStream output = rawOutput == null ? null : new BufferedOutputStream(rawOutput)) {
            if (input == null || output == null) throw new IllegalStateException("无法重命名缓存文件");
            copy(input, output);
        }
        DocumentsContract.deleteDocument(context.getContentResolver(), source.uri);
    }

    private static void moveFile(File source, File target) throws Exception {
        if (source.equals(target)) return;
        if (target.exists() && !target.delete()) throw new IllegalStateException("无法替换缓存文件：" + target.getName());
        if (source.renameTo(target)) return;
        try (InputStream input = new BufferedInputStream(new FileInputStream(source));
             OutputStream output = new BufferedOutputStream(new FileOutputStream(target))) {
            copy(input, output);
        }
        if (!source.delete()) throw new IllegalStateException("旧缓存文件无法删除：" + source.getName());
    }

    private static boolean isManagedCacheName(String name) {
        if (name == null || name.endsWith(".part") || name.endsWith(".move_part")) return false;
        if (isMetadataName(name)) return validKey(keyFromMetadataName(name));
        if (validKey(legacyKeyFromName(name))) return true;
        int close = name.lastIndexOf(']');
        int open = name.lastIndexOf('[', close);
        if (open >= 0 && close == open + 9) {
            String shortKey = name.substring(open + 1, close);
            return shortKey.matches("[0-9a-fA-F]{8}");
        }
        return false;
    }

    private static boolean isMetadataName(String name) {
        return name != null && name.startsWith(META_PREFIX) && name.endsWith(META_SUFFIX);
    }

    private static String keyFromMetadataName(String name) {
        if (!isMetadataName(name)) return "";
        return name.substring(META_PREFIX.length(), name.length() - META_SUFFIX.length())
            .toLowerCase(Locale.ROOT);
    }

    private static String legacyKeyFromName(String name) {
        if (name == null || name.length() <= KEY_LENGTH || name.charAt(KEY_LENGTH) != '.') return "";
        String candidate = name.substring(0, KEY_LENGTH).toLowerCase(Locale.ROOT);
        return validKey(candidate) ? candidate : "";
    }

    private static boolean validKey(String key) {
        if (key == null || key.length() != KEY_LENGTH) return false;
        for (int i = 0; i < key.length(); i++) {
            char ch = Character.toLowerCase(key.charAt(i));
            if (!((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f'))) return false;
        }
        return true;
    }

    private static boolean isLyricName(String name) {
        return name != null && name.toLowerCase(Locale.ROOT).endsWith(".lrc");
    }

    private static String extensionOf(String name) {
        int dot = name == null ? -1 : name.lastIndexOf('.');
        return sanitizeExtension(dot < 0 ? "audio" : name.substring(dot + 1));
    }

    private static String sanitizeExtension(String value) {
        String extension = value == null ? "" : value.toLowerCase(Locale.ROOT)
            .replaceAll("[^a-z0-9]", "");
        if (extension.isEmpty()) return "audio";
        return extension.length() > 12 ? extension.substring(0, 12) : extension;
    }

    private static String safeNamePart(String value, String fallback, int maxLength) {
        String safe = value == null ? "" : value.trim();
        if (safe.isEmpty()) safe = fallback;
        safe = safe.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]", "_")
            .replaceAll("\\s+", " ").trim();
        while (safe.endsWith(".") || safe.endsWith(" ")) {
            safe = safe.substring(0, safe.length() - 1);
        }
        if (safe.isEmpty()) safe = fallback;
        if (safe.length() > maxLength) safe = safe.substring(0, maxLength).trim();
        return safe;
    }

    private static boolean deleteFile(File file) {
        return file != null && file.isFile() && file.delete();
    }

    private static String readText(InputStream raw) {
        if (raw == null) return "";
        try (InputStream input = raw) {
            byte[] buffer = new byte[16 * 1024];
            ByteArrayOutputStream output = new ByteArrayOutputStream();
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
        try (InputStream input = new FileInputStream(source);
             OutputStream output = new FileOutputStream(target)) {
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

    private static String mimeForName(String name) {
        if (isMetadataName(name)) return "application/json";
        if (isLyricName(name)) return "text/plain";
        return audioMime(extensionOf(name));
    }

    private static String audioMime(String extension) {
        if ("mp3".equals(extension)) return "audio/mpeg";
        if ("flac".equals(extension)) return "audio/flac";
        if ("m4a".equals(extension) || "mp4".equals(extension)) return "audio/mp4";
        if ("aac".equals(extension)) return "audio/aac";
        if ("ogg".equals(extension)) return "audio/ogg";
        if ("opus".equals(extension)) return "audio/opus";
        if ("wav".equals(extension)) return "audio/wav";
        if ("webm".equals(extension)) return "audio/webm";
        if ("amr".equals(extension)) return "audio/amr";
        if ("aiff".equals(extension) || "aif".equals(extension)) return "audio/aiff";
        if ("mid".equals(extension) || "midi".equals(extension)) return "audio/midi";
        if ("wma".equals(extension)) return "audio/x-ms-wma";
        if ("ac3".equals(extension)) return "audio/ac3";
        if ("eac3".equals(extension)) return "audio/eac3";
        return "application/octet-stream";
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

    private static final class MetadataRecord {
        String key = "";
        String title = "";
        String artist = "";
        String album = "";
        String catalogJson = "";
        String audioFile = "";
        String lyricFile = "";

        JSONObject toJson() {
            JSONObject object = new JSONObject();
            try {
                object.put("key", key);
                object.put("title", title);
                object.put("artist", artist);
                object.put("album", album);
                object.put("catalogJson", catalogJson);
                object.put("audioFile", audioFile);
                object.put("lyricFile", lyricFile);
            } catch (Exception ignored) {
            }
            return object;
        }

        static MetadataRecord fromJson(String raw) {
            if (raw == null || raw.trim().isEmpty()) return null;
            try {
                JSONObject object = new JSONObject(raw);
                MetadataRecord record = new MetadataRecord();
                record.key = object.optString("key", "").toLowerCase(Locale.ROOT);
                if (!validKey(record.key)) return null;
                record.title = object.optString("title", "");
                record.artist = object.optString("artist", "");
                record.album = object.optString("album", "");
                record.catalogJson = object.optString("catalogJson", "");
                record.audioFile = object.optString("audioFile", "");
                record.lyricFile = object.optString("lyricFile", "");
                return record;
            } catch (Exception ignored) {
                return null;
            }
        }
    }
}
