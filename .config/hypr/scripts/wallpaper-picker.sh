#!/bin/bash
WALLPAPER_DIR="$HOME/Pictures/1BASASS"
CACHE_DIR="$HOME/.cache/wallpaper-picker"
APPLY_SCRIPT="$HOME/.config/hypr/scripts/apply-theme.sh"

mkdir -p "$CACHE_DIR"

# Generate thumbnails
for img in "$WALLPAPER_DIR"/*.jpg "$WALLPAPER_DIR"/*.jpeg "$WALLPAPER_DIR"/*.png "$WALLPAPER_DIR"/*.gif "$WALLPAPER_DIR"/*.webp; do
    [[ -f "$img" ]] || continue
    filename=$(basename "$img")
    thumb="$CACHE_DIR/${filename%.*}.jpg"
    if [[ ! -f "$thumb" ]]; then
        python3 -c "
from PIL import Image
img = Image.open('$img')
img.thumbnail((400, 225), Image.LANCZOS)
bg = Image.new('RGB', (400, 225), (0, 0, 0))
offset = ((400 - img.width) // 2, (225 - img.height) // 2)
bg.paste(img, offset)
bg.save('$thumb', 'JPEG', quality=85)
" 2>/dev/null
    fi
done

# Build menu with full path as entry and thumbnail as icon
MENU=""
for img in "$WALLPAPER_DIR"/*.jpg "$WALLPAPER_DIR"/*.jpeg "$WALLPAPER_DIR"/*.png "$WALLPAPER_DIR"/*.gif "$WALLPAPER_DIR"/*.webp; do
    [[ -f "$img" ]] || continue
    filename=$(basename "$img")
    thumb="$CACHE_DIR/${filename%.*}.jpg"
    [[ -f "$thumb" ]] || continue
    MENU+="$img\0icon\x1f$thumb\n"
done

# Launch rofi and get selected full path
SELECTED=$(printf "%b" "$MENU" | rofi \
    -dmenu \
    -i \
    -show-icons \
    -theme ~/.config/rofi/wallpaper-picker.rasi \
    -p "  Wallpapers" \
    -display-columns 0)

[[ -z "$SELECTED" ]] && exit 0
[[ -f "$SELECTED" ]] && "$APPLY_SCRIPT" "$SELECTED"
