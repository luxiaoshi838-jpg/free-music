package com.jianglab.babywife;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.media.MediaMetadataRetriever;
import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;

/** Loads and caches album artwork for MediaSession, notification and lock screen. */
final class PlaybackArtworkLoader {
    private static final int CONNECT_TIMEOUT_MS = 9000;
    private static final int READ_TIMEOUT_MS = 15000;
    private static final int MAX_REDIRECTS = 6;
    private static final int MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024;
    private static final int TARGET_SIZE = 1280;
    private static final int MAX_CACHE_FILES = 180;
    private static final long MAX_CACHE_BYTES = 96L * 1024L * 1024L;

    private PlaybackArtworkLoader() {
    }

    static String identity(String title, String artist, String catalogJson, String mediaUri) {
        try {
            JSONObject catalog = new JSONObject(catalogJson == null ? "{}" : catalogJson);
            String source = catalog.optString("source", "").trim().toLowerCase(Locale.ROOT);
            String id = catalog.optString("id", "").trim();
            if (!source.isEmpty() && !id.isEmpty()) return source + "|" + id;
        } catch (Exception ignored) {
        }
        String uri = mediaUri == null ? "" : mediaUri.trim();
        if (uri.startsWith("content:") || uri.startsWith("file:")) return "local|" + uri;
        return "meta|" + safe(title).trim().toLowerCase(Locale.ROOT)
            + "|" + safe(artist).trim().toLowerCase(Locale.ROOT);
    }

    static Bitmap load(Context context, String title, String artist,
                       String catalogJson, String mediaUri) {
        return load(context, title, artist, catalogJson, "", mediaUri);
    }

    static Bitmap load(Context context, String title, String artist,
                       String catalogJson, String explicitArtworkUrl,
                       String mediaUri) {
        if (context == null) return null;
        String identity = identity(title, artist, catalogJson, mediaUri);
        File directory = cacheDirectory(context);
        File cached = new File(directory, sha256(identity) + ".jpg");
        Bitmap bitmap = decodeScaledFile(cached, TARGET_SIZE);
        if (bitmap != null) {
            cached.setLastModified(System.currentTimeMillis());
            return bitmap;
        }

        bitmap = embeddedArtwork(context, mediaUri);
        if (bitmap == null) {
            String url = explicitArtworkUrl == null ? "" : explicitArtworkUrl.trim();
            if (url.isEmpty()) url = findArtworkUrl(catalogJson);
            if (!url.isEmpty()) bitmap = downloadArtwork(url);
        }
        if (bitmap == null) return null;

        Bitmap square = centerCropSquare(bitmap, TARGET_SIZE);
        if (square != bitmap) bitmap.recycle();
        saveJpeg(cached, square);
        prune(directory);
        return square;
    }

    private static Bitmap embeddedArtwork(Context context, String mediaUri) {
        String raw = mediaUri == null ? "" : mediaUri.trim();
        if (!raw.startsWith("content:") && !raw.startsWith("file:")) return null;
        MediaMetadataRetriever retriever = new MediaMetadataRetriever();
        try {
            retriever.setDataSource(context, Uri.parse(raw));
            byte[] bytes = retriever.getEmbeddedPicture();
            if (bytes == null || bytes.length == 0 || bytes.length > MAX_DOWNLOAD_BYTES) return null;
            return decodeScaledBytes(bytes, TARGET_SIZE);
        } catch (Throwable ignored) {
            return null;
        } finally {
            try {
                retriever.release();
            } catch (Exception ignored) {
            }
        }
    }

    static String extractArtworkUrl(String catalogJson) {
        return findArtworkUrl(catalogJson);
    }

    private static String findArtworkUrl(String catalogJson) {
        try {
            JSONObject root = new JSONObject(catalogJson == null ? "{}" : catalogJson);
            String direct = findImageValue(root, 0);
            if (!direct.isEmpty()) return normalizeImageUrl(direct);

            String source = root.optString("source", "").trim().toLowerCase(Locale.ROOT);
            if ("qq".equals(source)) {
                String albumMid = findStringForKeys(root, 0,
                    "albummid", "album_mid", "albummidstr", "albumid");
                if (!albumMid.isEmpty() && albumMid.matches("[A-Za-z0-9]+")) {
                    return "https://y.gtimg.cn/music/photo_new/T002R800x800M000"
                        + albumMid + ".jpg";
                }
            }
        } catch (Exception ignored) {
        }
        return "";
    }

