#!/usr/bin/env bash
# db-switch.sh — Toggle between SQLite and PostgreSQL in settings.py.
# Run from the project root (the directory containing manage.py).
set -euo pipefail

SETTINGS="jerinshop/settings.py"

if [ ! -f "$SETTINGS" ]; then
    echo "Error: $SETTINGS not found. Run this script from the project root." >&2
    exit 1
fi

# Detect active backend: check which block's DATABASES line is uncommented
if grep -A1 "# ═══ DB:SQLITE ═══" "$SETTINGS" | tail -1 | grep -q "^DATABASES"; then
    FROM="sqlite"
    TO="postgresql"
else
    FROM="postgresql"
    TO="sqlite"
fi

python3 - "$SETTINGS" "$FROM" "$TO" << 'PYEOF'
import sys

settings_path = sys.argv[1]
from_block = sys.argv[2]
to_block = sys.argv[3]

with open(settings_path) as f:
    lines = f.readlines()

marker_start = f"# ═══ DB:{from_block.upper()} ═══"
marker_end   = f"# ═══ END {from_block.upper()} ═══"
target_start = f"# ═══ DB:{to_block.upper()} ═══"
target_end   = f"# ═══ END {to_block.upper()} ═══"

def find_line(lns, substr):
    for i, line in enumerate(lns):
        if substr in line:
            return i
    raise SystemExit(f"Marker not found: {substr}")

from_a = find_line(lines, marker_start) + 1
from_b = find_line(lines, marker_end)
to_a   = find_line(lines, target_start) + 1
to_b   = find_line(lines, target_end)

# Comment out the currently-active block (skip already-commented lines)
for i in range(from_a, from_b):
    s = lines[i].lstrip()
    if s and not s.startswith('#'):
        lines[i] = '# ' + lines[i]

# Uncomment the target block (strip at most one '#' or '# ' prefix)
for i in range(to_a, to_b):
    if lines[i].startswith('# '):
        lines[i] = lines[i][2:]
    elif lines[i].startswith('#'):
        lines[i] = lines[i][1:]

with open(settings_path, 'w') as f:
    f.writelines(lines)
PYEOF

echo "✅ Switched to $TO"
