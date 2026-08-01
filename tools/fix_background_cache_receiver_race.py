#!/usr/bin/env python3
from pathlib import Path
import argparse

# Triggered after the workflow was installed so GitHub Actions validates the full patch.

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    root = Path(parser.parse_args().root).resolve()
    path = root / "app/src/main/java/com/jianglab/babywife/MainActivity.java"
    text = path.read_text(encoding="utf-8")
    old = '''            if (currentSong != null && identity.equals(currentSong.key())) {
                copyBatchSongFields(currentSong, updated);
                if (titleView != null) titleView.setText(currentSong.title);
                if (artistView != null) artistView.setText(currentSong.artist + " · " + currentSong.source);
            }
            savePlaylists();
        } catch (Exception ignored) {
'''
    new = '''            if (currentSong != null && identity.equals(currentSong.key())) {
                copyBatchSongFields(currentSong, updated);
                if (titleView != null) titleView.setText(currentSong.title);
                if (artistView != null) artistView.setText(currentSong.artist + " · " + currentSong.source);
            }
            // PlaylistBatchCacheService is the single writer while the queue is running.
            // The Activity only refreshes its in-memory view to avoid overwriting newer results.
        } catch (Exception ignored) {
'''
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"batch receiver persistence anchor count: {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("batch_service_single_writer=enabled")


if __name__ == "__main__":
    main()
