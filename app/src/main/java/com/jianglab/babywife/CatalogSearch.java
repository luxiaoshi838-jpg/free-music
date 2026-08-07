package com.jianglab.babywife;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import bridge.Bridge;

/**
 * Lightweight catalog-only search.
 *
 * Search requests return stable metadata only. Audio resolution, lyric loading,
 * and file caching are deliberately deferred until the user selects a track.
 */
final class CatalogSearch {
    private static final int DISPLAY_BATCH_SIZE = 16;
    private static final int PER_SOURCE_SLICE = 4;
    private static final int SOURCE_GROUP_SIZE = 6;

    private static final List<String> QUICK_SOURCES = Arrays.asList(
        "netease", "qq", "kugou", "soda", "kuwo", "migu"
    );
    private static final List<String> MORE_SOURCES = Arrays.asList(
        "soda", "bilibili", "fivesing", "qianqian", "jamendo", "joox", "apple"
    );
    private static final List<String> ALL_SOURCES = Arrays.asList(
        "netease", "qq", "kugou", "kuwo", "migu", "soda",
        "bilibili", "fivesing", "qianqian", "jamendo", "joox", "apple"
    );

    private CatalogSearch() {
    }

    static Session newSession(String keyword, String modeLabel) {
        return new Session(keyword, modeLabel, sourcesForMode(modeLabel));
    }

    static String labelForSource(String source) {
        if (source == null) return "未知平台";
        switch (source.toLowerCase(Locale.ROOT)) {
            case "netease": return "网易云";
            case "qq": return "QQ音乐";
            case "kugou": return "酷狗";
            case "kuwo": return "酷我";
            case "migu": return "咪咕";
            case "soda": return "汽水";
            case "bilibili": return "哔哩哔哩";
            case "fivesing": return "5sing";
            case "qianqian": return "千千";
            case "jamendo": return "Jamendo";
            case "joox": return "Joox";
            case "apple": return "Apple Music";
            default: return source;
        }
    }

    private static List<String> sourcesForMode(String modeLabel) {
        String mode = modeLabel == null ? "快速搜索" : modeLabel.trim();
        if (mode.contains("本地")) return Collections.emptyList();
        if (mode.contains("快速")) return new ArrayList<>(QUICK_SOURCES);
        if (mode.contains("全部")) return new ArrayList<>(ALL_SOURCES);
        if (mode.contains("更多")) return new ArrayList<>(MORE_SOURCES);
        if (mode.contains("网易")) return Collections.singletonList("netease");
        if (mode.contains("QQ")) return Collections.singletonList("qq");
        if (mode.contains("酷狗")) return Collections.singletonList("kugou");
        if (mode.contains("酷我")) return Collections.singletonList("kuwo");
        if (mode.contains("咪咕")) return Collections.singletonList("migu");
        if (mode.contains("汽水")) return Collections.singletonList("soda");
        if (mode.contains("哔哩") || mode.contains("B站")) return Collections.singletonList("bilibili");
        if (mode.toLowerCase(Locale.ROOT).contains("5sing")) return Collections.singletonList("fivesing");
        if (mode.contains("千千")) return Collections.singletonList("qianqian");
        if (mode.toLowerCase(Locale.ROOT).contains("jamendo")) return Collections.singletonList("jamendo");
        if (mode.toLowerCase(Locale.ROOT).contains("joox")) return Collections.singletonList("joox");
        if (mode.toLowerCase(Locale.ROOT).contains("apple")) return Collections.singletonList("apple");
        return new ArrayList<>(QUICK_SOURCES);
    }

    static final class Track {
        final String id;
        final String title;
        final String artist;
        final String album;
        final String sourceCode;
        final String sourceLabel;
        final String rawJson;

