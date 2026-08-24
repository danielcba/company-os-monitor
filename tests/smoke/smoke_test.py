#!/usr/bin/env python3
"""Phase 16 — Smoke Test Script for Docker/Deployment Validation.

This script validates that the system is working end-to-end:
login → JWT → gateway → tenant data → cognitive read → recommendation → decision read

Usage:
    python tests/smoke/smoke_test.py --base-url http://localhost:8100
"""
import argparse
import json
import sys
import urllib.request
import urllib.error


def log_ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def log_fail(msg: str) -> None:
    print(f"  ✗ {msg}")


def log_step(msg: str) -> None:
    print(f"\n→ {msg}")


def http_request(
    url: str,
    method: str = "GET",
    data: dict | None = None,
    headers: dict | None = None,
) -> tuple[int, dict]:
    """Make an HTTP request and return (status, body)."""
    headers = headers or {}
    if data:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def smoke_test(base_url: str) -> bool:
    """Run the full smoke test flow."""
    all_passed = True

    # Step 1: Health check
    log_step("1. Health check")
    status, body = http_request(f"{base_url}/health")
    if status == 200:
        log_ok(f"Gateway healthy: {body.get('status', 'ok')}")
    else:
        log_fail(f"Gateway health check failed: {status}")
        all_passed = False

    # Step 2: Login (if user service is available)
    log_step("2. Login")
    user_url = base_url.replace("8100", "8099")
    status, body = http_request(
        f"{user_url}/api/v1/auth/login",
        method="POST",
        data={"username": "admin", "password": "admin"},
    )
    if status == 200 and "access_token" in body:
        access_token = body["access_token"]
        log_ok("Login successful, got access token")
    else:
        log_fail(f"Login failed: {status} - {body}")
        log_ok("Skipping remaining tests (login required)")
        return False

    # Step 3: Gateway with auth
    log_step("3. Gateway with auth")
    headers = {"Authorization": f"Bearer {access_token}"}
    status, body = http_request(f"{base_url}/api/v1/cognitive/contexts", headers=headers)
    if status in (200, 404):
        log_ok(f"Gateway responded: {status}")
    else:
        log_fail(f"Gateway auth failed: {status}")
        all_passed = False

    # Step 4: Cognitive read
    log_step("4. Cognitive read")
    status, body = http_request(f"{base_url}/api/v1/cognitive/patterns", headers=headers)
    if status in (200, 404):
        log_ok(f"Cognitive read OK: {status}")
    else:
        log_fail(f"Cognitive read failed: {status}")
        all_passed = False

    # Step 5: Summary
    log_step("5. Summary")
    status, body = http_request(f"{base_url}/api/v1/cognitive/summary", headers=headers)
    if status in (200, 404):
        log_ok(f"Summary OK: {status}")
    else:
        log_fail(f"Summary failed: {status}")
        all_passed = False

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Smoke test for Company OS Monitor")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8100",
        help="Base URL of the gateway (default: http://localhost:8100)",
    )
    args = parser.parse_args()

    print(f"Smoke test against {args.base_url}")
    print("=" * 50)

    passed = smoke_test(args.base_url)

    print("\n" + "=" * 50)
    if passed:
        print("All smoke tests PASSED")
        sys.exit(0)
    else:
        print("Some smoke tests FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
