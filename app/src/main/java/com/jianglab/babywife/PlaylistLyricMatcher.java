package com.jianglab.babywife;

import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import bridge.Bridge;

/** Resolves lyrics from the selected catalog first, then exact cross-platform alternatives. */
final class PlaylistLyricMatcher {
    private static final String TAG = "BabywifeLyrics";
    private static final List<String> SOURCES = Arrays.asList(
        "netease", "qq", "kugou", "kuwo", "migu", "soda",
        "bilibili", "fivesing", "qianqian", "jamendo", "joox", "apple"
    );

    interface Callback {
        void onMatched(String lyric, String label);
        void onUnavailable();
    }

    private PlaylistLyricMatcher() {
    }

    static void matchAsync(String title, String artist, String catalogJson, Callback callback) {
        new Thread(() -> {
            Match result = find(title, artist, catalogJson);
            if (result == null) {
                Log.w(TAG, "all lyric sources unavailable title=" + safe(title) + " artist=" + safe(artist));
                if (callback != null) callback.onUnavailable();
            } else if (callback != null) {
                callback.onMatched(result.lyric, result.label);
            }
        }, "playlist-lyric-matcher").start();
    }

    static String fetchExactLyric(String catalogJson) {
        FetchResult result = fetchLyric(catalogJson);
        return result.lyric;
    }

    private static Match find(String title, String artist, String catalogJson) {
        String safeTitle = safe(title);
        String safeArtist = safe(artist);
        if (safeTitle.isEmpty()) return null;

        Set<String> attempted = new HashSet<>();
        Match original = tryCatalog(catalogJson, safeTitle, safeArtist, attempted, "selected");
        if (original != null) return original;

        if (catalogJson != null && !catalogJson.trim().isEmpty()) {
            List<CatalogSearch.Track> alternatives = CatalogSearch.findExactAlternatives(catalogJson);
            for (CatalogSearch.Track track : alternatives) {
                Match candidate = tryCatalog(track.rawJson, track.title, track.artist, attempted, track.sourceCode);
                if (candidate != null) return candidate;
            }
        }

        String keyword = (safeTitle + " " + safeArtist).trim();
        for (String source : orderedSources(catalogJson)) {
            try {
                JSONObject response = new JSONObject(Bridge.search(source, keyword));
                if (!response.optBoolean("ok", false)) {
                    Log.w(TAG, "search failed source=" + source + " error=" + response.optString("error", "unknown"));
                    continue;
                }
                JSONArray data = response.optJSONArray("data");
                if (data == null) continue;
                int accepted = 0;
                for (int i = 0; i < data.length() && accepted < 8; i++) {
                    JSONObject item = data.optJSONObject(i);
                    if (item == null) continue;
                    item.put("source", source);
                    String candidateTitle = item.optString("name", "");
                    String candidateArtist = artistText(item.opt("artist"));
                    if (!sameSong(safeTitle, safeArtist, candidateTitle, candidateArtist)) continue;
                    accepted++;
                    Match candidate = tryCatalog(item.toString(), candidateTitle, candidateArtist, attempted, source);
                    if (candidate != null) return candidate;
                }
            } catch (Exception error) {
                Log.w(TAG, "search exception source=" + source + " message=" + error.getMessage());
            }
        }
        return null;
    }

    private static Match tryCatalog(String catalogJson, String title, String artist,
                                    Set<String> attempted, String sourceHint) {
        if (catalogJson == null || catalogJson.trim().isEmpty()) return null;
        String key = catalogKey(catalogJson);
        if (!attempted.add(key)) return null;
        FetchResult result = fetchLyric(catalogJson);
        if (result.lyric.isEmpty()) {
            Log.w(TAG, "lyric unavailable source=" + sourceHint + " key=" + key + " error=" + result.error);
            return null;
        }
        String sourceLabel = sourceHint;
        try {
            JSONObject catalog = new JSONObject(catalogJson);
            sourceLabel = CatalogSearch.labelForSource(catalog.optString("source", sourceHint));
        } catch (Exception ignored) {
        }
        Log.i(TAG, "lyric matched source=" + sourceLabel + " key=" + key + " chars=" + result.lyric.length());
        return new Match(result.lyric, safe(title) + " · " + safe(artist) + " · " + sourceLabel);
    }