        Track(JSONObject object, String requestedSource) {
            String canonicalSource = requestedSource == null ? "" : requestedSource.trim().toLowerCase(Locale.ROOT);
            if (canonicalSource.isEmpty()) {
                canonicalSource = object.optString("source", "").trim().toLowerCase(Locale.ROOT);
            }
            try {
                object.put("source", canonicalSource);
            } catch (Exception ignored) {
            }
            this.id = object.optString("id", "").trim();
            this.title = safe(object.optString("name"), "未知歌曲");
            this.artist = safe(object.optString("artist"), "未知歌手");
            this.album = object.optString("album", "").trim();
            this.sourceCode = canonicalSource;
            this.sourceLabel = labelForSource(sourceCode);
            this.rawJson = object.toString();
        }

        String key() {
            return sourceCode + "|" + id;
        }
    }

    static final class Batch {
        final List<Track> tracks;
        final boolean hasMore;
        final List<String> attemptedSources;

        Batch(List<Track> tracks, boolean hasMore, List<String> attemptedSources) {
            this.tracks = tracks;
            this.hasMore = hasMore;
            this.attemptedSources = attemptedSources;
        }
    }

    static final class Session {
        private final String keyword;
        private final String modeLabel;
        private final List<String> sourceQueue;
        private final Map<String, List<Track>> sourceRows = new LinkedHashMap<>();
        private final Map<String, Integer> visibleOffsets = new HashMap<>();
        private final Set<String> emittedKeys = new HashSet<>();
        private int nextSourceIndex = 0;
        private boolean loading = false;

        Session(String keyword, String modeLabel, List<String> sourceQueue) {
            this.keyword = keyword == null ? "" : keyword.trim();
            this.modeLabel = modeLabel == null ? "快速搜索" : modeLabel;
            this.sourceQueue = sourceQueue;
        }

        synchronized boolean isLoading() {
            return loading;
        }

        synchronized boolean hasMore() {
            if (nextSourceIndex < sourceQueue.size()) return true;
            for (Map.Entry<String, List<Track>> entry : sourceRows.entrySet()) {
                int offset = visibleOffsets.containsKey(entry.getKey()) ? visibleOffsets.get(entry.getKey()) : 0;
                if (offset < entry.getValue().size()) return true;
            }
            return false;
        }

        Batch loadNext() {
            synchronized (this) {
                if (loading || keyword.isEmpty()) return new Batch(new ArrayList<>(), hasMore(), new ArrayList<>());
                loading = true;
            }
            try {
                List<Track> out = new ArrayList<>();
                List<String> attempted = new ArrayList<>();

                if (nextSourceIndex < sourceQueue.size()) {
                    int end = Math.min(sourceQueue.size(), nextSourceIndex + SOURCE_GROUP_SIZE);
                    List<String> group = new ArrayList<>(sourceQueue.subList(nextSourceIndex, end));
                    nextSourceIndex = end;
                    attempted.addAll(group);
                    loadSourceGroup(group);
                    appendVisibleSlices(out, group);
                } else {
                    appendVisibleSlices(out, new ArrayList<>(sourceRows.keySet()));
                }

                return new Batch(out, hasMore(), attempted);
            } finally {
                synchronized (this) {
                    loading = false;
                }
            }
        }

        String modeLabel() {
            return modeLabel;
        }

        private void loadSourceGroup(List<String> group) {
            if (group.isEmpty()) return;
            ExecutorService pool = Executors.newFixedThreadPool(Math.min(SOURCE_GROUP_SIZE, group.size()));
            try {
                Map<String, Future<List<Track>>> futures = new LinkedHashMap<>();
                for (String source : group) {
                    futures.put(source, pool.submit(new Callable<List<Track>>() {
                        @Override
                        public List<Track> call() {
                            return searchOneSource(source, keyword);
                        }
                    }));
                }
                for (Map.Entry<String, Future<List<Track>>> entry : futures.entrySet()) {
                    List<Track> rows = new ArrayList<>();
                    try {
                        rows = entry.getValue().get(15, TimeUnit.SECONDS);
                    } catch (Exception ignored) {
                    }
                    sourceRows.put(entry.getKey(), rows);
                    visibleOffsets.put(entry.getKey(), 0);
                }
            } finally {
                pool.shutdownNow();
            }
        }

