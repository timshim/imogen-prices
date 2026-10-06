"""Checks prices.json before it's published: the shape the Imogen app reads, sane values, no
rates added or removed (new rates only come from Imogen releases), and a later updatedAt whenever
a rate changes (the app only applies a list newer than the one it already has).

The checks are explicit rather than asserts, so running Python with -O can't switch them off."""
import json, math, subprocess, sys
from datetime import datetime, timezone


class Invalid(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Invalid(message)


def updated_at(data):
    try:
        stamp = datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, TypeError, ValueError) as error:
        raise Invalid(f"updatedAt is missing or not an ISO 8601 time ({type(error).__name__}: {error})")
    # A plain date, or a time without an offset, is UTC, as the app reads it.
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def load(text, name):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise Invalid(f"{name} isn't JSON (JSONDecodeError: {error})")
    check(isinstance(data, dict), f"{name} isn't a JSON object")
    check(isinstance(data.get("version"), str) and data["version"], "version missing")
    check(data.get("currency") == "USD", "currency must be USD")
    updated_at(data)
    rates = data.get("rates")
    check(isinstance(rates, dict) and rates, "rates missing")
    for key, value in rates.items():
        check(isinstance(value, (int, float)) and not isinstance(value, bool), f"{key} is not a number")
        check(math.isfinite(value) and 0 < value < 1000, f"{key} = {value} is out of range")
    return data


def main():
    with open("prices.json") as file:
        new = load(file.read(), "prices.json")
    committed = subprocess.run(["git", "show", "HEAD:prices.json"], capture_output=True, text=True)
    if committed.returncode != 0:
        raise Invalid(f"there's no committed prices.json to compare with (CalledProcessError: {committed.stderr.strip()})")
    try:
        old = load(committed.stdout, "the committed prices.json")
    except Invalid as error:
        # A broken committed list mustn't block every later update: check the new one on its own.
        print(f"Warning: {error}. Checked the new list on its own.")
        print(f"OK: {len(new['rates'])} rates")
        return

    check(set(new["rates"]) == set(old["rates"]), "rates were added or removed")
    for key in new["rates"]:
        before, after = old["rates"][key], new["rates"][key]
        # A price moving more than 5x either way is almost certainly a unit mistake.
        check(after / before <= 5 and before / after <= 5, f"{key} changed {before} -> {after}; check the units")
    changed = [key for key in new["rates"] if new["rates"][key] != old["rates"][key]]
    if changed:
        check(updated_at(new) > updated_at(old),
              "rates changed but updatedAt didn't move forward; the app only applies a list newer than the one it has")
    print(f"OK: {len(new['rates'])} rates, {len(changed)} changed: {', '.join(changed) or 'none'}")


if __name__ == "__main__":
    try:
        main()
    except Invalid as error:
        sys.exit(f"Invalid price list: {error}")
