#!/usr/bin/env python3
"""Validate a declared reverse-video contract; never claim semantic/video QA."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys

FIELDS = ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"]
I2VA_PREFIX = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)


def number(value: object) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def validate_prompt(prompt: str, mode: str, duration: float, audio_omitted: bool) -> list[str]:
    errors: list[str] = []
    headers = list(re.finditer(r"^([a-z][a-z0-9_]*)\s*:", prompt, re.M))
    if [m.group(1) for m in headers] != FIELDS:
        return ["H3 fields must appear exactly once in the prescribed three-field order"]
    sections = {}
    for i, header in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(prompt)
        sections[header.group(1)] = prompt[header.end():end].strip()
    if any(not value for value in sections.values()):
        errors.append("H3 fields must not be empty")
    main = sections[FIELDS[0]]
    shots = list(re.finditer(r"\[Shot (\d+)\]", main))
    if not shots or [int(s.group(1)) for s in shots] != list(range(1, len(shots) + 1)):
        errors.append("H3 shot labels must start at 1 and be consecutive")
    if not main.startswith("[Shot 1]"):
        errors.append("H3 main description must begin with [Shot 1]")
    if re.match(r"\[Shot 1\]\s+At\s+\d", main):
        errors.append("The first shot must not begin with a cut timestamp")
    last_cut = 0.0
    for shot in shots[1:]:
        tail = main[shot.end():]
        stamp = re.match(r"\s+At (\d{2,}):([0-5]\d)\.(\d{3}),", tail)
        if not stamp:
            errors.append("Later shots require At MM:SS.mmm, cut timestamps")
            continue
        moment = int(stamp[1]) * 60 + int(stamp[2]) + int(stamp[3]) / 1000
        if not last_cut < moment < duration:
            errors.append("Cut times must increase strictly within the job duration")
        last_cut = moment
    prefix = prompt[:headers[0].start()]
    if mode == "T2VA":
        if prefix:
            errors.append("T2VA must begin directly with the three fields")
    elif mode == "I2VA":
        if prefix != I2VA_PREFIX + "\n\n":
            errors.append("I2VA requires the exact first-frame alignment line and a blank line")
        if len(shots) != 1:
            errors.append("This per-shot I2VA contract requires one continuous target shot")
    elif mode == "FL2VA":
        expected = (
            "How the reference pictures align with the target video — Picture 1 (from Shot 1) "
            "aligns with the 0.00-second mark of the target video; "
            f"Picture 2 (from Shot {len(shots)}) aligns with the {duration:.2f}-second mark "
            "of the target video.\n\n"
        )
        if prefix != expected:
            errors.append("FL2VA frame alignment must match final shot and job duration")
        if len(shots) != 1:
            errors.append("This per-shot FL2VA contract requires one continuous target shot")
    else:
        errors.append("Unsupported engine mode; use T2VA, I2VA or FL2VA")
    if audio_omitted and any(sections[field] != "N/A" for field in FIELDS[1:]):
        errors.append("Unverified or excluded audio fields must be N/A unless explicitly user-directed")
    picture_numbers = {int(n) for n in re.findall(r"<?Picture (\d+)>?", prompt)}
    allowed = {1} if mode == "I2VA" else {1, 2} if mode == "FL2VA" else set()
    if picture_numbers != allowed:
        errors.append("Picture references do not match the selected engine mode")
    return errors


def validate(data: object, base_dir: Path | None = None, *, require_reviewed: bool = False, verify_local_media: bool = False) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Contract must be a JSON object"]
    if data.get("schema_version") == 2:
        from evidence_contract import validate_v2
        return validate_v2(data, base_dir, require_reviewed, verify_local_media)
    if require_reviewed or verify_local_media:
        return ["Legacy v1 is a format-only draft; use v2 evidence and reviews for the strict gate"]
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    status = data.get("analysis_status")
    if status not in ("COMPLETE", "PARTIAL", "BLOCKED"):
        errors.append("Invalid analysis_status")
    if status == "BLOCKED":
        if data.get("jobs") or data.get("segments") or data.get("generation_ready"):
            errors.append("BLOCKED cannot contain a complete timeline or generation jobs")
        if not data.get("missing_capability") or not data.get("required_input_or_capability"):
            errors.append("BLOCKED must explain missing capability and required input")
        return errors
    source = data.get("source")
    if not isinstance(source, dict):
        return errors + ["source must be an object"]
    duration = source.get("duration_s")
    if not number(duration) or duration <= 0:
        return errors + ["source.duration_s must be a finite positive number"]
    precision = source.get("timestamp_precision_s")
    if not number(precision) or precision <= 0:
        errors.append("Declare a finite positive timestamp_precision_s")
    if source.get("visual_access") != "full":
        errors.append("Full-video contracts require full visual access; otherwise use BLOCKED")
    audio = source.get("audio_status")
    if audio not in ("verified", "no_track", "unavailable", "not_requested"):
        errors.append("Invalid audio_status")
    if status == "COMPLETE" and audio == "unavailable":
        errors.append("Unverified requested audio requires PARTIAL")
    intent = data.get("intent")
    deviations = data.get("intentional_deviations")
    if intent not in ("faithful", "adapted"):
        errors.append("intent must be faithful or adapted")
    if not isinstance(deviations, list) or any(not isinstance(x, str) or not x.strip() for x in deviations):
        errors.append("intentional_deviations must be a list of nonempty strings")
    elif (intent == "adapted" and not deviations) or (intent == "faithful" and deviations):
        errors.append("Adaptations must be declared; faithful output must not list deviations")
    user_audio = data.get("user_audio_request", "")
    if not isinstance(user_audio, str) or (user_audio and intent != "adapted"):
        errors.append("User-directed new audio requires an adapted contract and a text request")
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, dict):
        return errors + ["capabilities must be an object"]
    max_duration = capabilities.get("max_job_duration_s")
    if max_duration is not None and (not number(max_duration) or max_duration <= 0):
        errors.append("max_job_duration_s must be positive or null")
        max_duration = None
    if capabilities.get("end_frames") is not None and type(capabilities["end_frames"]) is not bool:
        errors.append("end_frames must be true, false or null")
    ready = data.get("generation_ready")
    if not isinstance(ready, bool):
        errors.append("generation_ready must be boolean")
    if ready:
        errors.append("Legacy v1 cannot claim generation readiness; use the v2 evidence gate")
    if ready and (max_duration is None or capabilities.get("duration_verified") is not True):
        errors.append("Generation readiness requires a verified platform duration limit")
    if data.get("fixture") is True and ready:
        errors.append("A synthetic fixture cannot claim generation readiness")
    segments = data.get("segments")
    if not isinstance(segments, list) or not segments:
        return errors + ["segments must contain the complete source timeline"]
    ids: set[str] = set()
    shot_ids: set[str] = set()
    cursor = 0.0
    for index, segment in enumerate(segments):
        label = f"segments[{index}]"
        if not isinstance(segment, dict):
            errors.append(f"{label} must be an object")
            continue
        sid = segment.get("id")
        if not isinstance(sid, str) or not sid or sid in ids:
            errors.append(f"{label} requires a unique string id")
        else:
            ids.add(sid)
        start, end = segment.get("start_s"), segment.get("end_s")
        if not number(start) or not number(end) or not 0 <= start < end <= duration + 1e-6:
            errors.append(f"{label} has invalid or out-of-range times")
            continue
        if abs(start - cursor) > 1e-6:
            errors.append(f"{label} leaves a gap or overlaps the previous segment")
        cursor = end
        kind = segment.get("kind")
        if kind == "transition":
            if not segment.get("transition"):
                errors.append(f"{label} must name its transition")
            continue
        if kind != "shot":
            errors.append(f"{label} kind must be shot or transition")
            continue
        if isinstance(sid, str):
            shot_ids.add(sid)
        for field in ("initial_state", "end_state", "motion_prompt", "reference_prompt"):
            if not isinstance(segment.get(field), str) or not segment[field].strip():
                errors.append(f"{label} requires {field}")
        frame = segment.get("reference_frame_s")
        if not number(frame) or not start <= frame < end:
            errors.append(f"{label} reference frame must lie inside its source shot")
        elif frame > start and not segment.get("opening_handling"):
            errors.append(f"{label} must explain how the earlier opening is retained")
        route = segment.get("i2v_type")
        if route not in ("I2V-A", "I2V-B"):
            errors.append(f"{label} requires I2V-A or I2V-B")
        if route == "I2V-B":
            if capabilities.get("end_frames") is not True:
                errors.append(f"{label} cannot use end frames without confirmed support")
            end_frame = segment.get("end_frame_s")
            if not number(end_frame) or not number(frame) or not frame < end_frame < end:
                errors.append(f"{label} end frame must be an actual later frame within the shot")
            if not isinstance(segment.get("end_frame_prompt"), str) or not segment["end_frame_prompt"].strip():
                errors.append(f"{label} requires an end_frame_prompt")
    if abs(cursor - duration) > 1e-6:
        errors.append("Source timeline does not cover the full visual duration")
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        return errors + ["jobs must be a nonempty list for this delivery contract"]
    job_ids: set[str] = set()
    covered: set[str] = set()
    for index, job in enumerate(jobs):
        label = f"jobs[{index}]"
        if not isinstance(job, dict):
            errors.append(f"{label} must be an object")
            continue
        jid = job.get("id")
        if not isinstance(jid, str) or not jid or jid in job_ids:
            errors.append(f"{label} requires a unique string id")
        else:
            job_ids.add(jid)
        length = job.get("duration_s")
        if not number(length) or length <= 0:
            errors.append(f"{label} duration must be positive and finite")
            continue
        if max_duration is not None and length > max_duration + 1e-6:
            errors.append(f"{label} exceeds the declared platform duration limit")
        source_shots = job.get("source_shots")
        if not isinstance(source_shots, list) or not source_shots or any(not isinstance(s, str) or s not in shot_ids for s in source_shots):
            errors.append(f"{label} references unknown or missing source shots")
            source_shots = []
        covered.update(source_shots)
        mode = job.get("mode")
        if mode in ("I2VA", "FL2VA") and len(source_shots) > 1 and intent != "adapted":
            errors.append(f"{label} cannot combine real source cuts into faithful I2V")
        if mode == "FL2VA" and capabilities.get("end_frames") is not True:
            errors.append(f"{label} FL2VA requires confirmed end-frame support")
        images = job.get("reference_images")
        required_count = 1 if mode == "I2VA" else 2 if mode == "FL2VA" else 0
        if not isinstance(images, list) or len(images) != required_count or any(not isinstance(p, str) or not p for p in images):
            errors.append(f"{label} reference_images must contain {required_count} path(s)")
        elif ready:
            if base_dir is None:
                errors.append(f"{label} readiness needs a base directory to check image files")
            else:
                for raw in images:
                    path = base_dir / raw
                    if not path.is_file() or path.stat().st_size == 0:
                        errors.append(f"{label} missing local reference image: {raw}")
        prompt = job.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append(f"{label} requires a nonempty H3 prompt")
        else:
            errors.extend(f"{label}: {e}" for e in validate_prompt(prompt, mode, length, audio != "verified" and not user_audio))
    if shot_ids - covered:
        errors.append("Some source shots have no generation job; omissions must not be silent")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--require-reviewed", action="store_true", help="Require current media and semantic review declarations")
    parser.add_argument("--verify-local-media", action="store_true", help="Check source, evidence and reference asset hashes")
    args = parser.parse_args()
    try:
        data = json.loads(args.contract.read_text(encoding="utf-8"))
        errors = validate(data, args.contract.resolve().parent, require_reviewed=args.require_reviewed, verify_local_media=args.verify_local_media)
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("Contract check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Contract check passed. Structural checks only; video facts and generation quality are unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
