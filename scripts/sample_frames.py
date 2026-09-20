#!/usr/bin/env python3
"""Extract requested local frames at actual decoded PTS; extraction is not review."""

import argparse
from bisect import bisect_left
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from evidence_contract import file_digest


def frame_times(frames):
    """Keep decoder indices; normalize display timestamps against the first frame."""
    result = []
    for index, frame in enumerate(frames):
        raw = frame.get("best_effort_timestamp_time")
        try:
            pts = float(raw)
        except (TypeError, ValueError):
            raise ValueError("A decoded frame has no usable PTS; do not substitute average FPS") from None
        if not math.isfinite(pts) or (result and pts <= result[-1][1]):
            raise ValueError("Frame PTS must increase strictly; inspect this media with a capable host")
        result.append((index, pts))
    if not result:
        raise ValueError("No decoded frames found")
    origin = result[0][1]
    return [(index, pts, pts - origin) for index, pts in result]


def choose_frames(timeline, requested):
    times = [row[2] for row in timeline]
    selected = {0, len(timeline) - 1}
    for value in requested:
        if not math.isfinite(value) or value < 0 or value > times[-1]:
            raise ValueError(f"Requested time {value} is outside the decoded frame range")
        right = bisect_left(times, value)
        candidates = [i for i in (right - 1, right) if 0 <= i < len(times)]
        selected.add(min(candidates, key=lambda i: (abs(times[i] - value), i)))
    if len(selected) > 120:
        raise ValueError("Use at most 120 frames per inspection batch")
    return [timeline[i] for i in sorted(selected)]


def extract(video, output, requested):
    ffprobe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise ValueError("FFprobe and FFmpeg must already be installed; no automatic install")
    video = video.resolve()
    if not video.is_file():
        raise ValueError("Input must be a local media file")
    if output.exists():
        raise ValueError("Output directory already exists; use a new batch directory")
    raw = subprocess.run([
        ffprobe, "-v", "error", "-protocol_whitelist", "file", "-select_streams", "V:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time,pkt_duration_time,duration_time", "-of", "json", str(video),
    ], check=True, capture_output=True, text=True, timeout=60)
    decoded = json.loads(raw.stdout).get("frames", [])
    timeline = frame_times(decoded)
    selected = choose_frames(timeline, requested)
    # Hash before and after extraction, so a replaced input cannot silently bind evidence.
    source_hash = file_digest(video)
    output.mkdir(parents=True)
    expression = "+".join(f"eq(n\\,{row[0]})" for row in selected)
    subprocess.run([
        ffmpeg, "-nostdin", "-v", "error", "-protocol_whitelist", "file", "-i", str(video),
        "-map", "0:V:0", "-vf", f"select={expression}", "-fps_mode", "vfr",
        "-frames:v", str(len(selected)), str(output / "frame-%04d.png"),
    ], check=True, capture_output=True, timeout=60)
    if file_digest(video) != source_hash:
        raise ValueError("Source bytes changed during extraction; discard this frame batch")
    actual = sorted(output.glob("frame-*.png"))
    if len(actual) != len(selected):
        raise ValueError("Decoded frame count differs from selected PTS; do not use this batch")
    evidence = []
    for index, (row, path) in enumerate(zip(selected, actual), 1):
        evidence.append({
            "id": f"EV{index:03}", "kind": "frame", "range_s": [row[2], row[2]],
            "source_sha256": source_hash, "asset": {"path": path.name, "sha256": file_digest(path)},
            "decoder_index": row[0], "pts_s": row[1], "visual_content_reviewed": False,
        })
    final_duration = decoded[-1].get("duration_time", decoded[-1].get("pkt_duration_time"))
    try:
        final_duration = float(final_duration)
        if not math.isfinite(final_duration) or final_duration <= 0:
            final_duration = None
    except (TypeError, ValueError):
        final_duration = None
    manifest = {
        "source_sha256": source_hash, "time_origin_pts_s": timeline[0][1],
        "last_frame_time_s": timeline[-1][2],
        "visual_end_s": timeline[-1][2] + final_duration if final_duration is not None else None,
        "requested_times_s": requested, "evidence": evidence,
        "visual_content_reviewed": False, "audio_content_reviewed": False,
        "notes": "Actual decoded PTS. First and last frames included. Sampling is not continuous viewing or semantic review. Paths are relative to this manifest; rebase them if moving evidence into a contract.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--at", type=float, nargs="*", default=[], help="Requested source seconds; nearest actual PTS is recorded")
    args = parser.parse_args()
    try:
        manifest = extract(args.video, args.output, args.at)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # Decoder stderr can contain private paths/metadata. Keep diagnostics local and brief.
        print(f"Frame extraction failed ({type(exc).__name__}); check local input, timestamps and output directory.", file=sys.stderr)
        return 1
    print(f"Extracted {len(manifest['evidence'])} frames. Read manifest.json for actual PTS; no content has been reviewed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
