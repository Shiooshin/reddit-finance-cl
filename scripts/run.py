#!/usr/bin/env python3
"""One-off runner / dev entrypoint.

Usage:
    python scripts/run.py
"""

from main.logger import configure_root
from main.core import main

if __name__ == "__main__":
    configure_root()
    main()
