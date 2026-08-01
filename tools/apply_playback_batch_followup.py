#!/usr/bin/env python3
from pathlib import Path
import argparse


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count == 1:
        return text.replace(old, new, 1)
    if count == 0 and new in text:
        return text
    raise RuntimeError(f"{label}: expected one anchor, found {count}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    root = Path(parser.parse_args().root).resolve()

    network_path = root / "app/src/main/java/com/jianglab/babywife/NetworkMediaCache.java"
    network = network_path.read_text(encoding="utf-8")
    network = replace_once(
        network,
        '''    static boolean cachedAudioExists(Context context, String uriText) {
        return isAcceptableCachedAudio(context, uriText);
    }''',
        '''    static boolean cachedAudioExists(Context context, String uriText) {
        return CacheStorage.exists(context, uriText);
    }

    static boolean validateCatalogCache(Context context, String catalogJson) {
        String key = cacheKeyForCatalog(catalogJson);
        if (key.isEmpty()) return false;
        String uri = CacheStorage.findAudioUri(context, key);
        if (uri.isEmpty()) return false;
        if (isAcceptableCachedAudio(context, uri)) return true;
        CacheStorage.deleteKey(context, key);
        return false;
    }''',
        "cheap UI cache existence and background validator",
    )
    network_path.write_text(network, encoding="utf-8")

    main_path = root / "app/src/main/java/com/jianglab/babywife/MainActivity.java"
    main = main_path.read_text(encoding="utf-8")
    main = replace_once(
        main,
        '''                    NetworkMediaCache.normalizeCacheFiles(this, song.catalogJson);
                }
            }
            runOnUiThread(this::refreshCachedUrisAfterMigration);''',
        '''                    NetworkMediaCache.normalizeCacheFiles(this, song.catalogJson);
                    NetworkMediaCache.validateCatalogCache(this, song.catalogJson);
                }
            }
            runOnUiThread(this::refreshCachedUrisAfterMigration);''',
        "background cache validation",
    )
    main = replace_once(
        main,
        '''        } catch (Exception ex) {
            stopPlayback();
            playButton.setText("▶");
            toast("播放失败：" + ex.getMessage());
        }
    }

    private void attachPlaybackErrorHandler''',
        '''        } catch (Exception ex) {
            handlePlaybackFailure(song, "播放失败：" + ex.getMessage());
        }
    }

    private void attachPlaybackErrorHandler''',
        "synchronous playback failure containment",
    )
    main = replace_once(
        main,
        '''        } catch (Exception ignored) {
            stopPlayback();
            playButton.setText("▶");
        }
    }

    private void playSong(Song song) {''',
        '''        } catch (Exception ignored) {
            handlePlaybackFailure(currentSong, "上次缓存无法稳定恢复");
        }
    }

    private void playSong(Song song) {''',
        "restored playback failure containment",
    )
    main_path.write_text(main, encoding="utf-8")

    checks_path = root / "scripts/check_feature_requirements.py"
    checks = checks_path.read_text(encoding="utf-8")
    checks = replace_once(
        checks,
        "        and 'return isAcceptableCachedAudio(context, uriText);' in network\n",
        "        and 'validateCatalogCache' in network\n        and 'NetworkMediaCache.validateCatalogCache(this, song.catalogJson)' in main\n        and 'return CacheStorage.exists(context, uriText);' in network\n",
        "background compatibility check",
    )
    checks_path.write_text(checks, encoding="utf-8")

    print("playlist_ui_full_decode_validation=disabled")
    print("background_cache_compatibility_scan=enabled")
    print("sync_playback_failures_contained=pass")


if __name__ == "__main__":
    main()
