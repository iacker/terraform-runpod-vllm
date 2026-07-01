#!/usr/bin/env python3
"""Terraform external data source: safely create a RunPod vLLM pod.

Wraps RunPod's REST API with the false-500 protection documented in the
Hermes runpod-vllm-deploy skill: POST /v1/pods can return HTTP 500 while
STILL creating the pod, so naive retries spawn duplicate billed pods.

Contract (Terraform external provider):
  stdin  : JSON object with all vars as strings
  stdout : JSON object with string values only (pod_id, endpoint, cost_per_hr, status)
  errors : non-zero exit + message on stderr

This script is IDEMPOTENT by pod name: if a pod with the requested name
already exists, it is reused instead of creating a duplicate.
"""
import json
import sys
import time
import urllib.error
import urllib.request

API = "https://rest.runpod.io/v1"


def _req(method, path, key, body=None):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            parsed = json.loads(raw) if raw.strip() else None
        except json.JSONDecodeError:
            parsed = raw
        return e.code, parsed


def get_pods(key):
    status, data = _req("GET", "/pods", key)
    if status != 200:
        fail(f"GET /pods failed: HTTP {status}: {data}")
    # API may return a list or {"pods": [...]}
    if isinstance(data, dict):
        return data.get("pods", data.get("data", []))
    return data or []


def find_by_name(key, name):
    for p in get_pods(key):
        if p.get("name") == name:
            return p
    return None


def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def main():
    q = json.load(sys.stdin)
    key = q["runpod_api_key"]
    name = q["pod_name"]

    # 1) Idempotency: reuse existing pod with this name (never duplicate)
    existing = find_by_name(key, name)
    if existing:
        emit(existing)
        return

    gpu_type_ids = json.loads(q["gpu_type_ids"])  # passed as JSON string
    start_cmd = [
        "--host", "0.0.0.0", "--port", "8000",
        "--model", q["model"], "--trust-remote-code",
        "--max-model-len", str(int(float(q["max_model_len"]))),
    ]
    payload = {
        "name": name,
        "imageName": q["vllm_image"],
        "gpuTypeIds": gpu_type_ids,
        "gpuCount": int(float(q["gpu_count"])),
        "containerDiskInGb": int(float(q["container_disk_gb"])),
        "ports": ["8000/http"],
        "env": {"HF_HUB_ENABLE_HF_TRANSFER": "0"},
        "dockerStartCmd": start_cmd,
    }

    # 2) Safe create loop — NEVER trust the POST status, verify via GET
    created = None
    for _ in range(5):
        # Re-check before every attempt (false-500 may have created it already)
        existing = find_by_name(key, name)
        if existing:
            created = existing
            break
        status, data = _req("POST", "/pods", key, payload)
        # status may be 200/201 (ok) OR 500 (false-500 bug, pod may still exist)
        time.sleep(5)
        existing = find_by_name(key, name)
        if existing:
            created = existing
            break
        if status in (200, 201) and isinstance(data, dict) and data.get("id"):
            created = data
            break
    if not created:
        fail("pod creation failed after 5 attempts (no pod found via GET /pods)")

    # 3) Budget guard: delete and fail if cost exceeds the cap
    max_cost = float(q["max_cost_per_hr"])
    cost = float(created.get("costPerHr") or 0)
    if cost > max_cost > 0:
        pid = created.get("id")
        _req("DELETE", f"/pods/{pid}", key)
        fail(f"pod cost {cost}/hr exceeds cap {max_cost}/hr — deleted pod {pid}. "
             f"Tighten gpu_type_ids or raise max_cost_per_hr.")

    emit(created)


def emit(pod):
    pid = pod.get("id", "")
    endpoint = f"https://{pid}-8000.proxy.runpod.net" if pid else ""
    # Terraform external requires ALL values to be strings
    print(json.dumps({
        "pod_id": str(pid),
        "endpoint": endpoint,
        "cost_per_hr": str(pod.get("costPerHr") or ""),
        "status": str(pod.get("desiredStatus") or ""),
    }))


if __name__ == "__main__":
    main()
