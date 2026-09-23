#!/usr/bin/env python3
"""H3 v2: checked evidence -> canonical facts -> deterministic delivery.

Checks declarations and byte identity, never proves what a frame means.
No network, model calls, installs or automatic review approvals.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from validate_contract import I2VA_PREFIX, number, validate_prompt

VERSION = "h3-facts-2.1"
KINDS = {"identity", "initial", "state", "action", "camera", "ending", "transition", "soundscape", "music"}
AUDIO = {"soundscape", "music"}
TEMPORAL = {"action", "camera", "transition"}
SHA = re.compile(r"^[a-f0-9]{64}$")


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def span(value, duration):
    return (isinstance(value, list) and len(value) == 2
            and all(number(x) for x in value) and 0 <= value[0] <= value[1] <= duration
            and value[0] < duration)


def index_rows(value, label, errors):
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return {}
    result = {}
    for row in value:
        if not isinstance(row, dict) or not nonempty(row.get("id")) or row["id"] in result:
            errors.append(f"{label} requires objects with unique nonempty IDs")
        else:
            result[row["id"]] = row
    return result


def asset_ok(value):
    return (isinstance(value, dict) and nonempty(value.get("path"))
            and "://" not in value["path"]
            and isinstance(value.get("sha256"), str) and SHA.fullmatch(value["sha256"]) is not None)


def digest(data):
    inputs = {k: v for k, v in data.items() if k not in {"derived", "compilation", "reviews"}}
    raw = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def narrative_digest(data):
    """Bind a human-readable interpretation, not its delivery language or mode.

    The caller must keep the summary aligned with changed facts. This hash
    cannot read a conversation, infer consent or judge narrative fidelity.
    """
    review = data["narrative_review"]
    source = data["source"]
    scope = {
        "source_sha256": source["media"]["sha256"],
        "source_duration_s": source["duration_s"],
        "intent": data["intent"],
        "intentional_deviations": data["intentional_deviations"],
        **{key: review[key] for key in ("status", "revision", "summary", "target", "open_questions")},
    }
    raw = json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def narrative_review_errors(data, required=False):
    """Check declarations only. Never synthesize a user's confirmation."""
    if "narrative_review" not in data:
        return ["A current narrative_review is required; legacy input is draft-only"] if required else []
    review = data["narrative_review"]
    if not isinstance(review, dict):
        return ["narrative_review must be an object, not an implicit waiver"]
    errors = []
    status = review.get("status")
    if status not in ("pending", "confirmed", "waived"):
        errors.append("Narrative status must be pending, confirmed or waived")
    if type(review.get("revision")) is not int or review["revision"] < 1:
        errors.append("Narrative revision must be a positive integer")
    if not nonempty(review.get("summary")) or not nonempty(review.get("target")):
        errors.append("Narrative review needs a concrete summary and target")
    questions = review.get("open_questions")
    if not isinstance(questions, list) or any(not nonempty(q) for q in questions):
        errors.append("Narrative open_questions must be a list of nonempty strings")
    elif status == "confirmed" and questions:
        errors.append("Confirmed narrative cannot leave material questions unresolved")
    if status == "pending":
        errors.append("Narrative confirmation is pending; present the interpretation and wait for the user")
    if errors:
        return errors
    receipt = review.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("actor") != "user" or not nonempty(receipt.get("message")):
        return ["Narrative confirmation or waiver requires an actual user reply; AI review is not consent"]
    try:
        current = narrative_digest(data)
    except (KeyError, TypeError, ValueError):
        return ["Narrative scope cannot be bound to this source and target"]
    if receipt.get("scope_digest") != current:
        return ["Narrative confirmation is stale; update the interpretation and obtain a current user decision"]
    return []


def file_digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def active(fact, start, end):
    left, right = fact["range_s"]
    return left < end and (right > start or left == right == start)


def production(fact):
    return fact["status"] in {"observed", "user_requested"}


