#!/usr/bin/env sh
# macOS/Linux shortcut for: python3.12 dev.py run
cd "$(dirname "$0")" && exec python3.12 dev.py run "$@"
