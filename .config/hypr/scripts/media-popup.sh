#!/bin/bash
# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃         media-popup.sh — click mpris to show controls      ┃
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

# Get current track info
TITLE=$(playerctl metadata title 2>/dev/null || echo "Nothing playing")
ARTIST=$(playerctl metadata artist 2>/dev/null || echo "")
STATUS=$(playerctl status 2>/dev/null || echo "Stopped")

# Toggle pause icon
if [[ "$STATUS" == "Playing" ]]; then
    PAUSE_ICON=""
else
    PAUSE_ICON=""
fi

# Show wofi popup with controls
CHOICE=$(printf "󰒮  Previous\n%s  Play/Pause\n󰒭  Next\n󰓛  Stop" "$PAUSE_ICON" | wofi \
    --dmenu \
    --style ~/.config/wofi/style.css \
    --prompt "$ARTIST — $TITLE" \
    --width 300 \
    --height 200 \
    --no-actions)

case "$CHOICE" in
    *"Previous"*) playerctl previous ;;
    *"Play"*)     playerctl play-pause ;;
    *"Next"*)     playerctl next ;;
    *"Stop"*)     playerctl stop ;;
esac
