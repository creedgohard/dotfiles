#!/bin/bash
# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃     restore-theme.sh — restores last wallpaper on login     ┃
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

LAST_WALLPAPER="$HOME/.cache/wal/wal"

# Wait for swww-daemon to be ready
sleep 1

if [[ -f "$LAST_WALLPAPER" ]]; then
    WALLPAPER=$(cat "$LAST_WALLPAPER")
    if [[ -f "$WALLPAPER" ]]; then
        ~/.config/hypr/scripts/apply-theme.sh "$WALLPAPER"
    fi
else
    # First run fallback — set a default wallpaper if it exists
    DEFAULT="$HOME/Pictures/Wallpapers/default.jpg"
    if [[ -f "$DEFAULT" ]]; then
        ~/.config/hypr/scripts/apply-theme.sh "$DEFAULT"
    fi
fi
