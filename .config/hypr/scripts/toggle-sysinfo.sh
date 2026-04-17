#!/usr/bin/env sh
# toggle-sysinfo.sh
# Place at: ~/.config/hypr/scripts/toggle-sysinfo.sh

SCRIPT="$HOME/.config/waybar/modules/sysinfo_popup.py"

if pgrep -f "sysinfo_popup.py" > /dev/null; then
    pkill -f "sysinfo_popup.py"
else
    # Capture cursor position at the exact moment of click
    POS=$(hyprctl cursorpos -j 2>/dev/null)
    CX=$(echo "$POS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(int(d['x']))" 2>/dev/null)
    CY=$(echo "$POS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(int(d['y']))" 2>/dev/null)
    python3 "$SCRIPT" --cx "${CX:-0}" --cy "${CY:-0}" &
fi
