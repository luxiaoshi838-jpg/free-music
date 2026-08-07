package com.jianglab.babywife;

import android.content.Context;
import android.net.Uri;
import android.provider.DocumentsContract;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.InputStream;

/** Reliable cache-file checks for file:// and Storage Access Framework content:// URIs. */
final class CacheFileState {
    private static final int READ_ATTEMPTS = 6;
    private static final long RETRY_DELAY_MS = 160L;

    private CacheFileState() {
    }

    static boolean exists(Context context, String uriText) {
        if (context == null || uriText == null || uriText.trim().isEmpty()) return false;
        Uri uri;
        try {
            uri = Uri.parse(uriText.trim());
        } catch (Exception ignored) {
            return false;
        }

        if ("file".equalsIgnoreCase(uri.getScheme())) {
            String path = uri.getPath();
            if (path == null || path.isEmpty()) return false;
            File file = new File(path);
            return file.isFile() && file.length() > 0;
        }
        if (!"content".equalsIgnoreCase(uri.getScheme())) return false;

        for (int attempt = 0; attempt < READ_ATTEMPTS; attempt++) {
            try (InputStream raw = context.getContentResolver().openInputStream(uri);
                 InputStream input = raw == null ? null : new BufferedInputStream(raw)) {
                if (input != null && input.read() >= 0) return true;
            } catch (Exception ignored) {
            }
            if (attempt + 1 < READ_ATTEMPTS) {
                try {
                    Thread.sleep(RETRY_DELAY_MS);
                } catch (InterruptedException interrupted) {
                    Thread.currentThread().interrupt();
                    return false;
                }
            }
        }
        return false;
    }

    static boolean deleteDirect(Context context, String uriText) {
        if (context == null || uriText == null || uriText.trim().isEmpty()) return false;
        try {
            Uri uri = Uri.parse(uriText.trim());
            if ("file".equalsIgnoreCase(uri.getScheme())) {
                String path = uri.getPath();
                return path != null && !path.isEmpty() && new File(path).delete();
            }
            if ("content".equalsIgnoreCase(uri.getScheme())) {
                return DocumentsContract.deleteDocument(context.getContentResolver(), uri);
            }
        } catch (Exception ignored) {
        }
        return false;
    }
}
