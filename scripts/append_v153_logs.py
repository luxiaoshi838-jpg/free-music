from pathlib import Path

project_log = Path("PROJECT_LOG.md")
changelog = Path("docs/CHANGELOG.md")

project_marker = "## 2026-08-06 - v153 playlist playback-stop diagnosis and reporting"
project_entry = r'''

## 2026-08-06 - v153 playlist playback-stop diagnosis and reporting

- User reported that playlist playback can stop partway through a song without an app crash or an existing crash/no-response report.
- Confirmed a cache-completeness defect in the v151/v152 Range downloader: any response shorter than the requested 4 MiB chunk was treated as end-of-file, although some CDNs may legally return a smaller partial range before the real end.
- Replaced that shortcut with strict `Content-Range` validation: every HTTP 206 response must have a valid range, start at the exact accumulated byte offset, contain the declared number of bytes, and continue until the declared total length is reached. HTTP 416 is accepted only when the accumulated length exactly equals the server total.
- Added `PlaybackProblemReporter` so MediaPlayer errors and non-crash interruptions are stored in the existing copyable report slot with error codes, playback position/duration, queue, playlist/song, URI/cache URI, lifecycle state, and device/version context.
- Added a two-second playback health monitor. A player that disappears, stops without callback, or makes no position progress for 12 seconds now creates a report; a silently stopped player receives one automatic restart attempt.
- Added cached-duration validation against catalog duration metadata. Clearly truncated cached files are reported, deleted, and routed back through the existing retrieval path.
- Active playback followed by Activity destruction is now reported as `activity-destroyed-during-active-playback`; the current architecture still owns MediaPlayer in the Activity, so this report determines whether a later service-ownership refactor is required.
- Manual pause is excluded from interruption reporting.
- Version: `2026080153 / 2026.08.06.v153-playback-stop-report`.
- GitHub Actions run `31079587556` passed v151 Range regression, v152 rapid-next regression, v153 interruption checks, four-brand Android compilation, package-name checks, and version checks.
- Artifact: `8958922118`, digest `sha256:49c80e7132e9fc311add56fea8470858a4dd564356e687c38a12e63bca157cf8`.
- Real-device continuous playlist playback remains required; build success is not treated as proof that the phone-side stop is resolved.
'''

change_marker = "## v153 - 2026-08-06"
change_entry = r'''

## v153 - 2026-08-06

- Version: `2026080153 / 2026.08.06.v153-playback-stop-report`.
- Fixed Range caching so a short partial response is no longer mistaken for a complete song.
- Enforced continuous `Content-Range` offsets, exact range-body length, and exact final total length.
- Added copyable reports for MediaPlayer error, silent stop, stalled progress, missing player, early cached-file completion, and Activity destruction during active playback.
- Added one automatic restart attempt when MediaPlayer silently changes to a stopped state.
- Added cached-duration comparison and deletion/retrieval of clearly truncated cache files.
- Kept v152 rapid-next serialization and cancellation behavior.
- Automated checks and four-brand Android compilation passed; phone playback testing is still required.
'''

for path, marker, entry in (
    (project_log, project_marker, project_entry),
    (changelog, change_marker, change_entry),
):
    text = path.read_text(encoding="utf-8")
    if marker not in text:
        path.write_text(text.rstrip() + entry.rstrip() + "\n", encoding="utf-8")