    private static String findImageValue(Object node, int depth) {
        if (node == null || depth > 7) return "";
        if (node instanceof JSONObject) {
            JSONObject object = (JSONObject) node;
            List<String> keys = new ArrayList<>();
            Iterator<String> iterator = object.keys();
            while (iterator.hasNext()) keys.add(iterator.next());
            Collections.sort(keys, (left, right) -> imageKeyScore(right) - imageKeyScore(left));
            for (String key : keys) {
                int score = imageKeyScore(key);
                if (score <= 0) continue;
                Object value = object.opt(key);
                if (value instanceof String) {
                    String text = ((String) value).trim();
                    if (looksLikeImageUrl(text)) return text;
                }
            }
            for (String key : keys) {
                Object value = object.opt(key);
                if (value instanceof JSONObject || value instanceof JSONArray) {
                    String nested = findImageValue(value, depth + 1);
                    if (!nested.isEmpty()) return nested;
                }
            }
        } else if (node instanceof JSONArray) {
            JSONArray array = (JSONArray) node;
            for (int i = 0; i < array.length(); i++) {
                String nested = findImageValue(array.opt(i), depth + 1);
                if (!nested.isEmpty()) return nested;
            }
        }
        return "";
    }

    private static int imageKeyScore(String key) {
        String normalized = safe(key).toLowerCase(Locale.ROOT)
            .replace("_", "").replace("-", "").replace(".", "");
        if (normalized.equals("artworkurl") || normalized.equals("coverurl")
            || normalized.equals("picurl") || normalized.equals("imageurl")) return 100;
        if (normalized.contains("albumcover") || normalized.contains("albumart")
            || normalized.contains("albumpic")) return 95;
        if (normalized.contains("coverimg") || normalized.contains("coverpic")) return 90;
        if (normalized.contains("artwork") || normalized.contains("cover")) return 80;
        if (normalized.contains("pic") || normalized.contains("image")
            || normalized.equals("img")) return 60;
        return 0;
    }

    private static String findStringForKeys(Object node, int depth, String... wantedKeys) {
        if (node == null || depth > 7) return "";
        if (node instanceof JSONObject) {
            JSONObject object = (JSONObject) node;
            Iterator<String> iterator = object.keys();
            while (iterator.hasNext()) {
                String key = iterator.next();
                String normalized = key.toLowerCase(Locale.ROOT).replace("_", "").replace("-", "");
                for (String wanted : wantedKeys) {
                    String target = wanted.toLowerCase(Locale.ROOT).replace("_", "").replace("-", "");
                    if (!normalized.equals(target)) continue;
                    String value = object.optString(key, "").trim();
                    if (!value.isEmpty()) return value;
                }
            }
            iterator = object.keys();
            while (iterator.hasNext()) {
                Object child = object.opt(iterator.next());
                if (child instanceof JSONObject || child instanceof JSONArray) {
                    String nested = findStringForKeys(child, depth + 1, wantedKeys);
                    if (!nested.isEmpty()) return nested;
                }
            }
        } else if (node instanceof JSONArray) {
            JSONArray array = (JSONArray) node;
            for (int i = 0; i < array.length(); i++) {
                String nested = findStringForKeys(array.opt(i), depth + 1, wantedKeys);
                if (!nested.isEmpty()) return nested;
            }
        }
        return "";
    }

