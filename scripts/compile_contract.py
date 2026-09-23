#!/usr/bin/env python3
"""Compile v2 facts into H3 prompts. Does not review or approve media."""

import argparse
import json
import os
from pathlib import Path
import sys

from evidence_contract import compile_contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = json.loads(args.contract.read_text(encoding="utf-8"))
        # Recompilation can replace an explicitly selected output, never the input.
        if args.output.resolve() == args.contract.resolve():
            raise ValueError("Choose a separate output to preserve the source observation record")
        # Asset paths belong to the input file, not the process working directory.
        # Rebase only after structural validation, then compile the relocated input.
        result = compile_contract(data)
        if args.contract.resolve().parent != args.output.resolve().parent:
            assets = [result["source"]["media"]]
            assets += [e["asset"] for e in result["evidence"]]
            assets += [a for job in result["jobs"] for a in job["reference_images"]]
            for asset in assets:
                if not Path(asset["path"]).is_absolute():
                    absolute = args.contract.resolve().parent / asset["path"]
                    asset["path"] = os.path.relpath(absolute, args.output.resolve().parent)
            result = compile_contract(result)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"Compiled {len(result['derived']['jobs'])} jobs. Reviews are not granted automatically.")
    if "narrative_review" not in result:
        print("Legacy draft only: narrative confirmation is missing; do not deliver as a confirmed prompt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
