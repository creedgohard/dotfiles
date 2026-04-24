#!/bin/bash

# 1. Kill any existing portal processes to prevent "portal lag"
killall -9 xdg-desktop-portal-hyprland
killall -9 xdg-desktop-portal-gtk
killall -9 xdg-desktop-portal

# 2. Update the environment for Systemd and DBus
dbus-update-activation-environment --systemd WAYLAND_DISPLAY XDG_CURRENT_DESKTOP
systemctl --user import-environment WAYLAND_DISPLAY XDG_CURRENT_DESKTOP

# 3. Restart the portals cleanly
/usr/lib/xdg-desktop-portal-hyprland &
sleep 2
/usr/lib/xdg-desktop-portal &
