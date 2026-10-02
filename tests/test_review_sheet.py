"""Review sheets preserve evidence identity and never turn sampling into review."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_review_sheet as review

HAS_PILLOW = importlib.util.find_spec("PIL") is not None


class ReviewSheetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.manifest_path = self.root / "manifest.json"
        self.data = {"source_sha256": "a" * 64, "time_origin_pts_s": 7.0,
                     "last_frame_time_s": 2.0, "evidence": []}
        for index, time in enumerate((0.0, 0.125, 2.0)):
            asset = self.root / f"frame {index}.png"
            asset.write_bytes(f"placeholder {index}".encode())
            self.data["evidence"].append({
                "id": f"EV{index + 1:03}", "kind": "frame", "range_s": [time, time],
                "pts_s": 7.0 + time, "decoder_index": index, "source_sha256": "a" * 64,
                "asset": {"path": asset.name, "sha256": hashlib.sha256(asset.read_bytes()).hexdigest()},
                "visual_content_reviewed": True,
            })
        self.save()

    def save(self):
        self.manifest_path.write_text(json.dumps(self.data), encoding="utf-8")

    def real_images(self):
        from PIL import Image, ImageDraw
        for index, row in enumerate(self.data["evidence"]):
            path = self.root / row["asset"]["path"]
            size = ((200, 100), (200, 400), (80, 80))[index]
            with Image.new("RGB", size, (240, 20 + index, 30)) as image:
                draw = ImageDraw.Draw(image)
                draw.rectangle((0, 0, 19, 19), fill=(0, 0, 255))
                draw.rectangle((size[0] - 20, size[1] - 20, size[0] - 1, size[1] - 1), fill=(0, 255, 0))
                image.save(path)
            row["asset"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save()

    def test_range_uses_source_seconds_and_retains_actual_pts(self):
        result = review.load_manifest(self.manifest_path, [0.12, 0.13])
        self.assertEqual([row["id"] for row in result["frames"]], ["EV002"])
        frame = result["frames"][0]
        self.assertEqual((frame["source_time_s"], frame["pts_s"]), (0.125, 7.125))
        self.assertFalse(frame["reviewed"])
        self.assertEqual(result["input_manifest_sha256"], hashlib.sha256(self.manifest_path.read_bytes()).hexdigest())

    def test_nonfinite_inconsistent_and_unordered_clocks_fail(self):
        original = deepcopy(self.data)
        cases = [(0, "pts_s", float("nan")), (0, "range_s", [float("inf")] * 2),
                (1, "pts_s", 0.125), (1, "decoder_index", 0), (1, "range_s", [0.1, 0.2]),
                (0, "pts_s", 10 ** 400)]
        for position, field, value in cases:
            with self.subTest(field=field, value=value):
                self.data = deepcopy(original)
                self.data["evidence"][position][field] = value
                self.save()
                with self.assertRaises(ValueError):
                    review.load_manifest(self.manifest_path)
        self.data = deepcopy(original)
        self.data["evidence"].reverse()
        self.save()
        with self.assertRaisesRegex(ValueError, "increase strictly"):
            review.load_manifest(self.manifest_path)

    def test_duplicate_ids_and_source_hash_mismatch_fail_even_outside_range(self):
        for field, value in (("id", "EV001"), ("source_sha256", "b" * 64)):
            with self.subTest(field=field):
                self.data["evidence"][2][field] = value
                self.save()
                with self.assertRaises(ValueError):
                    review.load_manifest(self.manifest_path, [0, 0])
                self.data["evidence"][2][field] = "EV003" if field == "id" else "a" * 64

    def test_empty_and_invalid_ranges_fail(self):
        for span in ([0.2, 1.5], [7, 9], [1, 0], [-1, 2], [0, float("inf")]):
            with self.subTest(span=span), self.assertRaises(ValueError):
                review.load_manifest(self.manifest_path, span)

    def test_missing_and_changed_selected_frames_fail_without_output(self):
        output = self.root / "new-sheet"
        asset = self.root / self.data["evidence"][0]["asset"]["path"]
        asset.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash"):
            review.build_review_sheet(self.manifest_path, output, "What moved?")
        asset.unlink()
        with self.assertRaisesRegex(ValueError, "Missing"):
            review.build_review_sheet(self.manifest_path, output, "What moved?")
        self.assertFalse(output.exists())
        # Missing unselected files need not prevent inspection of other evidence.
        self.assertEqual(len(review.load_manifest(self.manifest_path, [0.1, 2])["frames"]), 2)

    def test_resource_limits_and_existing_output_are_rejected(self):
        for options in ((0, 2, 360), (3, 7, 360), (3, 2, 100000)):
            with self.subTest(options=options), self.assertRaises(ValueError):
                review.build_review_sheet(self.manifest_path, self.root / "new", "Check", columns=options[0], rows=options[1], cell_width=options[2])
        with self.assertRaisesRegex(ValueError, "already exists"):
            review.build_review_sheet(self.manifest_path, self.root, "Check")
        with patch.object(review, "MAX_FRAMES", 2), self.assertRaisesRegex(ValueError, "1 to 2"):
            review.load_manifest(self.manifest_path)
        with patch.object(review, "MAX_IMAGE_BYTES", 2), self.assertRaisesRegex(ValueError, "byte limit"):
            review.load_manifest(self.manifest_path)

    def test_cli_missing_optional_pillow_is_clear_and_leaves_no_output(self):
        output = self.root / "without-pillow"
        # -S disables third-party site packages even on a machine with Pillow.
        result = subprocess.run([sys.executable, "-S", str(Path(review.__file__)),
                                 str(self.manifest_path), "--output", str(output),
                                 "--question", "What moved?"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Pillow is required", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(output.exists())

    @unittest.skipUnless(HAS_PILLOW, "Pillow is optional; real PNG rendering requires it")
    def test_png_pagination_aspect_pixels_labels_original_links_and_unreviewed_state(self):
        from PIL import Image
        self.real_images()
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        output = self.root / "sheets"
        index = review.build_review_sheet(self.manifest_path, output, "判断前后变化", columns=1, rows=2, cell_width=128)
        self.assertEqual(len(index["pages"]), 2)
        self.assertEqual(index["question"], "判断前后变化")
        self.assertFalse(index["reviewed"])
        self.assertFalse(index["visual_content_reviewed"])
        for position, frame in enumerate(index["frames"]):
            self.assertFalse(frame["reviewed"])
            expected_size = ([200, 100], [200, 400], [80, 80])[position]
            self.assertEqual(frame["original_size"], expected_size)
            left, top, right, bottom = frame["thumbnail_box"]
            self.assertEqual((right - left) / (bottom - top), expected_size[0] / expected_size[1])
            if expected_size[1] > expected_size[0]:
                self.assertGreaterEqual(right - left, 0.85 * min(expected_size[0], index["layout"]["cell_width"]),
                                        "Portrait evidence should use most of the cell width, not a landscape-height letterbox")
            self.assertLessEqual(bottom, frame["label_box"][1])
            with Image.open(output / frame["sheet_path"]) as sheet:
                pixel = sheet.getpixel(((left + right) // 2, (top + bottom) // 2))
                self.assertEqual(pixel, (240, 19 + int(frame["id"][-1]), 30))
                self.assertEqual(sheet.getpixel((left + 2, top + 2)), (0, 0, 255))
                self.assertEqual(sheet.getpixel((right - 3, bottom - 3)), (0, 255, 0))
                label = sheet.crop(frame["label_box"])
                self.assertGreater(len(label.getcolors(label.width * label.height)), 1)
            self.assertIn(frame["original_path"], unquote((output / "review.md").read_text()))
        self.assertEqual(json.loads((output / "review.json").read_text()), index)
        for name, original in before.items():
            self.assertEqual((self.root / name).read_bytes(), original)

    @unittest.skipUnless(HAS_PILLOW, "Pillow is optional; image preflight requires it")
    def test_corrupt_image_and_excessive_canvas_leave_no_index(self):
        output = self.root / "invalid"
        with self.assertRaises(OSError):
            review.build_review_sheet(self.manifest_path, output, "Check")
        self.assertFalse(output.exists())
        self.real_images()
        with patch.object(review, "MAX_IMAGE_PIXELS", 100), self.assertRaisesRegex(ValueError, "bounded"):
            review.build_review_sheet(self.manifest_path, output, "Check")
        with patch.object(review, "MAX_CANVAS_PIXELS", 100), self.assertRaisesRegex(ValueError, "canvas"):
            review.build_review_sheet(self.manifest_path, output, "Check")
        self.assertFalse(output.exists())

    @unittest.skipUnless(HAS_PILLOW, "Pillow is optional; publication rollback requires rendering")
    def test_failed_publication_cleans_staging_and_partial_output(self):
        self.real_images()
        output = self.root / "publish-fails"
        original_replace = Path.replace

        def fail_index(path, target):
            if path.name == "review.json":
                raise OSError("simulated publication failure")
            return original_replace(path, target)

        with patch.object(Path, "replace", fail_index), self.assertRaisesRegex(OSError, "publication"):
            review.build_review_sheet(self.manifest_path, output, "Check")
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(".review-sheet-*")), [])


if __name__ == "__main__":
    unittest.main()
