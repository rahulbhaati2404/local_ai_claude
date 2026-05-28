from contextlib import contextmanager
import time

from core.logger import logger


class TraceManager:

    @contextmanager
    def trace(
        self,
        name: str
    ):

        start = time.time()

        logger.info(
            f"[TRACE START] {name}"
        )

        try:

            yield

        finally:

            duration = (
                (time.time() - start) * 1000
            )

            logger.info(
                f"[TRACE END] {name} | "
                f"{duration:.2f} ms"
            )


trace_manager = TraceManager()