#!/usr/bin/env python3
"""Unit tests for runpod_create.py — the money-critical logic.

Run: python3 test_runpod_create.py
No network: _req is monkeypatched. Covers the three failure modes that
otherwise burn GPU budget: duplicate pods, the false-500 bug, and cost overrun.
"""
import importlib.util
import io
import json
import sys

spec = importlib.util.spec_from_file_location("rc", "scripts/runpod_create.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

BASE_QUERY = {
    "runpod_api_key": "k", "pod_name": "tf-vllm", "model": "m",
    "gpu_type_ids": json.dumps(["NVIDIA A40"]), "gpu_count": "1",
    "container_disk_gb": "120", "max_model_len": "16384",
    "vllm_image": "vllm/vllm-openai:latest", "max_cost_per_hr": "0.8",
}


def run_main(query):
    out, err = io.StringIO(), io.StringIO()
    so, se, si = sys.stdout, sys.stderr, sys.stdin
    sys.stdout, sys.stderr, sys.stdin = out, err, io.StringIO(json.dumps(query))
    code = 0
    try:
        rc.main()
    except SystemExit as e:
        code = e.code or 0
    finally:
        sys.stdout, sys.stderr, sys.stdin = so, se, si
    return code, out.getvalue(), err.getvalue()


def test_idempotency():
    calls = {"POST": 0}

    def fake(method, path, key, body=None):
        if method == "POST":
            calls["POST"] += 1
        if method == "GET":
            return 200, [{"id": "abc123", "name": "tf-vllm", "costPerHr": 0.4,
                          "desiredStatus": "RUNNING"}]
        return 200, None
    rc._req = fake
    code, out, _ = run_main({"runpod_api_key": "k", "pod_name": "tf-vllm"})
    r = json.loads(out)
    assert calls["POST"] == 0
    assert r["pod_id"] == "abc123"
    print("PASS idempotency")


def test_false_500():
    state = {"created": False, "posts": 0}

    def fake(method, path, key, body=None):
        if method == "GET":
            return (200, [{"id": "new9", "name": "tf-vllm", "costPerHr": 0.39,
                           "desiredStatus": "RUNNING"}]) if state["created"] else (200, [])
        if method == "POST":
            state["posts"] += 1
            state["created"] = True  # pod created despite HTTP 500
            return 500, {"error": "Unknown column 'NetworkVolume.userId'"}
        return 200, None
    rc._req = fake
    code, out, _ = run_main(BASE_QUERY)
    r = json.loads(out)
    assert state["posts"] == 1, f"expected 1 POST, got {state['posts']}"
    assert r["pod_id"] == "new9"
    print("PASS false-500 (no duplicate pods)")


def test_budget_guard():
    seq = [[], [{"id": "exp", "name": "tf-vllm", "costPerHr": 3.2, "desiredStatus": "RUNNING"}]]
    gi = {"i": 0}
    deleted = {"n": 0}

    def fake(method, path, key, body=None):
        if method == "GET":
            v = seq[min(gi["i"], 1)]
            gi["i"] += 1
            return 200, v
        if method == "POST":
            return 201, {"id": "exp", "name": "tf-vllm", "costPerHr": 3.2,
                         "desiredStatus": "RUNNING"}
        if method == "DELETE":
            deleted["n"] += 1
            return 200, None
        return 200, None
    rc._req = fake
    code, out, err = run_main(BASE_QUERY)
    assert code == 1, f"expected exit 1, got {code}"
    assert deleted["n"] >= 1, "over-budget pod must be deleted"
    print("PASS budget guard")


if __name__ == "__main__":
    test_idempotency()
    test_false_500()
    test_budget_guard()
    print("\nALL PASS")
