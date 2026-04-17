#!/bin/bash
WALLPAPER_DIR="$HOME/Pictures/1BASASS"
APPLY_SCRIPT="$HOME/.config/hypr/scripts/apply-theme.sh"
SELECTED_FILE="$HOME/.cache/wallpaper-preview-selected"

rm -f "$SELECTED_FILE"

# Launch on special workspace so it's hidden initially
swayimg "$WALLPAPER_DIR"/* &
sleep 0.1

# Move it to center while hidden, then bring to current workspace
hyprctl dispatch focuswindow class:^swayimg
hyprctl dispatch movetoworkspacesilent special:swayimg,class:^swayimg
hyprctl dispatch moveactive exact 640 404
hyprctl dispatch movetoworkspace e+0,class:^swayimg

wait

if [[ -f "$SELECTED_FILE" ]]; then
    WALLPAPER=$(cat "$SELECTED_FILE")
    rm -f "$SELECTED_FILE"
    [[ -f "$WALLPAPER" ]] && "$APPLY_SCRIPT" "$WALLPAPER"
fi
