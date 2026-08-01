#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import tempfile

# Load the reviewed implementation from its immutable creation commit, adjust
# only the one deliberately duplicated anchor, then execute it unchanged.
SOURCE_COMMIT = "e9c382c5af143d10dccf3ca827338344abdb3b96"
SOURCE_PATH = "tools/apply_ui_responsiveness_notification_fix.py"


def main():
    patch_repo = Path(__file__).resolve().parents[1]
    source = subprocess.check_output(
        ["git", "-C", str(patch_repo), "show", f"{SOURCE_COMMIT}:{SOURCE_PATH}"],
        text=True,
        encoding="utf-8",
    )
    old = """def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {count}')
    return text.replace(old, new, 1)
"""
    new = """def replace_once(text, old, new, label):
    count = text.count(old)
    expected = 2 if label == 'cached button task state' else 1
    if count != expected:
        raise RuntimeError(f'{label}: expected {expected} anchor(s), found {count}')
    return text.replace(old, new, 1)
"""
    if old not in source:
        raise RuntimeError("reviewed patch helper function was not found")
    source = source.replace(old, new, 1)
    with tempfile.TemporaryDirectory(prefix="responsive_ui_patch_") as temp_dir:
        implementation = Path(temp_dir) / "implementation.py"
        implementation.write_text(source, encoding="utf-8")
        subprocess.run([sys.executable, str(implementation), *sys.argv[1:]], check=True)


if __name__ == "__main__":
    main()
