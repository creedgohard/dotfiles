#!/bin/bash

# 1. Terminate Waybar and tray apps to release the DBus locks
killall -9 waybar 2>/dev/null
killall -9 nm-applet 2>/dev/null
killall -9 swaync 2>/dev/null

# 2. Brief pause to ensure the DBus drops the StatusNotifierWatcher claim
sleep 0.5

# 3. Relaunch Waybar first to claim the tray host
waybar &

# 4. Stagger the tray apps so they connect cleanly to the new bar
(sleep 2 && nm-applet --indicator) &
(sleep 2.5 && swaync) &
