#!/bin/bash
# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃              apply-theme.sh — pywal theme dispatcher        ┃
# ┃   Called by waypaper/swww hook whenever wallpaper changes   ┃
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

WALLPAPER="$1"

if [[ -z "$WALLPAPER" ]]; then
    echo "Usage: apply-theme.sh /path/to/wallpaper.jpg"
    exit 1
fi

# ── 1. Set wallpaper on both monitors with a fade transition ──
echo "$(date): Starting theme change" >> /tmp/theme-debug.log
awww img "$WALLPAPER" \
    --outputs DP-1,DP-2 \
    --transition-type grow \
    --transition-duration 1.5 \
    --transition-fps 144

# ── 2. Run pywal to extract palette ──
#   -n  = skip setting the wallpaper (swww already did it)
#   -e  = skip reloading apps pywal manages itself (we do it manually)
#   --backend wal = best colour extraction quality
#   Force background to pure black for OLED — no grey near-blacks
wal -i "$WALLPAPER" -n -e -s --backend wal --saturate 1.0
wal_cache="$HOME/.cache/wal"
echo "$(date): After wal" >> /tmp/theme-debug.log
# Give wal a moment to write its cache files
sleep 0.3

# ── 3. Read colours from pywal cache ──
source "$wal_cache/colors.sh"

# color0  = background (we force #000000 for OLED)
# color1  = darkest accent
# color2  = mid accent
# color3  = warm accent
# color4  = primary accent (used for active border)
# color5  = secondary accent
# color6  = highlight
# color7  = foreground
BG="#000000"           # Force true black for OLED
ACCENT="${color4}"     # Primary accent (replaces crimson)
INACTIVE="${color1}"   # Dark tone for inactive borders
SPLASH="${color6}"     # Bright tone for splash text

# Strip the # for hyprctl rgba format (adds ff alpha)
to_rgba() { echo "rgba(${1:1}ff)"; }

ACCENT_RGBA=$(to_rgba "$ACCENT")
INACTIVE_RGBA=$(to_rgba "$INACTIVE")
BG_RGBA=$(to_rgba "$BG")

# Fade to transparent for glow effect
ACCENT_TRANSPARENT="rgba(${ACCENT:1}00)"
hyprctl --batch \
    "keyword general:col.inactive_border $INACTIVE_RGBA; \
     keyword misc:background_color $BG_RGBA; \
     keyword misc:col.splash $ACCENT_RGBA"
hyprctl keyword general:col.active_border "$ACCENT_RGBA $ACCENT_RGBA 45deg"
hyprctl keyword shadow:color "$ACCENT_RGBA"
hyprctl keyword shadow:range 40
hyprctl keyword shadow:render_power 1
echo "$(date): After hyprctl" >> /tmp/theme-debug.log
# ── 5. Reload Waybar with new colours ──
# Write pywal CSS variables for waybar, wofi, and wlogout to import
# accent-transparent is the accent colour at 50% opacity for hover effects

# Convert hex to rgb components for rgba usage
hex_to_rgb() {
    local hex="${1:1}"  # strip #
    printf "%d, %d, %d" "0x${hex:0:2}" "0x${hex:2:2}" "0x${hex:4:2}"
}
ACCENT_RGB=$(hex_to_rgb "$ACCENT")

mkdir -p "$HOME/.config/waybar"
cat > "$HOME/.config/waybar/colors.css" << EOF
@define-color background         ${BG};
@define-color foreground         ${color7};
@define-color accent             ${color4};
@define-color accent2            ${color2};
@define-color accent3            ${color6};
@define-color inactive           ${color1};
@define-color warning            ${color3};
@define-color urgent             ${color9:-${color1}};
@define-color accent-transparent rgba(${ACCENT_RGB}, 0.5);
EOF

# Restart waybar and re-register tray icons
pkill -SIGUSR2 waybar || waybar &

# ── 6. wofi and wlogout read colors.css via @import — nothing extra needed ──

# ── 7. Apply GTK theme via pywal (optional, comment out if unwanted) ──
# wal-gtk  # only if you have wal-gtk installed

# ── 8. Reload mako notification colours ──
if command -v makoctl &>/dev/null; then
    mkdir -p "$HOME/.config/mako"
    cat > "$HOME/.config/mako/colors" << EOF
background-color=${BG}
text-color=${color7}
border-color=${ACCENT}
EOF
    makoctl reload 2>/dev/null || true
fi

echo "✓ Theme applied from: $WALLPAPER"
echo "  Accent: $ACCENT | BG: $BG"

# ── Reload kitty colours live ──
pkill -USR1 kitty 2>/dev/null || true


