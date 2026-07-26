#!/usr/bin/env python3
from __future__ import annotations

import getpass
import hashlib


def main() -> None:
    first = getpass.getpass("输入姜Lab首次验证口令: ")
    second = getpass.getpass("再次输入确认: ")
    if first != second:
        raise SystemExit("两次输入不一致")
    print(hashlib.sha256(first.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    main()
