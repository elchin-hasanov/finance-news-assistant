#!/bin/bash
# Generate icon PNGs from SVG using ImageMagick or similar
# Run: ./generate-icons.sh

# If you have ImageMagick installed:
# convert -background none -resize 16x16 icon.svg icon16.png
# convert -background none -resize 32x32 icon.svg icon32.png
# convert -background none -resize 48x48 icon.svg icon48.png
# convert -background none -resize 128x128 icon.svg icon128.png

# Or use an online converter like https://cloudconvert.com/svg-to-png

echo "To generate icons, use an SVG to PNG converter with these sizes:"
echo "  - 16x16 -> icon16.png"
echo "  - 32x32 -> icon32.png"
echo "  - 48x48 -> icon48.png"
echo "  - 128x128 -> icon128.png"
echo ""
echo "Online tools: https://cloudconvert.com/svg-to-png"
echo "Or with ImageMagick: convert -background none -resize 128x128 icon.svg icon128.png"