        private void appendVisibleSlices(List<Track> out, List<String> sourceOrder) {
            while (out.size() < DISPLAY_BATCH_SIZE) {
                String bestSource = null;
                Track bestTrack = null;
                int bestScore = Integer.MIN_VALUE;

                for (String source : sourceOrder) {
                    List<Track> rows = sourceRows.get(source);
                    if (rows == null || rows.isEmpty()) continue;
                    int offset = visibleOffsets.containsKey(source) ? visibleOffsets.get(source) : 0;
                    while (offset < rows.size()) {
                        Track candidate = rows.get(offset);
                        if (candidate == null || candidate.id.isEmpty() || emittedKeys.contains(candidate.key())) {
                            offset++;
                            visibleOffsets.put(source, offset);
                            continue;
                        }
                        int candidateScore = score(candidate, keyword);
                        if (bestTrack == null || candidateScore > bestScore) {
                            bestSource = source;
                            bestTrack = candidate;
                            bestScore = candidateScore;
                        }
                        break;
                    }
                }

                if (bestTrack == null || bestSource == null) return;
                int offset = visibleOffsets.containsKey(bestSource) ? visibleOffsets.get(bestSource) : 0;
                visibleOffsets.put(bestSource, offset + 1);
                if (emittedKeys.add(bestTrack.key())) out.add(bestTrack);
            }
        }
    }

    static Track findBestExactOnSource(String source, String title, String artist) {
        String sourceCode = source == null ? "" : source.trim().toLowerCase(Locale.ROOT);
        if (sourceCode.isEmpty() || normalize(title).isEmpty()) return null;
        String keyword = isUnknownArtist(artist) ? title : title + " " + artist;
        List<Track> rows = searchOneSource(sourceCode, keyword);
        Track best = null;
        int bestScore = Integer.MIN_VALUE;
        for (Track track : rows) {
            int score = replacementScore(title, artist, track);
            if (best == null || score > bestScore) {
                best = track;
                bestScore = score;
            }
        }
        return bestScore >= 700 ? best : null;
    }

    private static List<Track> searchOneSource(String source, String keyword) {
        List<Track> rows = new ArrayList<>();
        try {
            JSONObject response = new JSONObject(Bridge.search(source, keyword));
            if (!response.optBoolean("ok", false)) return rows;
            JSONArray data = response.optJSONArray("data");
            if (data == null) return rows;
            for (int i = 0; i < data.length(); i++) {
                JSONObject object = data.optJSONObject(i);
                if (object == null) continue;
                Track track = new Track(object, source);
                if (!track.id.isEmpty() && !track.sourceCode.isEmpty()) rows.add(track);
            }
            sortByRelevance(rows, keyword);
        } catch (Exception ignored) {
        }
        return rows;
    }

    static List<Track> findExactAlternatives(String catalogJson) {
        List<Track> matches = new ArrayList<>();
        try {
            JSONObject selected = new JSONObject(catalogJson == null ? "{}" : catalogJson);
            String selectedSource = selected.optString("source", "").trim().toLowerCase(Locale.ROOT);
            String selectedTitle = selected.optString("name", "");
            String selectedArtist = selected.optString("artist", "");
            if (normalize(selectedTitle).isEmpty()) return matches;
            String searchKeyword = isUnknownArtist(selectedArtist)
                ? selectedTitle : selectedTitle + " " + selectedArtist;

            List<String> sources = new ArrayList<>(ALL_SOURCES);
            sources.remove(selectedSource);
            ExecutorService pool = Executors.newFixedThreadPool(4);
            try {
                Map<String, Future<List<Track>>> futures = new LinkedHashMap<>();
                for (String source : sources) {
                    futures.put(source, pool.submit(() -> searchOneSource(source, searchKeyword)));
                }
                for (String source : sources) {
                    Future<List<Track>> future = futures.get(source);
                    if (future == null) continue;
                    List<Track> rows;
                    try {
                        rows = future.get(12, TimeUnit.SECONDS);
                    } catch (Exception ignored) {
                        continue;
                    }
                    for (Track track : rows) {
                        if (replacementScore(selectedTitle, selectedArtist, track) >= 700) matches.add(track);
                    }
                }
            } finally {
                pool.shutdownNow();
            }
        } catch (Exception ignored) {
        }
        Collections.sort(matches, (left, right) ->
            replacementScore(selectedTitleSafe(catalogJson), selectedArtistSafe(catalogJson), right)
                - replacementScore(selectedTitleSafe(catalogJson), selectedArtistSafe(catalogJson), left));
        return matches;
    }

