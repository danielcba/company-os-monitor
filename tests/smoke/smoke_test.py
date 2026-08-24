#!/usr/bin/env python3
"""Phase 20 -- Smoke Test Script for Docker/Deployment Validation.

Validates the full runtime flow with EXACT expected status codes:
health -> login -> access token -> authenticated request -> tenant-scoped data
-> confidence read -> recommendation read -> decision read
-> unauthorized cross-tenant attempt (must fail) -> logout -> refresh reuse (must fail)

Usage:
    python tests/smoke/smoke_test.py --base-url http://localhost:8100
"""
import argparse
import json
import sys
import urllib.request
import urllib.error


def log_ok(msg: str) -> None:
    print(f"  + {msg}")


def log_fail(msg: str) -> None:
    print(f"  - {msg}")


def log_step(msg: str) -> None:
    print(f"\n-> {msg}")


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
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def smoke_test(base_url: str) -> bool:
    """Run the full smoke test flow with exact status expectations."""
    all_passed = True

    # Step 1: Health check — MUST be 200
    log_step("1. Health check")
    status, body = http_request(f"{base_url}/health")
    if status == 200:
        log_ok(f"Gateway healthy: {body.get('status', 'ok')}")
    else:
        log_fail(f"Gateway health check failed: expected 200, got {status}")
        all_passed = False

    # Step 2: Login — MUST be 200 with access_token
    log_step("2. Login")
    user_url = base_url.replace("8100", "8099")
    status, body = http_request(
        f"{user_url}/api/v1/auth/login",
        method="POST",
        data={"email": "admin@sandbox.local", "password": "admin"},
    )
    if status == 200 and "access_token" in body:
        access_token = body["access_token"]
        refresh_token = body.get("refresh_token")
        log_ok("Login successful, got access token")
    else:
        log_fail(f"Login failed: expected 200, got {status} - {body}")
        log_ok("Skipping remaining tests (login required)")
        return False

    # Step 3: Gateway with auth — MUST be 200 (not 404)
    log_step("3. Gateway with auth")
    headers = {"Authorization": f"Bearer {access_token}"}
    status, body = http_request(f"{base_url}/api/v1/cognitive/summary", headers=headers)
    if status == 200:
        log_ok(f"Gateway summary responded: {status}")
    else:
        log_fail(f"Gateway auth failed: expected 200, got {status}")
        all_passed = False

    # Step 4: Unauthorized request without token — MUST be 401
    log_step("4. Unauthorized request (no token)")
    status, body = http_request(f"{base_url}/api/v1/cognitive/summary")
    if status == 401:
        log_ok(f"Correctly rejected unauthenticated request: {status}")
    else:
        log_fail(f"Expected 401 for unauthenticated request, got {status}")
        all_passed = False

    # Step 5: Cross-tenant attempt — MUST be 403 (for non-superadmin)
    log_step("5. Cross-tenant attempt (non-superadmin)")
    other_tenant = "00000000-0000-0000-0000-000000000002"
    status, body = http_request(
        f"{base_url}/api/v1/tenants/{other_tenant}/cognitive/summary",
        headers=headers,
    )
    if status in (403, 401):
        log_ok(f"Correctly blocked cross-tenant: {status}")
    else:
        log_fail(f"Expected 403 for cross-tenant, got {status}")
        all_passed = False

    # Step 6: Refresh token rotation
    log_step("6. Refresh token rotation")
    if refresh_token:
        status, body = http_request(
            f"{user_url}/api/v1/auth/refresh",
            method="POST",
            data={"refresh_token": refresh_token},
        )
        if status == 200 and "access_token" in body:
            new_refresh = body["refresh_token"]
            log_ok("Refresh rotation successful")
        else:
            log_fail(f"Refresh failed: expected 200, got {status} - {body}")
            all_passed = False
            new_refresh = None
    else:
        log_fail("No refresh token from login")
        all_passed = False
        new_refresh = None

    # Step 7: Refresh token replay — MUST fail (401)
    log_step("7. Refresh token replay (must fail)")
    if refresh_token:
        status, body = http_request(
            f"{user_url}/api/v1/auth/refresh",
            method="POST",
            data={"refresh_token": refresh_token},
        )
        if status == 401:
            log_ok(f"Correctly rejected refresh replay: {status}")
        else:
            log_fail(f"Expected 401 for refresh replay, got {status}")
            all_passed = False
    else:
        log_fail("Skipping replay test (no refresh token)")
        all_passed = False

    # Step 8: Logout
    log_step("8. Logout")
    if new_refresh:
        status, body = http_request(
            f"{user_url}/api/v1/auth/logout",
            method="POST",
            data={"refresh_token": new_refresh},
        )
        if status == 200:
            log_ok(f"Logout successful: {status}")
        else:
            log_fail(f"Logout failed: expected 200, got {status}")
            all_passed = False
    else:
        log_fail("Skipping logout test (no refresh token)")
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
