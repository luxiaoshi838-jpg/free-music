package com.jianglab.babywife;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/** Writes standard ID3v2.3 title/artist/album tags to downloaded MP3 files. */
final class AudioMetadataWriter {
    private AudioMetadataWriter() {
    }

    static void apply(File file, String extension, String title, String artist, String album) throws Exception {
        if (file == null || !file.isFile() || file.length() <= 0) return;
        if (!"mp3".equalsIgnoreCase(extension)) return;
        writeId3v23(file, title, artist, album);
    }

    static void applyAndVerify(File file, String title, String artist, String album) throws Exception {
        String safeTitle = required(title, "未知歌曲");
        String safeArtist = required(artist, "未知歌手");
        String safeAlbum = required(album, "未知专辑");
        apply(file, "mp3", safeTitle, safeArtist, safeAlbum);
        Map<String, String> frames = readTextFrames(file);
        if (!safeTitle.equals(frames.get("TIT2"))
            || !safeArtist.equals(frames.get("TPE1"))
            || !safeAlbum.equals(frames.get("TALB"))) {
            throw new IllegalStateException("MP3 歌曲信息写入校验失败");
        }
    }

    private static void writeId3v23(File source, String title, String artist, String album) throws Exception {
        byte[] tag = buildTag(title, artist, album);
        if (tag.length <= 10) return;

        long skip = existingTagLength(source);
        File parent = source.getParentFile();
        File temp = new File(parent, source.getName() + ".tagging");
        try (OutputStream output = new BufferedOutputStream(new FileOutputStream(temp));
             InputStream input = new BufferedInputStream(new FileInputStream(source))) {
            output.write(tag);
            long remaining = skip;
            while (remaining > 0) {
                long skipped = input.skip(remaining);
                if (skipped <= 0) {
                    if (input.read() < 0) break;
                    skipped = 1;
                }
                remaining -= skipped;
            }
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                if (count > 0) output.write(buffer, 0, count);
            }
        }

        if (source.exists() && !source.delete()) {
            temp.delete();
            throw new IllegalStateException("无法更新歌曲信息标签");
        }
        if (!temp.renameTo(source)) {
            try (InputStream input = new FileInputStream(temp);
                 OutputStream output = new FileOutputStream(source)) {
                byte[] buffer = new byte[64 * 1024];
                int count;
                while ((count = input.read(buffer)) >= 0) {
                    if (count > 0) output.write(buffer, 0, count);
                }
            }
            temp.delete();
        }
    }

    private static byte[] buildTag(String title, String artist, String album) throws Exception {
        ByteArrayOutputStream frames = new ByteArrayOutputStream();
        writeTextFrame(frames, "TIT2", title);
        writeTextFrame(frames, "TPE1", artist);
        writeTextFrame(frames, "TALB", album);
        byte[] body = frames.toByteArray();

        ByteArrayOutputStream tag = new ByteArrayOutputStream();
        tag.write('I');
        tag.write('D');
        tag.write('3');
        tag.write(3);
        tag.write(0);
        tag.write(0);
        writeSynchsafe(tag, body.length);
        tag.write(body);
        return tag.toByteArray();
    }

    private static void writeTextFrame(ByteArrayOutputStream output, String id, String value) throws Exception {
        String safe = value == null ? "" : value.trim();
        if (safe.isEmpty()) return;
        byte[] text = safe.getBytes(StandardCharsets.UTF_16);
        int bodySize = 1 + text.length;
        output.write(id.getBytes(StandardCharsets.ISO_8859_1));
        writeInt32(output, bodySize);
        output.write(0);
        output.write(0);
        output.write(1);
        output.write(text);
    }

    private static long existingTagLength(File file) {
        try (InputStream input = new FileInputStream(file)) {
            byte[] header = new byte[10];
            int count = input.read(header);
            if (count != 10 || header[0] != 'I' || header[1] != 'D' || header[2] != '3') return 0L;
            int size = ((header[6] & 0x7f) << 21)
                | ((header[7] & 0x7f) << 14)
                | ((header[8] & 0x7f) << 7)
                | (header[9] & 0x7f);
            long total = 10L + size;
            if ((header[5] & 0x10) != 0) total += 10L;
            return Math.min(total, file.length());
        } catch (Exception ignored) {
            return 0L;
        }
    }

    private static Map<String, String> readTextFrames(File file) throws Exception {
        Map<String, String> result = new HashMap<>();
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            byte[] header = new byte[10];
            if (input.read(header) != 10 || header[0] != 'I' || header[1] != 'D' || header[2] != '3') return result;
            int size = ((header[6] & 0x7f) << 21) | ((header[7] & 0x7f) << 14)
                | ((header[8] & 0x7f) << 7) | (header[9] & 0x7f);
            if (size <= 0 || size > 1024 * 1024) return result;
            byte[] body = new byte[size];
            int offset = 0;
            while (offset < body.length) {
                int count = input.read(body, offset, body.length - offset);
                if (count < 0) break;
                offset += count;
            }
            int position = 0;
            while (position + 10 <= offset) {
                String id = new String(body, position, 4, StandardCharsets.ISO_8859_1);
                int frameSize = ((body[position + 4] & 0xff) << 24) | ((body[position + 5] & 0xff) << 16)
                    | ((body[position + 6] & 0xff) << 8) | (body[position + 7] & 0xff);
                if (frameSize <= 0 || position + 10 + frameSize > offset) break;
                if (("TIT2".equals(id) || "TPE1".equals(id) || "TALB".equals(id)) && frameSize > 1) {
                    int encoding = body[position + 10] & 0xff;
                    java.nio.charset.Charset charset = encoding == 1 ? StandardCharsets.UTF_16
                        : encoding == 3 ? StandardCharsets.UTF_8 : StandardCharsets.ISO_8859_1;
                    String value = new String(body, position + 11, frameSize - 1, charset)
                        .replace("\u0000", "").trim();
                    result.put(id, value);
                }
                position += 10 + frameSize;
            }
        }
        return result;
    }

    private static String required(String value, String fallback) {
        String safe = value == null ? "" : value.trim();
        return safe.isEmpty() ? fallback : safe;
    }

    private static void writeSynchsafe(ByteArrayOutputStream output, int value) {
        output.write((value >> 21) & 0x7f);
        output.write((value >> 14) & 0x7f);
        output.write((value >> 7) & 0x7f);
        output.write(value & 0x7f);
    }

    private static void writeInt32(ByteArrayOutputStream output, int value) {
        output.write((value >> 24) & 0xff);
        output.write((value >> 16) & 0xff);
        output.write((value >> 8) & 0xff);
        output.write(value & 0xff);
    }
}
