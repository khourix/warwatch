#!/usr/bin/env bash
# verify-warwatch entry point: quick | full | live-read. Exit 0 pass, 1 fail. See SKILL.md.
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/checks.py" "$@"
