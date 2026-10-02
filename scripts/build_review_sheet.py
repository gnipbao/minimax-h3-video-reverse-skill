#!/usr/bin/env python3
"""Build offline PNG contact sheets from sample_frames evidence; never approve review.

Pillow is optional for the repository, but required to render a sheet. No network,
installation, source-image edits, ROI extraction, or semantic judgments occur.
"""

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import quote
import warnings


MAX_FRAMES = 120
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_TOTAL_PIXELS = 600_000_000
MAX_CANVAS_PIXELS = 20_000_000
MAX_TOTAL_CANVAS_PIXELS = 150_000_000
SHA = re.compile(r"^[a-f0-9]{64}$")
EVIDENCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bounded_bytes(path, limit):
    if not path.is_file():
        raise ValueError("Input must be a local regular file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Input exceeds the permitted byte limit")
    return raw


def load_manifest(manifest_path, time_range=None):
    """Validate clocks/identities without Pillow; hash selected local frame bytes."""
    manifest_path = Path(manifest_path).resolve()
    raw = bounded_bytes(manifest_path, MAX_MANIFEST_BYTES)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Manifest must be an object")
    source_hash = data.get("source_sha256")
    if not isinstance(source_hash, str) or not SHA.fullmatch(source_hash):
        raise ValueError("Manifest source_sha256 must be a lowercase SHA-256")
    origin, last = data.get("time_origin_pts_s"), data.get("last_frame_time_s")
    if not finite(origin) or not finite(last) or last < 0:
        raise ValueError("Manifest requires finite source-clock origin and last-frame time")
    if time_range is not None:
        if (len(time_range) != 2 or not all(finite(t) for t in time_range)
                or not 0 <= time_range[0] <= time_range[1]):
            raise ValueError("Range must be finite ordered nonnegative source seconds")
        start, end = time_range
    else:
        start, end = 0, last
    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= MAX_FRAMES:
        raise ValueError(f"Manifest must contain 1 to {MAX_FRAMES} frames")
    selected, seen, previous = [], set(), None
    for row in evidence:
        if not isinstance(row, dict) or row.get("kind") != "frame":
            raise ValueError("Every evidence entry must be a frame object")
        identifier = row.get("id")
        if (not isinstance(identifier, str) or not EVIDENCE_ID.fullmatch(identifier)
                or identifier in seen):
            raise ValueError("Frame IDs must be unique, short ASCII evidence identifiers")
        seen.add(identifier)
        span, pts, decoder_index = row.get("range_s"), row.get("pts_s"), row.get("decoder_index")
        if (not isinstance(span, list) or len(span) != 2
                or not all(finite(t) for t in span) or span[0] != span[1]
                or not 0 <= span[0] <= last or not finite(pts)
                or type(decoder_index) is not int or decoder_index < 0):
            raise ValueError("Frames require finite point ranges, PTS and decoder indices")
        source_time = span[0]
        if not math.isclose(pts - origin, source_time, rel_tol=0, abs_tol=1e-6):
            raise ValueError("Frame PTS does not agree with its normalized source clock")
        current = source_time, pts, decoder_index
        if previous is not None and any(a <= b for a, b in zip(current, previous)):
            raise ValueError("Frame source times, PTS and decoder indices must increase strictly")
        previous = current
        if row.get("source_sha256") != source_hash:
            raise ValueError("Frame source hash differs from the manifest source hash")
        asset = row.get("asset")
        if (not isinstance(asset, dict) or not isinstance(asset.get("path"), str)
                or not asset["path"].strip() or "://" in asset["path"] or "\x00" in asset["path"]
                or not isinstance(asset.get("sha256"), str) or not SHA.fullmatch(asset["sha256"])):
            raise ValueError("Frame asset requires a local path and lowercase SHA-256")
        if start <= source_time <= end:
            selected.append({
                "id": identifier, "source_time_s": source_time, "range_s": span,
                "pts_s": pts, "decoder_index": decoder_index,
                "source_sha256": source_hash,
                "original_path": str((manifest_path.parent / asset["path"]).resolve()),
                "sha256": asset["sha256"], "reviewed": False,
            })
    if not selected:
        raise ValueError("No sampled frames fall inside the requested source-time range")
    total_bytes = 0
    for frame in selected:
        raw_image = checked_frame_bytes(frame)
        total_bytes += len(raw_image)
        if total_bytes > MAX_TOTAL_BYTES:
            raise ValueError("Selected frames exceed the total byte budget")
    return {
        "input_manifest": str(manifest_path), "input_manifest_sha256": digest(raw),
        "source_sha256": source_hash, "time_origin_pts_s": origin,
        "selection_range_s": [start, end], "frames": selected,
    }


