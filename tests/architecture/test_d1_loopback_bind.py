"""D1 contract tests: host-native services bind loopback only (127.0.0.1).

D1 architectural decision (2026-09-29): the 14 host-native services started by
``start.sh`` (SERVICE_SPECS + linux-agent, ports 8090-8103) must listen on
``127.0.0.1`` exclusively. They are plain host processes - not containers -
and every verified consumer (gateway health fan-out, browser ``client.ts``,
``start.sh`` probes) is host-local, so ``0.0.0.0`` only added unnecessary LAN
surface while the compose perimeter already publishes loopback-only.

Static tests pin the architectural decision where it is expressed (service
code, launcher inventory, compose publications, consumer registry); the
runtime test boots the real linux-agent entry point and fails if the health
server stops binding loopback (regression guard), including an OS-level
socket check and a reachability check from a non-loopback interface.

Out of scope by the same decision: ``windows-agent``/``vmware-agent`` health
servers still declare ``0.0.0.0`` but are never launched by ``start.sh``, so
they open no socket on this host; a future remote-agent deployment requires
its own explicit architectural decision.
"""
import http
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT / "apps" / "agents" / "linux-agent"

# The 14 services of the D1 decision: launcher inventory (ports) + bind sites.
D1_BIND_FILES = [
    "apps/services/collector-service/src/health.py",
    "apps/services/context-service/src/health.py",
    "apps/services/pattern-service/src/health.py",
    "apps/services/anomaly-service/src/health.py",
    "apps/services/hypothesis-service/src/health.py",
    "apps/services/confidence-service/src/health.py",
    "apps/services/recommendation-service/src/health.py",
    "apps/services/decision-service/src/health.py",
    "apps/services/report-service/src/health.py",
    "apps/services/insight-service/src/health.py",
    "apps/services/evaluation-service/src/main.py",
    "apps/services/user-service/src/health.py",
    "apps/gateway/api-gateway/src/health.py",
    "apps/agents/linux-agent/src/health.py",
]

# Canonical launcher inventory: name|dir|env|port (must stay 8090-8103).
LAUNCHER_SPECS = [
    "collector|apps/services/collector-service|HEALTH_PORT|8090",
    "context|apps/services/context-service|ACTIVATOR_HEALTH_PORT|8091",
    "pattern|apps/services/pattern-service|PATTERN_HEALTH_PORT|8092",
    "anomaly|apps/services/anomaly-service|ANOMALY_HEALTH_PORT|8093",
    "hypothesis|apps/services/hypothesis-service|HYPOTHESIS_HEALTH_PORT|8094",
    "insight|apps/services/insight-service|INSIGHT_HEALTH_PORT|8101",
    "confidence|apps/services/confidence-service|CONFIDENCE_HEALTH_PORT|8095",
    "recommendation|apps/services/recommendation-service|RECOMMENDATION_HEALTH_PORT|8096",
    "decision|apps/services/decision-service|DECISION_HEALTH_PORT|8097",
    "evaluation|apps/services/evaluation-service|EVALUATION_HEALTH_PORT|8102",
    "report|apps/services/report-service|REPORT_HEALTH_PORT|8098",
    "user|apps/services/user-service|USER_HEALTH_PORT|8099",
    "gateway|apps/gateway/api-gateway|GATEWAY_HEALTH_PORT|8100",
    "linux-agent|apps/agents/linux-agent|AGENT_HEALTH_PORT|8103",
]

LOOPBACK = "127.0.0.1"
BIND_ALL = "0.0.0.0"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


@pytest.mark.parametrize("relative", D1_BIND_FILES)
def test_d1_service_binds_loopback(relative: str):
    """1. Each of the 14 services binds 127.0.0.1 and carries no 0.0.0.0."""
    src = _read(relative)
    assert re.search(
        rf'TCPSite\([^)]*"{re.escape(LOOPBACK)}"', src
    ), f"{relative} must TCPSite on 127.0.0.1"
    assert BIND_ALL not in src, f"{relative} must not retain 0.0.0.0 (D1)"


def test_launcher_inventory_keeps_14_services_on_8090_8103():
    """2. The launcher inventory still starts exactly the 14 D1 services/ports."""
    start = _read("start.sh")
    for spec in LAUNCHER_SPECS:
        assert f'"{spec}"' in start, f"start.sh must keep spec {spec}"
    ports = sorted(int(spec.rsplit("|", 1)[1]) for spec in LAUNCHER_SPECS)
    assert ports == [
        8090, 8091, 8092, 8093, 8094, 8095, 8096, 8097, 8098, 8099,
        8100, 8101, 8102, 8103,
    ], "D1 port inventory changed"


def test_start_sh_probes_are_loopback():
    """2. The launcher health checks only ever probe 127.0.0.1."""
    start = _read("start.sh")
    assert 'curl -fsS "http://127.0.0.1:$port/health"' in start
    assert 'http://127.0.0.1:%s/health' in start
    assert not re.search(r'http://(?!127\.0\.0\.1)[^"]*:\$port/health', start)


