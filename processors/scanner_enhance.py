"""
تحسين صور السكانر قبل OCR:
  - تحويل للتدرج الرمادي
  - تصحيح الإمالة (deskew)
  - إزالة الضوضاء
  - تحسين التباين (adaptive threshold)
  - تحويل للأبيض والأسود النظيف
"""
import logging
import numpy as np
import cv2
from PIL import Image

logger = logging.getLogger(__name__)


def enhance_for_ocr(image_path: str) -> str:
    """
    يُحسّن صورة السكانر ويحفظها في نفس المسار.

    Args:
        image_path: مسار الصورة المدخلة.

    Returns:
        مسار الصورة المحسّنة (نفس المسار، مكتوبة من جديد).
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            pil = Image.open(image_path).convert("RGB")
            img = np.array(pil)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # إزالة الضوضاء
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # تصحيح الإمالة
        deskewed = _deskew(denoised)

        # تحسين التباين
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrasted = clahe.apply(deskewed)

        # Adaptive threshold للأبيض/أسود النظيف
        binary = cv2.adaptiveThreshold(
            contrasted, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 10,
        )

        # حفظ النتيجة
        cv2.imwrite(image_path, binary)
        logger.debug(f"تم تحسين الصورة: {image_path}")
        return image_path

    except Exception as e:
        logger.warning(f"تعذّر تحسين الصورة {image_path}: {e} — سيتم استخدام الصورة الأصلية.")
        return image_path


def _deskew(gray: np.ndarray) -> np.ndarray:
    """تصحيح زاوية الإمالة باستخدام Hough Lines."""
    try:
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        if lines is None:
            return gray

        angles = []
        for rho, theta in lines[:, 0]:
            angle = (theta - np.pi / 2) * (180 / np.pi)
            if abs(angle) < 15:
                angles.append(angle)

        if not angles:
            return gray

        median_angle = float(np.median(angles))
        if abs(median_angle) < 0.5:
            return gray

        h, w = gray.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            gray, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        logger.debug(f"تصحيح الإمالة: {median_angle:.2f}°")
        return rotated

    except Exception:
        return gray