def _input_errors(data):
    """Validate before compilation; keep malformed input out of the renderer."""
    errors = []
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data.get("schema_version") != 2:
        return ["Evidence contract requires schema_version 2"]
    source, caps = data.get("source"), data.get("capabilities")
    if not isinstance(source, dict) or not isinstance(caps, dict):
        return ["source and capabilities must be objects"]
    duration, precision = source.get("duration_s"), source.get("timestamp_precision_s")
    if not number(duration) or duration <= 0 or not number(precision) or not 0 < precision < duration:
        return ["Source duration and timestamp precision must be finite positive numbers, precision < duration"]
    if source.get("visual_access") != "full":
        errors.append("Full visual access is required; use a BLOCKED response for missing video")
    if not asset_ok(source.get("media")):
        errors.append("source.media needs a local path and SHA-256")
    if source.get("audio_status") not in {"verified", "no_track", "unavailable", "not_requested"}:
        errors.append("Invalid source audio_status")
    if data.get("analysis_status") not in {"PARTIAL", "COMPLETE"}:
        errors.append("v2 analysis_status must be PARTIAL or COMPLETE")
    if data.get("analysis_status") == "COMPLETE" and source.get("audio_status") == "unavailable":
        errors.append("Unavailable requested audio requires PARTIAL")
    if data.get("intent") not in {"faithful", "adapted"}:
        errors.append("intent must be faithful or adapted")
    deviations = data.get("intentional_deviations")
    if not isinstance(deviations, list) or any(not nonempty(x) for x in deviations):
        errors.append("intentional_deviations must be a list of nonempty strings")
    elif bool(deviations) != (data.get("intent") == "adapted"):
        errors.append("Adaptations must be declared; faithful output has no deviations")
    if data.get("delivery") not in {"T2VA", "I2V", "DUAL"}:
        errors.append("Resolve AUTO to T2VA, I2V or DUAL before compilation")
    limit = caps.get("max_job_duration_s")
    if limit is not None and (not number(limit) or limit <= 0):
        errors.append("max_job_duration_s must be positive or null")
    if caps.get("audio") not in {"supported", "unsupported", "unknown"}:
        errors.append("Declare target audio capability independently of source audio access")
    if caps.get("end_frames") is not None and type(caps["end_frames"]) is not bool:
        errors.append("end_frames must be true, false or null")
    if type(data.get("generation_ready")) is not bool:
        errors.append("generation_ready must be boolean")
    errors.extend(narrative_review_errors(data, required=data.get("generation_ready") is True))

    segments = index_rows(data.get("segments"), "segments", errors)
    evidence = index_rows(data.get("evidence"), "evidence", errors)
    facts = index_rows(data.get("facts"), "facts", errors)
    jobs = index_rows(data.get("jobs"), "jobs", errors)
    if not segments or not facts or not jobs:
        errors.append("segments, facts and jobs must not be empty")
    cursor = 0
    for sid, shot in segments.items():
        start, end = shot.get("start_s"), shot.get("end_s")
        if (not number(start) or not number(end) or not 0 <= start < end <= duration
                or abs(start - cursor) > 1e-6):
            errors.append(f"{sid}: timeline has a gap, overlap or invalid bounds")
        else:
            cursor = end
        if shot.get("kind") != "shot":
            errors.append(f"{sid}: v2 segments are shots; attach timed transition facts to adjacent shots")
        if shot.get("end_condition") not in {"settled", "ongoing", "cutoff", "unknown"}:
            errors.append(f"{sid}: declare settled/ongoing/cutoff/unknown end_condition")
        elif shot["end_condition"] == "unknown" and data.get("analysis_status") == "COMPLETE":
            errors.append(f"{sid}: unknown ending requires PARTIAL")
    if abs(cursor - duration) > 1e-6:
        errors.append("Source timeline must cover full visual duration")

    for eid, item in evidence.items():
        if item.get("kind") not in {"frame", "clip", "audio"} or not span(item.get("range_s"), duration):
            errors.append(f"{eid}: invalid evidence kind or time range")
            continue
        if item["kind"] == "frame" and item["range_s"][0] != item["range_s"][1]:
            errors.append(f"{eid}: a frame has one actual presentation time")
        if item["kind"] in {"clip", "audio"} and item["range_s"][0] == item["range_s"][1]:
            errors.append(f"{eid}: continuous evidence needs a nonzero range")
        if not asset_ok(item.get("asset")):
            errors.append(f"{eid}: evidence needs a local asset path and SHA-256")
        if item.get("source_sha256") != source.get("media", {}).get("sha256"):
            errors.append(f"{eid}: evidence belongs to a different source")

    for fid, fact in facts.items():
        sid, kind, status = fact.get("segment_id"), fact.get("kind"), fact.get("status")
        if not isinstance(sid, str) or sid not in segments or kind not in KINDS or status not in {"observed", "uncertain", "user_requested"}:
            errors.append(f"{fid}: invalid segment, kind or status")
            continue
        shot = segments[sid]
        if not span(fact.get("range_s"), duration):
            errors.append(f"{fid}: invalid fact range")
            continue
        left, right = fact["range_s"]
        if (not number(shot.get("start_s")) or not number(shot.get("end_s"))
                or not shot["start_s"] <= left < shot["end_s"] or right > shot["end_s"]):
            errors.append(f"{fid}: fact lies outside its source shot")
        text = fact.get("text")
        if not nonempty(text) or re.search(r"[\r\n]|\[Shot \d+\]|Picture \d+|(?:integrated_multimodal_description|overall_soundscape|non_diegetic_music):", text):
            errors.append(f"{fid}: use one plain-text fact; H3 wrappers are compiler-owned")
        refs = fact.get("evidence_ids")
        if not isinstance(refs, list) or any(not isinstance(x, str) or x not in evidence for x in refs) or len(set(refs)) != len(refs):
            errors.append(f"{fid}: unknown or duplicate evidence IDs")
            continue
        if status == "uncertain":
            if data.get("analysis_status") == "COMPLETE":
                errors.append(f"{fid}: unresolved facts require PARTIAL")
            continue
        if status == "user_requested":
            if data.get("intent") != "adapted" or not nonempty(fact.get("request")):
                errors.append(f"{fid}: new content needs an explicit user request and adapted intent")
        else:
            supports = [evidence[x] for x in refs if span(evidence[x].get("range_s"), duration)]
            relevant = [e for e in supports if e.get("kind") in ({"audio"} if kind in AUDIO else {"frame", "clip"})]
            if not relevant:
                errors.append(f"{fid}: observed fact lacks direct evidence in its own channel")
                continue
            if any(e["range_s"][1] < left - precision or e["range_s"][0] > right + precision for e in relevant):
                errors.append(f"{fid}: evidence is outside the fact interval")
            if min(e["range_s"][0] for e in relevant) > left + precision or max(e["range_s"][1] for e in relevant) < right - precision:
                errors.append(f"{fid}: evidence does not span the declared fact interval")
            if kind in TEMPORAL:
                times = {e["range_s"][0] for e in relevant if e.get("kind") == "frame"}
                if len(times) < 2 and not any(e.get("kind") == "clip" and e["range_s"][0] < e["range_s"][1] for e in relevant):
                    errors.append(f"{fid}: temporal claims need a reviewed clip or multiple distinct frame times")
            if kind in AUDIO and source.get("audio_status") != "verified":
                errors.append(f"{fid}: observed audio requires verified source audio")
        if kind in AUDIO and caps.get("audio") != "supported":
            errors.append(f"{fid}: audio output requires supported target audio capability")

    # Bail before code that assumes well-shaped records. Failures above remain actionable.
    if errors:
        return errors
    for fid, fact in facts.items():
        after = fact.get("after", [])
        if not isinstance(after, list) or any(not isinstance(x, str) or x not in facts or x == fid for x in after):
            errors.append(f"{fid}: after must reference other known fact IDs")
            continue
        for predecessor in after:
            earlier = facts[predecessor]
            if ((production(fact) and not production(earlier))
                    or earlier["range_s"][0] >= fact["range_s"][0]
                    or earlier["range_s"][1] > fact["range_s"][0] + precision):
                errors.append(f"{fid}: event order contradicts its declared predecessor")
    for sid, shot in segments.items():
        own = [f for f in facts.values() if f["segment_id"] == sid and production(f)]
        if not any(f["kind"] == "initial" and abs(f["range_s"][0] - shot["start_s"]) <= precision for f in own):
            errors.append(f"{sid}: an evidenced opening state is required")
        if not any(f["kind"] == "ending" and shot["end_s"] - f["range_s"][1] <= precision + 1e-6 for f in own):
            errors.append(f"{sid}: an evidenced final state near the visual endpoint is required")

    routes = {"T2VA": [], "I2V": []}
    for jid, job in jobs.items():
        allowed = {"id", "mode", "source_range_s", "duration_s", "opening_fact_ids", "closing_fact_ids", "reference_images"}
        if set(job) - allowed:
            errors.append(f"{jid}: unsupported plan fields; prompts belong only in derived output")
        mode, interval, length = job.get("mode"), job.get("source_range_s"), job.get("duration_s")
        if (mode not in {"T2VA", "I2VA", "FL2VA"} or not isinstance(interval, list) or len(interval) != 2
                or not all(number(x) for x in interval) or not 0 <= interval[0] < interval[1] <= duration
                or not number(length) or length <= 0):
            errors.append(f"{jid}: invalid mode, source range or duration")
            continue
        start, end = interval
        routes["T2VA" if mode == "T2VA" else "I2V"].append(interval)
        if limit is not None and length > limit + 1e-6:
            errors.append(f"{jid}: exceeds platform duration limit")
        if data["intent"] == "faithful" and abs(length - (end - start)) > 1e-6:
            errors.append(f"{jid}: faithful output must preserve source timing")
        covered = [s for s in segments.values() if s["start_s"] < end and s["end_s"] > start]
        if mode != "T2VA" and len(covered) != 1:
            errors.append(f"{jid}: image-to-video cannot silently merge source cuts")
        if mode == "FL2VA" and caps.get("end_frames") is not True:
            errors.append(f"{jid}: FL2VA requires confirmed end-frame support")
        for fact in facts.values():
            if production(fact) and fact["kind"] in {"action", "transition"}:
                left, right = fact["range_s"]
                if left < start < right or left < end < right:
                    errors.append(f"{jid}: split temporal fact {fact['id']} at the job boundary and record the current state")
        for field, boundary in (("opening_fact_ids", start), ("closing_fact_ids", end)):
            refs = job.get(field)
            if not isinstance(refs, list) or any(not isinstance(x, str) or x not in facts for x in refs) or len(set(refs)) != len(refs):
                errors.append(f"{jid}: invalid {field}")
                continue
            required = field == "opening_fact_ids" or mode == "FL2VA"
            if required and not refs:
                errors.append(f"{jid}: {field} cannot be empty")
            for fid in refs:
                f = facts[fid]
                if (not production(f) or f["kind"] not in {"initial", "state", "ending"}
                        or not start <= f["range_s"][0] <= f["range_s"][1] < end
                        or min(abs(t - boundary) for t in f["range_s"]) > precision + 1e-6):
                    errors.append(f"{jid}: {field} must bind a current boundary state, not an earlier pose")
        images = job.get("reference_images")
        count = 0 if mode == "T2VA" else 1 if mode == "I2VA" else 2
        if not isinstance(images, list) or len(images) != count or any(not asset_ok(a) for a in images):
            errors.append(f"{jid}: reference_images needs {count} local assets with hashes")
    needed = {"T2VA", "I2V"} if data["delivery"] == "DUAL" else {data["delivery"]}
    for route, intervals in routes.items():
        if route not in needed:
            if intervals:
                errors.append(f"Unexpected delivery route {route}")
            continue
        cursor = 0
        for start, end in sorted(intervals):
            if abs(start - cursor) > 1e-6:
                errors.append(f"{route}: job ranges leave a gap or overlap")
            cursor = end
        if abs(cursor - duration) > 1e-6:
            errors.append(f"{route}: jobs must cover the entire source, including the tail")
    return errors


