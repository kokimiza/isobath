"""Render entry point: run the installed server directly, without a uv parent process."""

from __future__ import annotations

import logging
import os
import signal
from typing import TYPE_CHECKING

import uvicorn

if TYPE_CHECKING:
    from types import FrameType

log = logging.getLogger("uvicorn.error")


class Server(uvicorn.Server):
    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        # Uvicorn's normal "Shutting down" line does not identify the initiating signal.
        # Log no environment values, connection strings or request data here.
        log.warning("Shutdown requested: signal=%s pid=%s", signal.Signals(sig).name, os.getpid())
        super().handle_exit(sig, frame)


def config() -> uvicorn.Config:
    raw_port = os.environ.get("PORT", "10000")
    try:
        port = int(raw_port)
    except ValueError:
        raise ValueError("PORT must be an integer between 1 and 65535") from None
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535")
    return uvicorn.Config(
        "isobath.main:app",
        host="0.0.0.0",  # noqa: S104 -- Render requires an externally reachable listener
        port=port,
        workers=1,
        access_log=False,
    )


def main() -> None:
    server = Server(config())
    log.info(
        "Starting ISOBATH: host=%s port=%s pid=%s",
        server.config.host,
        server.config.port,
        os.getpid(),
    )
    server.run()


if __name__ == "__main__":
    main()