def test_gateway_consumers_stay_host_local():
    """3. The gateway health fan-out keeps consuming localhost (loopback-safe)."""
    service_src = _read("apps/gateway/api-gateway/src/service.py")
    registry = re.search(
        r"DEFAULT_SERVICE_HEALTH: dict\[str, str\] = \{(.*?)\}", service_src, re.DOTALL
    )
    assert registry, "DEFAULT_SERVICE_HEALTH registry must exist"
    values = re.findall(r'"(http://[^"]+)"', registry.group(1))
    assert values, "registry must declare targets"
    for value in values:
        assert value.startswith("http://localhost:8"), (
            f"consumer target {value} must stay host-local (D1)"
        )


def test_browser_consumers_stay_host_local():
    """4. The tracked browser API client keeps its loopback fallback URLs.

    Only versioned artefacts are inspected: ``apps/web/src/api/client.ts``
    declares the canonical localhost fallbacks for both APIs. Untracked
    local overrides (gitignored ``.env*`` files) are out of scope by design -
    the contract lives in versioned code so it holds in a clean checkout.
    """
    client = _read("apps/web/src/api/client.ts")
    assert "http://localhost:8100/api/v1" in client
    assert "http://localhost:8099/api/v1" in client


def test_compose_publications_remain_loopback():
    """8. The compose perimeter keeps publishing loopback-only ports."""
    compose = _read("infrastructure/docker/docker-compose.yml")
    for publish in ("127.0.0.1:8080:8080", "127.0.0.1:5433:5432", "127.0.0.1:6379:6379"):
        assert publish in compose, f"compose must keep {publish}"
    assert not re.search(r'ports:\s*\[\s*"0\.0\.0\.0', compose)


def test_excluded_agents_are_never_launched():
    """Scope pin: windows/vmware agents are not part of the running topology.

    Both still declare ``0.0.0.0`` in their health servers; because neither
    appears in ``start.sh`` neither opens a socket on this host. Adding either
    launcher entry requires fixing its bind under a future architectural
    decision first - this test forces that conversation.
    """
    start = _read("start.sh")
    assert "windows-agent" not in start, "windows-agent must stay out of start.sh"
    assert "vmware-agent" not in start, "vmware-agent must stay out of start.sh"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOOPBACK, 0))
        return sock.getsockname()[1]


def _listen_entries(port: int) -> list[tuple[str, str]]:
    """(local_addr_hex, state) of every LISTEN socket on ``port`` (Linux)."""
    proc_tcp = Path("/proc/net/tcp")
    if not proc_tcp.exists():
        return []
    wanted = f"{port:04X}"
    entries = []
    for line in proc_tcp.read_text().splitlines()[1:]:
        fields = line.split()
        local_hex, state = fields[1], fields[3]
        if local_hex.endswith(f":{wanted}") and state == "0A":
            entries.append(local_hex)
    return entries


def _non_loopback_ipv4s() -> list[str]:
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))  # TEST-NET-1; UDP sends no packet
        ip = sock.getsockname()[0]
        if not ip.startswith("127."):
            ips.add(ip)
    except OSError:
        pass
    finally:
        sock.close()
    return sorted(ips)


def test_agent_health_server_binds_loopback_only_runtime():
    """5-7. Real entry point: loopback reachable, LAN unreachable, socket on 127.0.0.1."""
    port = _free_port()
    env = os.environ.copy()
    env.update(
        AGENT_HEALTH_PORT=str(port),
        OBSERVATION_BUS_URL="redis://127.0.0.1:9/0",
        PYTHONPATH=os.pathsep.join([str(AGENT_DIR), str(ROOT)]),
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.main"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out, err = proc.communicate(timeout=5)
                pytest.fail(
                    f"agent exited early (rc={proc.returncode})\nstdout:{out}\nstderr:{err}"
                )
            try:
                with urllib.request.urlopen(f"http://{LOOPBACK}:{port}/health", timeout=1) as resp:
                    status_code = resp.status
                    payload = json.loads(resp.read())
            except Exception as exc:  # noqa: BLE001 - bounded retry loop
                last_error = exc
                time.sleep(0.25)
            else:
                assert status_code == http.HTTPStatus.OK
                assert payload["status"] in {"healthy", "degraded"}
                break
        else:
            pytest.fail(f"health server unreachable on loopback within 20s: {last_error}")

        # OS-level proof: every LISTEN socket on this port is 127.0.0.1.
        entries = _listen_entries(port)
        if entries:
            assert all(addr.startswith("0100007F:") for addr in entries), (
                f"expected loopback-only LISTEN sockets on :{port}, got {entries}"
            )
            assert not any(addr.startswith("00000000:") for addr in entries), (
                "a 0.0.0.0 listener would re-expose the service to LAN"
            )

        # Reachability proof: non-loopback interfaces must not answer.
        for ip in _non_loopback_ipv4s():
            try:
                with socket.create_connection((ip, port), timeout=2):
                    reachable = True
            except OSError:
                reachable = False
            assert not reachable, f"LAN interface {ip}:{port} is reachable (D1 regression)"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
