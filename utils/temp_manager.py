import os
import shutil
import uuid
import logging
from config import TEMP_DIR

logger = logging.getLogger(__name__)


def create_temp_dir() -> str:
    session_id = str(uuid.uuid4())
    path = os.path.join(TEMP_DIR, session_id)
    os.makedirs(path, exist_ok=True)
    return path


def cleanup_temp_dir(path: str) -> None:
    try:
        if path and os.path.exists(path):
            shutil.rmtree(path)
            logger.info(f"Cleaned up temp dir: {path}")
    except Exception as e:
        logger.warning(f"Failed to clean up temp dir {path}: {e}")


def ensure_dirs() -> None:
    os.makedirs(TEMP_DIR, exist_ok=True)
