#!/usr/bin/env bash
set -euo pipefail

DEFAULT_DSL_NAME="card.dsl.jsonl"

usage() {
  cat <<EOF
Usage: flatten_cards.sh -i <source_dir> -o <output_dir> [-n <dsl_name>] [-h]

Copy all DSL files from subdirectories of <source_dir> into
<output_dir>, prefixing each filename with its source directory name.

Options:
  -i,  --src <dir>       Source directory to search (required)
  -o,  --dst <dir>       Output directory (will be created if missing)
  -n,  --dsl-name <name> DSL file name to search and copy.
                         Default: ${DEFAULT_DSL_NAME}
  -h,  --help            Show this help message and exit

Examples:
  flatten_cards.sh -i datasets/cases-600-mix -o datasets/cards-dsl-flat
  flatten_cards.sh -i datasets/case-600-newSkill-gpt5.5 \\
      -o datasets/cards-m3-flat -n card.MiniMax-M3.dsl.jsonl
EOF
}

SRC=""
DST=""
DSL_NAME="${DEFAULT_DSL_NAME}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    -i|--src)
      [ "$#" -lt 2 ] && { echo "Error: $1 requires an argument" >&2; exit 1; }
      SRC="$2"; shift 2 ;;
    --src=*) SRC="${1#*=}"; shift ;;
    -o|--dst)
      [ "$#" -lt 2 ] && { echo "Error: $1 requires an argument" >&2; exit 1; }
      DST="$2"; shift 2 ;;
    --dst=*) DST="${1#*=}"; shift ;;
    -n|--dsl-name)
      [ "$#" -lt 2 ] && { echo "Error: $1 requires an argument" >&2; exit 1; }
      DSL_NAME="$2"; shift 2 ;;
    --dsl-name=*) DSL_NAME="${1#*=}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Error: unknown option: $1" >&2; usage; exit 1 ;;
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
  name="${dir}.${DSL_NAME}"
  printf '[%4d] %s -> %s\n' "$count" "$f" "$DST/$name"
  cp "$f" "$DST/$name"
  count=$((count + 1))
done < <(find "$SRC" -mindepth 2 -name "$DSL_NAME" -type f -print0)

echo "Copied $count file(s) to $DST"
