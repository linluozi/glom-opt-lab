#!/usr/bin/env python3
"""Generate deterministic glom results for one checkout.

Invoked as a subprocess by ``tests/test_diff.py`` with ``PYTHONPATH`` pointing
at either the baseline or the optimized checkout.  Writes one line per case:
``<case index>\t<OK|ERR> <canonical json or exception>``.
"""
import json
import random
import sys

import glom
from glom import T

SEED = 20261031
KEYS = ["a", "b", "c", "x", "y", "0", "1", "\u00fc", "\u952e", "\u00e9"]
LEAVES = [None, 0, 1, -1, 2 ** 70, 3.5, float("nan"), "", "s", "\u00fc", [], {}]


def canon(obj):
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, allow_nan=True, default=repr
    )


def run_case(target, spec):
    try:
        return "OK " + canon(glom.glom(target, spec))
    except Exception as exc:  # noqa: BLE001 - exception text is the compared output
        return "ERR " + type(exc).__name__ + " " + json.dumps(str(exc), ensure_ascii=False)


def rand_target(rng, depth):
    if depth <= 0:
        return rng.choice(LEAVES)
    kind = rng.choice(["dict", "dict", "list"])
    if kind == "dict":
        return {
            rng.choice(KEYS): rand_target(rng, depth - 1)
            for _ in range(rng.randint(0, 3))
        }
    return [rand_target(rng, depth - 1) for _ in range(rng.randint(0, 3))]


def rand_valid_path(rng, target):
    parts = []
    cur = target
    for _ in range(rng.randint(0, 5)):
        if isinstance(cur, dict) and cur:
            key = rng.choice(sorted(cur.keys()))
            parts.append(key)
            cur = cur[key]
        elif isinstance(cur, list) and cur:
            idx = rng.randrange(len(cur))
            parts.append(str(idx))
            cur = cur[idx]
        else:
            break
    return ".".join(parts)


def rand_spec(rng, target):
    kind = rng.randrange(10)
    if kind < 6:
        return rand_valid_path(rng, target)
    if kind == 6:
        return ".".join(rng.choice(KEYS) for _ in range(rng.randint(0, 5)))
    if kind == 7:
        return T[rng.choice(KEYS)]
    if kind == 8:
        return {"out": rand_valid_path(rng, target)}
    return [rand_valid_path(rng, target)]


def fixed_cases():
    return [
        ({}, ""),
        ({}, "a"),
        ({"a": 1}, "a"),
        ({"a": {"b": 2}}, "a.b"),
        ({"a": [1, 2, 3]}, "a.0"),
        ({"a": [1, 2, 3]}, "a.-1"),
        ({"\u00fc": {"\u952e": "\u503c"}}, "\u00fc.\u952e"),
        ({"a": None}, "a"),
        ({"a": float("nan")}, "a"),
        ({"a": ""}, "a"),
        ({"a": "x" * 10000}, "a"),
        ({"a": 1}, "a.b"),
        ({"a": 1}, "missing"),
        ({"a": 1}, T["a"]),
        ({"a": {"b": 1}}, T["a"]["b"]),
        ({"a": 1}, T.get("missing")),
        ({"a": 1}, T.get("missing", "dflt")),
        ({"a": 1}, {"x": "a"}),
        ({"a": 1}, ("a",)),
        ({"a": "Hello"}, T["a"].upper()),
        ({"a": "a-b"}, T["a"].replace("-", "_")),
        ({"a": 1}, T["a"].bit_length()),
        ({"a": 1}, T["a"] + 1),
        ({"a": 1}, lambda t: t["a"]),
        ({"a": [{"b": 1}]}, "a.0.b"),
        ({"a": {"b": {"c": {"d": 4}}}}, "a.b.c.d"),
        ({"a": 1, "b": 2}, T["a"]),
        ({"a": 1}, T),
        ({"a": 1}, []),
        ({"a": 1}, ["a"]),
        ({"a": 1}, {}),
    ]


def build_cases():
    cases = fixed_cases()
    rng = random.Random(SEED)
    for _ in range(1400):
        target = rand_target(rng, rng.randint(0, 4))
        cases.append((target, rand_spec(rng, target)))
    return cases


def main():
    out_path = sys.argv[1]
    cases = build_cases()
    with open(out_path, "w", encoding="utf-8") as f:
        for idx, (target, spec) in enumerate(cases):
            f.write("%d\t%s\n" % (idx, run_case(target, spec)))


if __name__ == "__main__":
    main()
