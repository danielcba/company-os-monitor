"""Unit tests for the graceful shutdown handler."""
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "libs" / "shared"))

from graceful_shutdown import GracefulShutdown


def test_should_exit_initially_not_set():
    gs = GracefulShutdown()
    assert gs.should_exit.is_set() is False


def test_handle_signal_sets_event():
    gs = GracefulShutdown()
    gs._handle_signal(signal.SIGTERM)
    assert gs.should_exit.is_set() is True


def test_handle_signal_sets_event_for_sigint():
    gs = GracefulShutdown()
    gs._handle_signal(signal.SIGINT)
    assert gs.should_exit.is_set() is True


async def test_install_and_signal():
    gs = GracefulShutdown()
    gs.install()
    gs._handle_signal(signal.SIGTERM)
    assert gs.should_exit.is_set() is True
