#!/usr/bin/env python3
"""Benchmark for the glom literal-string fast path.

Each timed sample is one batch of ``iters`` calls to ``glom.glom(target, spec)``.
Warmup batches are recorded but excluded from the aggregate.  Every raw sample
is written to ``benchmark/raw/<impl>-<scale>-<i>.json``.

Usage:
    python benchmark/bench.py --impl baseline --out benchmark/baseline.json
    python benchmark/bench.py --impl optimized --out benchmark/optimized.json
"""
import argparse
import json
import os
import platform
import resource
import statistics
import sys
import time

import glom

SEED = 20261031
SCALES = [
    # name, path depth, calls per sample
    ("small", 3, 10000),
    ("medium", 5, 15000),
    ("large", 8, 20000),
]


def build_target(depth):
    """Nested dicts: {"k0": {"k1": ... {"leaf": 42}}}."""
    target = {"leaf": 42}
    for i in range(depth - 1, -1, -1):
        target = {"k%d" % i: target}
    return target


def path_for(depth):
    return ".".join("k%d" % i for i in range(depth)) + ".leaf"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", required=True, choices=["baseline", "optimized"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw-dir", default="benchmark/raw")
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--samples", type=int, default=5)
    args = ap.parse_args()

    os.makedirs(args.raw_dir, exist_ok=True)
    cpu = ""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass

    summary = {
        "impl": args.impl,
        "upstream": "mahmoud/glom",
        "glom_file": glom.__file__,
        "python": platform.python_version(),
        "cpu": cpu,
        "seed": SEED,
        "command": " ".join([sys.executable] + sys.argv),
        "warmup": args.warmup,
        "samples": args.samples,
        "scales": {},
    }

    for scale, depth, iters in SCALES:
        target = build_target(depth)
        spec = path_for(depth)
        expected = glom.glom(target, spec)
        assert expected == 42, (scale, expected)
        timed_ns = []
        run_index = 0
        for kind, count in (("warmup", args.warmup), ("timed", args.samples)):
            for _ in range(count):
                t0 = time.perf_counter()
                for _ in range(iters):
                    glom.glom(target, spec)
                elapsed = time.perf_counter() - t0
                ns_per_call = elapsed / iters * 1e9
                record = {
                    "impl": args.impl,
                    "scale": scale,
                    "kind": kind,
                    "index": run_index,
                    "depth": depth,
                    "iters": iters,
                    "elapsed_s": elapsed,
                    "ns_per_call": ns_per_call,
                    "seed": SEED,
                    "check_ok": True,
                }
                path = os.path.join(
                    args.raw_dir,
                    "%s-%s-%d.json" % (args.impl, scale, run_index),
                )
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(record, f, indent=2, sort_keys=True)
                    f.write("\n")
                if kind == "timed":
                    timed_ns.append(ns_per_call)
                run_index += 1

        q25, median, q75 = statistics.quantiles(timed_ns, n=4, method="inclusive")
        mean = statistics.mean(timed_ns)
        rel_std = (
            statistics.stdev(timed_ns) / mean * 100.0 if len(timed_ns) > 1 else 0.0
        )
        summary["scales"][scale] = {
            "depth": depth,
            "iters_per_sample": iters,
            "median_ns_per_call": median,
            "p25_ns_per_call": q25,
            "p75_ns_per_call": q75,
            "rel_std_pct": rel_std,
            "timed_samples_ns": timed_ns,
        }
        print(
            "%-6s depth=%d iters=%d median=%.0f ns/call p25=%.0f p75=%.0f rsd=%.1f%%"
            % (scale, depth, iters, median, q25, q75, rel_std)
        )

    summary["peak_rss_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    print("peak_rss_kb=%d" % summary["peak_rss_kb"])
    print("wrote", args.out)


if __name__ == "__main__":
    main()
