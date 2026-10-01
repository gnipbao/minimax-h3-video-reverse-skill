#!/usr/bin/env python3
"""Read-only H3 text checks; source cuts and adaptation are caller declarations."""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_contract import number, validate_prompt


def positive_duration(value: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("duration must be a finite positive number") from exc
    if not number(result) or result <= 0:
        raise argparse.ArgumentTypeError("duration must be a finite positive number")
    return result


def positive_count(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("source-shot-count must be a positive integer") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("source-shot-count must be a positive integer")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="UTF-8 H3 prompt to check; never modified")
    parser.add_argument("--mode", choices=("T2VA", "I2VA", "FL2VA"), required=True)
    parser.add_argument("--duration", type=positive_duration, required=True, help="target Job duration in seconds")
    parser.add_argument("--source-shot-count", type=positive_count, required=True,
                        help="real source shots covered by this Job, established through observation")
    parser.add_argument("--audio-omitted", action="store_true",
                        help="require both audio fields to be N/A")
    parser.add_argument("--continuous-adaptation", action="store_true",
                        help="declare existing explicit user authorization and a recorded adaptation from source cuts to one continuous target shot")
    args = parser.parse_args(argv)
    try:
        prompt = args.file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        parser.error(f"cannot read UTF-8 prompt: {exc}")

    errors = validate_prompt(prompt, args.mode, args.duration, args.audio_omitted)
    if args.mode in {"I2VA", "FL2VA"} and args.source_shot_count > 1 and not args.continuous_adaptation:
        errors.append("Image-to-video Job covers multiple declared source shots; use separate Jobs or an explicitly authorized continuous adaptation")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print("Prompt format and declared source-cut gate passed.")
    print("This does not verify media interpretation, observed cut counts, user authorization, platform capabilities or generated-video similarity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
