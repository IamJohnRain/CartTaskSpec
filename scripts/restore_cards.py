import argparse
import os
import re
import shutil


def parse_args():
    parser = argparse.ArgumentParser(
        prog="restore_cards.py",
        description=(
            "Restore card DSL images from a flat staging directory into a "
            "per-card directory layout.\n\n"
            "Source layout (flat):\n"
            "  <src>/<card_name>_card_dsl.png\n\n"
            "Target layout (per-card):\n"
            "  <dst>/<card_name>/card.dsl.png"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-i", "--input",
        dest="src",
        metavar="SRC",
        default="datasets/tmp",
        help="Source directory containing flat <name>_card_dsl.png files (default: datasets/tmp)",
    )
    parser.add_argument(
        "-o", "--output",
        dest="dst",
        metavar="DST",
        default="datasets/cases-100/codex-gpt-5.5",
        help="Target root directory; each card is placed in <dst>/<name>/card.dsl.png (default: datasets/cases-100/codex-gpt-5.5)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    src_path = args.src
    dst_path = args.dst

    if not os.path.isdir(src_path):
        print(f"Error: source directory not found: {src_path}")
        raise SystemExit(1)

    if not os.path.isdir(dst_path):
        print(f"Warning: destination directory not found: {dst_path}. Skipping move.")
        return

    moved = 0
    for i, filename in enumerate(os.listdir(src_path)):
        if not filename.endswith(".png"):
            continue
        if "_card_dsl.png" not in filename:
            print(f"[{i}] Skip (not a _card_dsl.png): {filename}")
            continue

        src_file = os.path.join(src_path, filename)
        sub_dir = re.sub(r"^(.+)_card_dsl\.png$", r"\1", filename)
        dst_file = os.path.join(dst_path, sub_dir, "card.dsl.png")

        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
        print(f"[{i}] Moving {src_file} -> {dst_file}")
        shutil.move(src_file, dst_file)
        moved += 1

    print(f"\nDone. Moved {moved} file(s) from {src_path} to {dst_path}.")


if __name__ == "__main__":
    main()
