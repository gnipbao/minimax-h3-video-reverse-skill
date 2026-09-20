#!/usr/bin/env python3
"""Read local media metadata with FFprobe; does not inspect visuals or listen."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys


def numeric(value: object) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def summarize(data: dict) -> dict:
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        raise ValueError("No video stream found")
    duration = numeric(video.get("duration"))
    start = numeric(video.get("start_time"))
    rotation = next((s.get("rotation") for s in video.get("side_data_list", []) if "rotation" in s), None)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return {
        "video_stream_index": video.get("index"),
        "width": video.get("width"),
        "height": video.get("height"),
        "sample_aspect_ratio": video.get("sample_aspect_ratio"),
        "display_aspect_ratio": video.get("display_aspect_ratio"),
        "rotation_degrees": rotation,
        "video_start_s": start,
        "video_duration_s": duration,
        "container_duration_s": numeric(data.get("format", {}).get("duration")),
        "avg_frame_rate": video.get("avg_frame_rate"),
        "nominal_frame_rate": video.get("r_frame_rate"),
        "time_base": video.get("time_base"),
        "audio_track_present": has_audio,
        "audio_status": "unavailable" if has_audio else "no_track",
        "visual_content_reviewed": False,
        "audio_content_reviewed": False,
        "last_frame_time_s": None,
        "notes": [
            "Stream metadata only; duration is not a decoded end-frame measurement.",
            "Frame rates do not prove CFR/VFR; use actual PTS for frame-level timing.",
            "Missing stream duration remains unknown; container audio may extend beyond video.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    args = parser.parse_args()
    if not args.video.is_file():
        parser.error("Input must be an existing local media file; URLs are not downloaded")
    executable = shutil.which("ffprobe")
    if not executable:
        parser.error("FFprobe is not installed; install it explicitly or use your host's media tools")
    try:
        path = args.video.resolve()
        # No shell and no network protocols: untrusted media cannot fetch nested remote URLs.
        result = subprocess.run(
            [executable, "-v", "error", "-protocol_whitelist", "file", "-show_streams", "-show_format", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60, check=True,
        )
        summary = summarize(json.loads(result.stdout))
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        summary["sha256"] = digest.hexdigest()
        # No absolute source path, tags, account names or private text metadata in the report.
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Media probe failed: {type(exc).__name__}. Check the local file and FFprobe support.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