def checked_frame_bytes(frame):
    path = Path(frame["original_path"])
    if not path.is_file():
        raise ValueError(f"Missing local frame for {frame['id']}")
    raw = bounded_bytes(path, MAX_IMAGE_BYTES)
    if digest(raw) != frame["sha256"]:
        raise ValueError(f"Frame bytes changed or hash is incorrect for {frame['id']}")
    return raw


def layout_options(columns, rows, cell_width):
    if (type(columns) is not int or not 1 <= columns <= 6
            or type(rows) is not int or not 1 <= rows <= 6
            or type(cell_width) is not int or not 128 <= cell_width <= 1024):
        raise ValueError("Use 1-6 columns, 1-6 rows, and a cell width of 128-1024 pixels")


def pillow_modules():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise ValueError("Pillow is required to render review sheets; use a Python interpreter with Pillow already installed. No automatic installation is performed.") from None
    return Image, ImageDraw, ImageFont


def wrapped_label(draw, font, frame, width):
    lines = []
    for text in (frame["id"], f"source {frame['source_time_s']!r} s", f"PTS {frame['pts_s']!r} s"):
        line = ""
        for char in text:
            if line and draw.textbbox((0, 0), line + char, font=font)[2] > width:
                lines.append(line)
                line = ""
            line += char
        lines.append(line)
    return lines


def markdown(index):
    lines = ["# Visual review material — unreviewed", "", "Question:", ""]
    # Escape link/image syntax so a question cannot cause remote image retrieval.
    lines.extend("> " + re.sub(r"([\\`*_{}\[\]()#!|])", r"\\\1", line).replace("<", "&lt;").replace(">", "&gt;")
                 for line in index["question"].splitlines())
    lines += ["", "reviewed: false. Generating or opening these sheets does not record a review.", "",
              "Selection uses normalized source seconds (inclusive bounds). Labels also show actual decoded PTS.", "",
              f"Input manifest SHA-256: `{index['input_manifest_sha256']}`", "",
              "## Contact sheets", ""]
    lines.extend(f"- [Page {page['number']}]({page['path']})" for page in index["pages"])
    lines += ["", "## Original frames", ""]
    for frame in index["frames"]:
        target = quote(frame["original_path"], safe="/:")
        lines.append(f"- [{frame['id']} — original {frame['original_size'][0]} × {frame['original_size'][1]}]({target})"
                     f"; source {frame['source_time_s']!r} s; PTS {frame['pts_s']!r} s; page {frame['page']}; reviewed: false")
    return "\n".join(lines) + "\n"


