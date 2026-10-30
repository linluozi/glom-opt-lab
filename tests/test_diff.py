"""Byte-for-byte differential test: baseline glom vs patched glom.

Both checkouts must already exist.  Point the test at them with GLOM_BASE and
GLOM_OPT (defaults: /tmp/glom-base and /tmp/glom-opt).

    GLOM_BASE=/tmp/glom-base GLOM_OPT=/tmp/glom-opt \
        python -m pytest -q tests/test_diff.py
"""
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = os.path.join(ROOT, "tests", "_diff_child.py")
BASE = os.environ.get("GLOM_BASE", "/tmp/glom-base")
OPT = os.environ.get("GLOM_OPT", "/tmp/glom-opt")


def produce(checkout, out_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = checkout + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run(
        [sys.executable, CHILD, str(out_path)],
        check=True,
        env=env,
        cwd=ROOT,
    )


def test_diff_byte_identical(tmp_path):
    base_out = tmp_path / "baseline.txt"
    opt_out = tmp_path / "optimized.txt"
    produce(BASE, base_out)
    produce(OPT, opt_out)

    base_bytes = base_out.read_bytes()
    opt_bytes = opt_out.read_bytes()
    lines = [ln for ln in base_bytes.splitlines() if b"\t" in ln]
    assert len(lines) >= 1000, "expected >=1000 cases, got %d" % len(lines)
    assert base_bytes == opt_bytes, (
        "differential mismatch: baseline sha256=%s optimized sha256=%s"
        % (
            hashlib.sha256(base_bytes).hexdigest(),
            hashlib.sha256(opt_bytes).hexdigest(),
        )
    )
    print("cases=%d sha256=%s" % (len(lines), hashlib.sha256(base_bytes).hexdigest()))
