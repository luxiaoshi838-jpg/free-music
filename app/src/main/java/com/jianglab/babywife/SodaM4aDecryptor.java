package com.jianglab.babywife;

import android.util.Base64;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Decrypts Soda Music CENC M4A downloads using the PlayAuth carried in the
 * resolved URL. Algorithm ported from music-lib/soda DecryptAudio (AGPL-3.0).
 */
final class SodaM4aDecryptor {
    private static final long MAX_MOOV_BYTES = 32L * 1024L * 1024L;

    private SodaM4aDecryptor() {
    }

    static boolean isEncryptedM4a(File file) {
        if (file == null || !file.isFile() || file.length() < 16) return false;
        try (RandomAccessFile input = new RandomAccessFile(file, "r")) {
            Box moov = findFileBox(input, "moov", 0L, input.length());
            if (moov == null || moov.size > MAX_MOOV_BYTES) return false;
            byte[] data = readBox(input, moov);
            return indexOf(data, ascii("enca"), 0, data.length) >= 0
                && indexOf(data, ascii("senc"), 0, data.length) >= 0
                && indexOf(data, ascii("cenc"), 0, data.length) >= 0;
        } catch (Exception ignored) {
            return false;
        }
    }

    static void decrypt(File encrypted, File output, String playAuth) throws Exception {
        if (encrypted == null || !encrypted.isFile() || encrypted.length() <= 0) {
            throw new IllegalArgumentException("加密 M4A 文件无效");
        }
        if (output == null) throw new IllegalArgumentException("解密输出文件无效");
        byte[] key = extractKey(playAuth);
        copyFile(encrypted, output);

        try (RandomAccessFile file = new RandomAccessFile(output, "rw")) {
            Box moov = findFileBox(file, "moov", 0L, file.length());
            Box mdat = findFileBox(file, "mdat", 0L, file.length());
            if (moov == null) throw new IllegalStateException("加密 M4A 缺少 moov");
            if (mdat == null) throw new IllegalStateException("加密 M4A 缺少 mdat");
            if (moov.size > MAX_MOOV_BYTES || moov.size > Integer.MAX_VALUE) {
                throw new IllegalStateException("M4A 索引区过大");
            }

            byte[] moovData = readBox(file, moov);
            Box stbl = findDescendant(moovData, "stbl", moov.headerSize, moovData.length, 0);
            if (stbl == null) throw new IllegalStateException("加密 M4A 缺少 stbl");
            Box stsz = findDescendant(moovData, "stsz", stbl.contentStart(), stbl.end(), 0);
            Box senc = findDescendant(moovData, "senc", moov.headerSize, moovData.length, 0);
            Box stsd = findDescendant(moovData, "stsd", stbl.contentStart(), stbl.end(), 0);
            if (stsz == null) throw new IllegalStateException("加密 M4A 缺少 stsz");
            if (senc == null) throw new IllegalStateException("加密 M4A 缺少 senc");

            long[] sampleSizes = parseStsz(moovData, stsz);
            List<byte[]> ivs = parseSenc(moovData, senc);
            if (sampleSizes.length == 0 || ivs.isEmpty()) {
                throw new IllegalStateException("加密 M4A 样本索引为空");
            }

            long pointer = mdat.offset + mdat.headerSize;
            long payloadEnd = mdat.offset + mdat.size;
            long processed = 0L;
            for (int index = 0; index < sampleSizes.length; index++) {
                long sizeLong = sampleSizes[index];
                if (sizeLong < 0 || sizeLong > Integer.MAX_VALUE || pointer + sizeLong > payloadEnd) {
                    throw new IllegalStateException("加密 M4A 样本范围无效");
                }
                int size = (int) sizeLong;
                byte[] sample = new byte[size];
                file.seek(pointer);
                file.readFully(sample);
                if (index < ivs.size()) {
                    byte[] iv = new byte[16];
                    byte[] sourceIv = ivs.get(index);
                    System.arraycopy(sourceIv, 0, iv, 0, Math.min(sourceIv.length, iv.length));
                    Cipher cipher = Cipher.getInstance("AES/CTR/NoPadding");
                    cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(key, "AES"), new IvParameterSpec(iv));
                    byte[] decoded = cipher.doFinal(sample);
                    file.seek(pointer);
                    file.write(decoded);
                }
                pointer += sizeLong;
                processed += sizeLong;
            }
            if (processed != mdat.size - mdat.headerSize) {
                throw new IllegalStateException("加密 M4A 解密长度不一致");
            }

            if (stsd != null) {
                int enca = indexOf(moovData, ascii("enca"), stsd.offset, stsd.end());
                if (enca >= 0) {
                    file.seek(moov.offset + enca);
                    file.write(ascii("mp4a"));
                }
            }
        } catch (Exception error) {
            output.delete();
            throw error;
        }
        if (isEncryptedM4a(output)) {
            output.delete();
            throw new IllegalStateException("M4A 解密后仍包含加密标记");
        }
    }

    private static byte[] extractKey(String playAuth) throws Exception {
        if (playAuth == null || playAuth.trim().isEmpty()) {
            throw new IllegalStateException("汽水音乐缺少 PlayAuth，无法解密 M4A");
        }
        byte[] encoded = Base64.decode(playAuth.trim(), Base64.DEFAULT);
        if (encoded.length < 3) throw new IllegalStateException("PlayAuth 数据过短");
        int paddingLength = ((((encoded[0] & 0xff) ^ (encoded[1] & 0xff)
            ^ (encoded[2] & 0xff)) - 48) & 0xff);
        if (encoded.length < paddingLength + 2) {
            throw new IllegalStateException("PlayAuth 填充长度无效");
        }
        byte[] inner = new byte[encoded.length - paddingLength - 1];
        System.arraycopy(encoded, 1, inner, 0, inner.length);
        byte[] decoded = decryptSpadeInner(inner);
        if (decoded.length == 0) throw new IllegalStateException("PlayAuth 解码失败");
        int skip = decodeBase36(decoded[0]);
        int end = 1 + (encoded.length - paddingLength - 2) - skip;
        if (skip == 0xff || end <= 1 || end > decoded.length) {
            throw new IllegalStateException("PlayAuth 密钥范围无效");
        }
        String hex = new String(decoded, 1, end - 1, StandardCharsets.US_ASCII);
        if ((hex.length() & 1) != 0) throw new IllegalStateException("PlayAuth 密钥长度无效");
        byte[] key = new byte[hex.length() / 2];
        for (int i = 0; i < key.length; i++) {
            int high = Character.digit(hex.charAt(i * 2), 16);
            int low = Character.digit(hex.charAt(i * 2 + 1), 16);
            if (high < 0 || low < 0) throw new IllegalStateException("PlayAuth 密钥不是十六进制");
            key[i] = (byte) ((high << 4) | low);
        }
        if (key.length != 16 && key.length != 24 && key.length != 32) {
            throw new IllegalStateException("PlayAuth AES 密钥长度无效");
        }
        return key;
    }

    private static byte[] decryptSpadeInner(byte[] input) {
        byte[] result = new byte[input.length];
        byte[] buffer = new byte[input.length + 2];
        buffer[0] = (byte) 0xfa;
        buffer[1] = 0x55;
        System.arraycopy(input, 0, buffer, 2, input.length);
        for (int i = 0; i < result.length; i++) {
            int value = ((input[i] & 0xff) ^ (buffer[i] & 0xff)) - Integer.bitCount(i) - 21;
            while (value < 0) value += 255;
            result[i] = (byte) value;
        }
        return result;
    }

    private static int decodeBase36(byte value) {
        int c = value & 0xff;
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'z') return c - 'a' + 10;
        return 0xff;
    }

    private static long[] parseStsz(byte[] data, Box box) {
        int start = box.contentStart();
        if (start + 12 > box.end()) return new long[0];
        long fixed = uint32(data, start + 4);
        long countLong = uint32(data, start + 8);
        if (countLong > 1_000_000L) throw new IllegalStateException("M4A 样本数量异常");
        int count = (int) countLong;
        long[] sizes = new long[count];
        if (fixed != 0L) {
            for (int i = 0; i < count; i++) sizes[i] = fixed;
        } else {
            int pointer = start + 12;
            for (int i = 0; i < count; i++) {
                if (pointer + 4 > box.end()) throw new IllegalStateException("stsz 数据不完整");
                sizes[i] = uint32(data, pointer);
                pointer += 4;
            }
        }
        return sizes;
    }

    private static List<byte[]> parseSenc(byte[] data, Box box) {
        List<byte[]> ivs = new ArrayList<>();
        int start = box.contentStart();
        if (start + 8 > box.end()) return ivs;
        long flags = uint32(data, start) & 0x00ffffffL;
        long countLong = uint32(data, start + 4);
        if (countLong > 1_000_000L) throw new IllegalStateException("senc 样本数量异常");
        int pointer = start + 8;
        boolean subsamples = (flags & 0x02L) != 0L;
        for (int i = 0; i < (int) countLong; i++) {
            if (pointer + 8 > box.end()) throw new IllegalStateException("senc IV 数据不完整");
            byte[] iv = new byte[8];
            System.arraycopy(data, pointer, iv, 0, 8);
            ivs.add(iv);
            pointer += 8;
            if (subsamples) {
                if (pointer + 2 > box.end()) throw new IllegalStateException("senc 子样本数据不完整");
                int subCount = uint16(data, pointer);
                pointer += 2 + subCount * 6;
                if (pointer > box.end()) throw new IllegalStateException("senc 子样本范围无效");
            }
        }
        return ivs;
    }

    private static Box findFileBox(RandomAccessFile file, String wanted, long start, long end) throws Exception {
        long pointer = start;
        while (pointer + 8L <= end) {
            file.seek(pointer);
            long size = file.readInt() & 0xffffffffL;
            byte[] typeBytes = new byte[4];
            file.readFully(typeBytes);
            int header = 8;
            if (size == 1L) {
                size = file.readLong();
                header = 16;
            } else if (size == 0L) {
                size = end - pointer;
            }
            String type = new String(typeBytes, StandardCharsets.ISO_8859_1);
            if (size < header || pointer + size > end || size > Integer.MAX_VALUE) break;
            if (wanted.equals(type)) return new Box((int) pointer, (int) size, header, type);
            pointer += size;
        }
        return null;
    }

    private static Box findDescendant(byte[] data, String wanted, int start, int end, int depth) {
        if (depth > 8) return null;
        int pointer = Math.max(0, start);
        int safeEnd = Math.min(data.length, end);
        while (pointer + 8 <= safeEnd) {
            long sizeLong = uint32(data, pointer);
            int header = 8;
            if (sizeLong == 1L) {
                if (pointer + 16 > safeEnd) return null;
                sizeLong = uint64(data, pointer + 8);
                header = 16;
            } else if (sizeLong == 0L) {
                sizeLong = safeEnd - pointer;
            }
            if (sizeLong < header || sizeLong > Integer.MAX_VALUE || pointer + sizeLong > safeEnd) break;
            int size = (int) sizeLong;
            String type = new String(data, pointer + 4, 4, StandardCharsets.ISO_8859_1);
            Box box = new Box(pointer, size, header, type);
            if (wanted.equals(type)) return box;
            if (isContainer(type)) {
                Box nested = findDescendant(data, wanted, box.contentStart(), box.end(), depth + 1);
                if (nested != null) return nested;
            }
            pointer += size;
        }
        return null;
    }

    private static boolean isContainer(String type) {
        return "moov".equals(type) || "trak".equals(type) || "mdia".equals(type)
            || "minf".equals(type) || "stbl".equals(type) || "moof".equals(type)
            || "traf".equals(type) || "edts".equals(type) || "dinf".equals(type);
    }

    private static byte[] readBox(RandomAccessFile file, Box box) throws Exception {
        byte[] data = new byte[box.size];
        file.seek(box.offset);
        file.readFully(data);
        return data;
    }

    private static int indexOf(byte[] data, byte[] target, int start, int end) {
        int safeEnd = Math.min(data.length, end);
        for (int i = Math.max(0, start); i + target.length <= safeEnd; i++) {
            boolean match = true;
            for (int j = 0; j < target.length; j++) {
                if (data[i + j] != target[j]) { match = false; break; }
            }
            if (match) return i;
        }
        return -1;
    }

    private static byte[] ascii(String value) {
        return value.getBytes(StandardCharsets.ISO_8859_1);
    }

    private static int uint16(byte[] data, int offset) {
        return ((data[offset] & 0xff) << 8) | (data[offset + 1] & 0xff);
    }

    private static long uint32(byte[] data, int offset) {
        return ((long) (data[offset] & 0xff) << 24)
            | ((long) (data[offset + 1] & 0xff) << 16)
            | ((long) (data[offset + 2] & 0xff) << 8)
            | (long) (data[offset + 3] & 0xff);
    }

    private static long uint64(byte[] data, int offset) {
        return (uint32(data, offset) << 32) | uint32(data, offset + 4);
    }

    private static void copyFile(File source, File target) throws Exception {
        File parent = target.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IllegalStateException("无法创建 M4A 解密目录");
        }
        try (BufferedInputStream input = new BufferedInputStream(new FileInputStream(source));
             BufferedOutputStream output = new BufferedOutputStream(new FileOutputStream(target))) {
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                if (count > 0) output.write(buffer, 0, count);
            }
        }
    }

    private static final class Box {
        final int offset;
        final int size;
        final int headerSize;
        final String type;

        Box(int offset, int size, int headerSize, String type) {
            this.offset = offset;
            this.size = size;
            this.headerSize = headerSize;
            this.type = type;
        }

        int contentStart() { return offset + headerSize; }
        int end() { return offset + size; }
    }
}
