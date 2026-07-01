#!/usr/bin/env python3
import argparse
import json
import random
import re
import sys
from pathlib import Path

DEFAULT_INPUT = "datasets/Scenario/codex-gpt-5.5"
SAMPLE_NAME = "task.request.json"
STRATUM_RE = re.compile(r"^Case-(\d+)-\d+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stratified train/test split of chat-completion request samples."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path(DEFAULT_INPUT),
        help=f"Root directory containing Case-aa-bbbb subdirectories. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for train.jsonl / test.jsonl. Defaults to --input.",
    )
    parser.add_argument(
        "-r",
        "--ratio",
        type=float,
        default=0.1,
        help="Test-set ratio in [0,1]. Default: 0.1",
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility. Default: 42",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print split statistics without writing files.",
    )
    return parser.parse_args()


def load_samples(root: Path) -> dict[str, list[Path]]:
    """Group sample paths by stratum key (the 'aa' part of Case-aa-bbbb)."""
    strata: dict[str, list[Path]] = {}
    missing: list[Path] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        m = STRATUM_RE.match(entry.name)
        if not m:
            continue
        sample = entry / SAMPLE_NAME
        if not sample.is_file():
            missing.append(sample)
            continue
        strata.setdefault(m.group(1), []).append(sample)

    if missing:
        preview = ", ".join(str(p) for p in missing[:5])
        more = f" ... (+{len(missing) - 5} more)" if len(missing) > 5 else ""
        print(f"warn: {len(missing)} missing {SAMPLE_NAME} files: {preview}{more}", file=sys.stderr)
    if not strata:
        raise FileNotFoundError(f"No Case-aa-bbbb samples found under {root}")
    return strata


def split_stratum(paths: list[Path], ratio: float, rng: random.Random) -> tuple[list[Path], list[Path]]:
    n = len(paths)
    shuffled = paths[:]
    rng.shuffle(shuffled)
    n_test = round(n * ratio)
    n_test = max(1, min(n_test, n - 1))
    return shuffled[n_test:], shuffled[:n_test]


def main() -> int:
    args = parse_args()

    if not 0.0 < args.ratio < 1.0:
        print(f"error: --ratio must be in (0, 1), got {args.ratio}", file=sys.stderr)
        return 2
    if not args.input.is_dir():
        print(f"error: input dir not found: {args.input}", file=sys.stderr)
        return 2

    output_dir = args.output_dir or args.input
    rng = random.Random(args.seed)

    try:
        strata = load_samples(args.input)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    train_paths: list[Path] = []
    test_paths: list[Path] = []

    label_w = max(len(f"Case-{k}") for k in strata)
    col_w = max(label_w, len("stratum"))
    print(
        f"{'stratum':<{col_w}}  {'total':>5}  {'train':>5}  {'test':>5}",
        file=sys.stderr,
    )
    print("-" * (col_w + 24), file=sys.stderr)
    for stratum in sorted(strata):
        paths = sorted(strata[stratum])
        train, test = split_stratum(paths, args.ratio, rng)
        train_paths.extend(train)
        test_paths.extend(test)
        print(
            f"{'Case-' + stratum:<{col_w}}  {len(paths):>5}  {len(train):>5}  {len(test):>5}",
            file=sys.stderr,
        )
    print("-" * (col_w + 24), file=sys.stderr)
    total = len(train_paths) + len(test_paths)
    actual_ratio = len(test_paths) / total if total else 0.0
    print(
        f"{'TOTAL':<{col_w}}  {total:>5}  {len(train_paths):>5}  {len(test_paths):>5}  (test={actual_ratio:.1%})",
        file=sys.stderr,
    )

    if args.dry_run:
        print("dry-run: no files written.", file=sys.stderr)
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train.jsonl"
    test_path = output_dir / "test.jsonl"

    for out_file, paths in ((train_path, train_paths), (test_path, test_paths)):
        with out_file.open("w", encoding="utf-8") as fh:
            for p in paths:
                with p.open("r", encoding="utf-8") as src:
                    data = json.load(src)
                fh.write(json.dumps(data, ensure_ascii=False))
                fh.write("\n")
        print(f"wrote {len(paths)} samples -> {out_file}", file=sys.stderr)

    validate_path = output_dir / "validate.json"
    validate_entries = []
    for p in test_paths:
        with p.open("r", encoding="utf-8") as src:
            data = json.load(src)
        keep = [m for m in data["messages"] if m["role"] in ("system", "user")]
        user_msgs = [m for m in keep if m["role"] == "user"]
        if not user_msgs:
            raise ValueError(f"no user message in {p}")
        validate_entries.append({"name": user_msgs[0]["content"], "message": keep})
    with validate_path.open("w", encoding="utf-8") as fh:
        json.dump(validate_entries, fh, ensure_ascii=False, indent=2)
    print(f"wrote {len(validate_entries)} samples -> {validate_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
