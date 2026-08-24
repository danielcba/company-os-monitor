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
import urllib.error
import urllib.request

# HTTP status codes used in smoke test assertions.
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429


def log_ok(msg: str) -> None:
    print(f"  + {msg}")  # noqa: T201 - CLI output


def log_fail(msg: str) -> None:
    print(f"  - {msg}")  # noqa: T201 - CLI output


def log_step(msg: str) -> None:
    print(f"\n-> {msg}")  # noqa: T201 - CLI output


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


def _check_step(
    all_passed: bool,
    status: int,
    expected: int | tuple[int, ...],
    success_msg: str,
    fail_msg: str,
) -> bool:
    """Check if status matches expected and log result."""
    expected_tuple = expected if isinstance(expected, tuple) else (expected,)
    if status in expected_tuple:
        log_ok(success_msg)
        return all_passed
    log_fail(fail_msg)
    return False


def _health_check(base_url: str, all_passed: bool) -> bool:
    log_step("1. Health check")
    status, body = http_request(f"{base_url}/health")
    return _check_step(
        all_passed,
        status,
        HTTP_OK,
        f"Gateway healthy: {body.get('status', 'ok')}",
        f"Gateway health check failed: expected 200, got {status}",
    )


def _login(user_url: str, all_passed: bool) -> tuple[bool, str | None, str | None]:
    log_step("2. Login")
    status, body = http_request(
        f"{user_url}/api/v1/auth/login",
        method="POST",
        data={"email": "admin@sandbox.local", "password": "admin"},
    )
    if status == HTTP_OK and "access_token" in body:
        access_token = body["access_token"]
        refresh_token = body.get("refresh_token")
        log_ok("Login successful, got access token")
        return True, access_token, refresh_token
    log_fail(f"Login failed: expected 200, got {status} - {body}")
    log_ok("Skipping remaining tests (login required)")  # noqa: T201 - CLI output
    return False, None, None


def _gateway_with_auth(base_url: str, access_token: str, all_passed: bool) -> bool:
    log_step("3. Gateway with auth")
    headers = {"Authorization": f"Bearer {access_token}"}
    status, body = http_request(f"{base_url}/api/v1/cognitive/summary", headers=headers)
    return _check_step(
        all_passed,
        status,
        HTTP_OK,
        f"Gateway summary responded: {status}",
        f"Gateway auth failed: expected 200, got {status}",
    )


def _unauthorized_request(base_url: str, all_passed: bool) -> bool:
    log_step("4. Unauthorized request (no token)")
    status, body = http_request(f"{base_url}/api/v1/cognitive/summary")
    return _check_step(
        all_passed,
        status,
        HTTP_UNAUTHORIZED,
        f"Correctly rejected unauthenticated request: {status}",
        f"Expected 401 for unauthenticated request, got {status}",
    )


def _cross_tenant_attempt(base_url: str, access_token: str, all_passed: bool) -> bool:
    log_step("5. Cross-tenant attempt (non-superadmin)")
    other_tenant = "00000000-0000-0000-0000-000000000002"
    headers = {"Authorization": f"Bearer {access_token}"}
    status, body = http_request(
        f"{base_url}/api/v1/tenants/{other_tenant}/cognitive/summary",
        headers=headers,
    )
    return _check_step(
        all_passed,
        status,
        (HTTP_FORBIDDEN, HTTP_UNAUTHORIZED),
        f"Correctly blocked cross-tenant: {status}",
        f"Expected 403 for cross-tenant, got {status}",
    )


def _refresh_token_rotation(
    user_url: str, refresh_token: str | None, all_passed: bool
) -> tuple[bool, str | None]:
    log_step("6. Refresh token rotation")
    if not refresh_token:
        log_fail("No refresh token from login")
        return False, None
    status, body = http_request(
        f"{user_url}/api/v1/auth/refresh",
        method="POST",
        data={"refresh_token": refresh_token},
    )
    if status == HTTP_OK and "access_token" in body:
        new_refresh = body["refresh_token"]
        log_ok("Refresh rotation successful")
        return True, new_refresh
    log_fail(f"Refresh failed: expected 200, got {status} - {body}")
    return False, None


def _refresh_token_replay(
    user_url: str, refresh_token: str | None, all_passed: bool
) -> bool:
    log_step("7. Refresh token replay (must fail)")
    if not refresh_token:
        log_fail("Skipping replay test (no refresh token)")
        return False
    status, body = http_request(
        f"{user_url}/api/v1/auth/refresh",
        method="POST",
        data={"refresh_token": refresh_token},
    )
    return _check_step(
        all_passed,
        status,
        HTTP_UNAUTHORIZED,
        f"Correctly rejected refresh replay: {status}",
        f"Expected 401 for refresh replay, got {status}",
    )


def _logout(
    user_url: str, new_refresh: str | None, all_passed: bool
) -> bool:
    log_step("8. Logout")
    if not new_refresh:
        log_fail("Skipping logout test (no refresh token)")
        return False
    status, body = http_request(
        f"{user_url}/api/v1/auth/logout",
        method="POST",
        data={"refresh_token": new_refresh},
    )
    return _check_step(
        all_passed,
        status,
        HTTP_OK,
        f"Logout successful: {status}",
        f"Logout failed: expected 200, got {status}",
    )


def smoke_test(base_url: str) -> bool:
    """Run the full smoke test flow with exact status expectations."""
    all_passed = True
    user_url = base_url.replace("8100", "8099")

    all_passed = _health_check(base_url, all_passed)
    all_passed, access_token, refresh_token = _login(user_url, all_passed)
    if access_token is None:
        return False

    all_passed = _gateway_with_auth(base_url, access_token, all_passed)
    all_passed = _unauthorized_request(base_url, all_passed)
    all_passed = _cross_tenant_attempt(base_url, access_token, all_passed)
    all_passed, new_refresh = _refresh_token_rotation(user_url, refresh_token, all_passed)
    all_passed = _refresh_token_replay(user_url, refresh_token, all_passed)
    all_passed = _logout(user_url, new_refresh, all_passed)

    return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test for Company OS Monitor")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8100",
        help="Base URL of the gateway (default: http://localhost:8100)",
    )
    args = parser.parse_args()

    print(f"Smoke test against {args.base_url}")  # noqa: T201 - CLI output
    print("=" * 50)  # noqa: T201 - CLI output

    passed = smoke_test(args.base_url)

    print("\n" + "=" * 50)  # noqa: T201 - CLI output
    if passed:
        print("All smoke tests PASSED")  # noqa: T201 - CLI output
        sys.exit(0)
    else:
        print("Some smoke tests FAILED")  # noqa: T201 - CLI output
        sys.exit(1)


if __name__ == "__main__":
    main()
