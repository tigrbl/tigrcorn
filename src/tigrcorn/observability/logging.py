from __future__ import annotations

import logging
from logging import Logger


class AccessLogger:
    def __init__(self, logger: Logger, enabled: bool = True) -> None:
        self.logger = logger
        self.enabled = enabled

    def log_http(self, client: tuple[str, int] | None, method: str, path: str, status: int, proto: str) -> None:
        if not self.enabled:
            return
        peer = f"{client[0]}:{client[1]}" if client else "-"
        self.logger.info('%s "%s %s %s" %d', peer, method, path, proto, status)

    def log_ws(self, client: tuple[str, int] | None, path: str, result: str) -> None:
        if not self.enabled:
            return
        peer = f"{client[0]}:{client[1]}" if client else "-"
        self.logger.info('%s "WEBSOCKET %s" %s', peer, path, result)


def configure_logging(level: str = "info") -> logging.Logger:
    logger = logging.getLogger("tigrcorn")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    return logger
