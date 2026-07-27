package com.jianglab.babywife;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;

/** Keeps managed network-audio cache lightweight: accept only real MP3 files. */
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

        if (!isMp3(source)) {
            throw new IllegalStateException("解析到的音频不是 MP3，轻量版不内置转码");
        }
        copyOrMove(source, target);
        if (!isMp3(target) || target.length() <= 0) {
            target.delete();
            throw new IllegalStateException("缓存结果不是真实 MP3");
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
}
