import os
import logging
from typing import List
from pdf2image import convert_from_path
from config import PDF_DPI

logger = logging.getLogger(__name__)


def pdf_to_images(pdf_path: str, output_dir: str) -> List[str]:
    """
    Convert each page of a PDF to a PNG image.

    Args:
        pdf_path: Absolute path to the input PDF file.
        output_dir: Directory where page images will be saved.

    Returns:
        Sorted list of absolute paths to generated image files.

    Raises:
        RuntimeError: If conversion fails or produces no pages.
    """
    logger.info(f"Converting PDF to images: {pdf_path}")

    try:
        pages = convert_from_path(pdf_path, dpi=PDF_DPI)
    except Exception as e:
        raise RuntimeError(f"Failed to convert PDF to images: {e}") from e

    if not pages:
        raise RuntimeError("PDF produced zero pages. The file may be empty or corrupted.")

    image_paths: List[str] = []
    for idx, page in enumerate(pages, start=1):
        image_path = os.path.join(output_dir, f"page_{idx:04d}.png")
        page.save(image_path, "PNG")
        image_paths.append(image_path)
        logger.debug(f"Saved page {idx} → {image_path}")

    logger.info(f"Converted {len(image_paths)} pages")
    return sorted(image_paths)