def input_errors(data):
    try:
        return _input_errors(data)
    except (TypeError, KeyError, IndexError, AttributeError, OverflowError):
        return ["Malformed evidence contract: check object, list, string and numeric field types"]


def stamp(seconds):
    total = round(seconds * 1000)
    minutes, rest = divmod(total, 60000)
    secs, ms = divmod(rest, 1000)
    return f"{minutes:02}:{secs:02}.{ms:03}"


def render(data):
    """Pure projection; both routes consume the same automatically selected facts."""
    facts = {f["id"]: f for f in data["facts"]}
    result = {"jobs": [], "uncertainties": [f["id"] for f in facts.values() if not production(f)]}
    for job in data["jobs"]:
        start, end = job["source_range_s"]
        scale = job["duration_s"] / (end - start)
        ids = set(job["opening_fact_ids"] + job["closing_fact_ids"])
        selected = [f for f in facts.values() if production(f) and (active(f, start, end) or f["id"] in ids)]
        selected.sort(key=lambda f: (f["range_s"][0], list(facts).index(f["id"])))

        def timed(f):
            left = max(0, (f["range_s"][0] - start) * scale)
            right = min(job["duration_s"], (f["range_s"][1] - start) * scale)
            if f["kind"] == "initial" and f["range_s"][0] <= start:
                return f["text"]
            if f["kind"] == "identity" and f["range_s"][0] <= start and f["range_s"][1] >= end:
                return f["text"]
            prefix = f"At {left:.2f} seconds" if left == right else f"From {left:.2f} to {right:.2f} seconds"
            return f"{prefix}, {f['text']}"

        chunks = []
        for shot in data["segments"]:
            if shot["start_s"] >= end or shot["end_s"] <= start:
                continue
            own = [f for f in selected if f["segment_id"] == shot["id"] and f["kind"] not in AUDIO]
            label = f"[Shot {len(chunks) + 1}] "
            if chunks:
                label += f"At {stamp((shot['start_s'] - start) * scale)}, "
            chunks.append(label + " ".join(timed(f) for f in own))
        main = " ".join(chunks)
        audio = {kind: " ".join(timed(f) for f in selected if f["kind"] == kind) or "N/A" for kind in AUDIO}
        prefix = ""
        if job["mode"] == "I2VA":
            prefix = I2VA_PREFIX + "\n\n"
        elif job["mode"] == "FL2VA":
            prefix = ("How the reference pictures align with the target video — Picture 1 (from Shot 1) "
                      "aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) "
                      f"aligns with the {job['duration_s']:.2f}-second mark of the target video.\n\n")
        prompt = (f"{prefix}integrated_multimodal_description: {main}\n\n"
                  f"overall_soundscape: {audio['soundscape']}\n\nnon_diegetic_music: {audio['music']}")
        def identities_at(moment):
            return [f["id"] for f in selected if f["kind"] == "identity" and f["range_s"][0] <= moment <= f["range_s"][1]]
        final_time = max((facts[x]["range_s"][1] for x in job["closing_fact_ids"]), default=end)
        opening = list(dict.fromkeys(identities_at(start) + job["opening_fact_ids"]))
        closing = list(dict.fromkeys(identities_at(final_time) + job["closing_fact_ids"]))
        result["jobs"].append({
            "id": job["id"], "fact_ids": [f["id"] for f in selected], "prompt": prompt,
            "reference_prompt": " ".join(facts[x]["text"] for x in opening),
            "motion_prompt": " ".join(timed(f) for f in selected if f["kind"] not in AUDIO | {"initial"}
                                      and not (f["kind"] == "identity" and f["range_s"][0] <= start and f["range_s"][1] >= end)),
            "end_frame_prompt": " ".join(facts[x]["text"] for x in closing) if job["mode"] == "FL2VA" else "",
        })
    return result


