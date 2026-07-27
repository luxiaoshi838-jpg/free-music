package com.jianglab.babywife;

import com.arthenica.ffmpegkit.FFmpegKit;
import com.arthenica.ffmpegkit.FFmpegSession;
import com.arthenica.ffmpegkit.ReturnCode;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;

/** Ensures every managed network-audio cache is a real MP3, not a renamed source file. */
final class AudioTranscoder {
    private AudioTranscoder() {
    }

    static boolean isMp3(File file) {
        if (file == null || !file.isFile() || file.length() < 4) return false;
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            byte[] header = new byte[10];
            int count = input.read(header);
            if (count >= 3 && header[0] == 'I' && header[1] == 'D' && header[2] == '3') return true;
            if (count >= 2) {
                int first = header[0] & 0xff;
                int second = header[1] & 0xff;
                return first == 0xff && (second & 0xe0) == 0xe0 && (second & 0x18) != 0x08 && (second & 0x06) != 0;
            }
        } catch (Exception ignored) {
        }
        return false;
    }

    static File ensureMp3(File source, File target) throws Exception {
        if (source == null || !source.isFile() || source.length() <= 0) {
            throw new IllegalArgumentException("待转换歌曲文件无效");
        }
        if (target == null) throw new IllegalArgumentException("MP3 输出文件无效");
        File parent = target.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IllegalStateException("无法创建 MP3 转码目录");
        }
        if (target.exists() && !target.delete()) throw new IllegalStateException("无法替换旧 MP3 临时文件");

        if (isMp3(source)) {
            copyOrMove(source, target);
        } else {
            FFmpegSession session = FFmpegKit.executeWithArguments(new String[] {
                "-y", "-hide_banner", "-loglevel", "error",
                "-i", source.getAbsolutePath(),
                "-map", "0:a:0", "-vn", "-map_metadata", "-1",
                "-ac", "2", "-ar", "44100",
                "-c:a", "libmp3lame", "-b:a", "192k",
                target.getAbsolutePath()
            });
            if (!ReturnCode.isSuccess(session.getReturnCode())) {
                target.delete();
                String details = session.getAllLogsAsString();
                if (details == null || details.trim().isEmpty()) details = "FFmpeg 返回码 " + session.getReturnCode();
                throw new IllegalStateException("音频转为 MP3 失败：" + compact(details));
            }
        }
        if (!isMp3(target) || target.length() <= 0) {
            target.delete();
            throw new IllegalStateException("转码结果不是真实 MP3");
        }
        return target;
    }

    private static void copyOrMove(File source, File target) throws Exception {
        if (source.renameTo(target)) return;
        try (InputStream input = new BufferedInputStream(new FileInputStream(source));
             java.io.OutputStream output = new java.io.BufferedOutputStream(new java.io.FileOutputStream(target))) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) if (count > 0) output.write(buffer, 0, count);
        }
    }

    private static String compact(String text) {
        String value = text == null ? "" : text.replaceAll("\\s+", " ").trim();
        return value.length() > 240 ? value.substring(0, 240) : value;
    }
}
