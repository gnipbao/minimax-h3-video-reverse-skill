"""Regression checks for consequential timing, evidence and handoff failures."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_contract import validate, validate_prompt  # noqa: E402
from probe_video import summarize  # noqa: E402


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "examples/contract.json").read_text())

    def fails(self, fragment):
        errors = validate(self.data)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_valid_synthetic_partial_delivery(self):
        self.assertEqual(validate(self.data), [])

    def test_missing_visual_access_cannot_claim_complete_timeline(self):
        self.data["source"]["visual_access"] = "partial"
        self.fails("full visual access")

    def test_blocked_must_not_include_generation(self):
        self.data["analysis_status"] = "BLOCKED"
        self.fails("BLOCKED cannot")

    def test_valid_blocked_response(self):
        data = {"schema_version": 1, "analysis_status": "BLOCKED", "missing_capability": "Only three screenshots", "required_input_or_capability": "Readable full video"}
        self.assertEqual(validate(data), [])

    def test_unknown_audio_is_not_complete(self):
        self.data["analysis_status"] = "COMPLETE"
        self.fails("requires PARTIAL")

    def test_visual_only_explicit_scope_can_complete(self):
        self.data["analysis_status"] = "COMPLETE"
        self.data["source"]["audio_status"] = "not_requested"
        self.assertEqual(validate(self.data), [])

    def test_unheard_audio_cannot_be_filled_in(self):
        self.data["jobs"][0]["prompt"] = self.data["jobs"][0]["prompt"].replace("overall_soundscape: N/A", "overall_soundscape: A loud impact.")
        self.fails("Unverified or excluded audio")

    def test_user_requested_audio_is_explicit_adaptation(self):
        self.data.update(intent="adapted", intentional_deviations=["User requested added piano music"], user_audio_request="Add soft piano music")
        self.data["jobs"][0]["prompt"] = self.data["jobs"][0]["prompt"].replace("non_diegetic_music: N/A", "non_diegetic_music: Sparse piano notes.")
        self.assertEqual(validate(self.data), [])

    def test_timeline_gap(self):
        self.data["segments"][0]["start_s"] = 0.2
        self.fails("gap or overlaps")

    def test_timeline_overlap(self):
        duplicate = deepcopy(self.data["segments"][0])
        duplicate.update(id="SH02", start_s=9, end_s=10, reference_frame_s=9)
        self.data["segments"].append(duplicate)
        self.fails("gap or overlaps")

    def test_missing_tail(self):
        self.data["segments"][0]["end_s"] = 9
        self.fails("full visual duration")

    def test_reference_cannot_be_at_exclusive_end(self):
        self.data["segments"][0]["reference_frame_s"] = 10
        self.fails("inside its source shot")

    def test_late_reference_must_account_for_opening(self):
        self.data["segments"][0]["reference_frame_s"] = 1
        self.fails("earlier opening")

    def test_end_frame_route_needs_capability(self):
        self.data["segments"][0].update(i2v_type="I2V-B", end_frame_s=9.9, end_frame_prompt="Ball at rest")
        self.fails("without confirmed support")

    def test_job_cannot_exceed_platform_limit(self):
        self.data["jobs"][0]["duration_s"] = 30
        self.fails("exceeds the declared")

    def test_ready_needs_verified_limit(self):
        self.data.update(fixture=False, generation_ready=True)
        self.data["capabilities"]["duration_verified"] = False
        self.fails("verified platform duration")

    def test_planned_image_cannot_be_generation_ready(self):
        self.data.update(fixture=False, generation_ready=True)
        errors = validate(self.data, ROOT)
        self.assertTrue(any("missing local reference image" in e for e in errors))

    def test_adaptation_cannot_be_silent(self):
        self.data["intent"] = "adapted"
        self.fails("Adaptations must be declared")

    def test_unknown_source_shot_rejected(self):
        self.data["jobs"][0]["source_shots"] = ["SH99"]
        self.fails("unknown or missing source")

    def test_multiple_source_cuts_cannot_be_faithful_i2v(self):
        self.data["segments"][0]["end_s"] = 5
        second = deepcopy(self.data["segments"][0])
        second.update(id="SH02", start_s=5, end_s=10, reference_frame_s=5)
        self.data["segments"].append(second)
        self.data["jobs"][0]["source_shots"] = ["SH01", "SH02"]
        self.fails("cannot combine real source cuts")

    def test_terminal_transition_preserves_source_coverage(self):
        self.data["source"]["duration_s"] = 11
        self.data["segments"].append({"id": "TR01", "kind": "transition", "start_s": 10, "end_s": 11, "transition": "fade to black"})
        self.assertEqual(validate(self.data), [])

    def test_nonfinite_and_boolean_times_rejected(self):
        for value in [float("nan"), float("inf"), True, "10", 10**1000]:
            with self.subTest(value=str(value)[:15]):
                self.data["source"]["duration_s"] = value
                self.fails("finite positive")

    def test_malformed_json_shapes_report_errors(self):
        for key in ["source", "capabilities", "segments", "jobs", "analysis_status", "intent"]:
            data = deepcopy(self.data)
            data[key] = ["invalid"]
            with self.subTest(key=key):
                self.assertTrue(validate(data))


class PromptTests(unittest.TestCase):
    def prompt(self, main):
        return f"integrated_multimodal_description: {main}\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A"

    def test_valid_t2va_two_shots(self):
        prompt = self.prompt("[Shot 1] A fixed wide view. [Shot 2] At 00:04.500, the shot cuts to a close view.")
        self.assertEqual(validate_prompt(prompt, "T2VA", 10, True), [])

    def test_cut_at_end_is_not_valid(self):
        prompt = self.prompt("[Shot 1] A room. [Shot 2] At 00:10.000, the shot cuts to a street.")
        self.assertTrue(any("within the job" in e for e in validate_prompt(prompt, "T2VA", 10, True)))

    def test_shot_ids_restart_for_each_job(self):
        self.assertTrue(validate_prompt(self.prompt("[Shot 4] A room."), "T2VA", 10, True))

    def test_forbidden_fourth_h3_field(self):
        prompt = self.prompt("[Shot 1] A room.") + "\n\nnegative_prompt: blur"
        self.assertTrue(validate_prompt(prompt, "T2VA", 10, True))

    def test_unbound_picture_reference(self):
        prompt = self.prompt("[Shot 1] A room from <Picture 9>.")
        self.assertTrue(any("Picture references" in e for e in validate_prompt(prompt, "T2VA", 10, True)))

    def test_fl2va_alignment_matches_duration(self):
        prefix = "How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video.\n\n"
        prompt = prefix + self.prompt("[Shot 1] Move continuously from Picture 1 to Picture 2.")
        self.assertEqual(validate_prompt(prompt, "FL2VA", 8, True), [])
        self.assertTrue(validate_prompt(prompt, "FL2VA", 9, True))

    def test_i2va_prefix_and_blank_line_required(self):
        fixture = json.loads((ROOT / "examples/contract.json").read_text())
        prompt = fixture["jobs"][0]["prompt"].replace("\n\nintegrated", "\nintegrated")
        self.assertTrue(validate_prompt(prompt, "I2VA", 10, True))


class ProbeTests(unittest.TestCase):
    def test_metadata_does_not_claim_observation(self):
        data = {"streams": [{"codec_type": "video", "duration": "10", "start_time": "0", "avg_frame_rate": "24/1"}, {"codec_type": "audio"}], "format": {"duration": "10.4"}}
        result = summarize(data)
        self.assertEqual(result["video_duration_s"], 10)
        self.assertEqual(result["container_duration_s"], 10.4)
        self.assertIsNone(result["last_frame_time_s"])
        self.assertFalse(result["visual_content_reviewed"])
        self.assertEqual(result["audio_status"], "unavailable")

    def test_container_duration_does_not_replace_unknown_visual_duration(self):
        result = summarize({"streams": [{"codec_type": "video"}], "format": {"duration": "12"}})
        self.assertIsNone(result["video_duration_s"])
        self.assertEqual(result["audio_status"], "no_track")

    def test_cover_art_is_not_a_video_stream(self):
        with self.assertRaises(ValueError):
            summarize({"streams": [{"codec_type": "video", "disposition": {"attached_pic": 1}}, {"codec_type": "audio"}]})


if __name__ == "__main__":
    unittest.main()
