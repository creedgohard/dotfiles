#!/bin/bash
ART=$(playerctl metadata mpris:artUrl 2>/dev/null | sed 's|file://||')
if [[ -n "$ART" && -f "$ART" ]]; then
    echo "$ART"
else
    echo "$HOME/.config/eww/music-fallback.png"
fi
