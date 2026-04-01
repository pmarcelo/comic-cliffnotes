#!/bin/bash

# 1. Find the Tachimanga sandbox automatically
echo "🔍 Searching for Tachimanga sandbox..."
TARGET_DIR=$(find ~/Library/Containers -name "downloads2" -type d 2>/dev/null | grep "Tachidesk")

if [ -z "$TARGET_DIR" ]; then
    echo "❌ Error: Could not find the Tachimanga downloads folder."
    exit 1
fi

echo "✅ Found it: $TARGET_DIR"

# 2. Ask for a series name
read -p "📝 Enter the Series Name (e.g., SoloLeveling): " SERIES_NAME
ZIP_NAME="${SERIES_NAME}_batch.zip"
DESKTOP_PATH="$HOME/Desktop/$ZIP_NAME"

# 3. Identify and Zip only non-empty content (excluding hidden files)
echo "📦 Filtering out empty directories (ignoring .DS_Store)..."

cd "$TARGET_DIR" || exit

# LOGIC: Find directories that contain at least one file that is NOT .DS_Store
DIRS_TO_ZIP=()
for dir in */; do
    # Remove trailing slash for the array
    dir_clean="${dir%/}"
    
    # Count files in directory excluding .DS_Store and hidden files
    # We use 'find' to look for files (-type f) and exclude .DS_Store
    content_count=$(find "$dir_clean" -type f ! -name ".DS_Store" ! -name ".*" | wc -l)
    
    if [ "$content_count" -gt 0 ]; then
        DIRS_TO_ZIP+=("$dir_clean")
    fi
done

# Safety check
if [ ${#DIRS_TO_ZIP[@]} -eq 0 ]; then
    echo "⚠️  No folders with actual content found. (Hidden system files were ignored)."
    exit 1
fi

echo "🗜️  Zipping ${#DIRS_TO_ZIP[@]} folder(s) to $DESKTOP_PATH..."

# -q (Quiet mode): Silences the "adding:" lines
# -x "*/.DS_Store": Explicitly excludes .DS_Store from the final zip archive
zip -rq "$DESKTOP_PATH" "${DIRS_TO_ZIP[@]}" -x "*/.DS_Store" "*/.*"

echo "------------------------------------------------"
echo "🚀 SUCCESS: '$ZIP_NAME' created on Desktop."
echo "📂 Contents: ${#DIRS_TO_ZIP[@]} Series/Sources included."
echo "🔗 Next Step: Upload to your Google Drive 'Inbound' folder."