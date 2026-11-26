#!/usr/bin/env bash
# Pack Moodle plugin as antiplagiat.zip (folder name inside ZIP must be "antiplagiat")
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/plagiarism_antiplagiat"
OUT="$ROOT/plagiarism_antiplagiat.zip"
STAGE="$ROOT/.pack_stage"
rm -rf "$STAGE"
mkdir -p "$STAGE/antiplagiat"
cp -R "$SRC/"* "$STAGE/antiplagiat/"
(cd "$STAGE" && zip -r "$OUT" antiplagiat >/dev/null)
rm -rf "$STAGE"
echo "Wrote $OUT"
