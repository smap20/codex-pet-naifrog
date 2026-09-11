#!/usr/bin/env bash
set -euo pipefail
bundle_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$bundle_dir/install.py" uninstall "$@"
