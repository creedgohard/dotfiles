#!/bin/bash

# Ensure we use the delimiter defined in your cava config (;)
cava -p ~/.config/cava/config 2>/dev/null | while read -r line; do
    # Remove the semicolons first, then swap numbers for smooth blocks
    echo "$line" | sed 's/;//g;s/0/ /g;s/1/▂/g;s/2/▃/g;s/3/▄/g;s/4/▅/g;s/5/▆/g;s/6/▇/g;s/7/█/g' 2>/dev/null
done 2>/dev/null