    private static boolean looksLikeImageUrl(String value) {
        String text = normalizeImageUrl(value);
        if (!text.startsWith("http://") && !text.startsWith("https://")) return false;
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.contains(".mp3") || lower.contains(".m4a") || lower.contains(".flac")
            || lower.contains(".aac") || lower.contains("audio")) return false;
        return true;
    }

    private static String normalizeImageUrl(String value) {
        String text = safe(value).trim().replace("\\/", "/");
        if (text.startsWith("//")) text = "https:" + text;
        text = text.replace("{size}", "800")
            .replace("{width}", "800")
            .replace("{height}", "800");
        return text;
    }

    private static Bitmap downloadArtwork(String urlText) {
        HttpURLConnection connection = null;
        try {
            URL current = new URL(normalizeImageUrl(urlText));
            for (int redirect = 0; redirect <= MAX_REDIRECTS; redirect++) {
                connection = (HttpURLConnection) current.openConnection();
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
                connection.setReadTimeout(READ_TIMEOUT_MS);
                connection.setUseCaches(true);
                connection.setRequestProperty("User-Agent",
                    "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Chrome/131 Mobile Safari/537.36");
                connection.setRequestProperty("Accept", "image/avif,image/webp,image/apng,image/*,*/*;q=0.8");
                int code = connection.getResponseCode();
                if (code >= 300 && code < 400) {
                    String location = connection.getHeaderField("Location");
                    connection.disconnect();
                    connection = null;
                    if (location == null || location.trim().isEmpty()) return null;
                    current = new URL(current, location.trim());
                    continue;
                }
                if (code < 200 || code >= 300) return null;
                int declared = connection.getContentLength();
                if (declared > MAX_DOWNLOAD_BYTES) return null;
                try (InputStream input = new BufferedInputStream(connection.getInputStream());
                     ByteArrayOutputStream output = new ByteArrayOutputStream(
                         declared > 0 ? Math.min(declared, MAX_DOWNLOAD_BYTES) : 64 * 1024)) {
                    byte[] buffer = new byte[32 * 1024];
                    int total = 0;
                    int read;
                    while ((read = input.read(buffer)) >= 0) {
                        if (read == 0) continue;
                        total += read;
                        if (total > MAX_DOWNLOAD_BYTES) return null;
                        output.write(buffer, 0, read);
                    }
                    return decodeScaledBytes(output.toByteArray(), TARGET_SIZE);
                }
            }
        } catch (Throwable ignored) {
            return null;
        } finally {
            if (connection != null) connection.disconnect();
        }
        return null;
    }

    private static Bitmap decodeScaledFile(File file, int target) {
        if (file == null || !file.isFile() || file.length() <= 0L) return null;
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(file.getAbsolutePath(), bounds);
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = sampleSize(bounds.outWidth, bounds.outHeight, target);
        options.inPreferredConfig = Bitmap.Config.ARGB_8888;
        try {
            return BitmapFactory.decodeFile(file.getAbsolutePath(), options);
        } catch (OutOfMemoryError ignored) {
            return null;
        }
    }

    private static Bitmap decodeScaledBytes(byte[] bytes, int target) {
        if (bytes == null || bytes.length == 0) return null;
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(bytes, 0, bytes.length, bounds);
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = sampleSize(bounds.outWidth, bounds.outHeight, target);
        options.inPreferredConfig = Bitmap.Config.ARGB_8888;
        try {
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
        } catch (OutOfMemoryError ignored) {
            return null;
        }
    }

    private static int sampleSize(int width, int height, int target) {
        int sample = 1;
        while (width / (sample * 2) >= target && height / (sample * 2) >= target) sample *= 2;
        return Math.max(1, sample);
    }

    private static Bitmap centerCropSquare(Bitmap input, int target) {
        if (input == null) return null;
        int width = input.getWidth();
        int height = input.getHeight();
        int side = Math.min(width, height);
        int left = Math.max(0, (width - side) / 2);
        int top = Math.max(0, (height - side) / 2);
        Bitmap cropped = Bitmap.createBitmap(input, left, top, side, side);
        if (side == target) return cropped;
        Bitmap scaled = Bitmap.createScaledBitmap(cropped, target, target, true);
        if (scaled != cropped) cropped.recycle();
        return scaled;
    }

    private static void saveJpeg(File file, Bitmap bitmap) {
        if (file == null || bitmap == null) return;
        File temp = new File(file.getParentFile(), file.getName() + ".tmp");
        try (OutputStream output = new BufferedOutputStream(new FileOutputStream(temp, false))) {
            if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 90, output)) return;
            output.flush();
            if (file.exists()) file.delete();
            if (!temp.renameTo(file)) {
                try (InputStream input = new FileInputStream(temp);
                     OutputStream fallback = new FileOutputStream(file, false)) {
                    byte[] buffer = new byte[32 * 1024];
                    int read;
                    while ((read = input.read(buffer)) >= 0) {
                        if (read > 0) fallback.write(buffer, 0, read);
                    }
                }
            }
        } catch (Exception ignored) {
        } finally {
            if (temp.exists()) temp.delete();
        }
    }

    private static File cacheDirectory(Context context) {
        File directory = new File(context.getFilesDir(), "playback_artwork_cache");
        if (!directory.exists()) directory.mkdirs();
        return directory;
    }

    private static void prune(File directory) {
        File[] files = directory == null ? null : directory.listFiles();
        if (files == null || files.length == 0) return;
        List<File> list = new ArrayList<>();
        long total = 0L;
        for (File file : files) {
            if (!file.isFile() || !file.getName().endsWith(".jpg")) continue;
            list.add(file);
            total += Math.max(0L, file.length());
        }
        Collections.sort(list, Comparator.comparingLong(File::lastModified));
        int index = 0;
        while ((list.size() - index > MAX_CACHE_FILES || total > MAX_CACHE_BYTES)
            && index < list.size()) {
            File file = list.get(index++);
            long length = Math.max(0L, file.length());
            if (file.delete()) total -= length;
        }
    }

    static int averageColor(Bitmap bitmap) {
        if (bitmap == null || bitmap.getWidth() <= 0 || bitmap.getHeight() <= 0) return 0;
        int width = bitmap.getWidth();
        int height = bitmap.getHeight();
        long red = 0L;
        long green = 0L;
        long blue = 0L;
        int count = 0;
        int stepX = Math.max(1, width / 24);
        int stepY = Math.max(1, height / 24);
        for (int y = stepY / 2; y < height; y += stepY) {
            for (int x = stepX / 2; x < width; x += stepX) {
                int color = bitmap.getPixel(x, y);
                red += (color >> 16) & 0xff;
                green += (color >> 8) & 0xff;
                blue += color & 0xff;
                count++;
            }
        }
        if (count == 0) return 0;
        return 0xff000000
            | ((int) (red / count) << 16)
            | ((int) (green / count) << 8)
            | (int) (blue / count);
    }

    private static String sha256(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] bytes = digest.digest(safe(value).getBytes("UTF-8"));
            StringBuilder builder = new StringBuilder();
            for (byte item : bytes) builder.append(String.format(Locale.ROOT, "%02x", item));
            return builder.toString();
        } catch (Exception ignored) {
            return Integer.toHexString(safe(value).hashCode());
        }
    }

    private static String safe(String value) {
        return value == null ? "" : value;
    }
}