    private static FetchResult fetchLyric(String catalogJson) {
        try {
            JSONObject response = new JSONObject(Bridge.lyrics(catalogJson));
            if (!response.optBoolean("ok", false)) {
                return new FetchResult("", response.optString("error", "lyrics unavailable"));
            }
            Object value = response.opt("data");
            if (value instanceof String) {
                return new FetchResult(((String) value).trim(), "");
            }
            if (value instanceof JSONObject) {
                JSONObject object = (JSONObject) value;
                String lyric = firstNonEmpty(
                    object.optString("lyric", ""),
                    object.optString("lrc", ""),
                    object.optString("text", "")
                );
                return new FetchResult(lyric, lyric.isEmpty() ? "lyric payload empty" : "");
            }
            return new FetchResult("", "unexpected lyric payload");
        } catch (Exception error) {
            return new FetchResult("", error.getClass().getSimpleName() + ": " + error.getMessage());
        }
    }

    private static List<String> orderedSources(String catalogJson) {
        List<String> ordered = new ArrayList<>();
        try {
            String selected = new JSONObject(catalogJson == null ? "{}" : catalogJson)
                .optString("source", "").trim().toLowerCase(Locale.ROOT);
            if (!selected.isEmpty()) ordered.add(selected);
        } catch (Exception ignored) {
        }
        for (String source : SOURCES) if (!ordered.contains(source)) ordered.add(source);
        return ordered;
    }

    private static String catalogKey(String raw) {
        try {
            JSONObject object = new JSONObject(raw);
            return object.optString("source", "") + "|" + object.optString("id", "");
        } catch (Exception ignored) {
            return Integer.toHexString(raw.hashCode());
        }
    }

    private static boolean sameSong(String wantedTitle, String wantedArtist, String title, String artist) {
        String leftTitle = normalizeTitle(wantedTitle);
        String rightTitle = normalizeTitle(title);
        if (leftTitle.isEmpty() || rightTitle.isEmpty()) return false;
        if (!(leftTitle.equals(rightTitle) || leftTitle.contains(rightTitle) || rightTitle.contains(leftTitle))) {
            return false;
        }
        String leftArtist = normalizeArtist(wantedArtist);
        String rightArtist = normalizeArtist(artist);
        if (leftArtist.isEmpty() || rightArtist.isEmpty()) return true;
        return leftArtist.equals(rightArtist)
            || leftArtist.contains(rightArtist)
            || rightArtist.contains(leftArtist);
    }

    private static String artistText(Object value) {
        if (value instanceof String) return ((String) value).trim();
        if (value instanceof JSONArray) {
            JSONArray array = (JSONArray) value;
            StringBuilder out = new StringBuilder();
            for (int i = 0; i < array.length(); i++) {
                String part = array.optString(i, "").trim();
                if (part.isEmpty()) continue;
                if (out.length() > 0) out.append('/');
                out.append(part);
            }
            return out.toString();
        }
        return value == null ? "" : String.valueOf(value).trim();
    }

    private static String normalizeTitle(String value) {
        return safe(value).toLowerCase(Locale.ROOT)
            .replaceAll("[（(【\\[].*?[）)】\\]]", "")
            .replaceAll("[\\s\\p{Punct}《》·•]", "")
            .trim();
    }

    private static String normalizeArtist(String value) {
        return safe(value).toLowerCase(Locale.ROOT)
            .replaceAll("[\\s\\p{Punct}/、&·•]", "")
            .trim();
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) if (value != null && !value.trim().isEmpty()) return value.trim();
        return "";
    }

    private static String safe(String value) {
        return value == null ? "" : value.trim();
    }

    private static final class FetchResult {
        final String lyric;
        final String error;

        FetchResult(String lyric, String error) {
            this.lyric = safe(lyric);
            this.error = safe(error);
        }
    }

    private static final class Match {
        final String lyric;
        final String label;

        Match(String lyric, String label) {
            this.lyric = lyric;
            this.label = label;
        }
    }
}
