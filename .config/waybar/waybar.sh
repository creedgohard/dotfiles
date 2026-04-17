#!/usr/bin/env sh

killall -q waybar

while pgrep -x waybar >/dev/null; do sleep 1; done

waybar &
sleep 2
pkill easyeffects
sleep 1
easyeffects --gapplication-service &