    private static String selectedTitleSafe(String catalogJson) {
        try { return new JSONObject(catalogJson == null ? "{}" : catalogJson).optString("name", ""); }
        catch (Exception ignored) { return ""; }
    }

    private static String selectedArtistSafe(String catalogJson) {
        try { return new JSONObject(catalogJson == null ? "{}" : catalogJson).optString("artist", ""); }
        catch (Exception ignored) { return ""; }
    }

    static int replacementScore(String title, String artist, Track candidate) {
        if (candidate == null) return 0;
        String wantedTitle = normalizeTitleForReplacement(title);
        String candidateTitle = normalizeTitleForReplacement(candidate.title);
        if (wantedTitle.isEmpty() || candidateTitle.isEmpty()) return 0;
        int score = 0;
        if (wantedTitle.equals(candidateTitle)) score += 1000;
        else if (wantedTitle.contains(candidateTitle) || candidateTitle.contains(wantedTitle)) {
            int shortLength = Math.min(wantedTitle.length(), candidateTitle.length());
            int longLength = Math.max(wantedTitle.length(), candidateTitle.length());
            score += 650 + (longLength == 0 ? 0 : shortLength * 250 / longLength);
        } else {
            score += titleOverlapScore(wantedTitle, candidateTitle);
        }
        String wantedArtist = artistSignature(artist);
        String candidateArtist = artistSignature(candidate.artist);
        if (!wantedArtist.isEmpty() && wantedArtist.equals(candidateArtist)) score += 650;
        else if (!wantedArtist.isEmpty() && !candidateArtist.isEmpty()
            && (wantedArtist.contains(candidateArtist) || candidateArtist.contains(wantedArtist))) score += 300;
        if (isUnknownArtist(artist) || isUnknownArtist(candidate.artist)) score += 80;
        return score;
    }

    private static int titleOverlapScore(String left, String right) {
        Set<String> leftPairs = characterPairs(left);
        Set<String> rightPairs = characterPairs(right);
        if (leftPairs.isEmpty() || rightPairs.isEmpty()) return 0;
        int common = 0;
        for (String pair : leftPairs) if (rightPairs.contains(pair)) common++;
        int denominator = Math.max(leftPairs.size(), rightPairs.size());
        return common * 700 / Math.max(1, denominator);
    }

    private static Set<String> characterPairs(String value) {
        Set<String> pairs = new HashSet<>();
        if (value == null) return pairs;
        if (value.length() == 1) { pairs.add(value); return pairs; }
        for (int i = 0; i + 1 < value.length(); i++) pairs.add(value.substring(i, i + 2));
        return pairs;
    }

    private static boolean isUnknownArtist(String value) {
        String normalized = normalize(value);
        return normalized.isEmpty() || normalized.contains("未知歌手") || normalized.equals("unknown");
    }

    private static String normalizeTitleForReplacement(String value) {
        if (value == null) return "";
        return value.toLowerCase(Locale.ROOT)
            .replaceAll("(?i)\\b(live|remaster(?:ed)?|version|edit|mix|cover|instrumental|karaoke)\\b", "")
            .replace("现场版", "")
            .replace("伴奏", "")
            .replace("翻唱", "")
            .replace("重制版", "")
            .replaceAll("[\\s\\p{Punct}（）()《》【】\\[\\]·•]+", "")
            .trim();
    }

    static boolean sameIdentity(String title, String artist, Track candidate) {
        String wantedTitle = normalize(title);
        String candidateTitle = normalize(candidate.title);
        if (!wantedTitle.equals(candidateTitle)) return false;
        return sameArtistIdentity(artist, candidate.artist);
    }