def build_review_sheet(manifest_path, output, question, time_range=None, columns=3, rows=2, cell_width=360):
    """Render bounded sheets in staging; publish the completion index last."""
    layout_options(columns, rows, cell_width)
    if not isinstance(question, str) or not question.strip() or len(question) > 4000:
        raise ValueError("Question must contain 1-4000 characters and name what needs inspection")
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Output directory already exists; choose a new directory")
    index = load_manifest(manifest_path, time_range)
    Image, ImageDraw, ImageFont = pillow_modules()
    font = ImageFont.load_default()
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    labels = {frame["id"]: wrapped_label(measure, font, frame, cell_width - 24) for frame in index["frames"]}
    line_height = max(14, measure.textbbox((0, 0), "Ag", font=font)[3] + 3)
    label_height = max(map(len, labels.values())) * line_height + 16
    total_pixels = 0
    # Inspect every selected image before creating an output directory or any index.
    for frame in index["frames"]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(checked_frame_bytes(frame))) as source:
                    w, h = source.size
                    if (w <= 0 or h <= 0 or max(w, h) > 32768 or w * h > MAX_IMAGE_PIXELS
                            or getattr(source, "n_frames", 1) != 1):
                        raise ValueError("Frames must be bounded, single-image stills")
                    total_pixels += w * h
                    if total_pixels > MAX_TOTAL_PIXELS:
                        raise ValueError("Selected images exceed the decoded pixel budget")
                    frame["original_size"] = [w, h]
                    source.verify()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ValueError("Image exceeds the safe decoded pixel budget") from None
    # Give portrait frames their full available width. Exceptionally tall stills
    # retain all their content while fitting a bounded image area.
    tallest_ratio = max(frame["original_size"][1] / frame["original_size"][0]
                        for frame in index["frames"])
    image_height = min(2 * cell_width, max(32, math.ceil((cell_width - 16) * tallest_ratio) + 16))
    cell_height, header_height = image_height + label_height, 36
    width, height = columns * cell_width, rows * cell_height + header_height
    page_count = math.ceil(len(index["frames"]) / (columns * rows))
    if (max(width, height) > 8192 or width * height > MAX_CANVAS_PIXELS
            or width * height * page_count > MAX_TOTAL_CANVAS_PIXELS):
        raise ValueError("Layout exceeds the per-page or total canvas pixel budget")
    index.update({"schema": "frame-review-sheet-v1", "question": question.strip(), "reviewed": False,
                  "visual_content_reviewed": False, "audio_content_reviewed": False,
                  "layout": {"columns": columns, "rows": rows, "cell_width": cell_width}, "pages": []})
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".review-sheet-", dir=output.parent))
    published = False
    try:
        for page_number in range(1, page_count + 1):
            page = Image.new("RGB", (width, height), "#e4e7eb")
            draw = ImageDraw.Draw(page)
            draw.text((12, 10), f"Source frames | page {page_number}/{page_count}", font=font, fill="#161b22")
            batch = index["frames"][(page_number - 1) * columns * rows:page_number * columns * rows]
            for slot, frame in enumerate(batch):
                x, y = slot % columns * cell_width, header_height + slot // columns * cell_height
                draw.rectangle((x, y, x + cell_width - 1, y + image_height - 1), fill="#20252b")
                with Image.open(io.BytesIO(checked_frame_bytes(frame))) as source:
                    source.load()
                    thumb = source.convert("RGBA")
                    thumb.thumbnail((cell_width - 16, image_height - 16), Image.Resampling.LANCZOS)
                    left, top = x + (cell_width - thumb.width) // 2, y + (image_height - thumb.height) // 2
                    page.paste(thumb, (left, top), thumb)
                    frame.update({"page": page_number, "sheet_path": f"sheet-{page_number:03}.png",
                                  "thumbnail_box": [left, top, left + thumb.width, top + thumb.height],
                                  "label_box": [x + 12, y + image_height + 8, x + cell_width - 12, y + cell_height - 8]})
                for line_number, line in enumerate(labels[frame["id"]]):
                    draw.text((x + 12, y + image_height + 8 + line_number * line_height), line, font=font, fill="#161b22")
            filename = f"sheet-{page_number:03}.png"
            page.save(staging / filename)
            page.close()
            index["pages"].append({"number": page_number, "path": filename, "size": [width, height],
                                   "frame_ids": [frame["id"] for frame in batch]})
        if digest(bounded_bytes(Path(index["input_manifest"]), MAX_MANIFEST_BYTES)) != index["input_manifest_sha256"]:
            raise ValueError("Manifest changed while rendering; discard this sheet batch")
        for frame in index["frames"]:
            checked_frame_bytes(frame)
        (staging / "review.md").write_text(markdown(index), encoding="utf-8")
        (staging / "review.json").write_text(json.dumps(index, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        # Exclusive creation also refuses a destination created while rendering.
        output.mkdir()
        published = True
        for page in index["pages"]:
            (staging / page["path"]).replace(output / page["path"])
        (staging / "review.md").replace(output / "review.md")
        (staging / "review.json").replace(output / "review.json")
        return index
    except BaseException:
        if published:
            shutil.rmtree(output)
        raise
    finally:
        shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="sample_frames manifest.json")
    parser.add_argument("--output", type=Path, required=True, help="New local output directory")
    parser.add_argument("--question", required=True, help="Unresolved visual question; retained in the review index")
    parser.add_argument("--range", dest="time_range", type=float, nargs=2, metavar=("START", "END"), help="Inclusive normalized source seconds, not raw PTS")
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--cell-width", type=int, default=360)
    args = parser.parse_args()
    try:
        index = build_review_sheet(args.manifest, args.output, args.question, args.time_range, args.columns, args.rows, args.cell_width)
    except (OSError, ValueError, SyntaxError, Warning) as exc:
        print(f"Review sheet failed: {exc}", file=sys.stderr)
        return 1
    print(f"Created {len(index['pages'])} PNG pages for {len(index['frames'])} frames. Open the PNGs and original-frame links to inspect them; reviewed=false.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
