# src/config/logger.py

from loguru import logger
from rich.console import Console
from src.config.settings import settings

# Initialize Rich console
console = Console()

# Remove default logger
logger.remove()

# Add new logger with Rich formatting
logger.add(
    lambda msg: console.print(msg, end=''),
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY/MM/DD HH:mm:ss}</green> | {level.icon} - <level>{message}</level>",
    enqueue=True
)
