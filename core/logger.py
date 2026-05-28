import sys
from pathlib import Path
from loguru import logger

logger.remove()

logger.add(
    sys.stdout,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "{message}"
    ),
    level="INFO",
    colorize=True,
)

try:
    Path("logs").mkdir(parents=True, exist_ok=True)
    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="10 days",
        level="INFO",
    )
except Exception as exc:
    logger.warning(f"File logging disabled: {exc}")

__all__ = ["logger"]