def compile_contract(data):
    errors = input_errors(data)
    if errors:
        raise ValueError("\n".join(errors))
    result = deepcopy(data)
    current = digest(result)
    result["derived"] = render(result)
    result["compilation"] = {"version": VERSION, "input_digest": current}
    reviews = result.get("reviews")
    if not isinstance(reviews, dict):
        reviews = {}
    result["reviews"] = {
        key: reviews[key] if isinstance(reviews.get(key), dict) and reviews[key].get("input_digest") == current
        else {"status": "unreviewed", "input_digest": current}
        for key in ("media", "semantic")
    }
    return result


def validate_v2(data, base_dir=None, require_reviewed=False, verify_local_media=False):
    errors = input_errors(data)
    if errors:
        return errors
    try:
        current = digest(data)
    except (ValueError, TypeError):
        return ["Contract contains values that cannot be hashed as finite JSON"]
    expected = render(data)
    if data.get("derived") != expected:
        errors.append("Derived prompts differ from canonical facts; recompile instead of editing output")
    if data.get("compilation") != {"version": VERSION, "input_digest": current}:
        errors.append("Compilation digest is stale; recompile and review changed content")
    for job, output in zip(data["jobs"], expected["jobs"]):
        errors.extend(f"{job['id']}: {e}" for e in validate_prompt(output["prompt"], job["mode"], job["duration_s"], data["capabilities"]["audio"] != "supported"))
    reviews = data.get("reviews", {})
    required = require_reviewed or data["generation_ready"]
    if required and "narrative_review" not in data:
        errors.extend(narrative_review_errors(data, required=True))
    for key in ("media", "semantic"):
        receipt = reviews.get(key, {}) if isinstance(reviews, dict) else {}
        if not isinstance(receipt, dict):
            errors.append(f"{key} review must be an object")
            continue
        if receipt.get("status") == "reviewed":
            if receipt.get("input_digest") != current or not nonempty(receipt.get("reviewer")) or not nonempty(receipt.get("notes")):
                errors.append(f"{key} review is stale or lacks reviewer and concrete notes")
            if key == "media":
                expected_ids = {e["id"] for e in data["evidence"]}
                refs = receipt.get("evidence_ids")
                if not isinstance(refs, list) or any(not isinstance(x, str) for x in refs) or set(refs) != expected_ids:
                    errors.append("Media review must account for every evidence item")
                if receipt.get("full_timeline_viewed") is not True or receipt.get("tail_rechecked") is not True:
                    errors.append("Media review must declare full timeline viewing and tail recheck")
            elif receipt.get("fact_text_checked") is not True or receipt.get("route_parity_checked") is not True:
                errors.append("Semantic review must check fact wording and route parity")
            if key == "semantic" and data["delivery"] != "T2VA" and receipt.get("reference_alignment_checked") is not True:
                errors.append("Semantic review must check image reference alignment against boundary states")
            if key == "semantic" and "narrative_review" in data and receipt.get("narrative_alignment_checked") is not True:
                errors.append("Semantic review must check facts and prompts against the user's narrative decision")
        elif required:
            errors.append(f"A current {key} review is required")
    if data["generation_ready"]:
        caps = data["capabilities"]
        if data.get("fixture") or caps.get("duration_verified") is not True or caps.get("max_job_duration_s") is None:
            errors.append("Generation readiness needs real media and a verified duration limit")
    if verify_local_media or data["generation_ready"]:
        if base_dir is None:
            errors.append("Local verification needs a contract base directory")
        else:
            assets = [("source", data["source"]["media"])]
            assets += [(e["id"], e["asset"]) for e in data["evidence"]]
            assets += [(j["id"], a) for j in data["jobs"] for a in j["reference_images"]]
            checked = {}
            for label, asset in assets:
                path = Path(base_dir) / asset["path"]
                try:
                    if path not in checked:
                        if path.stat().st_size == 0:
                            raise OSError("Empty local asset")
                        checked[path] = file_digest(path)
                    if checked[path] != asset["sha256"]:
                        errors.append(f"{label}: local asset hash mismatch")
                except OSError:
                    errors.append(f"{label}: local asset missing or unreadable")
    return errors
