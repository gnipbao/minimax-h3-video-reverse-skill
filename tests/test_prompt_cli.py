"""Read-only prompt CLI regressions; these do not judge visual semantics."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_contract import I2VA_PREFIX


def prompt(mode="I2VA", main="[Shot 1] A folded blue product opens continuously."):
    prefix = ""
    if mode == "I2VA":
        prefix = I2VA_PREFIX + "\n\n"
    elif mode == "FL2VA":
        prefix = ("How the reference pictures align with the target video — Picture 1 (from Shot 1) "
                  "aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) "
                  "aligns with the 2.00-second mark of the target video.\n\n")
    return (prefix + f"integrated_multimodal_description: {main}\n\n"
            "overall_soundscape: N/A\n\nnon_diegetic_music: N/A")


class PromptCliTests(unittest.TestCase):
    def run_cli(self, text, mode="I2VA", duration="2", shots="1", extra=()):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompt.txt"
            original = text.encode("utf-8")
            path.write_bytes(original)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/validate_prompt.py"), str(path),
                 "--mode", mode, "--duration", duration, "--source-shot-count", shots, *extra],
                capture_output=True, text=True,
            )
            self.assertEqual(path.read_bytes(), original, "The validator must not modify its input")
            return result

    def test_single_i2va_and_fl2va_pass_with_explicit_limitations(self):
        for mode in ("I2VA", "FL2VA"):
            with self.subTest(mode=mode):
                result = self.run_cli(prompt(mode), mode=mode, extra=("--audio-omitted",))
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertIn("declared source-cut gate passed", result.stdout)
                self.assertIn("does not verify media interpretation", result.stdout)
                self.assertIn("user authorization", result.stdout)

    def test_multiple_target_shots_remain_invalid_for_i2va(self):
        result = self.run_cli(prompt(main="[Shot 1] A room. [Shot 2] At 00:01.000, a second view."), shots="2")
        self.assertEqual(result.returncode, 1)
        self.assertIn("one continuous target shot", result.stdout)

    def test_multiple_declared_source_shots_cannot_hide_behind_single_label(self):
        for mode in ("I2VA", "FL2VA"):
            with self.subTest(mode=mode):
                result = self.run_cli(prompt(mode), mode=mode, shots="3")
                self.assertEqual(result.returncode, 1)
                self.assertIn("multiple declared source shots", result.stdout)

    def test_declared_continuous_adaptation_still_requires_single_target_shot(self):
        result = self.run_cli(prompt(), shots="3", extra=("--continuous-adaptation",))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        multiple = prompt(main="[Shot 1] A room. [Shot 2] At 00:01.000, a second view.")
        result = self.run_cli(multiple, shots="3", extra=("--continuous-adaptation",))
        self.assertEqual(result.returncode, 1)
        self.assertIn("one continuous target shot", result.stdout)

    def test_multiple_t2va_shots_pass(self):
        text = prompt("T2VA", "[Shot 1] A room. [Shot 2] At 00:01.000, a rear view.")
        result = self.run_cli(text, mode="T2VA", shots="2")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_out_of_range_or_nonincreasing_cut_times_fail(self):
        for main in ("[Shot 1] A room. [Shot 2] At 00:02.000, a second view.",
                     "[Shot 1] A room. [Shot 2] At 00:01.000, a second view. [Shot 3] At 00:00.500, a third view."):
            with self.subTest(main=main):
                result = self.run_cli(prompt("T2VA", main), mode="T2VA", shots="2")
                self.assertEqual(result.returncode, 1)
                self.assertIn("Cut times must increase strictly", result.stdout)

    def test_invalid_mode_duration_and_source_count_are_argument_errors(self):
        cases = [("mode", "AUTO"), *[("duration", x) for x in ("0", "-1", "nan", "inf", "no")],
                 *[("shots", x) for x in ("0", "-1", "1.5", "no")]]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                result = self.run_cli(prompt(), **{field: value})
                self.assertEqual(result.returncode, 2)
                self.assertIn("error:", result.stderr)

    def test_audio_omission_is_opt_in_and_enforced(self):
        text = prompt().replace("overall_soundscape: N/A", "overall_soundscape: A declared bell rings.")
        self.assertEqual(self.run_cli(text).returncode, 0)
        result = self.run_cli(text, extra=("--audio-omitted",))
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unverified or excluded audio fields", result.stdout)

    def test_unreadable_or_non_utf8_file_is_an_argument_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "input.txt"
            for content in (None, b"\xff"):
                if content is not None:
                    path.write_bytes(content)
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/validate_prompt.py"), str(path),
                     "--mode", "I2VA", "--duration", "2", "--source-shot-count", "1"],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot read UTF-8 prompt", result.stderr)
                if content is not None:
                    self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
