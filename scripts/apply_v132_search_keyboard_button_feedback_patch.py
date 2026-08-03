from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
main_path = root / 'app/src/main/java/com/jianglab/babywife/MainActivity.java'
gradle_path = root / 'app/build.gradle'
check_path = root / 'scripts/check_feature_requirements.py'


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'Cannot find {label}')
    return text.replace(old, new, 1)


main = main_path.read_text(encoding='utf-8')

if 'import android.view.inputmethod.InputMethodManager;' not in main:
    main = replace_once(
        main,
        'import android.view.inputmethod.EditorInfo;\n',
        'import android.view.inputmethod.EditorInfo;\nimport android.view.inputmethod.InputMethodManager;\n',
        'InputMethodManager import',
    )

main = replace_once(
    main,
    '        setContentView(buildContentView());\n        maybeRequireJiangLabPassphrase();',
    '        setContentView(buildContentView());\n        attachPressFeedbackTree(shellView);\n        maybeRequireJiangLabPassphrase();',
    'global press feedback installation',
)

main = replace_once(
    main,
    '    private void performSearch() {\n        String keyword = searchInput.getText().toString().trim();',
    '    private void performSearch() {\n        hideKeyboardAndClearFocus(searchInput);\n        String keyword = searchInput.getText().toString().trim();',
    'song search keyboard dismissal',
)

playlist_pattern = re.compile(
    r'''        playlistSearchInput = new EditText\(this\);\n'''
    r'''.*?'''
    r'''        panel\.addView\(playlistSearchInput, searchParams\);\n''',
    re.S,
)
playlist_replacement = '''        FrameLayout playlistSearchBox = new FrameLayout(this);
        playlistSearchInput = new EditText(this);
        playlistSearchInput.setSingleLine(true);
        playlistSearchInput.setHint("搜索当前歌单中的歌曲 / 歌手");
        playlistSearchInput.setTextColor(TEXT_MAIN);
        playlistSearchInput.setHintTextColor(Color.argb(185, 255, 255, 255));
        playlistSearchInput.setBackground(rounded(Color.argb(72, 255, 255, 255), dp(20)));
        playlistSearchInput.setPadding(dp(14), 0, dp(48), 0);
        playlistSearchInput.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        playlistSearchInput.setOnEditorActionListener((view, actionId, event) -> {
            boolean keyboardSearch = actionId == EditorInfo.IME_ACTION_SEARCH
                || actionId == EditorInfo.IME_ACTION_DONE;
            boolean enterUp = event != null
                && event.getKeyCode() == KeyEvent.KEYCODE_ENTER
                && event.getAction() == KeyEvent.ACTION_UP;
            if (keyboardSearch || enterUp) {
                applyPlaylistFilter();
                hideKeyboardAndClearFocus(playlistSearchInput);
                return true;
            }
            return false;
        });
        playlistSearchBox.addView(playlistSearchInput, new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        TextView clearPlaylistSearchButton = new TextView(this);
        clearPlaylistSearchButton.setText("×");
        clearPlaylistSearchButton.setTextColor(Color.WHITE);
        clearPlaylistSearchButton.setTextSize(17);
        clearPlaylistSearchButton.setGravity(Gravity.CENTER);
        clearPlaylistSearchButton.setIncludeFontPadding(false);
        clearPlaylistSearchButton.setVisibility(View.GONE);
        clearPlaylistSearchButton.setClickable(true);
        clearPlaylistSearchButton.setFocusable(true);
        clearPlaylistSearchButton.setContentDescription("清除歌单搜索文字");
        clearPlaylistSearchButton.setBackground(rounded(Color.argb(190, 112, 112, 118), dp(12)));
        clearPlaylistSearchButton.setOnClickListener(view -> {
            playlistSearchInput.setText("");
            playlistSearchInput.requestFocus();
        });
        attachSubtlePressFeedback(clearPlaylistSearchButton);
        FrameLayout.LayoutParams playlistClearParams = new FrameLayout.LayoutParams(dp(24), dp(24));
        playlistClearParams.gravity = Gravity.END | Gravity.CENTER_VERTICAL;
        playlistClearParams.setMargins(0, 0, dp(10), 0);
        playlistSearchBox.addView(clearPlaylistSearchButton, playlistClearParams);

        playlistSearchInput.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence text, int start, int count, int after) {
            }

            @Override
            public void afterTextChanged(Editable editable) {
            }

            @Override
            public void onTextChanged(CharSequence text, int start, int before, int count) {
                clearPlaylistSearchButton.setVisibility(
                    text != null && text.length() > 0 ? View.VISIBLE : View.GONE);
                applyPlaylistFilter();
            }
        });
        LinearLayout.LayoutParams searchParams = new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, dp(44));
        searchParams.setMargins(0, dp(6), 0, dp(6));
        panel.addView(playlistSearchBox, searchParams);
'''
main, count = playlist_pattern.subn(playlist_replacement, main, count=1)
if count != 1:
    raise SystemExit(f'Cannot replace playlist search block: {count}')

