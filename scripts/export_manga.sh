#!/bin/bash

# 1. Find the Tachidesk downloads folder automatically
echo "🔍 Searching for Tachimanga sandbox..."
TARGET_DIR=$(find ~/Library/Containers -name "downloads2" -type d 2>/dev/null | grep "Tachidesk")

if [ -z "$TARGET_DIR" ]; then
    echo "❌ Error: Could not find the Tachimanga downloads folder."
    exit 1
fi

echo "✅ Found it: $TARGET_DIR"

# 2. Ask for a series name
read -p "📝 Enter the Series Name (e.g., SoloLeveling): " SERIES_NAME

# 3. Zip it up
ZIP_NAME="${SERIES_NAME}_batch.zip"
echo "📦 Zipping series to Desktop/$ZIP_NAME..."

# We cd into the folder so the zip structure is clean
cd "$TARGET_DIR"
zip -r ~/Desktop/"$ZIP_NAME" .

echo "🚀 Done! Upload '$ZIP_NAME' to Google Drive now."