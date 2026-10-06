"""Tests for scripts/validate.py, the check that runs before an updated price list is published.

validate.py compares ./prices.json with the committed list (`git show HEAD:prices.json`), so each
test builds a throwaway git repository with a committed baseline, writes the new list next to it
and runs the script there.

Run from the repository root: python3 -m unittest discover -s tests
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "validate.py")

BASELINE = {
    "version": "2026-10-06",
    "currency": "USD",
    "updatedAt": "2026-10-06T06:00:00Z",
    "source": "Official pricing pages of each provider",
    "rates": {
        "byteplus/seedance-2.0.1080p": 0.1512,
        "google/nano-banana-2.image-1k": 0.067,
        "kling/credit": 0.14,
        "openai/gpt-image-2.image-output": 30.0,
        "topaz/credit": 0.25,
    },
    "details": {
        "openai/gpt-image-2.image-output": {"label": "Image output tokens", "unit": "perMillionTokens", "provider": "openai", "model": "GPT Image 2"},
    },
    "pricingPages": {"openai": "https://developers.openai.com/api/docs/pricing"},
}


def git(repo, *args):
    """Runs git in `repo` without the user's hooks, signing or identity."""
    subprocess.run(
        ["git", "-c", "user.name=Price Tests", "-c", "user.email=tests@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        cwd=repo, check=True, capture_output=True, text=True,
    )


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="imogen-prices-test-")
        self.repo = self._tmp.name
        git(self.repo, "init", "-q")
        self.commit(BASELINE)

    def tearDown(self):
        self._tmp.cleanup()

    # Helpers

    def write(self, data=None, raw=None):
        text = raw if raw is not None else json.dumps(data, indent=2, sort_keys=True) + "\n"
        with open(os.path.join(self.repo, "prices.json"), "w") as file:
            file.write(text)

    def commit(self, data):
        self.write(data)
        git(self.repo, "add", "prices.json")
        git(self.repo, "commit", "-q", "-m", "Prices")

    def validate(self, data=None, raw=None, python_flags=()):
        if data is not None or raw is not None:
            self.write(data, raw)
        return subprocess.run([sys.executable, *python_flags, SCRIPT], cwd=self.repo, capture_output=True, text=True)

    def updated(self, **rates):
        """The baseline with some rates changed or added, a week later (as an update is)."""
        data = copy.deepcopy(BASELINE)
        data["updatedAt"] = "2026-10-13T06:00:00Z"
        for key, value in rates.items():
            data["rates"][key] = value
        return data

    def assertPasses(self, result):
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return result.stdout

    def assertFails(self, result, message):
        self.assertNotEqual(result.returncode, 0, msg=result.stdout)
        self.assertIn(message, result.stderr)

    # A valid list

    def test_an_unchanged_list_passes(self):
        out = self.assertPasses(self.validate(BASELINE))
        self.assertEqual(out.strip(), "OK: 5 rates, 0 changed: none")

    def test_reports_the_rates_that_changed(self):
        data = copy.deepcopy(BASELINE)
        data["rates"]["kling/credit"] = 0.12
        data["rates"]["openai/gpt-image-2.image-output"] = 40
        data["updatedAt"] = "2026-10-13T06:00:00Z"
        data["version"] = "2026-10-13"
        out = self.assertPasses(self.validate(data))
        self.assertEqual(out.strip(), "OK: 5 rates, 2 changed: kling/credit, openai/gpt-image-2.image-output")

    def test_the_same_price_written_differently_is_not_a_change(self):
        data = copy.deepcopy(BASELINE)
        data["rates"]["openai/gpt-image-2.image-output"] = 30  # was 30.0
        out = self.assertPasses(self.validate(data))
        self.assertIn("0 changed: none", out)

    def test_accepts_the_timestamp_formats_the_app_and_workflow_write(self):
        for stamp in ["2026-10-13T06:00:00Z", "2026-10-13T06:00:00+00:00", "2026-10-13T14:00:00+08:00", "2026-10-13T06:00:00.123Z", "2026-10-13"]:
            data = copy.deepcopy(BASELINE)
            data["updatedAt"] = stamp
            with self.subTest(stamp=stamp):
                self.assertPasses(self.validate(data))

    def test_ignores_details_and_pricing_pages(self):
        # The app only reads `rates`; the other sections are notes for people.
        data = copy.deepcopy(BASELINE)
        data["details"] = {}
        data["pricingPages"]["topaz"] = "https://www.topazlabs.com/api"
        self.assertPasses(self.validate(data))

    # The shape the app reads

    def test_needs_a_version(self):
        for version in [None, "", 20261006]:
            data = copy.deepcopy(BASELINE)
            if version is None:
                del data["version"]
            else:
                data["version"] = version
            with self.subTest(version=version):
                self.assertFails(self.validate(data), "version missing")

    def test_needs_us_dollars(self):
        for currency in [None, "EUR", "usd"]:
            data = copy.deepcopy(BASELINE)
            if currency is None:
                del data["currency"]
            else:
                data["currency"] = currency
            with self.subTest(currency=currency):
                self.assertFails(self.validate(data), "currency must be USD")

    def test_needs_a_valid_update_time(self):
        for stamp, error in [("next Monday", "ValueError"), ("2026-13-45T00:00:00Z", "ValueError"), (None, "KeyError"), (1791273600, "AttributeError")]:
            data = copy.deepcopy(BASELINE)
            if stamp is None:
                del data["updatedAt"]
            else:
                data["updatedAt"] = stamp
            with self.subTest(stamp=stamp):
                self.assertFails(self.validate(data), error)

    def test_needs_rates(self):
        for rates in [{}, [], None]:
            data = copy.deepcopy(BASELINE)
            data["rates"] = rates
            with self.subTest(rates=rates):
                result = self.validate(data)
                self.assertNotEqual(result.returncode, 0)

    def test_rates_must_be_numbers(self):
        for value in ["0.14", True, False, None, [0.14], {"usd": 0.14}]:
            with self.subTest(value=value):
                self.assertFails(self.validate(self.updated(**{"kling/credit": value})), "kling/credit is not a number")

    def test_rates_must_be_positive_and_below_a_thousand(self):
        for value in [0, -0.14, 1000, 1500.5]:
            with self.subTest(value=value):
                self.assertFails(self.validate(self.updated(**{"kling/credit": value})), "out of range")

    def test_rejects_non_finite_rates(self):
        # Python's json module reads these non-standard tokens.
        raw = json.dumps(BASELINE, indent=2).replace('"kling/credit": 0.14', '"kling/credit": NaN')
        self.assertFails(self.validate(raw=raw), "out of range")
        raw = json.dumps(BASELINE, indent=2).replace('"kling/credit": 0.14', '"kling/credit": Infinity')
        self.assertFails(self.validate(raw=raw), "out of range")

    def test_the_largest_allowed_rate_is_just_under_a_thousand(self):
        data = copy.deepcopy(BASELINE)
        data["rates"]["openai/gpt-image-2.image-output"] = 300
        self.commit(data)
        data["rates"]["openai/gpt-image-2.image-output"] = 999.99
        data["updatedAt"] = "2026-10-13T06:00:00Z"
        self.assertPasses(self.validate(data))

    def test_rejects_a_file_that_is_not_json(self):
        result = self.validate(raw="{ this is not json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("JSONDecodeError", result.stderr)

    # The set of rates

    def test_rejects_added_rates(self):
        self.assertFails(self.validate(self.updated(**{"newco/model.image": 0.05})), "rates were added or removed")

    def test_rejects_removed_rates(self):
        data = copy.deepcopy(BASELINE)
        del data["rates"]["topaz/credit"]
        self.assertFails(self.validate(data), "rates were added or removed")

    def test_rejects_renamed_rates(self):
        data = copy.deepcopy(BASELINE)
        data["rates"]["topaz/credits"] = data["rates"].pop("topaz/credit")
        self.assertFails(self.validate(data), "rates were added or removed")

    # Implausible jumps

    def test_rejects_a_price_more_than_five_times_higher(self):
        result = self.validate(self.updated(**{"openai/gpt-image-2.image-output": 151}))
        self.assertFails(result, "openai/gpt-image-2.image-output changed 30.0 -> 151; check the units")

    def test_rejects_a_price_more_than_five_times_lower(self):
        # e.g. a per-million-token price entered per thousand tokens.
        result = self.validate(self.updated(**{"openai/gpt-image-2.image-output": 0.03}))
        self.assertFails(result, "openai/gpt-image-2.image-output changed 30.0 -> 0.03; check the units")

    def test_allows_up_to_five_times_either_way(self):
        for value in [150, 6, 29.5, 31]:
            with self.subTest(value=value):
                self.assertPasses(self.validate(self.updated(**{"openai/gpt-image-2.image-output": value})))
        for value in [1.25, 0.05]:
            with self.subTest(value=value):
                self.assertPasses(self.validate(self.updated(**{"topaz/credit": value})))

    def test_checks_every_rate_not_just_the_first(self):
        result = self.validate(self.updated(**{"topaz/credit": 0.25, "byteplus/seedance-2.0.1080p": 2.0}))
        self.assertFails(result, "byteplus/seedance-2.0.1080p changed 0.1512 -> 2.0")

    # The update time

    def test_changed_rates_need_a_later_update_time(self):
        # The app only applies a hosted list newer than the one it has, so an update that keeps
        # the old time would never reach anyone.
        for stamp in ["2026-10-06T06:00:00Z", "2026-10-06T05:00:00Z", "2026-10-06T14:00:00+08:00"]:
            data = self.updated(**{"kling/credit": 0.12})
            data["updatedAt"] = stamp
            with self.subTest(stamp=stamp):
                self.assertFails(self.validate(data), "updatedAt didn't move forward")
        self.assertPasses(self.validate(self.updated(**{"kling/credit": 0.12})))

    def test_an_unchanged_list_may_keep_its_update_time(self):
        self.assertPasses(self.validate(BASELINE))

    def test_checks_still_run_with_python_optimizations(self):
        # `python -O` strips asserts; the checks don't rely on them.
        self.assertFails(self.validate(self.updated(**{"kling/credit": -1}), python_flags=("-O",)), "out of range")
        data = copy.deepcopy(BASELINE)
        data["currency"] = "EUR"
        self.assertFails(self.validate(data, python_flags=("-O",)), "currency must be USD")

    # The committed list

    def test_a_broken_committed_list_doesnt_block_updates(self):
        self.write(raw="{ broken")
        git(self.repo, "add", "prices.json")
        git(self.repo, "commit", "-q", "-m", "Broken")
        out = self.assertPasses(self.validate(BASELINE))
        self.assertIn("Warning: the committed prices.json isn't JSON", out)
        # The new list itself is still checked.
        data = copy.deepcopy(BASELINE)
        data["currency"] = "EUR"
        self.assertFails(self.validate(data), "currency must be USD")

    def test_needs_a_committed_list_to_compare_with(self):
        # A repository whose last commit has no prices.json.
        git(self.repo, "rm", "-q", "prices.json")
        git(self.repo, "commit", "-q", "-m", "Remove")
        result = self.validate(BASELINE)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CalledProcessError", result.stderr)

    def test_compares_with_the_last_commit_not_the_working_copy(self):
        # Several runs without committing are each compared with HEAD.
        self.write(self.updated(**{"kling/credit": 0.6}))
        result = self.validate(self.updated(**{"kling/credit": 0.13}))
        self.assertIn("1 changed: kling/credit", self.assertPasses(result))


if __name__ == "__main__":
    unittest.main()