main = replace_once(
    main,
    '''    private void attachSubtlePressFeedback(View view) {
        if (view == null) return;
        view.setOnTouchListener((pressedView, event) -> {''',
    '''    private void attachSubtlePressFeedback(View view) {
        if (view == null) return;
        view.setOnTouchListener((pressedView, event) -> {
            if (!pressedView.isEnabled()) return false;''',
    'disabled press guard',
)

main = replace_once(
    main,
    '''            return false;
        });
    }

    private View buildPlaylistPage() {''',
    '''            return false;
        });
    }

    private void attachPressFeedbackTree(View root) {
        if (root == null) return;
        boolean buttonLike = root instanceof Button
            || root instanceof BroomIconView
            || root instanceof BackChevronView
            || (root instanceof TextView && !(root instanceof EditText) && root.isClickable())
            || (root instanceof ImageView && root.isClickable())
            || (root instanceof LinearLayout && root.isClickable());
        if (buttonLike) attachSubtlePressFeedback(root);
        if (root instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) root;
            for (int index = 0; index < group.getChildCount(); index++) {
                attachPressFeedbackTree(group.getChildAt(index));
            }
        }
    }

    private void hideKeyboardAndClearFocus(View target) {
        View focused = target != null ? target : getCurrentFocus();
        if (focused != null) {
            InputMethodManager manager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            if (manager != null) manager.hideSoftInputFromWindow(focused.getWindowToken(), 0);
            focused.clearFocus();
        }
    }

    private View buildPlaylistPage() {''',
    'feedback tree and keyboard helper',
)

make_button_pattern = re.compile(
    r'''(    private Button makeButton\(String text, boolean primary\) \{\n.*?'''
    r'''        button\.setBackground\(rounded\(primary \? ACCENT : Color\.argb\(78, 255, 255, 255\), dp\(22\)\)\);\n)'''
    r'''(        return button;\n    \})''',
    re.S,
)
main, count = make_button_pattern.subn(
    r'\1        attachSubtlePressFeedback(button);\n\2', main, count=1)
if count != 1:
    raise SystemExit(f'Cannot update makeButton: {count}')

