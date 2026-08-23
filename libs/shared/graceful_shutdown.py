"""Graceful shutdown handler for async services."""
import asyncio
import logging
import signal

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """Install signal handlers and set an event when shutdown is requested."""

    def __init__(self):
        self.should_exit = asyncio.Event()

    def install(self) -> None:
        """Register SIGTERM and SIGINT handlers on the running event loop."""
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self._handle_signal, sig)
        except (NotImplementedError, AttributeError):
            # Windows or non-main thread — skip signal handlers
            pass

    def _handle_signal(self, sig: signal.Signals) -> None:
        logger.info("Received %s, shutting down...", sig.name)
        self.should_exit.set()
