#!/bin/bash
# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃              apply-theme.sh — pywal theme dispatcher        ┃
# ┃   Called by waypaper/awww hook whenever wallpaper changes   ┃
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
#   -n  = skip setting the wallpaper (awww already did it)
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

# ── Define all colour variables first, then derive from them ──
BG="#000000"           # Force true black for OLED
ACCENT="${color4}"     # Primary accent
INACTIVE="${color1}"   # Dark tone for inactive borders
SPLASH="${color6}"     # Bright tone for splash text

# ── Helper functions ──

# hex #RRGGBB → "R,G,B" for KDE color scheme files
hex_to_kde() {
    local hex="${1:1}"
    printf "%d,%d,%d" "0x${hex:0:2}" "0x${hex:2:2}" "0x${hex:4:2}"
}

# hex #RRGGBB → "R, G, B" for CSS rgba()
hex_to_rgb() {
    local hex="${1:1}"
    printf "%d, %d, %d" "0x${hex:0:2}" "0x${hex:2:2}" "0x${hex:4:2}"
}

# Strip the # for hyprctl rgba format (adds ff alpha)
to_rgba() { echo "rgba(${1:1}ff)"; }

# Lighten a hex color toward white by 60% — used for foreground tint
# Must be called after ACCENT is defined
lighten_hex() {
    local hex="${1:1}"
    local r=$((16#${hex:0:2}))
    local g=$((16#${hex:2:2}))
    local b=$((16#${hex:4:2}))
    r=$(( r + (255 - r) * 8 / 10 ))
    g=$(( g + (255 - g) * 8 / 10 ))
    b=$(( b + (255 - b) * 8 / 10 ))
    printf "#%02x%02x%02x" $r $g $b
}

# Now safe to derive — ACCENT is defined above
LIGHT_ACCENT=$(lighten_hex "$ACCENT")
ACCENT_RGBA=$(to_rgba "$ACCENT")
INACTIVE_RGBA=$(to_rgba "$INACTIVE")
BG_RGBA=$(to_rgba "$BG")
ACCENT_RGB=$(hex_to_rgb "$ACCENT")
ACCENT_TRANSPARENT="rgba(${ACCENT:1}00)"

# ── 4. Apply Hyprland border/shadow colours ──
hyprctl --batch \
    "keyword general:col.inactive_border $INACTIVE_RGBA; \
     keyword misc:background_color $BG_RGBA; \
     keyword misc:col.splash $ACCENT_RGBA"
hyprctl keyword general:col.active_border "$ACCENT_RGBA $ACCENT_RGBA 45deg"
hyprctl keyword shadow:color "$ACCENT_RGBA"
hyprctl keyword shadow:range 40
hyprctl keyword shadow:render_power 1
echo "$(date): After hyprctl" >> /tmp/theme-debug.log

# ── 5. Apply GTK theme ──
mkdir -p "$HOME/.config/gtk-3.0" "$HOME/.config/gtk-4.0"
ln -sf "$wal_cache/gtk.css" "$HOME/.config/gtk-3.0/gtk.css"
ln -sf "$wal_cache/gtk.css" "$HOME/.config/gtk-4.0/gtk.css"
# Ensure adw-gtk3-dark is set as the GTK theme (only needs to run once but harmless)
gsettings set org.gnome.desktop.interface gtk-theme 'adw-gtk3-dark' 2>/dev/null || true

# ── 6. Apply Kvantum theme (themes Qt apps that use Kvantum) ──
mkdir -p "$HOME/.config/Kvantum/pywal"
cp "$wal_cache/pywal.kvconfig" "$HOME/.config/Kvantum/pywal/pywal.kvconfig"
cp "$wal_cache/pywal.svg" "$HOME/.config/Kvantum/pywal/pywal.svg"

# ── 7. Generate and apply KDE color scheme ──
# This is what actually themes Dolphin, Klassy, selection highlights,
# scrollbars — anything reading from kdeglobals
KDE_SCHEME_DIR="$HOME/.local/share/color-schemes"
KDE_SCHEME="$KDE_SCHEME_DIR/PywalGenerated.colors"
mkdir -p "$KDE_SCHEME_DIR"

cat > "$KDE_SCHEME" << EOF
[ColorEffects:Disabled]
Color=$(hex_to_kde "$color1")
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Color=$(hex_to_kde "$color1")
ColorAmount=0.025
ColorEffect=2
ContrastAmount=0.1
ContrastEffect=2
Enable=false
IntensityAmount=0
IntensityEffect=0

[Colors:Button]
BackgroundAlternate=$(hex_to_kde "$color1")
BackgroundNormal=$(hex_to_kde "$color1")
DecorationFocus=$(hex_to_kde "$ACCENT")
DecorationHover=$(hex_to_kde "$color6")
ForegroundActive=$(hex_to_kde "$ACCENT")
ForegroundInactive=$(hex_to_kde "$color7")
ForegroundLink=$(hex_to_kde "$color4")
ForegroundNegative=$(hex_to_kde "$color9")
ForegroundNeutral=$(hex_to_kde "$color3")
ForegroundNormal=$(hex_to_kde "$color7")
ForegroundPositive=$(hex_to_kde "$color2")
ForegroundVisited=$(hex_to_kde "$color5")

[Colors:Complementary]
BackgroundAlternate=$(hex_to_kde "$color1")
BackgroundNormal=$(hex_to_kde "$BG")
DecorationFocus=$(hex_to_kde "$ACCENT")
DecorationHover=$(hex_to_kde "$color6")
ForegroundActive=$(hex_to_kde "$ACCENT")
ForegroundInactive=$(hex_to_kde "$color7")
ForegroundLink=$(hex_to_kde "$color4")
ForegroundNegative=$(hex_to_kde "$color9")
ForegroundNeutral=$(hex_to_kde "$color3")
ForegroundNormal=$(hex_to_kde "$color7")
ForegroundPositive=$(hex_to_kde "$color2")
ForegroundVisited=$(hex_to_kde "$color5")

[Colors:Header]
BackgroundAlternate=$(hex_to_kde "$color1")
BackgroundNormal=$(hex_to_kde "$BG")
DecorationFocus=$(hex_to_kde "$ACCENT")
DecorationHover=$(hex_to_kde "$color6")
ForegroundActive=$(hex_to_kde "$ACCENT")
ForegroundInactive=$(hex_to_kde "$color7")
ForegroundLink=$(hex_to_kde "$color4")
ForegroundNegative=$(hex_to_kde "$color9")
ForegroundNeutral=$(hex_to_kde "$color3")
ForegroundNormal=$(hex_to_kde "$color7")
ForegroundPositive=$(hex_to_kde "$color2")
ForegroundVisited=$(hex_to_kde "$color5")

[Colors:Selection]
BackgroundAlternate=$(hex_to_kde "$ACCENT")
BackgroundNormal=$(hex_to_kde "$ACCENT")
DecorationFocus=$(hex_to_kde "$ACCENT")
DecorationHover=$(hex_to_kde "$color6")
ForegroundActive=$(hex_to_kde "$color7")
ForegroundInactive=$(hex_to_kde "$color7")
ForegroundLink=$(hex_to_kde "$color4")
ForegroundNegative=$(hex_to_kde "$color9")
ForegroundNeutral=$(hex_to_kde "$color3")
ForegroundNormal=$(hex_to_kde "$color7")
ForegroundPositive=$(hex_to_kde "$color2")
ForegroundVisited=$(hex_to_kde "$color5")

[Colors:Tooltip]
BackgroundAlternate=$(hex_to_kde "$color1")
BackgroundNormal=$(hex_to_kde "$color1")
DecorationFocus=$(hex_to_kde "$ACCENT")
DecorationHover=$(hex_to_kde "$color6")
ForegroundActive=$(hex_to_kde "$ACCENT")
ForegroundInactive=$(hex_to_kde "$color7")
ForegroundLink=$(hex_to_kde "$color4")
ForegroundNegative=$(hex_to_kde "$color9")
ForegroundNeutral=$(hex_to_kde "$color3")
ForegroundNormal=$(hex_to_kde "$color7")
ForegroundPositive=$(hex_to_kde "$color2")
ForegroundVisited=$(hex_to_kde "$color5")

[Colors:View]
BackgroundAlternate=$(hex_to_kde "$color1")
BackgroundNormal=$(hex_to_kde "$BG")
DecorationFocus=$(hex_to_kde "$ACCENT")
DecorationHover=$(hex_to_kde "$color6")
ForegroundActive=$(hex_to_kde "$ACCENT")
ForegroundInactive=$(hex_to_kde "$color7")
ForegroundLink=$(hex_to_kde "$color4")
ForegroundNegative=$(hex_to_kde "$color9")
ForegroundNeutral=$(hex_to_kde "$color3")
ForegroundNormal=$(hex_to_kde "$color7")
ForegroundPositive=$(hex_to_kde "$color2")
ForegroundVisited=$(hex_to_kde "$color5")

[Colors:Window]
BackgroundAlternate=$(hex_to_kde "$color1")
BackgroundNormal=$(hex_to_kde "$BG")
DecorationFocus=$(hex_to_kde "$ACCENT")
DecorationHover=$(hex_to_kde "$color6")
ForegroundActive=$(hex_to_kde "$ACCENT")
ForegroundInactive=$(hex_to_kde "$color7")
ForegroundLink=$(hex_to_kde "$color4")
ForegroundNegative=$(hex_to_kde "$color9")
ForegroundNeutral=$(hex_to_kde "$color3")
ForegroundNormal=$(hex_to_kde "$color7")
ForegroundPositive=$(hex_to_kde "$color2")
ForegroundVisited=$(hex_to_kde "$color5")

[General]
ColorScheme=PywalGenerated
Name=Pywal Generated
shadeSortColumn=true

[KDE]
contrast=4

[WM]
activeBackground=$(hex_to_kde "$BG")
activeForeground=$(hex_to_kde "$color7")
inactiveBackground=$(hex_to_kde "$color1")
inactiveForeground=$(hex_to_kde "$color7")
activeBlend=$(hex_to_kde "$ACCENT")
inactiveBlend=$(hex_to_kde "$color1")
EOF

# Apply the scheme — updates kdeglobals so Dolphin/Klassy pick it up immediately
plasma-apply-colorscheme PywalGenerated 2>/dev/null || true

# Force AccentColor in kdeglobals to match pywal (overrides the leftover crimson)
kwriteconfig6 --file kdeglobals --group General --key AccentColor "$(hex_to_kde "$color2")"
kwriteconfig6 --file kdeglobals --group General --key LastUsedCustomAccentColor "$(hex_to_kde "$color2")"

# Signal Plasma to reload color scheme live
qdbus-qt6 org.kde.KWin /KWin reconfigure 2>/dev/null || true
dbus-send --session --dest=org.kde.plasmashell /PlasmaShell \
    org.kde.PlasmaShell.refreshCurrentShell 2>/dev/null || true

# Only restart Dolphin if the user actually has it open as a window
# pgrep -x matches exact process name; we check for a window via wmctrl-style
# fallback: check if dolphin has an open file manager window, not just KIO workers
if pgrep -x dolphin > /dev/null; then
    pkill -x dolphin
    sleep 0.5
    dolphin &
fi

# ── 8. Reload Waybar with new colours ──
# foreground uses LIGHT_ACCENT — a 60%-lightened tint of the accent
# that varies per wallpaper, instead of pywal's always-cream color7
mkdir -p "$HOME/.config/waybar"
cat > "$HOME/.config/waybar/colors.css" << EOF
@define-color background         ${BG};
@define-color foreground         ${LIGHT_ACCENT};
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

# ── 9. wofi and wlogout read colors.css via @import — nothing extra needed ──

# ── 10. Reload mako notification colours ──
#if command -v makoctl &>/dev/null; then
   # mkdir -p "$HOME/.config/mako"
    #cat > "$HOME/.config/mako/colors" << EOF
#background-color=${BG}
#text-color=${LIGHT_ACCENT}
#border-color=${ACCENT}
#EOF
   # makoctl reload 2>/dev/null || true
#fi

# ── 11. Sync wpgtk for GTK apps (pavucontrol) ──
if command -v wpg &>/dev/null; then
    wpg -a "$WALLPAPER"
    wpg -s "$(basename "$WALLPAPER")"
fi

# ── 12. Refresh the Volume Popup colors ──
pkill -f volume_popup.py || true

echo "✓ Theme applied from: $WALLPAPER"
echo "  Accent: $ACCENT | Light Accent: $LIGHT_ACCENT | BG: $BG"

# ── Reload kitty colours live ──
pkill -USR1 kitty 2>/dev/null || true

# ── 13. Reload SwayNC CSS live ──
if command -v swaync-client &>/dev/null; then
    # Create a tiny shim so SwayNC knows what LIGHT_ACCENT is
    mkdir -p "$HOME/.cache/swaync"
    echo "@define-color light-accent ${LIGHT_ACCENT};" > "$HOME/.cache/swaync/colors.css"

    swaync-client -rs
fi
