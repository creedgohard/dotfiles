#!/usr/bin/env sh
# toggle-network.sh located at ~/.config/hypr/scripts/toggle-network.sh

SCRIPT="$HOME/.config/waybar/modules/network_popup.py"

if pgrep -f "network_popup.py" > /dev/null; then
    pkill -f "network_popup.py"
else
    # Capture cursor position exactly like your working sysinfo script
    POS=$(hyprctl cursorpos -j 2>/dev/null)
    CX=$(echo "$POS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(int(d['x']))" 2>/dev/null)
    CY=$(echo "$POS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(int(d['y']))" 2>/dev/null)
    python3 "$SCRIPT" --cx "${CX:-0}" --cy "${CY:-0}" &
fi
