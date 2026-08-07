from pathlib import Path

path = Path('app/src/main/java/com/jianglab/babywife/PlaybackControlService.java')
text = path.read_text(encoding='utf-8')

text = text.replace(
    'private static final int FALLBACK_MEDIA_COLOR = Color.rgb(34, 31, 40);',
    'private static final int FIXED_MEDIA_COLOR = Color.rgb(38, 34, 42);'
)

old = '''        int mediaColor = artwork == null
            ? FALLBACK_MEDIA_COLOR : darkMediaColor(PlaybackArtworkLoader.averageColor(artwork));
        builder.setColor(mediaColor);
        if (artwork != null) {
            // High-resolution square art is supplied to both MediaSession and
            // the notification. Android/OEM lock screens can then crop/enlarge
            // it as the media-card backdrop instead of falling back to white.
            builder.setLargeIcon(artwork);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder.setColorized(true);
        }
        return builder.build();
    }

    private int darkMediaColor(int color) {
        if (color == 0) return FALLBACK_MEDIA_COLOR;
        int red = Math.max(18, Color.red(color) * 58 / 100);
        int green = Math.max(18, Color.green(color) * 58 / 100);
        int blue = Math.max(22, Color.blue(color) * 58 / 100);
        return Color.rgb(red, green, blue);
    }
'''

new = '''        // v163: fixed dark media-card tint for HyperOS. Artwork remains artwork only;
        // it no longer changes the card color from song to song.
        builder.setColor(FIXED_MEDIA_COLOR);
        if (artwork != null) {
            builder.setLargeIcon(artwork);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder.setColorized(true);
        }
        return builder.build();
    }
'''

if old not in text:
    if 'FIXED_MEDIA_COLOR' in text and 'PlaybackArtworkLoader.averageColor(artwork)' not in text:
        print('v163 media color patch already applied')
    else:
        raise SystemExit('Expected v162 media-color block was not found')
else:
    text = text.replace(old, new)
    path.write_text(text, encoding='utf-8')
    print('Applied v163 fixed media color')