# Add feedback to button-like controls that are not produced by makeButton and may be
# constructed after the initial view-tree pass.
for old, new, label in [
    (
        '        clearCacheButton.setOnClickListener(view -> confirmClearTransientCache());\n',
        '        clearCacheButton.setOnClickListener(view -> confirmClearTransientCache());\n        attachSubtlePressFeedback(clearCacheButton);\n',
        'broom feedback',
    ),
    (
        '        clearSearchButton.setOnClickListener(view -> {\n            searchInput.setText("");\n            searchInput.requestFocus();\n        });\n',
        '        clearSearchButton.setOnClickListener(view -> {\n            searchInput.setText("");\n            searchInput.requestFocus();\n        });\n        attachSubtlePressFeedback(clearSearchButton);\n',
        'song clear feedback',
    ),
    (
        '        searchLoadMoreView.setOnClickListener(view -> loadNextSearchBatch(false));\n',
        '        searchLoadMoreView.setOnClickListener(view -> loadNextSearchBatch(false));\n        attachSubtlePressFeedback(searchLoadMoreView);\n',
        'load more feedback',
    ),
    (
        '        preview.setOnClickListener(view -> {\n            selectBuiltInBackground(mode);\n            if (holder[0] != null) holder[0].dismiss();\n        });\n',
        '        preview.setOnClickListener(view -> {\n            selectBuiltInBackground(mode);\n            if (holder[0] != null) holder[0].dismiss();\n        });\n        attachSubtlePressFeedback(preview);\n',
        'background preview feedback',
    ),
    (
        '        column.setOnClickListener(view -> {\n            switchLauncherIcon(mode);\n            if (holder[0] != null) holder[0].dismiss();\n        });\n',
        '        column.setOnClickListener(view -> {\n            switchLauncherIcon(mode);\n            if (holder[0] != null) holder[0].dismiss();\n        });\n        attachSubtlePressFeedback(column);\n',
        'icon preview feedback',
    ),
]:
    main = replace_once(main, old, new, label)

main_path.write_text(main, encoding='utf-8')

gradle = gradle_path.read_text(encoding='utf-8')
gradle = replace_once(gradle, 'versionCode 2026080131', 'versionCode 2026080132', 'version code')
gradle = replace_once(
    gradle,
    'versionName "2026.08.03.playable-format-priority"',
    'versionName "2026.08.03.search-keyboard-button-feedback"',
    'version name',
)
gradle_path.write_text(gradle, encoding='utf-8')

check = check_path.read_text(encoding='utf-8')
check = replace_once(
    check,
    "    'version bumped': 'versionCode 2026080131' in gradle,",
    '''    'search keyboards close after submit': (
        'import android.view.inputmethod.InputMethodManager;' in main
        and 'hideKeyboardAndClearFocus(searchInput);' in main
        and 'playlistSearchInput.setImeOptions(EditorInfo.IME_ACTION_SEARCH);' in main
        and 'hideKeyboardAndClearFocus(playlistSearchInput);' in main
    ),
    'playlist search clear control': (
        'TextView clearPlaylistSearchButton = new TextView(this);' in main
        and 'clearPlaylistSearchButton.setText("×")' in main
        and 'clearPlaylistSearchButton.setVisibility(View.GONE)' in main
        and 'playlistSearchInput.setText("")' in main
        and 'panel.addView(playlistSearchBox, searchParams);' in main
    ),
    'all main button press feedback': (
        'attachPressFeedbackTree(shellView);' in main
        and 'attachSubtlePressFeedback(button);' in main
        and 'root instanceof BroomIconView' in main
        and 'root instanceof BackChevronView' in main
        and 'root instanceof TextView' in main
        and '.scaleX(0.96f)' in main
        and '.scaleY(0.96f)' in main
    ),
    'version bumped': 'versionCode 2026080132' in gradle,''',
    'v132 feature checks',
)
check_path.write_text(check, encoding='utf-8')

with (root / 'docs/CHANGELOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- v132: submitting either the song search or the current-playlist search now hides the soft keyboard and clears input focus. The playlist search field gains the same circular clear button as the song search field.\n')
    output.write('- v132: all main button-like controls use the same subtle 96% press-and-release feedback as previous/next, including settings, broom cleanup, current playlist, search, replacement actions, playback mode, clear buttons, back buttons and other clickable controls.\n')
with (root / 'PROJECT_LOG.md').open('a', encoding='utf-8') as output:
    output.write('\n- v132 closes the IME after song/playlist search submission, adds a circular clear control to playlist search, and applies consistent subtle press feedback to all main button-like controls.\n')

print('Applied v132 search keyboard and button feedback patch')
