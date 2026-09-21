"""
Offline OCR engine for images and scanned document pages.
Supports rapidocr-onnxruntime (100% air-gapped / no external binaries) and pytesseract.
"""

import io
import logging
from pathlib import Path
from typing import Optional, Tuple, Union

from PIL import Image, ImageEnhance, ImageOps

from app.config import settings
from app.parsers.base import BaseParser, PageContent, ParsedDocument

logger = logging.getLogger(__name__)


class OCRParser(BaseParser):
    """Парсер для изображений и сканов документов с офлайн-распознаванием текста."""

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}

    def __init__(self):
        self._rapid_ocr = None
        self._tesseract_available = False
        self._initialized = False

    def _lazy_init(self) -> None:
        """Ленивая инициализация движка OCR без замедления старта системы."""
        if self._initialized:
            return

        # 1. Попытка загрузки RapidOCR (ONNX Runtime, офлайн)
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._rapid_ocr = RapidOCR()
            logger.info("RapidOCR (ONNX Runtime) successfully initialized for offline OCR.")
            self._initialized = True
            return
        except ImportError:
            logger.debug("rapidocr-onnxruntime is not installed. Checking pytesseract fallback...")

        # 2. Попытка загрузки pytesseract
        try:
            import pytesseract
            # Проверка доступности tesseract cmd
            pytesseract.get_tesseract_version()
            self._tesseract_available = True
            logger.info("Pytesseract successfully initialized.")
        except ImportError:
            logger.debug("pytesseract is not installed.")
        except EnvironmentError:
            logger.warning(
                "pytesseract is installed but Tesseract binary is not found or not accessible. "
                "Install Tesseract OCR or use rapidocr-onnxruntime for air-gapped OCR."
            )
        except Exception as exc:
            logger.warning("Unexpected error initializing pytesseract: %s", exc)

        if not self._rapid_ocr and not self._tesseract_available:
            logger.warning(
                "No OCR backend available. Scans will return placeholder notes. "
                "To enable offline OCR, install rapidocr-onnxruntime: pip install rapidocr-onnxruntime"
            )

        self._initialized = True

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """Предобработка изображения: градация серого, контраст, нормализация."""
        # Преобразование в RGB или L (градации серого)
        if image.mode not in ("L", "RGB"):
            image = image.convert("RGB")

        gray = image.convert("L")
        # Повышение контрастности для улучшения читаемости сканов документов
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.8)
        # Автоматическая балансировка гистограммы
        autocontrast = ImageOps.autocontrast(enhanced, cutoff=1)
        return autocontrast

    def recognize_image(self, img_source: Union[Path, str, bytes, Image.Image]) -> Tuple[str, float]:
        """
        Распознает текст с изображения.
        Возвращает кортеж (распознанный_текст, средняя_уверенность).
        """
        self._lazy_init()

        # Загрузка изображения в PIL
        if isinstance(img_source, (Path, str)):
            image = Image.open(str(img_source))
        elif isinstance(img_source, bytes):
            image = Image.open(io.BytesIO(img_source))
        elif isinstance(img_source, Image.Image):
            image = img_source
        else:
            raise ValueError(f"Unsupported image source type: {type(img_source)}")

        preprocessed = self.preprocess_image(image)

        # 1. Распознавание через RapidOCR
        if self._rapid_ocr is not None:
            try:
                import numpy as np
                img_np = np.array(preprocessed)
                ocr_results, _ = self._rapid_ocr(img_np)
                if not ocr_results:
                    return "", 1.0

                text_lines = []
                scores = []
                for box, text, score in ocr_results:
                    if text and text.strip():
                        text_lines.append(text.strip())
                        scores.append(float(score))

                full_text = "\n".join(text_lines)
                avg_score = sum(scores) / max(len(scores), 1)
                return full_text, avg_score
            except Exception as exc:
                logger.error("RapidOCR recognition error: %s", exc)

        # 2. Распознавание через pytesseract
        if self._tesseract_available:
            try:
                import pytesseract
                # Поддержка языков: русский, казахский, английский при наличии обученных данных
                langs = "+".join(settings.OCR_LANGUAGES) if settings.OCR_LANGUAGES else "rus+eng"
                text = pytesseract.image_to_string(preprocessed, lang=langs)
                return text.strip(), 0.85
            except Exception as exc:
                logger.error("Pytesseract recognition error: %s", exc)

        # 3. Fallback, если OCR движок не установлен
        return (
            "[Примечание OCR: Скан обнаружен, но модуль rapidocr-onnxruntime не установлен. "
            "Для офлайн-распознавания выполните: pip install rapidocr-onnxruntime]",
            0.0
        )

    def supports(self, file_path: Path, mime_type: str) -> bool:
        return (
            file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS or
            mime_type.startswith("image/")
        )

    def parse(self, file_path: Path) -> ParsedDocument:
        text, confidence = self.recognize_image(file_path)
        page = PageContent(
            page_number=1,
            text=text,
            is_ocr=True,
            confidence=confidence
        )
        return ParsedDocument(
            file_path=file_path,
            file_name=file_path.name,
            mime_type=f"image/{file_path.suffix.lstrip('.')}",
            source_type="image_scan",
            pages=[page],
            metadata={"ocr_engine": "rapidocr" if self._rapid_ocr else "tesseract/stub", "confidence": confidence}
        )
