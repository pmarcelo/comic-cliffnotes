#!/bin/bash

# 1. Find the Tachimanga sandbox automatically
echo "🔍 Searching for Tachimanga sandbox..."
# We search for 'downloads2' within the Containers directory
TARGET_DIR=$(find ~/Library/Containers -name "downloads2" -type d 2>/dev/null | grep "Tachidesk")

if [ -z "$TARGET_DIR" ]; then
    echo "❌ Error: Could not find the Tachimanga downloads folder."
    exit 1
fi

echo "✅ Found it: $TARGET_DIR"

# 2. Ask for a series name
# This will be used as the filename for your zip
read -p "📝 Enter the Series Name (e.g., SoloLeveling): " SERIES_NAME

# 3. Identify and Zip only non-empty content
ZIP_NAME="${SERIES_NAME}_batch.zip"
DESKTOP_PATH="$HOME/Desktop/$ZIP_NAME"

echo "📦 Filtering out empty directories..."

# Navigate to the target so the internal zip paths are clean (no absolute paths)
cd "$TARGET_DIR" || exit

# Find top-level directories (-maxdepth 1) that are NOT empty
# We use mapfile to safely handle folder names with spaces
mapfile -t DIRS_TO_ZIP < <(find . -mindepth 1 -maxdepth 1 -type d -not -empty)

# Safety check: If no folders have content, stop here.
if [ ${#DIRS_TO_ZIP[@]} -eq 0 ]; then
    echo "⚠️  No folders with actual content found. Is the download finished?"
    exit 1
fi

echo "🗜️  Zipping ${#DIRS_TO_ZIP[@]} folder(s) to $DESKTOP_PATH..."
# The "${DIRS_TO_ZIP[@]}" expansion ensures each folder is treated as a single argument
zip -r "$DESKTOP_PATH" "${DIRS_TO_ZIP[@]}"

echo "------------------------------------------------"
echo "🚀 SUCCESS: '$ZIP_NAME' created on Desktop."
echo "📂 Contents: ${#DIRS_TO_ZIP[@]} Series/Sources included."
echo "🔗 Next Step: Upload to your Google Drive 'Inbound' folder."