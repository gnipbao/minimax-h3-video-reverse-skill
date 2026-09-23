"""Synthetic workflow gate tests; not evidence of real user consent or video fidelity."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_evidence import fixture, reviewed, ROOT
from evidence_contract import compile_contract, input_errors, narrative_digest, narrative_review_errors
from validate_contract import validate


class NarrativeTests(unittest.TestCase):
    def setUp(self):
        self.data = reviewed(fixture())

    def test_pending_blocks_prompt_compilation_without_creating_confirmation(self):
        data = fixture()
        data["narrative_review"] = {
            "status": "pending", "revision": 1, "summary": "A cat interacts with a ball.",
            "target": "Preserve the action sequence.", "open_questions": [], "receipt": None,
        }
        original = deepcopy(data)
        with self.assertRaisesRegex(ValueError, "confirmation is pending"):
            compile_contract(data)
        self.assertEqual(data, original)
        self.assertNotIn("derived", data)

    def test_cli_pending_does_not_write_or_replace_a_prompt_file(self):
        self.data["narrative_review"].update(status="pending", receipt=None)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root / "input.json", root / "output.json"
            source.write_text(json.dumps(self.data))
            for existing in (False, True):
                if existing:
                    target.write_text("previous output")
                run = subprocess.run([sys.executable, str(ROOT / "scripts/compile_contract.py"), str(source), "--output", str(target)], capture_output=True, text=True)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn("confirmation is pending", run.stderr)
                if existing:
                    self.assertEqual(target.read_text(), "previous output")
                else:
                    self.assertFalse(target.exists())

    def test_confirmed_current_interpretation_passes_strict_review(self):
        self.assertEqual(validate(self.data, require_reviewed=True), [])

    def test_ai_empty_or_missing_reply_cannot_count_as_user_confirmation(self):
        for receipt in (None, {}, {"actor": "assistant", "message": "Looks correct."}, {"actor": "user", "message": " "}):
            self.data["narrative_review"]["receipt"] = receipt
            with self.subTest(receipt=receipt):
                self.assertTrue(any("actual user reply" in e for e in input_errors(self.data)))

    def test_partial_answer_does_not_resolve_all_material_questions(self):
        review = self.data["narrative_review"]
        review["open_questions"] = ["Is the phone recording or playing another video?"]
        review["receipt"]["scope_digest"] = narrative_digest(self.data)
        self.assertTrue(any("material questions unresolved" in e for e in input_errors(self.data)))

    def test_correction_requires_current_scope_not_an_old_confirmation(self):
        for key, value in (("summary", "The phone plays someone else's video."), ("target", "Replace the ending."), ("revision", 2)):
            data = deepcopy(self.data)
            data["narrative_review"][key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "confirmation is stale"):
                    compile_contract(data)

    def test_different_source_or_adaptation_invalidates_confirmation(self):
        other_source = deepcopy(self.data)
        other_source["source"]["media"]["sha256"] = "f" * 64
        other_target = deepcopy(self.data)
        other_target.update(intent="adapted", intentional_deviations=["Replace the ending at the user's request."])
        other_duration = deepcopy(self.data)
        other_duration["source"]["duration_s"] = 11
        for data in (other_source, other_target, other_duration):
            self.assertTrue(any("confirmation is stale" in e for e in narrative_review_errors(data)))

    def test_new_explicit_reply_can_confirm_the_revised_interpretation(self):
        review = self.data["narrative_review"]
        review.update(revision=2, summary="The ball is pushed only after the paw visibly withdraws.")
        review["receipt"] = {"actor": "user", "message": "Synthetic: use the correction and write the prompt."}
        review["receipt"]["scope_digest"] = narrative_digest(self.data)
        output = compile_contract(self.data)
        self.assertEqual(validate(output), [])
        self.assertTrue(all(r["status"] == "unreviewed" for r in output["reviews"].values()))

    def test_delivery_mode_change_reuses_narrative_but_invalidates_output_review(self):
        self.data["delivery"] = "T2VA"
        self.data["jobs"] = [self.data["jobs"][0]]
        self.assertEqual(narrative_review_errors(self.data, required=True), [])
        output = compile_contract(self.data)
        self.assertEqual(validate(output), [])
        self.assertEqual(output["narrative_review"], self.data["narrative_review"])
        self.assertEqual(output["reviews"]["semantic"]["status"], "unreviewed")

    def test_translation_reuses_interpretation_but_still_needs_semantic_recheck(self):
        self.data["facts"][0]["text"] = "一只灰色虎斑猫和一个红球位于浅色木地板上，柔和光线来自画面左侧。"
        self.assertEqual(narrative_review_errors(self.data, required=True), [])
        output = compile_contract(self.data)
        self.assertEqual(validate(output), [])
        self.assertEqual(output["reviews"]["semantic"]["status"], "unreviewed")

    def test_explicit_waiver_is_separate_from_confirmation_and_preserves_unknowns(self):
        review = self.data["narrative_review"]
        review.update(status="waived", open_questions=["The music has not been heard."])
        review["receipt"] = {"actor": "user", "message": "Synthetic: skip confirmation; describe only supported visuals."}
        review["receipt"]["scope_digest"] = narrative_digest(self.data)
        output = compile_contract(self.data)
        self.assertEqual(output["narrative_review"]["status"], "waived")
        self.assertEqual(output["analysis_status"], "PARTIAL")
        self.assertEqual(output["source"]["audio_status"], "unavailable")
        self.assertTrue(all("non_diegetic_music: N/A" in j["prompt"] for j in output["derived"]["jobs"]))

    def test_changing_confirmation_to_waiver_cannot_reuse_receipt(self):
        self.data["narrative_review"]["status"] = "waived"
        self.assertTrue(any("confirmation is stale" in e for e in input_errors(self.data)))

    def test_confirmation_does_not_upgrade_audio_or_create_media_reviews(self):
        data = fixture()
        data["narrative_review"] = deepcopy(self.data["narrative_review"])
        output = compile_contract(data)
        self.assertEqual(output["source"]["audio_status"], "unavailable")
        self.assertTrue(all(r["status"] == "unreviewed" for r in output["reviews"].values()))
        output["analysis_status"] = "COMPLETE"
        self.assertTrue(any("Unavailable requested audio" in e for e in input_errors(output)))

    def test_confirmed_summary_is_not_injected_into_generated_prompt(self):
        output = compile_contract(self.data)
        for job in output["derived"]["jobs"]:
            self.assertNotIn("Synthetic fixture", job["prompt"])
            self.assertNotIn("narrative_review", job["prompt"])
        self.assertEqual(output["derived"]["jobs"][0]["fact_ids"], output["derived"]["jobs"][1]["fact_ids"])

    def test_missing_gate_is_legacy_draft_not_implicit_user_waiver(self):
        legacy = compile_contract(fixture())
        self.assertEqual(validate(legacy), [])
        self.assertNotIn("narrative_review", legacy)
        self.assertTrue(any("narrative_review is required" in e for e in validate(legacy, require_reviewed=True)))
        legacy["generation_ready"] = True
        self.assertTrue(any("narrative_review is required" in e for e in input_errors(legacy)))

    def test_semantic_reviewer_must_check_narrative_alignment(self):
        self.data["reviews"]["semantic"].pop("narrative_alignment_checked")
        self.assertTrue(any("user's narrative decision" in e for e in validate(self.data, require_reviewed=True)))

    def test_malformed_gate_cannot_silently_disable_confirmation(self):
        for value in (None, [], "confirmed", {}, {"status": ["confirmed"]}, {"status": "confirmed", "revision": True}):
            self.data["narrative_review"] = value
            with self.subTest(value=value):
                self.assertTrue(input_errors(self.data))

    def test_file_relocation_preserves_semantic_scope(self):
        old_scope = narrative_digest(self.data)
        self.data["source"]["media"]["path"] = "../same-bytes/source.mp4"
        self.assertEqual(narrative_digest(self.data), old_scope)
        self.assertEqual(narrative_review_errors(self.data, required=True), [])


if __name__ == "__main__":
    unittest.main()
