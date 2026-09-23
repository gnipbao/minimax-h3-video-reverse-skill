"""Behavioral regressions: fabricated edits, lost events and stale approvals."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from evidence_contract import compile_contract, digest, file_digest, input_errors, narrative_digest
from validate_contract import validate


def fixture():
    return json.loads((ROOT / "examples/evidence-contract.input.json").read_text())


def reviewed(data):
    """Synthetic receipt for gate tests only; never applied to user media."""
    data = deepcopy(data)
    if "narrative_review" not in data:
        data["narrative_review"] = {
            "status": "confirmed", "revision": 1,
            "summary": "Fictional fixture: the cat touches, withdraws, pushes the ball again and watches it stop.",
            "target": "Preserve the declared action sequence and ending; no unverified sound.",
            "open_questions": [],
            "receipt": {"actor": "user", "message": "Synthetic fixture reply: use that interpretation."},
        }
        data["narrative_review"]["receipt"]["scope_digest"] = narrative_digest(data)
    out = compile_contract(data)
    common = {"status": "reviewed", "input_digest": digest(out), "reviewer": "synthetic-test", "notes": "Fictional gate fixture, not a media observation."}
    out["reviews"] = {
        "media": dict(common, evidence_ids=[e["id"] for e in out["evidence"]], full_timeline_viewed=True, tail_rechecked=True),
        "semantic": dict(common, fact_text_checked=True, route_parity_checked=True, reference_alignment_checked=True, narrative_alignment_checked=True),
    }
    return out


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def rejects(self, fragment, data=None, **kwargs):
        errors = validate(data if data is not None else self.data, **kwargs)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_compiled_dual_uses_the_same_facts(self):
        out = compile_contract(self.data)
        self.assertEqual(validate(out), [])
        a, b = out["derived"]["jobs"]
        self.assertEqual(a["fact_ids"], b["fact_ids"])
        for phrase in ["rests lightly", "visible gap", "second contact", "final frame"]:
            self.assertIn(phrase, a["prompt"])
            self.assertIn(phrase, b["prompt"])

    def test_old_unrecorded_flying_cat_mutation_is_now_rejected(self):
        out = compile_contract(self.data)
        out["derived"]["jobs"][1]["prompt"] += " The cat flies upward through the ceiling."
        self.rejects("Derived prompts differ", out)

    def test_editing_reference_motion_or_coverage_cannot_bypass_compiler(self):
        for field in ["reference_prompt", "motion_prompt", "end_frame_prompt", "fact_ids"]:
            out = compile_contract(self.data)
            out["derived"]["jobs"][0][field] = [] if field == "fact_ids" else "A spaceship appears."
            with self.subTest(field=field):
                self.rejects("Derived prompts differ", out)

    def test_handwritten_prompt_in_job_is_not_a_second_output_channel(self):
        self.data["jobs"][0]["prompt"] = "A spaceship appears."
        self.rejects("unsupported plan fields")

    def test_missing_fact_evidence_rejected(self):
        self.data["facts"][2]["evidence_ids"] = []
        self.rejects("lacks direct evidence")

    def test_single_frame_does_not_prove_action(self):
        self.data["facts"][2]["evidence_ids"] = ["EV01"]
        self.rejects("temporal claims need")

    def test_two_distinct_frame_times_support_declared_temporal_interval(self):
        new = deepcopy(self.data["evidence"][0])
        new.update(id="EV04", range_s=[2, 2])
        new["asset"] = dict(path="planned/two.png", sha256="3" * 64)
        self.data["evidence"].append(new)
        self.data["facts"][2]["evidence_ids"] = ["EV01", "EV04"]
        self.assertEqual(validate(compile_contract(self.data)), [])

    def test_evidence_from_a_different_source_is_rejected(self):
        self.data["evidence"][0]["source_sha256"] = "f" * 64
        self.rejects("different source")

    def test_evidence_from_later_event_cannot_support_initial_contact(self):
        self.data["facts"][2]["evidence_ids"] = ["EV03"]
        self.rejects("outside the fact interval")

    def test_unknown_fact_is_visible_in_ledger_but_absent_from_both_prompts(self):
        extra = deepcopy(self.data["facts"][2])
        extra.update(id="UNCERTAIN", status="uncertain", evidence_ids=[], text="Perhaps a spaceship appears.")
        self.data["facts"].append(extra)
        out = compile_contract(self.data)
        self.assertIn("UNCERTAIN", out["derived"]["uncertainties"])
        self.assertNotIn("spaceship", json.dumps(out["derived"]["jobs"]))

    def test_new_content_needs_a_declared_user_request(self):
        self.data["facts"][2]["status"] = "user_requested"
        self.rejects("explicit user request")

    def test_h3_wrappers_are_not_allowed_inside_fact_text(self):
        self.data["facts"][2]["text"] = "[Shot 9] A new event."
        self.rejects("compiler-owned")

    def add_audio(self, status="observed"):
        extra = deepcopy(self.data["facts"][2])
        extra.update(id="A01", kind="soundscape", status=status, text="a soft bell rings.")
        evidence = deepcopy(self.data["evidence"][1])
        evidence.update(id="EA01", kind="audio")
        extra["evidence_ids"] = ["EA01"]
        self.data["facts"].append(extra)
        self.data["evidence"].append(evidence)

    def test_audio_needs_actual_audio_evidence(self):
        self.add_audio()
        self.data["source"]["audio_status"] = "verified"
        self.data["capabilities"]["audio"] = "supported"
        self.data["facts"][-1]["evidence_ids"] = ["EV02"]
        self.rejects("own channel")

    def test_verified_source_audio_does_not_prove_target_audio_support(self):
        self.add_audio()
        self.data["source"]["audio_status"] = "verified"
        self.rejects("supported target audio")

    def test_target_support_does_not_prove_source_audio_was_heard(self):
        self.add_audio()
        self.data["capabilities"]["audio"] = "supported"
        self.rejects("verified source audio")

    def test_authorized_new_audio_still_needs_target_support(self):
        self.add_audio("user_requested")
        self.data.update(intent="adapted", intentional_deviations=["Add a bell at the user's request"])
        self.data["facts"][-1]["request"] = "Please add a soft bell."
        self.rejects("supported target audio")
        self.data["capabilities"]["audio"] = "supported"
        out = compile_contract(self.data)
        self.assertEqual(validate(out), [])
        self.assertIn("a soft bell rings", out["derived"]["jobs"][0]["prompt"])

    def test_either_route_losing_tail_fails(self):
        self.data["jobs"][1].update(source_range_s=[0, 8], duration_s=8)
        self.rejects("I2V: jobs must cover")

    def test_job_overlap_is_not_equivalent_to_full_coverage(self):
        self.data["jobs"].append(dict(self.data["jobs"][0], id="T02"))
        self.rejects("gap or overlap")

    def test_silent_speedup_is_an_adaptation(self):
        self.data["jobs"][0]["duration_s"] = 8
        self.rejects("preserve source timing")

    def test_continuation_job_needs_current_pose(self):
        self.data["jobs"][1].update(source_range_s=[5, 10], duration_s=5)
        self.rejects("current boundary state")

    def test_split_jobs_reset_time_and_inherit_current_state(self):
        state = deepcopy(self.data["facts"][4])
        state.update(id="SPLIT", kind="state", range_s=[5, 5], text="The lifted paw is separated from the ball by a visible gap.")
        self.data["facts"].append(state)
        self.data["jobs"][1].update(source_range_s=[0, 5], duration_s=5)
        second = deepcopy(self.data["jobs"][1])
        second.update(id="I02", source_range_s=[5, 10], opening_fact_ids=["SPLIT"])
        self.data["jobs"].append(second)
        out = compile_contract(self.data)
        self.assertEqual(validate(out), [])
        continuation = out["derived"]["jobs"][2]
        self.assertNotIn("both front paws resting", continuation["reference_prompt"])
        self.assertIn("visible gap", continuation["reference_prompt"])
        self.assertIn("From 0.00 to 1.00 seconds, the same paw", continuation["prompt"])
        self.assertNotIn("F05", continuation["fact_ids"])

    def two_shots(self):
        self.data["source"]["duration_s"] = 20
        # Test-only capability, not a claim about any H3 provider.
        self.data["capabilities"]["max_job_duration_s"] = 30
        self.data["segments"].append(dict(self.data["segments"][0], id="SH02", start_s=10, end_s=20))
        for evidence in deepcopy(self.data["evidence"]):
            evidence["id"] += "B"
            evidence["range_s"] = [x + 10 for x in evidence["range_s"]]
            self.data["evidence"].append(evidence)
        for fact in deepcopy(self.data["facts"]):
            fact["id"] += "B"
            fact["segment_id"] = "SH02"
            fact["evidence_ids"] = [x + "B" for x in fact["evidence_ids"]]
            fact["range_s"] = [x + 10 for x in fact["range_s"]]
            self.data["facts"].append(fact)
        self.data["jobs"][0].update(source_range_s=[0, 20], duration_s=20)
        second = deepcopy(self.data["jobs"][1])
        second.update(id="I02", source_range_s=[10, 20], opening_fact_ids=["F02B"])
        self.data["jobs"].append(second)

    def test_real_cuts_become_t2va_labels_and_separate_i2v_jobs(self):
        self.two_shots()
        out = compile_contract(self.data)
        self.assertEqual(validate(out), [])
        self.assertIn("[Shot 2] At 00:10.000,", out["derived"]["jobs"][0]["prompt"])
        self.assertNotIn("[Shot 2]", out["derived"]["jobs"][2]["prompt"])

    def test_i2v_cut_merge_remains_rejected(self):
        self.two_shots()
        self.data["jobs"][1].update(source_range_s=[0, 20], duration_s=20)
        self.data["jobs"].pop()
        self.rejects("silently merge source cuts")

    def test_final_state_must_be_near_last_frame(self):
        self.data["facts"][8].update(range_s=[8, 8], evidence_ids=["EV02"])
        self.rejects("final state near")

    def test_long_complete_action_is_not_repeated_in_each_job(self):
        self.data["facts"][2]["range_s"] = [0, 8]
        self.data["jobs"][1].update(source_range_s=[0, 5], duration_s=5)
        self.rejects("split temporal fact F03")

    def test_fl2va_requires_real_closing_state_and_capability(self):
        job = self.data["jobs"][1]
        job.update(mode="FL2VA", closing_fact_ids=["F09"])
        job["reference_images"].append(deepcopy(self.data["evidence"][2]["asset"]))
        self.rejects("confirmed end-frame")
        self.data["capabilities"]["end_frames"] = True
        self.assertEqual(validate(compile_contract(self.data)), [])
        job["closing_fact_ids"] = ["F02"]
        self.rejects("current boundary state")

    def test_compiler_never_grants_review(self):
        out = compile_contract(self.data)
        self.assertEqual(out["reviews"]["media"]["status"], "unreviewed")
        self.rejects("media review is required", out, require_reviewed=True)

    def test_unchanged_recompile_preserves_current_receipts(self):
        out = reviewed(self.data)
        self.assertEqual(validate(out, require_reviewed=True), [])
        self.assertEqual(compile_contract(out)["reviews"], out["reviews"])

    def test_fact_change_invalidates_both_receipts(self):
        out = reviewed(self.data)
        out["facts"][2]["text"] = "the cat lifts its other paw."
        self.rejects("review is stale", out)
        recompiled = compile_contract(out)
        self.assertTrue(all(x["status"] == "unreviewed" for x in recompiled["reviews"].values()))
        self.rejects("semantic review is required", recompiled, require_reviewed=True)

    def test_source_change_invalidates_review(self):
        out = reviewed(self.data)
        out["source"]["media"]["path"] = "different.mp4"
        self.rejects("review is stale", out)

    def test_old_receipt_without_tail_check_is_insufficient(self):
        out = reviewed(self.data)
        out["reviews"]["media"]["tail_rechecked"] = False
        self.rejects("tail recheck", out, require_reviewed=True)

    def test_image_alignment_needs_explicit_review(self):
        out = reviewed(self.data)
        out["reviews"]["semantic"]["reference_alignment_checked"] = False
        self.rejects("reference alignment", out, require_reviewed=True)

    def test_withdrawal_cannot_be_moved_after_second_contact(self):
        self.data["facts"][5]["after"] = ["F05"]
        self.assertEqual(validate(compile_contract(self.data)), [])
        self.data["facts"][4]["range_s"] = [6, 7]
        self.rejects("event order contradicts")

    def test_future_identity_change_does_not_leak_into_opening_image(self):
        extra = deepcopy(self.data["facts"][0])
        extra.update(id="LATE", range_s=[5, 10], text="A blue collar is visible only in the later interval.")
        self.data["facts"].append(extra)
        out = compile_contract(self.data)
        self.assertNotIn("blue collar", out["derived"]["jobs"][1]["reference_prompt"])
        self.assertIn("From 5.00 to 10.00 seconds, A blue collar", out["derived"]["jobs"][1]["prompt"])
        self.assertIn("From 5.00 to 10.00 seconds, A blue collar", out["derived"]["jobs"][1]["motion_prompt"])

    def test_media_receipt_cannot_omit_evidence(self):
        out = reviewed(self.data)
        out["reviews"]["media"]["evidence_ids"].pop()
        self.rejects("every evidence", out, require_reviewed=True)

    def test_v1_cannot_claim_strict_gate(self):
        old = json.loads((ROOT / "examples/contract.json").read_text())
        self.rejects("Legacy v1", old, require_reviewed=True)

    def test_local_hash_verification_detects_replaced_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "source.mp4"
            media.write_bytes(b"test fixture bytes, not a real video")
            hashed = file_digest(media)
            asset = {"path": "source.mp4", "sha256": hashed}
            self.data["source"]["media"] = dict(asset)
            for item in self.data["evidence"]:
                item.update(asset=dict(asset), source_sha256=hashed)
            self.data["jobs"][1]["reference_images"] = [dict(asset)]
            out = compile_contract(self.data)
            self.assertEqual(validate(out, root, verify_local_media=True), [])
            source_json = root / "observations.json"
            source_json.write_text(json.dumps(self.data))
            nested = root / "nested"
            nested.mkdir()
            relocated = nested / "contract.json"
            run = subprocess.run([sys.executable, str(ROOT / "scripts/compile_contract.py"), str(source_json), "--output", str(relocated)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(validate(json.loads(relocated.read_text()), nested, verify_local_media=True), [])
            media.write_bytes(b"changed bytes")
            self.rejects("hash mismatch", out, base_dir=root, verify_local_media=True)

    def test_synthetic_example_cannot_claim_generation_readiness(self):
        self.data["generation_ready"] = True
        self.rejects("needs real media", reviewed(self.data))

    def test_malformed_records_are_errors_not_tracebacks(self):
        for key in ["source", "capabilities", "facts", "evidence", "segments", "jobs", "delivery", "analysis_status"]:
            data = deepcopy(self.data)
            data[key] = ["invalid"]
            with self.subTest(key=key):
                self.assertTrue(validate(data))
        for key in ["kind", "evidence_ids", "range_s", "text", "segment_id", "status"]:
            data = deepcopy(self.data)
            data["facts"][0][key] = {"invalid": []}
            with self.subTest(fact_field=key):
                self.assertTrue(input_errors(data))


if __name__ == "__main__":
    unittest.main()
