"""Source-audio reuse is separate from hearing its content or generating new audio."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_evidence import fixture, reviewed, ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from evidence_contract import compile_contract, file_digest, input_errors, narrative_review_errors
from probe_video import summarize
from validate_contract import validate


def with_handoff():
    data = fixture()
    data["source"].update(audio_track_present=True, audio_stream_index=1, video_start_s=0.0, audio_start_s=0.0, audio_duration_s=10.0)
    data["audio_handoff"] = {"method": "postproduction_copy"}
    return data


class AudioInheritanceTests(unittest.TestCase):
    def test_probe_reports_track_timing_without_claiming_to_have_listened(self):
        info = summarize({
            "streams": [
                {"index": 0, "codec_type": "video", "duration": "10.0", "start_time": "0.0"},
                {"index": 1, "codec_type": "audio", "duration": "9.8", "start_time": "0.2"},
            ],
            "format": {"duration": "10.0"},
        })
        self.assertEqual(info["audio_stream_index"], 1)
        self.assertAlmostEqual(info["audio_start_s"], 0.2)
        self.assertAlmostEqual(info["audio_duration_s"], 9.8)
        self.assertEqual(info["audio_status"], "unavailable")
        self.assertFalse(info["audio_content_reviewed"])

    def test_unheard_track_can_be_preserved_without_fabricated_sound(self):
        output = compile_contract(with_handoff())
        self.assertEqual(validate(output), [])
        self.assertEqual(output["source"]["audio_status"], "unavailable")
        self.assertEqual(output["capabilities"]["audio"], "unknown")
        self.assertEqual(output["derived"]["audio_handoff"]["source_stream_index"], 1)
        self.assertEqual(output["derived"]["audio_handoff"]["audio_offset_from_video_s"], 0.0)
        self.assertEqual(output["derived"]["audio_handoff"]["route_maps"]["T2VA"][0]["source_range_s"], [0.0, 10.0])
        self.assertEqual(output["derived"]["audio_handoff"]["route_maps"]["I2V"][0]["target_range_s"], [0.0, 10.0])
        for job in output["derived"]["jobs"]:
            self.assertIn("overall_soundscape: N/A", job["prompt"])
            self.assertIn("non_diegetic_music: N/A", job["prompt"])
            self.assertNotIn("postproduction_copy", job["prompt"])

    def test_audio_offset_is_explicit_when_streams_start_at_different_times(self):
        data = with_handoff()
        data["source"].update(video_start_s=3.0, audio_start_s=3.2)
        output = compile_contract(data)
        self.assertAlmostEqual(output["derived"]["audio_handoff"]["audio_offset_from_video_s"], 0.2)

    def test_missing_or_excluded_track_cannot_be_preserved(self):
        for status in ("no_track", "not_requested"):
            data = with_handoff()
            data["source"]["audio_status"] = status
            with self.subTest(status=status):
                self.assertTrue(any("declared source audio track" in error for error in input_errors(data)))
        data = with_handoff()
        data["source"].pop("audio_stream_index")
        self.assertTrue(any("stream index" in error for error in input_errors(data)))

    def test_copy_does_not_silently_retime_or_pretend_to_be_ref2va(self):
        data = with_handoff()
        data.update(intent="adapted", intentional_deviations=["Compress the video."])
        self.assertTrue(any("faithful source timing" in error for error in input_errors(data)))
        data = with_handoff()
        data["audio_handoff"]["method"] = "ref2va"
        self.assertTrue(any("separate verified handoff" in error for error in input_errors(data)))

    def test_audio_route_change_invalidates_narrative_decision_and_derived_map(self):
        data = reviewed(fixture())
        data["source"].update(audio_track_present=True, audio_stream_index=1)
        data["audio_handoff"] = {"method": "postproduction_copy"}
        self.assertTrue(any("confirmation is stale" in error for error in narrative_review_errors(data)))
        output = compile_contract(with_handoff())
        output["derived"]["audio_handoff"]["route_maps"]["I2V"][0]["target_range_s"] = [0.0, 9.0]
        self.assertTrue(any("Derived prompts differ" in error for error in validate(output)))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe not installed")
    def test_real_local_source_stream_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            media = base / "source.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=16x16:r=1:d=10",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=8000:duration=10",
                "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(media),
            ], check=True, capture_output=True)
            result = subprocess.run([
                "ffprobe", "-v", "error", "-protocol_whitelist", "file", "-show_streams", "-show_format", "-of", "json", str(media),
            ], check=True, capture_output=True, text=True)
            report = summarize(json.loads(result.stdout))
            data = with_handoff()
            data["source"].update(
                media={"path": "source.mp4", "sha256": file_digest(media)},
                audio_stream_index=report["audio_stream_index"],
                video_start_s=report["video_start_s"],
                audio_start_s=report["audio_start_s"],
                audio_duration_s=report["audio_duration_s"],
            )
            for name, content in (("opening.png", b"opening"), ("ending.png", b"ending")):
                (base / name).write_bytes(content)
            for item in data["evidence"]:
                if item["id"] == "EV02":
                    item["asset"] = deepcopy(data["source"]["media"])
                else:
                    name = "opening.png" if item["id"] == "EV01" else "ending.png"
                    item["asset"] = {"path": name, "sha256": file_digest(base / name)}
                item["source_sha256"] = data["source"]["media"]["sha256"]
            data["jobs"][1]["reference_images"] = [deepcopy(data["evidence"][0]["asset"])]
            output = compile_contract(data)
            self.assertEqual(validate(output, base, verify_local_media=True), [])
            output["source"]["audio_stream_index"] += 1
            output = compile_contract(output)
            self.assertTrue(any("real source audio stream" in error for error in validate(output, base, verify_local_media=True)))


if __name__ == "__main__":
    unittest.main()
