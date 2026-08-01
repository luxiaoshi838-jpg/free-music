package com.jianglab.babywife;

import android.content.Context;

import java.io.File;
import java.io.FileOutputStream;
import java.io.RandomAccessFile;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;

import bridge.Bridge;

/**
 * Serializes access to the native catalog bridge across app processes.
 * Manual searches publish a shared lease before waiting for the bridge lock,
 * so automatic replacement and batch-cache searches yield after their current
 * native call and cannot race the next manual request.
 */
final class SearchPriorityCoordinator {
    private static final String FOLDER = "catalog_search_priority";
    private static final String MANUAL_LEASE = "manual_search.lease";
    private static final String BRIDGE_LOCK = "bridge_search.lock";
    private static final long LEASE_VALID_MS = 12000L;
    private static final long LEASE_REFRESH_MS = 1000L;
    private static final Object LOCAL_GUARD = new Object();
    private static final AtomicInteger LOCAL_MANUAL_COUNT = new AtomicInteger(0);
    private static volatile boolean refresherRunning;

    private SearchPriorityCoordinator() {
    }

    static String searchManual(Context context, String source, String keyword) throws Exception {
        try (ManualLease ignored = beginManual(context)) {
            return callBridge(context, true, source, keyword);
        }
    }

    static String searchAutomatic(Context context, String source, String keyword) throws Exception {
        return callBridge(context, false, source, keyword);
    }

    private static String callBridge(Context context, boolean manual,
                                     String source, String keyword) throws Exception {
        Context app = context == null ? null : context.getApplicationContext();
        while (true) {
            checkInterrupted();
            if (!manual) awaitManualIdle(app);
            File lockFile = bridgeLockFile(app);
            try (RandomAccessFile randomAccess = new RandomAccessFile(lockFile, "rw");
                 FileChannel channel = randomAccess.getChannel();
                 FileLock lock = channel.lock()) {
                checkInterrupted();
                if (!manual && manualActive(app)) continue;
                try {
                    return Bridge.search(source, keyword);
                } catch (Throwable error) {
                    if (error instanceof InterruptedException) throw (InterruptedException) error;
                    throw new IllegalStateException("歌曲目录搜索异常："
                        + error.getClass().getSimpleName() + safeMessage(error), error);
                }
            }
        }
    }

    private static ManualLease beginManual(Context context) {
        Context app = context == null ? null : context.getApplicationContext();
        synchronized (LOCAL_GUARD) {
            LOCAL_MANUAL_COUNT.incrementAndGet();
            touchManualLease(app);
            startRefresher(app);
        }
        return new ManualLease(app);
    }

    private static void awaitManualIdle(Context context) throws InterruptedException {
        while (manualActive(context)) {
            checkInterrupted();
            Thread.sleep(100L);
        }
    }

    private static boolean manualActive(Context context) {
        File lease = manualLeaseFile(context);
        if (!lease.isFile()) return false;
        long age = System.currentTimeMillis() - lease.lastModified();
        if (age >= 0L && age <= LEASE_VALID_MS) return true;
        if (!lease.delete()) lease.deleteOnExit();
        return false;
    }

    private static void touchManualLease(Context context) {
        try {
            File lease = manualLeaseFile(context);
            try (FileOutputStream output = new FileOutputStream(lease, false)) {
                output.write(String.valueOf(System.currentTimeMillis())
                    .getBytes(StandardCharsets.UTF_8));
                output.flush();
            }
        } catch (Exception ignored) {
        }
    }

    private static void startRefresher(Context context) {
        if (refresherRunning) return;
        refresherRunning = true;
        Thread thread = new Thread(() -> {
            try {
                while (true) {
                    synchronized (LOCAL_GUARD) {
                        if (LOCAL_MANUAL_COUNT.get() <= 0) break;
                        touchManualLease(context);
                    }
                    Thread.sleep(LEASE_REFRESH_MS);
                }
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            } finally {
                synchronized (LOCAL_GUARD) {
                    refresherRunning = false;
                    if (LOCAL_MANUAL_COUNT.get() > 0) startRefresher(context);
                }
            }
        }, "ManualSearchPriorityLease");
        thread.setDaemon(true);
        thread.start();
    }

    private static File root(Context context) {
        File base = context == null
            ? new File(System.getProperty("java.io.tmpdir", "."), "babywife_search_priority")
            : new File(context.getFilesDir(), FOLDER);
        if (!base.exists()) base.mkdirs();
        return base;
    }

    private static File manualLeaseFile(Context context) {
        return new File(root(context), MANUAL_LEASE);
    }

    private static File bridgeLockFile(Context context) {
        return new File(root(context), BRIDGE_LOCK);
    }

    private static void checkInterrupted() throws InterruptedException {
        if (Thread.currentThread().isInterrupted()) {
            throw new InterruptedException("歌曲搜索已取消");
        }
    }

    private static String safeMessage(Throwable error) {
        String message = error == null ? "" : error.getMessage();
        return message == null || message.trim().isEmpty() ? "" : "：" + message.trim();
    }

    private static final class ManualLease implements AutoCloseable {
        private final Context context;
        private boolean closed;

        ManualLease(Context context) {
            this.context = context;
        }

        @Override
        public void close() {
            synchronized (LOCAL_GUARD) {
                if (closed) return;
                closed = true;
                int remaining = LOCAL_MANUAL_COUNT.decrementAndGet();
                if (remaining <= 0) {
                    LOCAL_MANUAL_COUNT.set(0);
                    File lease = manualLeaseFile(context);
                    if (lease.isFile() && !lease.delete()) lease.deleteOnExit();
                }
            }
        }
    }
}
