#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: flatten_cards.sh -i <source_dir> -o <output_dir> [-h]

Copy all card.dsl.jsonl files from subdirectories of <source_dir> into
<output_dir>, prefixing each filename with its source directory name.

Options:
  -i  Source directory to search (required)
  -o  Output directory (will be created if missing)
  -h  Show this help message and exit

Example:
  flatten_cards.sh -i datasets/cases-600-mix -o datasets/cards-dsl-flat
EOF
}

SRC=""
DST=""

while getopts ":i:o:h" opt; do
  case "$opt" in
    i) SRC="$OPTARG" ;;
    o) DST="$OPTARG" ;;
    h) usage; exit 0 ;;
    \?) echo "Error: unknown option -$OPTARG" >&2; usage; exit 1 ;;
    :)  echo "Error: option -$OPTARG requires an argument" >&2; usage; exit 1 ;;
  esac
done

if [ -z "$SRC" ] || [ -z "$DST" ]; then
  echo "Error: both -i and -o are required" >&2
  usage
  exit 1
fi

if [ ! -d "$SRC" ]; then
  echo "Error: source directory does not exist: $SRC" >&2
  exit 1
fi

mkdir -p "$DST"

count=0
while IFS= read -r -d '' f; do
  dir=$(basename "$(dirname "$f")")
  name="${dir}.card.dsl.jsonl"
  printf '[%4d] %s -> %s\n' "$count" "$f" "$DST/$name"
  cp "$f" "$DST/$name"
  count=$((count + 1))
done < <(find "$SRC" -mindepth 2 -name "card.dsl.jsonl" -type f -print0)

echo "Copied $count file(s) to $DST"