    private static boolean sameArtistIdentity(String left, String right) {
        String leftSignature = artistSignature(left);
        String rightSignature = artistSignature(right);
        if (leftSignature.isEmpty() || rightSignature.isEmpty()) return false;
        return leftSignature.equals(rightSignature);
    }

    private static String artistSignature(String value) {
        if (value == null) return "";
        String prepared = value.toLowerCase(Locale.ROOT)
            .replace("（", "(")
            .replace("）", ")")
            .replaceAll("\\b(featuring|feat\\.?|ft\\.?)\\b", "/")
            .replaceAll("[、/&+,，;；]+", "/")
            .replaceAll("\\s+和\\s+", "/");
        String[] parts = prepared.split("/");
        List<String> tokens = new ArrayList<>();
        for (String part : parts) {
            String token = normalize(part);
            if (!token.isEmpty() && !tokens.contains(token)) tokens.add(token);
        }
        Collections.sort(tokens);
        StringBuilder builder = new StringBuilder();
        for (String token : tokens) {
            if (builder.length() > 0) builder.append('|');
            builder.append(token);
        }
        return builder.toString();
    }

    private static void sortByRelevance(List<Track> rows, String keyword) {
        Collections.sort(rows, (left, right) ->
            Integer.compare(score(right, keyword), score(left, keyword)));
    }

    private static int score(Track track, String keyword) {
        if (track == null) return 0;
        String wanted = normalize(keyword);
        String title = normalize(track.title);
        String artist = normalize(track.artist);
        if (wanted.isEmpty() || (title.isEmpty() && artist.isEmpty())) return 0;

        String titleArtist = title + artist;
        String artistTitle = artist + title;
        if (wanted.equals(titleArtist) || wanted.equals(artistTitle)) return 10000;

        int score = 0;
        if (title.equals(wanted)) score += 7600;
        else if (artist.equals(wanted)) score += 7000;
        else if (title.contains(wanted)) score += 5600 - Math.abs(title.length() - wanted.length());
        else if (wanted.contains(title) && title.length() > 1) score += 4700 + title.length();
        else if (artist.contains(wanted)) score += 4300;

        List<String> tokens = queryTokens(keyword);
        boolean allMatched = !tokens.isEmpty();
        int tokenScore = 0;
        for (String token : tokens) {
            if (title.equals(token)) tokenScore += 1700;
            else if (artist.equals(token)) tokenScore += 1600;
            else if (title.contains(token)) tokenScore += 1200;
            else if (artist.contains(token)) tokenScore += 1100;
            else {
                allMatched = false;
                tokenScore -= 600;
            }
        }
        if (allMatched && tokens.size() > 1) score += 5200;
        score += tokenScore;

        if (titleArtist.contains(wanted) || artistTitle.contains(wanted)) score += 2200;
        return Math.max(0, score);
    }

    private static List<String> queryTokens(String value) {
        List<String> tokens = new ArrayList<>();
        if (value == null) return tokens;
        String prepared = value.toLowerCase(Locale.ROOT)
            .replace("（", " ")
            .replace("）", " ")
            .replaceAll("[\\s\\p{Punct}《》【】\\[\\]·•]+", " ")
            .replaceAll("(?<=[a-z0-9])(?=[\\p{IsHan}])|(?<=[\\p{IsHan}])(?=[a-z0-9])", " ")
            .trim();
        for (String part : prepared.split("\\s+")) {
            String token = normalize(part);
            if (!token.isEmpty() && !tokens.contains(token)) tokens.add(token);
        }
        return tokens;
    }

    private static String normalize(String value) {
        if (value == null) return "";
        return value.toLowerCase(Locale.ROOT)
            .replaceAll("[\\s\\p{Punct}（）()《》【】\\[\\]·•]+", "")
            .trim();
    }

    private static String safe(String value, String fallback) {
        return value == null || value.trim().isEmpty() ? fallback : value.trim();
    }
}
