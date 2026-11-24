"""Logging setup. Call configure_logging() once, at program start."""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # The HTTP library logs every request at INFO, which drowns out our own lines.
    logging.getLogger("httpx").setLevel(logging.WARNING)
