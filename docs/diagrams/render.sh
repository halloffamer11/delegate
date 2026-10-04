#!/bin/sh
# Rebuild the README routing diagram (light and dark SVG) with D2 v0.9.0+.
set -eu
cd "$(dirname "$0")"
for t in light:0 dark:200; do
  d2 --layout elk --elk-padding '[top=32,left=20,bottom=32,right=20]' --elk-nodeNodeBetweenLayers 48 \
    --theme "${t#*:}" --pad 24 routing.d2 "routing-${t%%:*}.svg"
done
