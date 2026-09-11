#!/usr/bin/env bash
set -euo pipefail
bundle_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo '需要 Python 3.8 或以上；多数 Linux 发行版和 macOS 已自带 python3。' >&2
  exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' || {
  echo '需要 Python 3.8 或以上。' >&2
  exit 1
}
if [[ $# -eq 0 ]]; then set -- install; fi
exec python3 "$bundle_dir/install.py" "$@"
