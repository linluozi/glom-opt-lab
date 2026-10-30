# glom-opt-lab

`mahmoud/glom` is a Python library for declarative access and transformation of nested data. This lab pins upstream commit `fd70d30` and adds a 2-line fast path in `arg_val()`: a literal `str` argument returns immediately instead of entering the `_ArgValuator` / `MIN_MODE` scope machinery. Measured median speedup on repeated path access is **2.59x** with byte-identical results on 1,431 differential cases.

Upstream: https://github.com/mahmoud/glom

## What changed and why

In `glom/core.py`, every path segment evaluated by `_t_eval()` goes through `arg_val()`. That function installed a fresh `_ArgValuator`, saved/restored `MIN_MODE` through a `ChainMap`, and re-entered `_glom()` — only for `_ArgValuator.mode()` to return the value unchanged whenever it is not a `list`, `dict`, `tuple`, `set`, or `frozenset`. String segments (the common case for `glom(data, "a.b.c")`) paid that full cost per segment.

The patch adds an exact fast path before the scope bookkeeping:

```python
if type(arg) is str:  # fast path: literal strings evaluate to themselves
    return arg
```

`git diff --stat`: 1 file changed, 2 insertions(+). No public API, return value, or test file changes.

## Benchmark

`benchmark/bench.py` calls `glom.glom(target, "<depth keys>.leaf")` in batches. Each scale has 3 warmup batches (not timed) and 5 timed batches; every raw sample is in `benchmark/raw/`. Fixed seed `20261031`.

| scale | depth | baseline median | optimized median | speedup |
|---|---:|---:|---:|---:|
| small | 3 | 24,015 ns/call | 10,167 ns/call | 2.36x |
| medium | 5 | 32,544 ns/call | 12,586 ns/call | 2.59x |
| large | 8 | 45,078 ns/call | 16,298 ns/call | 2.77x |

Median of the three speedups: **2.59x**. Maximum relative standard deviation among timed samples was 1.9% (medium baseline); no scale exceeded 10%, so no noise caveat is needed beyond ordinary Python interpreter jitter.

This is a microbenchmark of the path-access hot path the patch targets, not an end-to-end application claim.

## Differential test

`tests/test_diff.py` runs `tests/_diff_child.py` twice under `PYTHONPATH=/tmp/glom-base` and `PYTHONPATH=/tmp/glom-opt`. The child generates 1,431 deterministic cases (1,400 seeded random nested targets/paths plus fixed edge cases: empty target, empty path, missing keys, single element, `2**70`, NaN, non-ASCII keys, 10,000-character strings, `T[...]`, `T.get`, dict/list/tuple specs, method calls, callables). Results and exception texts are serialized canonically and compared **byte for byte**.

```
cases=1431 sha256=328a217107574807f2e2bde1c0cf156b1db865dd95332aed023ac6100347e454
1 passed
```

## Quality gates

| gate | result | reproducible command |
|---|---|---|
| G1 upstream tests | **PASS** — 202 passed, 0 failed (baseline 0.43s; patched 0.42s) | `cd /tmp/glom-opt && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest -q` |
| G2 differential | **PASS** — 1,431/1,431 cases byte-identical | `GLOM_BASE=/tmp/glom-base GLOM_OPT=/tmp/glom-opt /tmp/glom-opt/.venv/bin/python -m pytest -q tests/test_diff.py` |
| G3 median speedup | **PASS** — 2.59x (threshold 1.15x) | `benchmark/bench.py` runs below, compare `median_ns_per_call` |
| G4 large-scale regression | **PASS** — 2.77x (threshold 0.95x) | same, `large` scale |
| G5 peak RSS | **PASS** — 24,392 KB baseline vs 24,392 KB patched, ratio 1.000 (threshold 1.10x) | `/usr/bin/time -v ... bench.py`; logs in `benchmark/raw/memory-*.txt` |

The upstream suite needs its declared test extra (PyYAML); without it the two YAML CLI tests fail for a missing optional dependency. The command above installs `pytest PyYAML`, which is what upstream's `setup.py` `test` extra lists.

## Reproduce

Run from the root of this repository. The three commands build the baseline and patched checkouts in `/tmp`, run the upstream and differential tests, and rerun both benchmarks.

```bash
git clone --depth=1 git@github-linluozi:mahmoud/glom.git /tmp/glom-opt && git -C /tmp/glom-opt apply "$PWD/patch.diff" && python3 -m venv /tmp/glom-opt/.venv && /tmp/glom-opt/.venv/bin/pip -q install -e /tmp/glom-opt pytest PyYAML
```

```bash
git clone --depth=1 git@github-linluozi:mahmoud/glom.git /tmp/glom-base && python3 -m venv /tmp/glom-base/.venv && /tmp/glom-base/.venv/bin/pip -q install -e /tmp/glom-base pytest PyYAML && (cd /tmp/glom-base && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest -q) && (cd /tmp/glom-opt && PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest -q) && GLOM_BASE=/tmp/glom-base GLOM_OPT=/tmp/glom-opt /tmp/glom-opt/.venv/bin/python -m pytest -q tests/test_diff.py
```

```bash
/tmp/glom-base/.venv/bin/python benchmark/bench.py --impl baseline --out /tmp/baseline.json --raw-dir /tmp/raw && /tmp/glom-opt/.venv/bin/python benchmark/bench.py --impl optimized --out /tmp/optimized.json --raw-dir /tmp/raw
```

## Environment

- CPU: AMD EPYC 7K62 48-Core Processor, 4 vCPU visible
- Memory: 3,812,564 kB total (3.6 GiB)
- Python: 3.12.3
- Upstream: `mahmoud/glom` @ `fd70d3051a6a1bcb5152ec2d8e2cdc8e852f95e6` (2026-09-08)
- Seed: `20261031`
- Timing: `time.perf_counter()`, batch medians with p25/p75 in the JSON files
