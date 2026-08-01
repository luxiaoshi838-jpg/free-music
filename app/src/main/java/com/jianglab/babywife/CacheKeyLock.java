package com.jianglab.babywife;

import android.content.Context;

import java.io.File;
import java.io.RandomAccessFile;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;

/** Cross-process lock for one managed cache key; different songs remain concurrent. */
final class CacheKeyLock implements AutoCloseable {
    private final RandomAccessFile file;
    private final FileChannel channel;
    private final FileLock lock;

    private CacheKeyLock(RandomAccessFile file, FileChannel channel, FileLock lock) {
        this.file = file;
        this.channel = channel;
        this.lock = lock;
    }

    static CacheKeyLock acquire(Context context, String key) throws Exception {
        File root = new File(context.getFilesDir(), "network_cache_locks");
        if (!root.exists() && !root.mkdirs()) {
            throw new IllegalStateException("无法创建歌曲缓存锁目录");
        }
        File lockFile = new File(root, key + ".lock");
        RandomAccessFile random = new RandomAccessFile(lockFile, "rw");
        FileChannel channel = random.getChannel();
        long deadline = System.currentTimeMillis() + 120000L;
        while (true) {
            if (Thread.currentThread().isInterrupted()) {
                channel.close();
                random.close();
                throw new InterruptedException("歌曲缓存任务已暂停");
            }
            try {
                FileLock lock = channel.tryLock();
                if (lock != null) return new CacheKeyLock(random, channel, lock);
            } catch (OverlappingFileLockException ignored) {
            }
            if (System.currentTimeMillis() >= deadline) {
                channel.close();
                random.close();
                throw new IllegalStateException("等待同一歌曲缓存任务超时");
            }
            Thread.sleep(120L);
        }
    }

    @Override
    public void close() {
        try { if (lock != null && lock.isValid()) lock.release(); } catch (Exception ignored) { }
        try { if (channel != null && channel.isOpen()) channel.close(); } catch (Exception ignored) { }
        try { if (file != null) file.close(); } catch (Exception ignored) { }
    }
}
