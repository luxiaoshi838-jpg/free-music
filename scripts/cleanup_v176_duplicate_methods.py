from pathlib import Path

path = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = path.read_text(encoding="utf-8")


def method_spans(source: str, signature: str):
    spans = []
    pos = 0
    while True:
        start = source.find(signature, pos)
        if start < 0:
            break
        brace = source.find("{", start)
        if brace < 0:
            break
        depth = 0
        end = None
        for i in range(brace, len(source)):
            ch = source[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is None:
            raise SystemExit("unterminated method: " + signature)
        while end < len(source) and source[end] in " \t":
            end += 1
        if end < len(source) and source[end] == "\r":
            end += 1
        if end < len(source) and source[end] == "\n":
            end += 1
        spans.append((start, end))
        pos = end
    return spans


def keep_first(source: str, signature: str) -> str:
    spans = method_spans(source, signature)
    if len(spans) <= 1:
        return source
    for start, end in reversed(spans[1:]):
        source = source[:start] + source[end:]
    return source

for signature in (
    "    private boolean isManualOnlyCacheSong(Song song)",
    "    private boolean songHasRecordedCacheQuick(Song song)",
    "    private Song copySongForPersistence(Song song)",
):
    text = keep_first(text, signature)

path.write_text(text, encoding="utf-8")
