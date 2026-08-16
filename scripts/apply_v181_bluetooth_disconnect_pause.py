from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"anchor missing: {label}")
    return text.replace(old, new, 1)


# Version
p = Path("app/build.gradle")
g = p.read_text(encoding="utf-8")
g = g.replace("versionCode 2026080880", "versionCode 2026080881", 1)
g = g.replace(
    'versionName "2026.08.14.v180-playback-health-snapshot"',
    'versionName "2026.08.16.v181-bluetooth-disconnect-pause"',
    1,
)
if "versionCode 2026080881" not in g:
    raise SystemExit("v181 version patch failed")
p.write_text(g, encoding="utf-8")


p = Path("app/src/main/java/com/jianglab/babywife/MainActivity.java")
text = p.read_text(encoding="utf-8")

text = replace_once(
    text,
    'import android.graphics.drawable.GradientDrawable;\n',
    'import android.graphics.drawable.GradientDrawable;\nimport android.media.AudioDeviceCallback;\nimport android.media.AudioDeviceInfo;\nimport android.media.AudioManager;\n',
    'audio device imports',
)

old = '''    private boolean playbackReceiverRegistered = false;\n    private int playbackRequestSerial = 0;'''
new = '''    private boolean playbackReceiverRegistered = false;\n    private AudioManager audioManager;\n    private boolean audioDeviceCallbackRegistered = false;\n    private final AudioDeviceCallback bluetoothAudioDeviceCallback = new AudioDeviceCallback() {\n        @Override\n        public void onAudioDevicesRemoved(AudioDeviceInfo[] removedDevices) {\n            if (!containsBluetoothAudioDevice(removedDevices)) return;\n            // Give Android a brief moment to finish route replacement. If another\n            // Bluetooth output is still connected, playback must continue.\n            playbackHealthHandler.postDelayed(() -> {\n                if (activityDestroyed || hasConnectedBluetoothAudioOutput()) return;\n                pauseForBluetoothDisconnect();\n            }, 300L);\n        }\n    };\n    private int playbackRequestSerial = 0;'''
text = replace_once(text, old, new, 'bluetooth callback fields')

text = replace_once(
    text,
    '        registerPlaybackControlReceiver();\n        PlaybackControlService.ensureStarted(this);',
    '        registerPlaybackControlReceiver();\n        registerBluetoothDisconnectPause();\n        PlaybackControlService.ensureStarted(this);',
    'register bluetooth callback on create',
)

anchor = '''    private void scheduleStartupWork() {'''
methods = '''    private void registerBluetoothDisconnectPause() {\n        if (audioDeviceCallbackRegistered) return;\n        try {\n            audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);\n            if (audioManager == null) return;\n            audioManager.registerAudioDeviceCallback(\n                bluetoothAudioDeviceCallback, new Handler(Looper.getMainLooper()));\n            audioDeviceCallbackRegistered = true;\n        } catch (Throwable ignored) {\n            audioDeviceCallbackRegistered = false;\n        }\n    }\n\n    private void unregisterBluetoothDisconnectPause() {\n        if (!audioDeviceCallbackRegistered || audioManager == null) return;\n        try {\n            audioManager.unregisterAudioDeviceCallback(bluetoothAudioDeviceCallback);\n        } catch (Throwable ignored) {\n        }\n        audioDeviceCallbackRegistered = false;\n    }\n\n    private boolean containsBluetoothAudioDevice(AudioDeviceInfo[] devices) {\n        if (devices == null) return false;\n        for (AudioDeviceInfo device : devices) {\n            if (device != null && isBluetoothAudioType(device.getType())) return true;\n        }\n        return false;\n    }\n\n    private boolean hasConnectedBluetoothAudioOutput() {\n        AudioManager manager = audioManager;\n        if (manager == null) return false;\n        try {\n            AudioDeviceInfo[] outputs = manager.getDevices(AudioManager.GET_DEVICES_OUTPUTS);\n            return containsBluetoothAudioDevice(outputs);\n        } catch (Throwable ignored) {\n            return false;\n        }\n    }\n\n    private boolean isBluetoothAudioType(int type) {\n        if (type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP\n            || type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) return true;\n        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P\n            && type == AudioDeviceInfo.TYPE_HEARING_AID) return true;\n        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S\n            && (type == AudioDeviceInfo.TYPE_BLE_HEADSET\n                || type == AudioDeviceInfo.TYPE_BLE_SPEAKER)) return true;\n        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU\n            && type == AudioDeviceInfo.TYPE_BLE_BROADCAST) return true;\n        return false;\n    }\n\n    private void pauseForBluetoothDisconnect() {\n        UnifiedMediaPlayer player = mediaPlayer;\n        if (player == null || playbackUserPaused || !playbackExpectedPlaying) return;\n        // Bluetooth route loss is an expected user/device event, not a playback\n        // failure. Pause silently: do not create recent-action, playback-problem,\n        // ANR, or crash diagnostics for this transition.\n        playbackUserPaused = true;\n        stopPlaybackHealthWatch();\n        try {\n            player.pause();\n        } catch (Throwable ignored) {\n        }\n        if (playButton != null) playButton.setText("▶");\n        try {\n            saveLastSong(player.getCurrentPosition());\n        } catch (Throwable ignored) {\n        }\n        lyricHandler.removeCallbacks(lyricTicker);\n        if (statusView != null) statusView.setText("蓝牙音频已断开，已自动暂停");\n        publishPlaybackControlState(true);\n    }\n\n''' + anchor
text = replace_once(text, anchor, methods, 'bluetooth pause methods')

# Unregister before executors/handlers are torn down.
text = replace_once(
    text,
    '        ++playlistCacheScanSerial;\n        playlistCacheScanExecutor.shutdownNow();',
    '        ++playlistCacheScanSerial;\n        unregisterBluetoothDisconnectPause();\n        playlistCacheScanExecutor.shutdownNow();',
    'unregister bluetooth callback on destroy',
)

p.write_text(text, encoding="utf-8")
