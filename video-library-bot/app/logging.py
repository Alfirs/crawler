from __future__ import annotations

import logging


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT)
    return logging.getLogger("video_library_bot")
