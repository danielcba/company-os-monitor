"""F3 contract tests: Linux Agent health port = AGENT_HEALTH_PORT (8103).

The agent health server used to hardcode ``8080`` while ``AGENT_HEALTH_PORT``
was only honored by the launcher (``start.sh``/``stop.sh``), colliding with
the nginx frontend published on ``127.0.0.1:8080``. The Monitor architectural
decision fixes the agent on ``8103`` and reserves ``8080`` for the frontend.

Static tests pin the contract everywhere it is expressed (agent code, launcher,
``.env.example``, ``cognitive_contract.md``, compose); the runtime test boots
the real agent entry point on a configured port and fails if the agent stops
honoring ``AGENT_HEALTH_PORT`` (regression guard).
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
FRONTEND_PUBLISH = "127.0.0.1:8080:8080"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


def test_agent_main_consumes_agent_health_port_env():
    """1. main.py resolves the operative port from AGENT_HEALTH_PORT."""
    src = _read("apps/agents/linux-agent/src/main.py")
    assert 'os.getenv("AGENT_HEALTH_PORT"' in src, "main.py must read AGENT_HEALTH_PORT"
    assert '"8103"' in src, "documented default must be 8103"
    assert "8080" not in src, "8080 must not remain anywhere in the agent entry point"


def test_agent_main_passes_port_explicitly():
    """4. main.py must not call health.start() with an implicit port."""
    src = _read("apps/agents/linux-agent/src/main.py")
    assert re.search(r"await\s+health\.start\(\s*port\s*\)", src), "must await health.start(port)"
    assert not re.search(r"await\s+health\.start\(\s*\)", src), (
        "implicit health.start() reintroduces a default"
    )


def test_agent_health_server_has_no_hardcoded_8080():
    """2. The health server must not carry 8080 as its operative port."""
    src = _read("apps/agents/linux-agent/src/health.py")
    assert "8080" not in src, "health.py must not hardcode 8080"
    assert "port: int = " not in src, "health.start must not default the port implicitly"


def test_no_residual_8080_in_linux_agent():
    """2. No file under the Linux Agent may still reference 8080."""
    offenders = [
        str(p.relative_to(ROOT))
        for p in AGENT_DIR.rglob("*")
        if p.is_file() and p.suffix in {".py", ".toml", ".cfg", ".txt"} and "8080" in p.read_text()
    ]
    assert offenders == [], f"stale 8080 references in agent: {offenders}"


def test_launcher_default_is_8103():
    """3. start.sh default for AGENT_HEALTH_PORT is 8103."""
    start = _read("start.sh")
    assert (
        '"linux-agent|apps/agents/linux-agent|AGENT_HEALTH_PORT|8103"' in start
    ), "launcher spec default must be 8103"
    assert "linux-agent observation capturer (:8103)" in start, "launcher docs must mention 8103"


def test_env_example_documents_8103():
    """3. The shipped template documents AGENT_HEALTH_PORT=8103."""
    env_example = _read(".env.example")
    assert re.search(r"^AGENT_HEALTH_PORT=8103$", env_example, re.MULTILINE), (
        ".env.example must pin 8103"
    )


def test_contract_table_allocates_ports():
    """3/6. cognitive_contract.md: 8103 = Linux Agent, 8080 = Frontend."""
    contract = _read("cognitive_contract.md")
    assert "8103: Linux Agent" in contract, "contract must allocate 8103 to the Linux Agent"
    assert "8080: Frontend" in contract, "contract must allocate 8080 to the frontend"
    assert "8080: Linux Agent" not in contract, "stale 8080 allocation for the agent"


def test_frontend_stays_on_8080():
    """6. The frontend keeps 127.0.0.1:8080 and compose publishes nothing on 8103."""
    compose = _read("infrastructure/docker/docker-compose.yml")
    assert FRONTEND_PUBLISH in compose, "frontend must keep its loopback publication on 8080"
    assert "8103" not in compose, "the agent is host-native; compose must not publish 8103"
    nginx = _read("apps/web/nginx.conf")
    assert re.search(r"listen\s+8080\s*;", nginx), "frontend nginx must keep listening on 8080"


def test_no_bind_conflict_between_frontend_and_agent():
    """7. Effective agent default and frontend publish port are disjoint."""
    main_src = _read("apps/agents/linux-agent/src/main.py")
    agent_default = re.search(r'os\.getenv\("AGENT_HEALTH_PORT",\s*"(\d+)"\)', main_src).group(1)
    compose = _read("infrastructure/docker/docker-compose.yml")
    assert FRONTEND_PUBLISH in compose, "frontend publication must remain as documented"
    frontend_port = FRONTEND_PUBLISH.split(":")[1]
    assert agent_default != frontend_port, "agent and frontend would collide"
    assert agent_default == "8103" and frontend_port == "8080", "canonical assignment changed"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_agent_listens_on_configured_agent_health_port_runtime():
    """1/5. Real entry point binds the configured port (regression guard)."""
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
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as resp:
                    status_code = resp.status
                    payload = json.loads(resp.read())
            except Exception as exc:  # noqa: BLE001 - bounded retry loop
                last_error = exc
                time.sleep(0.25)
            else:
                assert status_code == http.HTTPStatus.OK
                assert payload["status"] in {"healthy", "degraded"}
                assert {"status", "last_capture", "error_count", "capture_count"} <= set(payload)
                return
        pytest.fail(
            f"agent did not answer on AGENT_HEALTH_PORT={port} within 20s "
            f"(ignoring AGENT_HEALTH_PORT is an F3 regression); last error: {last_error}"
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
